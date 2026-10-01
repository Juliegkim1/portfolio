from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import mock_integrations

router = APIRouter(prefix="/api", tags=["projects"])


def get_project_or_404(db: Session, project_id: int) -> models.Project:
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).order_by(models.Project.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id)


@router.post("/estimates/fetch", response_model=schemas.EstimateFetchResult)
def fetch_estimate(payload: schemas.EstimateFetchRequest):
    return mock_integrations.lookup_quickbooks_estimate(payload.estimate_number)


@router.post("/estimates/upload", response_model=schemas.EstimateFetchResult)
async def upload_estimate(file: UploadFile):
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF uploads are accepted")
    return mock_integrations.mock_parse_estimate_pdf(file.filename)


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project_from_estimate(payload: schemas.CreateProjectFromEstimate, db: Session = Depends(get_db)):
    est = payload.estimate
    street = est.property_address.split(",")[0] if est.property_address else ""

    project = models.Project(
        name=f"{est.customer_name} — {street}" if street else (est.customer_name or "New Project"),
        project_type=payload.project_type,
        customer_name=est.customer_name or "",
        customer_phone=est.customer_phone or "",
        customer_email=est.customer_email or "",
        property_address=est.property_address or "",
        drive_folder_id=mock_integrations.create_drive_folder(est.customer_name or "Customer", street),
        sheet_id=mock_integrations.create_sheet(f"{est.customer_name} Reconciliation"),
    )
    db.add(project)
    db.flush()

    estimate = models.Estimate(
        project_id=project.id,
        estimate_number=est.estimate_number,
        date_issued=est.date_issued,
        tax_rate=est.tax_rate,
        permit_fees=est.permit_fees,
        discount=est.discount,
        scope_text=est.scope_text or "",
    )
    db.add(estimate)
    db.flush()
    for li in est.line_items:
        db.add(models.EstimateLineItem(estimate_id=estimate.id, **li.model_dump()))

    contract_package = models.ContractPackage(
        project_id=project.id,
        description=est.scope_text or "",
        attachments=[
            {"label": "Contract pp. 1-4", "kind": "contract"},
            {"label": "Att. 1 Notice of Cancellation", "kind": "noc"},
            {"label": "Att. 2 Change Order Form", "kind": "change_order_form"},
            {"label": "Att. 3 CA Checklist", "kind": "ca_checklist"},
            {"label": "Att. 4 Scope & Payment Schedule", "kind": "scope_schedule"},
            {"label": "Att. 5 QuickBooks Estimate", "kind": "estimate"},
        ],
    )
    db.add(contract_package)

    db.commit()
    db.refresh(project)
    return project
