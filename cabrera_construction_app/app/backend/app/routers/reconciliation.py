from __future__ import annotations

import csv
import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import change_orders as co_rules
from ..services import milestones as milestone_rules
from ..services import reconciliation as recon_rules
from .projects import get_project_or_404

router = APIRouter(prefix="/api", tags=["reconciliation"])


# --- Per-project Reconciliation & Closing -------------------------------------

@router.get("/projects/{project_id}/reconciliation")
def project_reconciliation(project_id: int, db: Session = Depends(get_db)):
    """Expenses (and now labor) must always be visible here, even for a
    project with no estimate yet -- this used to 404 the WHOLE page in
    that case, hiding every expense/labor entry tied to the project along
    with the contract math that genuinely can't be computed without one.
    Only the contract-amount KPIs degrade to zero; receipts, labor, and
    their totals are never gated on an estimate existing."""
    project = get_project_or_404(db, project_id)

    all_cos = sorted(project.change_orders, key=lambda c: c.number)
    signed_cos = [co for co in all_cos if co_rules.is_signed(co)]
    # Shown separately from the net "change_orders" figure below so a
    # discount (a signed CO that's pure amount_subtracted) doesn't get
    # buried inside a netted number -- any contractual change, discounts
    # included, goes through Change Orders (see ChangeOrdersPage), but
    # Reconciliation is where the owner actually looks for "how much did
    # we discount this job."
    scope_additions = sum(float(co.amount_added) for co in signed_cos)
    discounts_given = sum(float(co.amount_subtracted) for co in signed_cos)

    if project.estimate:
        original = project.estimate.total
        co_total = co_rules.revised_contract_total(original, all_cos) - original
        revised = original + co_total
    else:
        original = co_total = revised = 0.0

    milestones = sorted(project.scope_schedule.milestones, key=lambda m: m.number) if project.scope_schedule else []
    invoiced = sum(float(m.invoice.amount) for m in milestones if m.invoice)
    payment_receipts = [r for r in project.receipts if r.type == "payment"]
    expense_receipts = [r for r in project.receipts if r.type == "expense"]
    received = sum(float(r.amount) for r in payment_receipts)
    total_expenses = sum(float(r.amount) for r in expense_receipts)
    total_labor = sum(float(entry.amount) for entry in project.labor_entries)
    balance = milestone_rules.project_balance(revised, [float(r.amount) for r in payment_receipts]) if project.estimate else 0.0
    margin = revised - total_expenses - total_labor

    milestone_rows = []
    for m in milestones:
        received_for_m = sum(float(r.amount) for r in payment_receipts if r.milestone_id == m.id)
        milestone_rows.append(
            {
                "milestone_id": m.id,
                "title": m.title,
                "due_date": m.due_date,
                "amount": float(m.amount),
                "status": m.status,
                "invoice_number": m.invoice.invoice_number if m.invoice else None,
                "invoiced_amount": float(m.invoice.amount) if m.invoice else None,
                "received": received_for_m,
            }
        )

    return {
        "kpis": {
            "original": round(original, 2),
            "change_orders": round(co_total, 2),
            "scope_additions": round(scope_additions, 2),
            "discounts_given": round(discounts_given, 2),
            "revised": round(revised, 2),
            "invoiced": round(invoiced, 2),
            "received": round(received, 2),
            "balance_due": round(balance, 2),
            "total_expenses": round(total_expenses, 2),
            "total_labor": round(total_labor, 2),
            "margin": round(margin, 2),
        },
        "milestones": milestone_rows,
        "receipts": [schemas.ReceiptOut.model_validate(r) for r in sorted(project.receipts, key=lambda r: r.date, reverse=True)],
        "labor_entries": [schemas.LaborEntryOut.model_validate(entry) for entry in sorted(project.labor_entries, key=lambda e: e.date, reverse=True)],
        "sheet_id": project.sheet_id,
        "can_close": project.estimate is not None and round(balance, 2) == 0.0 and project.status != "completed",
    }


