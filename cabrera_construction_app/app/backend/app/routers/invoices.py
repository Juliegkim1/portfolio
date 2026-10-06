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


@router.get("/projects/{project_id}/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if not project.scope_schedule:
        return []
    return [m.invoice for m in project.scope_schedule.milestones if m.invoice]


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
