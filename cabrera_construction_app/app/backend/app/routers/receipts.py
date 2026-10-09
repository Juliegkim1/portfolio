from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import gemini_service, google_service, receipt_sync
from ..services import google_oauth as g_oauth

router = APIRouter(prefix="/api", tags=["receipts"])


def _recompute_milestone_payment_status(db: Session, milestone: models.Milestone) -> None:
    """Sums whatever payment receipts the milestone actually has right now
    and sets status/invoice.status from that — called after a receipt is
    added (status can only move up) or deleted (status can move back down:
    paid -> partial -> invoiced/scheduled), so it has to read real current
    state rather than just react to one receipt's amount."""
    total_paid = sum(
        float(r.amount)
        for r in db.query(models.Receipt).filter(
            models.Receipt.milestone_id == milestone.id, models.Receipt.type == "payment"
        )
    )
    target = float(milestone.invoice.amount) if milestone.invoice else float(milestone.amount)
    if target > 0 and total_paid >= target:
        milestone.status = "paid"
        if milestone.invoice:
            milestone.invoice.status = "paid"
    elif total_paid > 0:
        milestone.status = "partial"
        if milestone.invoice and milestone.invoice.status == "paid":
            milestone.invoice.status = "open"
    else:
        milestone.status = "invoiced" if milestone.invoice else "scheduled"
        if milestone.invoice and milestone.invoice.status == "paid":
            milestone.invoice.status = "open"


@router.get("/receipts", response_model=list[schemas.ReceiptOut])
def list_receipts(
    project_id: int | None = None,
    type: str | None = None,  # noqa: A002 - matches query param name in the design
    needs_project: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Receipt)
    if project_id is not None:
        query = query.filter(models.Receipt.project_id == project_id)
    if type is not None:
        query = query.filter(models.Receipt.type == type)
    if needs_project is not None:
        query = query.filter(models.Receipt.needs_project == needs_project)
    return query.order_by(models.Receipt.date.desc()).all()


@router.post("/receipts", response_model=schemas.ReceiptOut)
def create_receipt(payload: schemas.ReceiptIn, db: Session = Depends(get_db)):
    if payload.type == "payment" and payload.project_id is None:
        raise HTTPException(400, "Payments must have a project")

    needs_project = payload.type == "expense" and payload.project_id is None
    receipt = models.Receipt(
        project_id=payload.project_id,
        milestone_id=payload.milestone_id,
        date=payload.date,
        description=payload.description,
        amount=payload.amount,
        type=payload.type,
        needs_project=needs_project,
        source="manual",
    )
    db.add(receipt)
    db.flush()

    if payload.type == "payment" and payload.milestone_id:
        milestone = db.get(models.Milestone, payload.milestone_id)
        if milestone:
            _recompute_milestone_payment_status(db, milestone)

    db.commit()
    db.refresh(receipt)
    return receipt


