from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import documents, google_service, mock_integrations
from ..services import google_oauth as g_oauth
from .projects import get_project_or_404

router = APIRouter(prefix="/api", tags=["contracts"])


def _get_package_or_404(db: Session, project_id: int) -> models.ContractPackage:
    project = get_project_or_404(db, project_id)
    if not project.contract_package:
        raise HTTPException(404, "No contract package for this project yet")
    return project.contract_package


@router.get("/projects/{project_id}/contract-package", response_model=schemas.ContractPackageOut)
def get_contract_package(project_id: int, db: Session = Depends(get_db)):
    return _get_package_or_404(db, project_id)


@router.patch("/projects/{project_id}/contract-package", response_model=schemas.ContractPackageOut)
def update_contract_package(project_id: int, payload: schemas.ContractPackageUpdate, db: Session = Depends(get_db)):
    cp = _get_package_or_404(db, project_id)
    if payload.description is not None:
        cp.description = payload.description
    if payload.disclosures is not None:
        cp.disclosures = payload.disclosures
    db.commit()
    db.refresh(cp)
    return cp


@router.post("/projects/{project_id}/contract-package/regenerate-summary", response_model=schemas.ContractPackageOut)
def regenerate_summary(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    cp = _get_package_or_404(db, project_id)
    if not project.scope_schedule:
        raise HTTPException(400, "Save the Scope & Payment Schedule first")
    milestone_summary = "; ".join(m.title for m in sorted(project.scope_schedule.milestones, key=lambda m: m.number))
    cp.description = (
        f"{project.estimate.scope_text} Work will proceed in {len(project.scope_schedule.milestones)} "
        f"milestones: {milestone_summary}."
    ).strip()
    db.commit()
    db.refresh(cp)
    return cp


@router.post("/projects/{project_id}/contract-package/approve", response_model=schemas.ContractPackageOut)
def approve_contract_package(project_id: int, payload: schemas.ApproveContractPackage, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    cp = _get_package_or_404(db, project_id)
    if not project.scope_schedule:
        raise HTTPException(400, "Save the Scope & Payment Schedule before approving the contract package")
    cp.status = "approved"
    cp.approved_by = payload.approved_by
    cp.approved_at = dt.datetime.now()

    if g_oauth.get_connection(db):
        # Real save: generate the actual combined PDF and upload it into the
        # project's own Drive folder (not a separate folder — the template
        # README's layout is one file per project folder).
        try:
            pdf_bytes = documents.build_contract_package_pdf(
                project=project, estimate=project.estimate, scope_schedule=project.scope_schedule, contract_package=cp
            )
            filename = f"{project.customer_name} – {project.property_address.split(',')[0]} – Contract Package.pdf"
            cp.drive_file_id = google_service.upload_file(
                db, filename, pdf_bytes, "application/pdf", project.drive_folder_id
            )
        except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
            raise HTTPException(502, f"Google Drive error: {exc}") from exc
    else:
        cp.drive_file_id = cp.drive_file_id or mock_integrations.create_drive_folder(project.customer_name, "contract-package")
    db.commit()
    db.refresh(cp)
    return cp


@router.post("/projects/{project_id}/contract-package/send-for-signature", response_model=schemas.ContractPackageOut)
def send_for_signature(project_id: int, db: Session = Depends(get_db)):
    cp = _get_package_or_404(db, project_id)
    if cp.status != "approved":
        raise HTTPException(400, "Approve the contract package before sending it for signature")
    cp.status = "out_for_signature"
    cp.adobe_agreement_id = cp.adobe_agreement_id or f"agreement-{project_id}-{cp.id}"
    db.commit()
    db.refresh(cp)
    return cp


@router.post("/projects/{project_id}/contract-package/revert-to-draft", response_model=schemas.ContractPackageOut)
def revert_to_draft(project_id: int, db: Session = Depends(get_db)):
    cp = _get_package_or_404(db, project_id)
    if cp.status == "signed":
        raise HTTPException(400, "A signed contract package cannot be reverted to draft")
    cp.status = "draft"
    cp.approved_by = None
    cp.approved_at = None
    db.commit()
    db.refresh(cp)
    return cp


@router.post("/projects/{project_id}/contract-package/mark-signed", response_model=schemas.ContractPackageOut)
def mark_signed(project_id: int, db: Session = Depends(get_db)):
    """Simulates the Adobe Acrobat Sign completion webhook."""
    cp = _get_package_or_404(db, project_id)
    if cp.status != "out_for_signature":
        raise HTTPException(400, "Contract package must be sent for signature first")
    cp.status = "signed"
    db.commit()
    db.refresh(cp)
    return cp


@router.get("/projects/{project_id}/contract-package/pdf")
def download_contract_package_pdf(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    cp = _get_package_or_404(db, project_id)
    if not project.scope_schedule:
        raise HTTPException(400, "Save the Scope & Payment Schedule before generating the combined PDF")
    pdf_bytes = documents.build_contract_package_pdf(
        project=project, estimate=project.estimate, scope_schedule=project.scope_schedule, contract_package=cp
    )
    filename = f"{project.customer_name} - Contract Package.pdf".replace("/", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
