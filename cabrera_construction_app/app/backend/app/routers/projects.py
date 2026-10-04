from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_db
from ..services import gemini_service, google_service, mock_integrations
from ..services import google_oauth as g_oauth
from ..services import quickbooks_oauth as qb_oauth
from ..services import quickbooks_service

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
def fetch_estimate(payload: schemas.EstimateFetchRequest, db: Session = Depends(get_db)):
    if qb_oauth.get_connection(db):
        try:
            return quickbooks_service.lookup_estimate(db, payload.estimate_number)
        except qb_oauth.QuickBooksNotConnected as exc:
            raise HTTPException(409, str(exc)) from exc
        except quickbooks_service.QuickBooksApiError as exc:
            # Upstream (Intuit) returned an error — not our bug, but surface
            # it cleanly rather than a generic 500 crash. The message already
            # includes the intuit_tid for support troubleshooting.
            raise HTTPException(502, str(exc)) from exc
    # Not connected yet — demo fixtures (1042 / 2091) so the screen is still usable.
    return mock_integrations.lookup_quickbooks_estimate(payload.estimate_number)


_ACCEPTED_UPLOAD_EXTENSIONS = (".pdf", ".docx")


@router.post("/estimates/upload", response_model=schemas.EstimateFetchResult)
async def upload_estimate(file: UploadFile):
    if not file.filename.lower().endswith(_ACCEPTED_UPLOAD_EXTENSIONS):
        raise HTTPException(400, "Only PDF or DOCX uploads are accepted")
    file_bytes = await file.read()

    if not settings.gemini_api_key:
        # No honest way to extract an arbitrary document without Gemini —
        # fall back to the clearly-labeled demo data rather than failing outright.
        return mock_integrations.mock_parse_estimate_pdf(file.filename)

    try:
        return gemini_service.extract_estimate_from_document(file_bytes, file.filename, file.content_type or "")
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project_from_estimate(payload: schemas.CreateProjectFromEstimate, db: Session = Depends(get_db)):
    est = payload.estimate
    street = est.property_address.split(",")[0] if est.property_address else ""
    customer_name = est.customer_name or "Customer"

    if g_oauth.get_connection(db):
        try:
            drive_folder_id = google_service.create_project_folder(db, customer_name, street)
            sheet_id = google_service.create_sheet(db, f"{customer_name} Reconciliation", parent_folder_id=drive_folder_id)
        except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
            raise HTTPException(502, f"Google Drive/Sheets error: {exc}") from exc
    else:
        drive_folder_id = mock_integrations.create_drive_folder(customer_name, street)
        sheet_id = mock_integrations.create_sheet(f"{customer_name} Reconciliation")

    project = models.Project(
        name=f"{customer_name} — {street}" if street else customer_name,
        project_type=payload.project_type,
        customer_name=est.customer_name or "",
        customer_phone=est.customer_phone or "",
        customer_email=est.customer_email or "",
        property_address=est.property_address or "",
        drive_folder_id=drive_folder_id,
        sheet_id=sheet_id,
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