@router.post("/projects/{project_id}/close")
def close_project(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    data = project_reconciliation(project_id, db)
    if data["kpis"]["balance_due"] != 0.0:
        raise HTTPException(400, f"Cannot close: balance due is ${data['kpis']['balance_due']:,.2f}, not $0.00")
    project.status = "completed"
    db.commit()
    return {"status": "completed"}


# --- Labor -------------------------------------------------------------------
# Actual labor cost, entered straight on the Reconciliation page (person,
# date, amount) -- separate from Receipt since it's never a "business
# expense" the way an unassigned receipt can be; it's always tied to one
# project. Counted into that project's margin the same way material
# expenses are.

@router.post("/projects/{project_id}/labor", response_model=schemas.LaborEntryOut)
def create_labor_entry(project_id: int, payload: schemas.LaborEntryIn, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    entry = models.LaborEntry(project_id=project_id, person_name=payload.person_name, date=payload.date, amount=payload.amount)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/labor/{labor_id}", response_model=schemas.LaborEntryOut)
def update_labor_entry(labor_id: int, payload: schemas.LaborEntryUpdate, db: Session = Depends(get_db)):
    entry = db.get(models.LaborEntry, labor_id)
    if not entry:
        raise HTTPException(404, "Labor entry not found")
    fields_set = payload.model_fields_set
    if "person_name" in fields_set and payload.person_name is not None:
        entry.person_name = payload.person_name
    if "date" in fields_set and payload.date is not None:
        entry.date = payload.date
    if "amount" in fields_set and payload.amount is not None:
        entry.amount = payload.amount
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/labor/{labor_id}", status_code=204)
def delete_labor_entry(labor_id: int, db: Session = Depends(get_db)):
    entry = db.get(models.LaborEntry, labor_id)
    if not entry:
        raise HTTPException(404, "Labor entry not found")
    db.delete(entry)
    db.commit()


# --- Operational Reconciliation (company-wide bank matching) -----------------

def _unused_receipt_query(db: Session):
    matched_receipt_ids = {r[0] for r in db.query(models.BankTransaction.receipt_id).filter(models.BankTransaction.receipt_id.isnot(None))}
    query = db.query(models.Receipt)
    if matched_receipt_ids:
        query = query.filter(models.Receipt.id.notin_(matched_receipt_ids))
    return query


def _parse_bofa_csv(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.strip().lower().startswith("date,")), None)
    if header_idx is None:
        raise HTTPException(400, "Could not find the 'Date, Description, Amount' header row in this file")
    reader = csv.DictReader(lines[header_idx:])
    rows = []
    for row in reader:
        date_str = (row.get("Date") or "").strip()
        desc = (row.get("Description") or "").strip()
        amount_str = (row.get("Amount") or "").replace(",", "").strip()
        if not date_str or not amount_str:
            continue
        posted_date = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
            try:
                posted_date = dt.datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
        if posted_date is None:
            continue
        rows.append({"posted_date": posted_date, "description": desc, "amount": float(amount_str)})
    return rows


@router.post("/reconciliation/bank-import", response_model=schemas.BankImportResult)
async def import_bank_file(file: UploadFile, db: Session = Depends(get_db)):
    raw = await file.read()
    rows = _parse_bofa_csv(raw)

    import_id = f"import-{dt.datetime.now():%Y%m%d%H%M%S}"
    imported = skipped = matched = possible = needs_attention = 0
    used_receipt_ids: set[int] = set()

    for row in rows:
        fp = recon_rules.fingerprint(row["posted_date"], row["amount"], row["description"])
        if db.query(models.BankTransaction).filter(models.BankTransaction.fingerprint == fp).first():
            skipped += 1
            continue

        candidates = [r for r in _unused_receipt_query(db).all() if r.id not in used_receipt_ids]
        receipt, status = recon_rules.find_best_match(row["amount"], row["posted_date"], row["description"], candidates)

        txn = models.BankTransaction(
            import_id=import_id,
            posted_date=row["posted_date"],
            description=row["description"],
            amount=row["amount"],
            vendor=recon_rules.normalize_vendor_display(row["description"]),
            fingerprint=fp,
            match_status=status or "unmatched",
        )
        if receipt:
            txn.receipt_id = receipt.id
            txn.project_id = receipt.project_id
            used_receipt_ids.add(receipt.id)

        db.add(txn)
        imported += 1
        if status == "matched":
            matched += 1
        elif status == "possible":
            possible += 1
        else:
            needs_attention += 1

    db.commit()
    return schemas.BankImportResult(
        imported=imported, skipped_duplicates=skipped, matched=matched, possible=possible, needs_attention=needs_attention
    )


@router.get("/reconciliation/bank-transactions")
def list_bank_transactions(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.BankTransaction)
    if status and status != "all":
        if status == "deposits":
            query = query.filter(models.BankTransaction.amount > 0)
        elif status == "needs_attention":
            query = query.filter(models.BankTransaction.match_status.in_(["possible", "unmatched"]))
        else:
            query = query.filter(models.BankTransaction.match_status == status)
    transactions = query.order_by(models.BankTransaction.posted_date.desc()).all()

    all_txns = db.query(models.BankTransaction).all()
    needs_attention_txns = [t for t in all_txns if t.match_status in ("possible", "unmatched")]
    kpis = {
        "transactions": len(all_txns),
        "matched_to_receipts": sum(1 for t in all_txns if t.match_status == "matched"),
        "needs_attention": len(needs_attention_txns),
        "unresolved_amount": round(sum(abs(float(t.amount)) for t in needs_attention_txns), 2),
    }
    return {"kpis": kpis, "transactions": [schemas.BankTransactionOut.model_validate(t) for t in transactions]}


@router.post("/reconciliation/bank-transactions/{txn_id}/confirm", response_model=schemas.BankTransactionOut)
def confirm_match(txn_id: int, payload: schemas.ConfirmMatch, db: Session = Depends(get_db)):
    txn = db.get(models.BankTransaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    receipt = db.get(models.Receipt, payload.receipt_id)
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    txn.receipt_id = receipt.id
    txn.project_id = receipt.project_id
    txn.match_status = "matched"
    db.commit()
    db.refresh(txn)
    return txn


@router.post("/reconciliation/bank-transactions/{txn_id}/reject", response_model=schemas.BankTransactionOut)
def reject_match(txn_id: int, db: Session = Depends(get_db)):
    txn = db.get(models.BankTransaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    txn.receipt_id = None
    txn.match_status = "rejected"
    db.commit()
    db.refresh(txn)
    return txn


@router.post("/reconciliation/bank-transactions/{txn_id}/assign-project", response_model=schemas.BankTransactionOut)
def assign_transaction_project(txn_id: int, payload: schemas.AssignProject, db: Session = Depends(get_db)):
    txn = db.get(models.BankTransaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    txn.project_id = payload.project_id
    if not txn.receipt_id and payload.project_id is not None:
        receipt = models.Receipt(
            project_id=payload.project_id,
            date=txn.posted_date,
            description=txn.description,
            amount=abs(float(txn.amount)),
            type="payment" if txn.amount > 0 else "expense",
            source="bank",
        )
        db.add(receipt)
        db.flush()
        txn.receipt_id = receipt.id
        txn.match_status = "matched"
    db.commit()
    db.refresh(txn)
    return txn