@router.delete("/receipts/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    """Deletes a receipt entirely — e.g. one entered by mistake or no
    longer wanted, whether it's a business expense, a project expense, or
    a payment. A bank transaction matched to it is unlinked (not deleted),
    same as a deleted project's receipts are unlinked rather than taking
    the transaction down with them. If this was a payment tied to a
    milestone, the milestone's paid status is recomputed afterward — it can
    move back down from paid/partial now that this payment no longer counts."""
    receipt = db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Receipt not found")

    db.query(models.BankTransaction).filter(models.BankTransaction.receipt_id == receipt_id).update(
        {"receipt_id": None, "match_status": "unmatched"}, synchronize_session=False
    )

    milestone = db.get(models.Milestone, receipt.milestone_id) if receipt.type == "payment" and receipt.milestone_id else None

    db.delete(receipt)
    db.flush()

    if milestone:
        _recompute_milestone_payment_status(db, milestone)

    db.commit()


@router.patch("/receipts/{receipt_id}/assign-project", response_model=schemas.ReceiptOut)
def assign_project(receipt_id: int, payload: schemas.AssignProject, db: Session = Depends(get_db)):
    receipt = db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    if receipt.type == "payment" and payload.project_id is None:
        raise HTTPException(400, "Payments must have a project")
    receipt.project_id = payload.project_id
    receipt.needs_project = receipt.type == "expense" and payload.project_id is None
    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("/drive/files/{file_id}/content")
def get_drive_file_content(file_id: str, db: Session = Depends(get_db)):
    """Streams raw bytes for any Drive file by ID — used both to show a
    synced receipt's original photo (keyed by Receipt.drive_file_id) and
    to preview candidates in the "import from Google Drive" picker before
    they're imported at all (so there's no Receipt row yet to key off
    of). Generic on purpose rather than two near-identical endpoints."""
    try:
        content = google_service.download_file(db, file_id)
        mime_type = google_service.get_file_mime_type(db, file_id)
    except g_oauth.GoogleNotConnected as exc:
        raise HTTPException(409, str(exc)) from exc
    except google_service.GoogleApiError as exc:
        raise HTTPException(exc.status_code if exc.status_code < 500 else 502, str(exc)) from exc
    return Response(content=content, media_type=mime_type)


@router.get("/drive/receipt-images")
def search_drive_receipt_images(search: str | None = None, db: Session = Depends(get_db)):
    """Image files anywhere in the connected Drive account — the "import
    from Google Drive" picker on Business Expenses, for a receipt the
    automatic Receipts-inbox scan hasn't caught (filed somewhere else,
    synced to an unexpected folder, or the inbox resolution itself was
    briefly wrong — see google_service.get_or_create_receipts_root)."""
    if not g_oauth.get_connection(db):
        raise HTTPException(409, "Connect Google Workspace first.")
    try:
        files = google_service.search_images(db, search)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
        raise HTTPException(502, f"Google Drive error: {exc}") from exc
    return [{"id": f["id"], "name": f["name"], "modified_time": f.get("modifiedTime")} for f in files]


@router.post("/receipts/import-from-drive/{file_id}", response_model=schemas.ReceiptOut)
def import_receipt_from_drive(file_id: str, db: Session = Depends(get_db)):
    """Reads, matches, and records one receipt photo picked from the
    Drive picker above — the single-file counterpart to "Sync Receipts
    Now" for when the automatic inbox scan hasn't caught it. See
    services/receipt_sync.py's import_receipt_from_drive for the shared
    extraction/matching pipeline."""
    try:
        return receipt_sync.import_receipt_from_drive(db, file_id)
    except g_oauth.GoogleNotConnected as exc:
        raise HTTPException(409, str(exc)) from exc
    except gemini_service.GeminiNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except receipt_sync.ReceiptAlreadyImported as exc:
        raise HTTPException(409, str(exc)) from exc
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/business-expenses")
def business_expenses(db: Session = Depends(get_db)):
    expenses = db.query(models.Receipt).filter(models.Receipt.type == "expense").order_by(models.Receipt.date.desc()).all()
    total = sum(float(r.amount) for r in expenses)
    business = sum(float(r.amount) for r in expenses if r.project_id is None)
    assigned = total - business
    return {
        "kpis": {"total": round(total, 2), "assigned_to_projects": round(assigned, 2), "business": round(business, 2)},
        "receipts": [schemas.ReceiptOut.model_validate(r) for r in expenses],
        "needs_project_count": sum(1 for r in expenses if r.needs_project),
    }


@router.post("/receipts/sync-from-drive", response_model=schemas.ReceiptSyncResult)
def sync_receipts_from_drive(db: Session = Depends(get_db)):
    """"Sync Receipts Now" — scans My Drive/Receipts for new receipt
    photos, reads each one, matches any handwritten customer name against
    existing projects, and files + records the result. See
    services/receipt_sync.py for the full pipeline. Real daily automation
    (Cloud Scheduler hitting this same endpoint) is a planned later phase,
    not built here — this is manually triggered for now."""
    try:
        return receipt_sync.sync_receipts_from_drive(db)
    except g_oauth.GoogleNotConnected as exc:
        raise HTTPException(409, str(exc)) from exc
    except gemini_service.GeminiNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
