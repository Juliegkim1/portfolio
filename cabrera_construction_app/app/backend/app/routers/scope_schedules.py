from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import change_orders as co_rules
from ..services import milestones as milestone_rules
from .projects import get_project_or_404

router = APIRouter(prefix="/api", tags=["scope-schedules"])


def _revised_total(project: models.Project) -> float:
    """The balance/deposit checks compare against the revised contract total (estimate
    + signed change orders) so a project with a legitimately signed CO doesn't show as
    permanently "out of balance" against its original, pre-CO estimate."""
    return co_rules.revised_contract_total(project.estimate.total, project.change_orders)


def _validate(payload: schemas.ScopeScheduleIn, contract_total: float) -> tuple[bool, str, bool, str]:
    amounts = [m.amount for m in payload.milestones]
    balanced, balance_note = milestone_rules.check_balanced(amounts, contract_total)
    deposit = next((m.amount for m in payload.milestones if m.number == 0), 0.0)
    deposit_ok, deposit_note = milestone_rules.check_deposit(deposit, contract_total)
    return balanced, balance_note, deposit_ok, deposit_note


def _build_out(ss: models.ScopeSchedule, contract_total: float) -> schemas.ScopeScheduleOut:
    amounts = [float(m.amount) for m in ss.milestones]
    balanced, balance_note = milestone_rules.check_balanced(amounts, contract_total)
    deposit = next((float(m.amount) for m in ss.milestones if m.number == 0), 0.0)
    deposit_ok, deposit_note = milestone_rules.check_deposit(deposit, contract_total)
    return schemas.ScopeScheduleOut(
        id=ss.id,
        project_id=ss.project_id,
        contract_date=ss.contract_date,
        contract_type=ss.contract_type,
        payment_terms=ss.payment_terms,
        warranty_terms=ss.warranty_terms,
        drive_file_id=ss.drive_file_id,
        milestones=[schemas.MilestoneOut.model_validate(m) for m in sorted(ss.milestones, key=lambda m: m.number)],
        materials=[schemas.MaterialItemOut.model_validate(m) for m in ss.materials],
        total_amount=round(sum(amounts), 2),
        balanced=balanced,
        balance_note=balance_note,
        deposit_ok=deposit_ok,
        deposit_note=deposit_note,
    )


@router.get("/projects/{project_id}/scope-schedule", response_model=schemas.ScopeScheduleOut)
def get_scope_schedule(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if not project.scope_schedule:
        raise HTTPException(404, "No scope schedule for this project yet")
    return _build_out(project.scope_schedule, _revised_total(project))


@router.post("/projects/{project_id}/scope-schedule/validate")
def validate_scope_schedule(project_id: int, payload: schemas.ScopeScheduleIn, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    contract_total = _revised_total(project)
    balanced, balance_note, deposit_ok, deposit_note = _validate(payload, contract_total)
    return {
        "balanced": balanced,
        "balance_note": balance_note,
        "deposit_ok": deposit_ok,
        "deposit_note": deposit_note,
        "total_amount": sum(m.amount for m in payload.milestones),
        "contract_total": contract_total,
    }


@router.put("/projects/{project_id}/scope-schedule", response_model=schemas.ScopeScheduleOut)
def save_scope_schedule(project_id: int, payload: schemas.ScopeScheduleIn, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    contract_total = _revised_total(project)
    balanced, balance_note, deposit_ok, deposit_note = _validate(payload, contract_total)
    if not balanced:
        raise HTTPException(400, f"Cannot save: schedule is not balanced ({balance_note})")
    if not deposit_ok:
        raise HTTPException(400, f"Cannot save: {deposit_note}")

    ss = project.scope_schedule
    if not ss:
        ss = models.ScopeSchedule(project_id=project.id)
        db.add(ss)
        db.flush()
    else:
        ss.milestones.clear()
        ss.materials.clear()

    ss.contract_date = payload.contract_date
    ss.contract_type = payload.contract_type
    ss.payment_terms = payload.payment_terms
    ss.warranty_terms = payload.warranty_terms
    ss.drive_file_id = ss.drive_file_id or f"drive-file-scope-{project.id}"

    for m in payload.milestones:
        ss.milestones.append(models.Milestone(**m.model_dump()))
    for mi in payload.materials:
        ss.materials.append(models.MaterialItem(**mi.model_dump()))

    # "Save Schedule & Draft Contract": auto-summarize the contract description
    # from the estimate scope + milestone titles (user can edit/regenerate later).
    if project.contract_package:
        milestone_summary = "; ".join(m.title for m in payload.milestones)
        project.contract_package.description = (
            f"{project.estimate.scope_text} Work will proceed in {len(payload.milestones)} milestones: {milestone_summary}."
        ).strip()

    db.commit()
    db.refresh(ss)
    return _build_out(ss, contract_total)
