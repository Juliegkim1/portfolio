from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import quickbooks_oauth as qb_oauth
from ..services import quickbooks_service
from .projects import get_project_or_404

router = APIRouter(prefix="/api", tags=["invoices"])

# Invoice amount = milestone amount + signed CO deltas for that milestone (CLAUDE.md
# "Business rules"). Signed-CO deltas are folded into `milestone.amount` the moment
# both parties sign (see change_orders.sign_change_order), so by the time a milestone
# is invoiced its `amount` already reflects every signed change — no separate addition here.


def _payment_status(amount: float, received: float) -> str:
    if received >= amount - 0.01:  # cent-level rounding tolerance, same as milestones.py
        return "paid"
    if received > 0:
        return "partial"
    return "invoiced"


@router.get("/projects/{project_id}/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if not project.scope_schedule:
        return []
    invoices = [m.invoice for m in project.scope_schedule.milestones if m.invoice]
    out = []
    for inv in invoices:
        received = sum(
            float(r.amount)
            for r in db.query(models.Receipt).filter(models.Receipt.milestone_id == inv.milestone_id, models.Receipt.type == "payment")
        )
        out.append(
            schemas.InvoiceOut(
                id=inv.id,
                milestone_id=inv.milestone_id,
                invoice_number=inv.invoice_number,
                amount=float(inv.amount),
                date_issued=inv.date_issued,
                due_date=inv.due_date,
                status=inv.status,
                qb_invoice_id=inv.qb_invoice_id,
                amount_received=round(received, 2),
                payment_status=_payment_status(float(inv.amount), received),
            )
        )
    return out


@router.get("/projects/{project_id}/invoices/quickbooks", response_model=list[schemas.QuickBooksInvoiceOut])
def list_quickbooks_invoices(project_id: int, db: Session = Depends(get_db)):
    """Real, read-only pull of what QuickBooks actually has on file as sent
    for this project's customer — shown alongside (not instead of) this
    app's own local Invoice records, since this app never writes invoices
    to QuickBooks itself (see quickbooks_service's module docstring)."""
    project = get_project_or_404(db, project_id)
    if not qb_oauth.get_connection(db):
        raise HTTPException(409, "Connect QuickBooks first.")
    try:
        return quickbooks_service.list_invoices_for_customer(db, project.customer_name)
    except qb_oauth.QuickBooksNotConnected as exc:
        raise HTTPException(409, str(exc)) from exc
    except quickbooks_service.QuickBooksApiError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/invoices/quickbooks/lookup", response_model=schemas.QuickBooksInvoiceOut)
def lookup_quickbooks_invoice(number: str, db: Session = Depends(get_db)):
    """Look up one specific QuickBooks invoice by its DocNumber — the
    Invoices page's "look up a QuickBooks invoice number" entry point,
    separate from the per-customer list above (that one shows everything
    found for a customer; this looks up one invoice number directly, the
    same way estimate lookup works)."""
    if not qb_oauth.get_connection(db):
        raise HTTPException(409, "Connect QuickBooks first.")
    try:
        result = quickbooks_service.lookup_invoice(db, number)
    except qb_oauth.QuickBooksNotConnected as exc:
        raise HTTPException(409, str(exc)) from exc
    except quickbooks_service.QuickBooksApiError as exc:
        raise HTTPException(502, str(exc)) from exc
    if not result:
        raise HTTPException(404, f"No QuickBooks invoice found with number \"{number}\".")
    return result


@router.get("/projects/{project_id}/invoices/next-draft")
def next_invoice_draft(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if not project.scope_schedule:
        raise HTTPException(404, "No scope schedule for this project yet")
    next_milestone = next(
        (m for m in sorted(project.scope_schedule.milestones, key=lambda m: m.number) if m.status == "scheduled"),
        None,
    )
    if not next_milestone:
        return None
    amount = float(next_milestone.amount)
    issued = dt.date.today()
    return {
        "milestone_id": next_milestone.id,
        "milestone_title": next_milestone.title,
        "bill_to": project.customer_name,
        "date_issued": issued,
        "due_date": issued + dt.timedelta(days=15),
        "amount": amount,
    }


@router.post("/invoices", response_model=schemas.InvoiceOut)
def create_invoice(payload: schemas.InvoiceCreate, db: Session = Depends(get_db)):
    milestone = db.get(models.Milestone, payload.milestone_id)
    if not milestone:
        raise HTTPException(404, "Milestone not found")
    if milestone.invoice:
        raise HTTPException(400, "This milestone already has an invoice")

    project = milestone.scope_schedule.project
    amount = float(milestone.amount)
    issued = dt.date.today()
    invoice = models.Invoice(
        milestone_id=milestone.id,
        invoice_number=f"INV-{project.id:04d}-{milestone.number:02d}",
        amount=amount,
        date_issued=issued,
        due_date=issued + dt.timedelta(days=15),
        status="open",
        qb_invoice_id=f"qb-inv-{project.id}-{milestone.id}",
    )
    milestone.status = "invoiced"
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
