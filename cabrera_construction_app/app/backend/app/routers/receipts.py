from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api", tags=["receipts"])


def _apply_payment_to_milestone(db: Session, milestone: models.Milestone, receipt_amount: float) -> None:
    total_paid = sum(
        float(r.amount)
        for r in db.query(models.Receipt).filter(
            models.Receipt.milestone_id == milestone.id, models.Receipt.type == "payment"
        )
    )
    target = float(milestone.invoice.amount) if milestone.invoice else float(milestone.amount)
    if total_paid >= target:
        milestone.status = "paid"
        if milestone.invoice:
            milestone.invoice.status = "paid"
    elif total_paid > 0:
        milestone.status = "partial"


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
            _apply_payment_to_milestone(db, milestone, payload.amount)

    db.commit()
    db.refresh(receipt)
    return receipt


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
