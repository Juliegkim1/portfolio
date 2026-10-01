from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import change_orders as co_rules
from ..services import documents
from .projects import get_project_or_404

router = APIRouter(prefix="/api", tags=["change-orders"])


def _get_co_or_404(db: Session, co_id: int) -> models.ChangeOrder:
    co = db.get(models.ChangeOrder, co_id)
    if not co:
        raise HTTPException(404, "Change order not found")
    return co


def _build_out(co: models.ChangeOrder, estimate_total: float, all_cos: list[models.ChangeOrder]) -> schemas.ChangeOrderOut:
    prev = co_rules.previously_signed_contract_price(estimate_total, all_cos, co.number)
    new_price = co_rules.new_contract_price_for(estimate_total, all_cos, co)
    return schemas.ChangeOrderOut(
        id=co.id,
        project_id=co.project_id,
        number=co.number,
        owner_signed_at=co.owner_signed_at,
        contractor_signed_at=co.contractor_signed_at,
        parts_changed=co.parts_changed,
        scope=co.scope,
        amount_added=float(co.amount_added),
        amount_subtracted=float(co.amount_subtracted),
        milestone_changes=co.milestone_changes,
        new_completion_date=co.new_completion_date,
        uses_subcontractors=co.uses_subcontractors,
        status=co.status,
        created_at=co.created_at,
        is_signed=co_rules.is_signed(co),
        previously_signed_contract_price=prev,
        new_contract_price=new_price,
    )


@router.get("/projects/{project_id}/change-orders", response_model=list[schemas.ChangeOrderOut])
def list_change_orders(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    all_cos = sorted(project.change_orders, key=lambda c: c.number)
    estimate_total = project.estimate.total
    return [_build_out(co, estimate_total, all_cos) for co in all_cos]


@router.post("/projects/{project_id}/change-orders", response_model=schemas.ChangeOrderOut)
def create_change_order(project_id: int, payload: schemas.ChangeOrderIn, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    next_number = max((c.number for c in project.change_orders), default=0) + 1
    co = models.ChangeOrder(
        project_id=project.id,
        number=next_number,
        parts_changed=payload.parts_changed,
        scope=payload.scope,
        amount_added=payload.amount_added,
        amount_subtracted=payload.amount_subtracted,
        milestone_changes=[mc.model_dump() for mc in payload.milestone_changes],
        new_completion_date=payload.new_completion_date,
        uses_subcontractors=payload.uses_subcontractors,
    )
    db.add(co)
    db.commit()
    db.refresh(co)
    all_cos = sorted(project.change_orders, key=lambda c: c.number)
    return _build_out(co, project.estimate.total, all_cos)


@router.post("/change-orders/{co_id}/send", response_model=schemas.ChangeOrderOut)
def send_change_order(co_id: int, db: Session = Depends(get_db)):
    co = _get_co_or_404(db, co_id)
    if co.status != "draft":
        raise HTTPException(400, "Only a draft change order can be sent for signature")
    co.status = "out_for_signature"
    db.commit()
    db.refresh(co)
    all_cos = sorted(co.project.change_orders, key=lambda c: c.number)
    return _build_out(co, co.project.estimate.total, all_cos)


@router.post("/change-orders/{co_id}/sign", response_model=schemas.ChangeOrderOut)
def sign_change_order(co_id: int, payload: schemas.ChangeOrderSign, db: Session = Depends(get_db)):
    co = _get_co_or_404(db, co_id)
    if co.status != "out_for_signature":
        raise HTTPException(400, "Send the change order for signature first")

    now = dt.datetime.now()
    if payload.party == "owner":
        co.owner_signed_at = now
    else:
        co.contractor_signed_at = now

    if co_rules.is_signed(co):
        co.status = "signed"
        # A change order only affects totals/milestones/dates once BOTH parties have signed.
        for change in co.milestone_changes or []:
            milestone = db.get(models.Milestone, change["milestone_id"])
            if milestone:
                milestone.amount = float(milestone.amount) + float(change["delta"])
        if co.new_completion_date and co.project:
            co.project.end_date = co.new_completion_date

    db.commit()
    db.refresh(co)
    all_cos = sorted(co.project.change_orders, key=lambda c: c.number)
    return _build_out(co, co.project.estimate.total, all_cos)


@router.get("/change-orders/{co_id}/pdf")
def download_change_order_pdf(co_id: int, db: Session = Depends(get_db)):
    co = _get_co_or_404(db, co_id)
    project = co.project
    all_cos = sorted(project.change_orders, key=lambda c: c.number)
    original_price = project.estimate.total
    previously_signed = co_rules.previously_signed_contract_price(original_price, all_cos, co.number)
    new_price = co_rules.new_contract_price_for(original_price, all_cos, co)
    contract_date = project.scope_schedule.contract_date if project.scope_schedule else None
    pdf_bytes = documents.fill_change_order_pages(
        project=project,
        change_order=co,
        contract_date=contract_date,
        original_price=original_price,
        previously_signed_price=previously_signed,
        new_price=new_price,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="CO-{co.number:02d}.pdf"'},
    )
