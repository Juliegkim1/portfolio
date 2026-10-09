from __future__ import annotations

import datetime as dt
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import documents, gemini_service, google_service, mock_integrations
from ..services import google_oauth as g_oauth
from ..services import quickbooks_oauth as qb_oauth
from ..services import quickbooks_service

logger = logging.getLogger("cabrera.projects")

router = APIRouter(prefix="/api", tags=["projects"])

# Cabrera's standard warranty policy — the default for every new Scope &
# Payment Schedule (editable per project afterward), so the generated
# Contract Package PDF never ships with a blank warranty section just
# because extraction didn't find one or nobody visited the Scope & Payment
# Schedule screen to fill it in before Approve.
_DEFAULT_WARRANTY_TERMS = (
    "1-YEAR WORKMANSHIP WARRANTY POLICY (CSLB COMPLIANT)\n\n"
    "- Guarantee Duration: Cabrera Construction warrants all labor and installation craftsmanship "
    "for one (1) full year from the final completion date.\n"
    "- Scope of Coverage: Covers defects in installation workmanship, tile setting/grout, cabinet "
    "mounting, drywall finishing, and MEP connections.\n"
    "- Client Material Exclusions: Manufacturer defects on client-supplied items (cabinets, tiles, "
    "fixtures, appliances) are governed by manufacturer warranties.\n"
    "- Service Notice & Remedy: Contractor shall inspect and remedy any verified workmanship defect "
    "within 14 business days of written notification."
)


def get_project_or_404(db: Session, project_id: int) -> models.Project:
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _project_display_name(customer_name: str, property_address: str) -> str:
    """"{Customer} — {Street}" — the table/record-card title shown
    everywhere a project list is rendered. Not a computed property on the
    model: it's stored on Project.name so it survives independently of
    whatever the live customer_name/property_address are at render time —
    but that means anything that changes either of those two fields after
    creation (update_project_customer, update_project_address) has to
    recompute and re-save this too, or the title silently goes stale even
    though the fields it's titling have already been corrected."""
    street = property_address.split(",")[0] if property_address else ""
    return f"{customer_name} — {street}" if street else customer_name


@router.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).order_by(models.Project.created_at.desc()).all()


@router.get("/projects/drive-importable")
def list_drive_importable_projects(db: Session = Depends(get_db)):
    """Subfolders under Drive -> Projects that don't belong to a project in
    this app yet — e.g. real project folders from before this app existed.

    Registered ahead of GET /projects/{project_id} below: FastAPI matches
    routes in registration order, and "drive-importable" would otherwise be
    swallowed by {project_id}'s int parsing and 422 before ever reaching
    this handler."""
    if not g_oauth.get_connection(db):
        raise HTTPException(409, "Connect Google Workspace first to import existing projects from Drive.")
    existing_folder_ids = {
        row[0] for row in db.query(models.Project.drive_folder_id).filter(models.Project.drive_folder_id.isnot(None))
    }
    try:
        folders = google_service.list_importable_project_folders(db, existing_folder_ids)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
        raise HTTPException(502, f"Google Drive error: {exc}") from exc
    return [{"folder_id": f["id"], "name": f["name"]} for f in folders]


@router.get("/projects/drive-imports", response_model=list[schemas.DriveImportHistoryItem])
def list_drive_import_history(db: Session = Depends(get_db)):
    """Every project that came from POST .../confirm, newest first — the
    confirmation that a given Drive folder was actually imported, and what
    was extracted from it, for the dedicated Import from Drive page.
    Registered ahead of GET /projects/{project_id} for the same route-
    ordering reason as drive-importable above."""
    projects = (
        db.query(models.Project)
        .filter(models.Project.imported_at.isnot(None))
        .order_by(models.Project.imported_at.desc())
        .all()
    )
    return [
        schemas.DriveImportHistoryItem(
            project_id=p.id,
            project_name=p.name,
            customer_name=p.customer_name,
            property_address=p.property_address,
            project_type=p.project_type,
            imported_at=p.imported_at,
            drive_folder_id=p.drive_folder_id,
            scope_text=p.estimate.scope_text if p.estimate else "",
            total=p.estimate.total if p.estimate else 0,
            line_items=[schemas.EstimateLineItemOut.model_validate(li) for li in (p.estimate.line_items if p.estimate else [])],
            milestones=[schemas.MilestoneOut.model_validate(m) for m in (p.scope_schedule.milestones if p.scope_schedule else [])],
            contract_status=p.contract_package.status if p.contract_package else "draft",
        )
        for p in projects
    ]


@router.get("/projects/check-drive-folder")
def check_drive_folder(customer_name: str, street: str, db: Session = Depends(get_db)):
    """Read-only lookup for the Estimate Upload screen: warns before
    creating a project when a Drive folder for this customer+address
    already exists, since the new project will land as a sibling subfolder
    there (see google_service.create_project_folder), not get a folder of
    its own. Registered ahead of GET /projects/{project_id} for the same
    route-ordering reason as drive-importable above. Silently reports
    "no existing folder" rather than erroring when Google isn't connected
    or the check itself fails — this is advisory, not load-bearing."""
    if not g_oauth.get_connection(db):
        return {"exists": False, "existing_project_types": []}
    try:
        existing = google_service.find_existing_customer_folder(db, customer_name, street)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError):
        return {"exists": False, "existing_project_types": []}
    if not existing:
        return {"exists": False, "existing_project_types": []}
    return {"exists": True, "existing_project_types": existing["existing_project_types"]}


@router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Deletes a project and everything that only exists because of it
    (estimate, scope schedule, milestones, their invoices, contract
    package, change orders — all cascade via the model relationships).
    Receipts and bank transactions are NOT deleted — they represent real
    money that moved; they're unlinked back to "unassigned" instead, same
    as reassigning a receipt's project to None elsewhere in the app."""
    project = get_project_or_404(db, project_id)

    if project.scope_schedule:
        milestone_ids = [m.id for m in project.scope_schedule.milestones]
        if milestone_ids:
            db.query(models.Invoice).filter(models.Invoice.milestone_id.in_(milestone_ids)).delete(synchronize_session=False)

    receipt_ids = [r.id for r in project.receipts]
    if receipt_ids:
        db.query(models.BankTransaction).filter(models.BankTransaction.receipt_id.in_(receipt_ids)).update(
            {"receipt_id": None, "match_status": "unmatched"}, synchronize_session=False
        )
        db.query(models.Receipt).filter(models.Receipt.project_id == project_id).update(
            {"project_id": None, "needs_project": True}, synchronize_session=False
        )
    db.query(models.BankTransaction).filter(models.BankTransaction.project_id == project_id).update(
        {"project_id": None}, synchronize_session=False
    )

    db.delete(project)
    db.commit()


@router.patch("/projects/{project_id}/estimate", response_model=schemas.EstimateOut)
def override_estimate_total(project_id: int, payload: schemas.EstimateAmountOverride, db: Session = Depends(get_db)):
    """Manually correct the contract total and/or the real estimate number.
    Passing total_override: null clears the correction and reverts to the
    computed total (subtotal + tax + permit fees - discount). Each field is
    only touched when actually present in the request body (checked via
    model_fields_set, not just "is it None") — total_override's own None
    means "clear it", so a request updating only estimate_number must leave
    total_override untouched rather than defaulting it to None and wiping
    an existing override."""
    project = get_project_or_404(db, project_id)
    if not project.estimate:
        raise HTTPException(404, "No estimate for this project yet")
    fields_set = payload.model_fields_set
    if "total_override" in fields_set:
        project.estimate.total_override = payload.total_override
    if "estimate_number" in fields_set and payload.estimate_number is not None:
        project.estimate.estimate_number = payload.estimate_number
    db.commit()
    db.refresh(project.estimate)
    return project.estimate


@router.post("/projects/{project_id}/estimate/upload-pdf", response_model=schemas.EstimateOut)
async def upload_estimate_pdf(project_id: int, file: UploadFile, db: Session = Depends(get_db)):
    """Attaches the REAL estimate PDF (e.g. the one QuickBooks itself
    generates, exported and uploaded here) so the Contract Package's last
    page can embed the actual document instead of a bare "Estimate #" page
    — see services/documents.py's build_contract_package_pdf. There's no
    extraction here (no Gemini call); this is purely "save this exact file
    as the real source document," unlike /estimates/upload, which reads a
    file to populate a NEW project's fields."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF uploads are accepted here")
    project = get_project_or_404(db, project_id)
    if not project.estimate:
        raise HTTPException(404, "No estimate for this project yet")
    if not project.drive_folder_id:
        raise HTTPException(409, "This project has no Drive folder yet — connect Google Workspace first.")
    if not g_oauth.get_connection(db):
        raise HTTPException(409, "Connect Google Workspace first.")
    file_bytes = await file.read()
    try:
        project.estimate.source_file_id = google_service.upload_file(
            db, f"Estimate {project.estimate.estimate_number} (uploaded).pdf", file_bytes, "application/pdf", project.drive_folder_id
        )
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
        raise HTTPException(502, f"Google Drive error: {exc}") from exc
    db.commit()
    db.refresh(project.estimate)
    return project.estimate


@router.post("/projects/{project_id}/estimate/line-items/clean-up", response_model=schemas.EstimateOut)
def clean_up_estimate_line_items(project_id: int, db: Session = Depends(get_db)):
    """Rewrites every line item's description on an already-created
    project's estimate — for one extracted before the extraction prompt's
    own grammar/typo/summarize cleanup rule existed (or that still came
    out messy anyway, e.g. a real document with long rambling per-item
    text). section/qty/unit/unit_price are never touched — see
    gemini_service.clean_up_line_item_descriptions."""
    project = get_project_or_404(db, project_id)
    if not project.estimate or not project.estimate.line_items:
        raise HTTPException(404, "No line items to clean up for this project")
    if not gemini_service.any_provider_configured():
        raise HTTPException(400, "No AI extraction provider is configured — set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in app/backend/.env.")
    line_items = sorted(project.estimate.line_items, key=lambda li: li.id)
    try:
        cleaned_descriptions = gemini_service.clean_up_line_item_descriptions(line_items)
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
    for li, description in zip(line_items, cleaned_descriptions):
        li.description = description
    db.commit()
    db.refresh(project.estimate)
    return project.estimate


@router.patch("/projects/{project_id}/estimate/line-items", response_model=schemas.EstimateOut)
def update_estimate_line_item_descriptions(project_id: int, payload: schemas.EstimateLineItemsUpdate, db: Session = Depends(get_db)):
    """Manual hand-edit of one or more line item descriptions — e.g.
    touching up the AI clean-up pass's result, or fixing something it
    doesn't need to see. Only description changes; any id not found on
    this estimate is silently skipped rather than erroring, so a stale
    frontend list (edited, then the project's line items changed
    elsewhere) doesn't 404 the whole request over one missing row."""
    project = get_project_or_404(db, project_id)
    if not project.estimate:
        raise HTTPException(404, "No estimate for this project yet")
    by_id = {li.id: li for li in project.estimate.line_items}
    for item in payload.items:
        line_item = by_id.get(item.id)
        if line_item:
            line_item.description = item.description
    db.commit()
    db.refresh(project.estimate)
    return project.estimate


@router.patch("/projects/{project_id}/dates", response_model=schemas.ProjectOut)
def update_project_dates(project_id: int, payload: schemas.ProjectDatesUpdate, db: Session = Depends(get_db)):
    """Backfills/corrects start_date and end_date — see
    schemas.ProjectDatesUpdate for why these matter (Analytics)."""
    project = get_project_or_404(db, project_id)
    project.start_date = payload.start_date
    project.end_date = payload.end_date
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}/type", response_model=schemas.ProjectOut)
def update_project_type(project_id: int, payload: schemas.ProjectTypeUpdate, db: Session = Depends(get_db)):
    """Recategorizes a project (e.g. Kitchen Remodel -> Bathroom Remodel)
    after it's already been created or imported — the type picked at
    estimate-upload/Drive-import time is free text and easy to get wrong."""
    project = get_project_or_404(db, project_id)
    new_type = payload.project_type.strip()
    if not new_type:
        raise HTTPException(400, "Project type cannot be empty")
    project.project_type = new_type
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}/customer", response_model=schemas.ProjectOut)
def update_project_customer(project_id: int, payload: schemas.ProjectCustomerUpdate, db: Session = Depends(get_db)):
    """Corrects the customer's name/phone/email after a project already
    exists — extracted once at creation time (from a QuickBooks lookup,
    an upload, or notes) and easy to come out wrong or incomplete, with no
    way to fix it short of deleting and recreating the whole project.
    Phone/email stay optional (blank is valid, same as at creation); only
    the name is required."""
    project = get_project_or_404(db, project_id)
    new_name = payload.customer_name.strip()
    if not new_name:
        raise HTTPException(400, "Customer name cannot be empty")
    project.customer_name = new_name
    project.customer_phone = payload.customer_phone.strip()
    project.customer_email = payload.customer_email.strip()
    # project.name ("{Customer} — {Street}") is a separate stored field, not
    # computed from customer_name/property_address at render time — without
    # this it silently goes stale: the Customer column and this card both
    # show the corrected name, but the bold project title everywhere else
    # keeps showing the old one.
    project.name = _project_display_name(project.customer_name, project.property_address)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}/address", response_model=schemas.ProjectOut)
def update_project_address(project_id: int, payload: schemas.ProjectAddressUpdate, db: Session = Depends(get_db)):
    """Corrects the job site/property address after a project already
    exists — previously read-only everywhere (Projects, Scope & Payment
    Schedule, Contract Package), with no way to fix a typo short of
    deleting and recreating the whole project."""
    project = get_project_or_404(db, project_id)
    new_address = payload.property_address.strip()
    if not new_address:
        raise HTTPException(400, "Property address cannot be empty")
    project.property_address = new_address
    # See update_project_customer above for why this has to be recomputed too.
    project.name = _project_display_name(project.customer_name, project.property_address)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}/drive-folder", response_model=schemas.ProjectOut)
def update_project_drive_folder(project_id: int, payload: schemas.ProjectDriveFolderUpdate, db: Session = Depends(get_db)):
    """Manually points a project at a real Drive folder — for a project
    whose folder wasn't discoverable through the automatic scan (see
    GET /projects/drive-importable, which only looks directly under Drive ›
    Projects) or one created before Google was ever connected. No
    validation that the folder actually exists/is readable — same as how
    drive_folder_id already gets set from the automatic flows without a
    round-trip check, and a typo here is just as easy to re-correct."""
    project = get_project_or_404(db, project_id)
    project.drive_folder_id = google_service.extract_drive_folder_id(payload.drive_folder_link)
    db.commit()
    db.refresh(project)
    return project


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


_ACCEPTED_UPLOAD_EXTENSIONS = (".pdf", ".docx", ".xlsx")


@router.post("/estimates/upload", response_model=schemas.EstimateFetchResult)
async def upload_estimate(file: UploadFile):
    if not file.filename.lower().endswith(_ACCEPTED_UPLOAD_EXTENSIONS):
        raise HTTPException(400, "Only PDF, DOCX, or XLSX uploads are accepted")
    file_bytes = await file.read()

    if not gemini_service.any_provider_configured():
        # No honest way to extract an arbitrary document without at least
        # one AI provider configured — fall back to the clearly-labeled
        # demo data rather than failing outright.
        return mock_integrations.mock_parse_estimate_pdf(file.filename)

    try:
        return gemini_service.extract_estimate_from_document(file_bytes, file.filename, file.content_type or "")
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/estimates/paste", response_model=schemas.EstimateFetchResult)
def paste_estimate_text(payload: schemas.EstimateTextPaste):
    """Same extraction as /estimates/upload, sourcing the text directly from
    a paste instead of a file — the fallback when a .docx/.xlsx isn't
    actually readable (see gemini_service's docx/xlsx error messages) or
    when copy-pasting notes is just faster than exporting a file first."""
    if not gemini_service.any_provider_configured():
        return mock_integrations.mock_parse_estimate_pdf("pasted-notes.txt")
    try:
        return gemini_service.extract_estimate_from_text(payload.text)
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/estimates/combine-notes", response_model=schemas.EstimateFetchResult)
def combine_estimate_notes(payload: schemas.EstimateCombineNotes):
    """Merges supplementary notes into an estimate already on screen (from
    QuickBooks, an upload, Drive, or an earlier paste) — for the real-world
    case where the estimate has the cost breakdown but no payment schedule
    and separate notes supply the phases, or vice versa. See
    gemini_service.combine_estimate_with_notes for the merge rules."""
    if not gemini_service.any_provider_configured():
        raise HTTPException(400, "No AI extraction provider is configured — set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in app/backend/.env.")
    try:
        return gemini_service.combine_estimate_with_notes(payload.existing, payload.notes_text)
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/drive/documents")
def search_drive_documents(search: str | None = None, db: Session = Depends(get_db)):
    """PDF/DOCX files anywhere in the connected Drive account, for the
    Estimate Upload screen's "choose from Google Drive" route — an
    alternative to uploading from the local computer, not scoped to the
    Projects folder (the document being picked usually isn't filed under a
    project yet; that's the whole point of this screen)."""
    if not g_oauth.get_connection(db):
        raise HTTPException(409, "Connect Google Workspace first.")
    try:
        files = google_service.search_documents(db, search)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
        raise HTTPException(502, f"Google Drive error: {exc}") from exc
    return [{"id": f["id"], "name": f["name"], "modified_time": f.get("modifiedTime")} for f in files]


@router.post("/estimates/upload-from-drive/{file_id}", response_model=schemas.EstimateFetchResult)
def upload_estimate_from_drive(file_id: str, db: Session = Depends(get_db)):
    """Same extraction as /estimates/upload, sourcing the document's bytes
    from an existing Drive file (picked via /drive/documents) instead of a
    local file upload."""
    if not g_oauth.get_connection(db):
        raise HTTPException(409, "Connect Google Workspace first.")
    if not gemini_service.any_provider_configured():
        return mock_integrations.mock_parse_estimate_pdf(file_id)
    try:
        filename = google_service.get_file_name(db, file_id)
        file_bytes = google_service.download_file(db, file_id)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
        raise HTTPException(502, f"Google Drive error: {exc}") from exc
    try:
        return gemini_service.extract_estimate_from_document(file_bytes, filename, "")
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


_MAX_FOLDER_DOCUMENTS = 20


def _read_one_folder_document(db: Session, file_meta: dict) -> tuple[bytes, str, str]:
    """A native Google Sheet has no bytes of its own — alt=media 403s on it —
    so it has to be rendered via Drive's /export endpoint instead, as a PDF
    (preserves layout: section headers, merged cells) rather than CSV. Every
    other file type (uploaded .pdf/.docx) downloads as-is."""
    if file_meta.get("mimeType") == google_service.SHEET_MIME:
        content = google_service.export_file(db, file_meta["id"], "application/pdf")
        return content, file_meta["name"], "application/pdf"
    content = google_service.download_file(db, file_meta["id"])
    return content, file_meta["name"], file_meta.get("mimeType", "")


def _read_folder_documents(db: Session, folder_id: str) -> list[tuple[bytes, str, str]]:
    try:
        files_meta = google_service.list_folder_documents(db, folder_id)
        if not files_meta:
            raise HTTPException(422, "No PDF, DOCX, XLSX, or Google Sheets files found in this Drive folder to read.")
        # Filename-keyword prioritizing was a mistake for exactly the case
        # that matters most here: a contractor's own informal notes file
        # (e.g. "notes.docx", "Doc2.docx") has none of these keywords in its
        # name, so sorting by keyword match actively pushed the one file
        # most likely to hold the real scope/schedule to the back of the
        # list — right where a small cap would cut it off. The real fix is
        # a cap generous enough to just read everything in a normal project
        # folder (20 covers every real example seen so far with room to
        # spare), not a heuristic for guessing what's "relevant" by name.
        files_meta = sorted(files_meta, key=lambda f: f["name"])[:_MAX_FOLDER_DOCUMENTS]
        return [_read_one_folder_document(db, f) for f in files_meta]
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
        raise HTTPException(502, f"Google Drive error: {exc}") from exc


@router.post("/projects/drive-import/{folder_id}", response_model=schemas.DriveImportPreview)
def preview_drive_import(folder_id: str, db: Session = Depends(get_db)):
    """Reads a pre-existing Drive project folder (contract/estimate/payment
    schedule — whatever's in there) for review before import. Deliberately
    separate from the QuickBooks/upload estimate flow above: a folder found
    here predates this app, so it's a complete historical record (already
    signed, possibly already partially paid), not a fresh lead to run
    through the new-project wizard. See POST .../confirm for the second
    step, which actually creates the project from this preview."""
    if not g_oauth.get_connection(db):
        raise HTTPException(409, "Connect Google Workspace first.")
    if not gemini_service.any_provider_configured():
        raise HTTPException(400, "No AI extraction provider is configured — set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in app/backend/.env.")

    documents = _read_folder_documents(db, folder_id)
    try:
        folder_name = google_service.get_file_name(db, folder_id)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError):
        folder_name = folder_id
    try:
        return gemini_service.extract_historical_project(folder_id, folder_name, documents)
    except gemini_service.GeminiExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc


def _missing_import_fields(preview: schemas.DriveImportPreview) -> list[str]:
    missing = []
    if not preview.customer_name.strip():
        missing.append("Customer name")
    if not preview.property_address.strip():
        missing.append("Property address")
    if not preview.line_items:
        missing.append("At least one line item")
    return missing


@router.post("/projects/drive-import/{folder_id}/confirm", response_model=schemas.ProjectOut)
def confirm_drive_import(folder_id: str, payload: schemas.DriveImportConfirm, db: Session = Depends(get_db)):
    """Creates a full historical project from a reviewed/edited preview —
    Project, Estimate, Scope & Payment Schedule (with whatever milestones
    were found), and a Contract Package already marked "signed" (skipping
    draft/approve/send-for-signature entirely, since this project's contract
    was already signed before this app existed). Reuses the existing Drive
    folder rather than creating a new one, so receipts/reconciliation
    already filed there keep working once this project exists in the app."""
    preview = payload.preview
    missing = _missing_import_fields(preview)
    if missing:
        raise HTTPException(422, f"Missing required information before this project can be imported: {', '.join(missing)}.")

    customer_name = preview.customer_name

    project = models.Project(
        name=_project_display_name(customer_name, preview.property_address or ""),
        project_type=payload.project_type,
        customer_name=customer_name,
        customer_phone=preview.customer_phone,
        customer_email=preview.customer_email,
        property_address=preview.property_address,
        drive_folder_id=folder_id,
        imported_at=dt.datetime.now(),
    )
    db.add(project)
    db.flush()

    estimate = models.Estimate(
        project_id=project.id,
        estimate_number=f"IMPORTED-{folder_id[:12]}",
        scope_text=preview.scope_text,
    )
    db.add(estimate)
    db.flush()
    for li in preview.line_items:
        db.add(models.EstimateLineItem(estimate_id=estimate.id, **li.model_dump()))

    # A historical project with no extractable payment schedule still needs
    # *some* milestone for invoicing/reconciliation to hang off of — fall
    # back to one covering the full amount rather than leaving the schedule
    # empty. Status stays "scheduled", not "paid": a signed contract doesn't
    # mean every milestone has actually been paid yet, and that's exactly
    # what Reconciliation (bank/receipt matching) is for, on this project
    # like any other.
    scope_schedule = models.ScopeSchedule(
        project_id=project.id,
        contract_date=preview.contract_date,
        payment_terms=preview.payment_terms or "Due on milestone completion, net 15",
        warranty_terms=preview.warranty_terms.strip() or _DEFAULT_WARRANTY_TERMS,
    )
    db.add(scope_schedule)
    db.flush()
    milestones = preview.milestones or [schemas.MilestonePreview(number=0, title="Full Contract Amount", amount=preview.total)]
    for m in milestones:
        db.add(
            models.Milestone(
                scope_schedule_id=scope_schedule.id,
                number=m.number,
                title=m.title,
                amount=m.amount,
                due_date=m.due_date,
                scope_verification=getattr(m, "scope_verification", None) or "",
            )
        )
    project.start_date, project.end_date = _derive_project_dates(milestones)

    contract_package = models.ContractPackage(
        project_id=project.id,
        description=preview.scope_text,
        status="signed",
        approved_by="Imported from Drive",
        approved_at=dt.datetime.now(),
        attachments=[
            {"label": "Contract pp. 1-4", "kind": "contract"},
            {"label": "Att. 1 Notice of Cancellation", "kind": "noc"},
            {"label": "Att. 2 Change Order Form", "kind": "change_order_form"},
            {"label": "Att. 3 CA Checklist", "kind": "ca_checklist"},
            {"label": "4. Project Scope and Payment Schedule", "kind": "scope_schedule"},
            {"label": "5. Estimate", "kind": "estimate"},
        ],
    )
    db.add(contract_package)
    db.commit()
    db.refresh(project)

    # Best-effort, same reasoning as create_project_from_estimate below: the
    # project is already fully usable even if the Sheet write fails. Catches
    # httpx.HTTPError too, not just our own exception types — a raw httpx
    # error (e.g. token refresh hitting an unexpected status, a network
    # blip) previously escaped this except clause entirely, crashing the
    # whole request with a 500 *after* the project/estimate/schedule/
    # contract package were already committed above — so the record really
    # was created, but the response never confirmed it and the frontend had
    # no way to know.
    try:
        project.sheet_id = google_service.create_sheet(db, f"{customer_name} Reconciliation", parent_folder_id=folder_id)
        db.commit()
        db.refresh(project)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError, httpx.HTTPError) as exc:
        db.rollback()
        logger.error("Reconciliation Sheet creation failed for imported project %s (%s): %s", project.id, project.name, exc)

    return project


def _derive_project_dates(milestones: list) -> tuple[dt.date | None, dt.date | None]:
    """Project.start_date/end_date are never set anywhere else, and the
    Analytics page's Project Timeline / Concurrency charts both require
    both to be set to show a project at all — so without this, every real
    project (new or imported) is invisible there forever, not just until
    more data comes in. The milestone due dates already extracted are the
    best available signal for a project's actual date range in the absence
    of an explicit start/completion date in the source document."""
    due_dates = [m.due_date for m in milestones if m.due_date]
    if not due_dates:
        return None, None
    return min(due_dates), max(due_dates)


def _missing_required_fields(est: schemas.EstimateFetchResult) -> list[str]:
    missing = []
    if not (est.customer_name or "").strip():
        missing.append("Customer name")
    if not (est.property_address or "").strip():
        missing.append("Property address")
    if not est.line_items:
        missing.append("At least one line item")
    return missing


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project_from_estimate(payload: schemas.CreateProjectFromEstimate, db: Session = Depends(get_db)):
    est = payload.estimate

    # Prompt for missing info rather than silently creating a broken/unusable
    # project — these fields are load-bearing for the Scope & Payment
    # Schedule and Contract Package screens further down the flow.
    missing = _missing_required_fields(est)
    if missing:
        raise HTTPException(422, f"Missing required information before this project can be created: {', '.join(missing)}.")

    street = est.property_address.split(",")[0] if est.property_address else ""
    customer_name = est.customer_name or "Customer"

    # Database work happens first and commits as one unit — only AFTER that
    # succeeds do we touch Google Drive/Sheets. Doing it in this order (not
    # the reverse) means a failure here can never leave an orphaned Drive
    # folder/Sheet with no project behind it, and a later Drive/Sheets
    # failure can't lose an already-valid project record either.
    project = models.Project(
        name=_project_display_name(customer_name, est.property_address or ""),
        project_type=payload.project_type,
        customer_name=est.customer_name or "",
        customer_phone=est.customer_phone or "",
        customer_email=est.customer_email or "",
        property_address=est.property_address or "",
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
            {"label": "4. Project Scope and Payment Schedule", "kind": "scope_schedule"},
            {"label": "5. Estimate", "kind": "estimate"},
        ],
    )
    db.add(contract_package)

    # If the source document had its own payment schedule, pre-populate the
    # Scope & Payment Schedule step with it instead of leaving that screen to
    # generate a generic deposit/final-payment default — a plain QuickBooks
    # lookup never has milestones, so this is skipped there and that default
    # still applies, unchanged.
    # Cabrera's own QuickBooks estimates are structured as one line item per
    # payment phase (per real examples reviewed — "1. Demolition $5,000",
    # "2. Rough Framing $10,000", ...), not a materials/labor cost
    # breakdown — so when nothing already extracted a payment schedule
    # (true of every QuickBooks-sourced estimate, since the QB API has no
    # payment-schedule concept at all), each line item becomes one
    # milestone directly rather than falling back to a generic, made-up
    # deposit/final-walkthrough split that doesn't reflect the real phases.
    milestone_sources = est.milestones or [
        schemas.MilestonePreview(number=i, title=li.description, amount=round(li.qty * li.unit_price, 2))
        for i, li in enumerate(est.line_items)
    ]
    if milestone_sources:
        scope_schedule = models.ScopeSchedule(
            project_id=project.id,
            contract_date=est.contract_date,
            payment_terms=est.payment_terms or "Due on milestone completion, net 15",
            warranty_terms=(est.warranty_terms or "").strip() or _DEFAULT_WARRANTY_TERMS,
        )
        db.add(scope_schedule)
        db.flush()
        for m in milestone_sources:
            db.add(
                models.Milestone(
                    scope_schedule_id=scope_schedule.id,
                    number=m.number,
                    title=m.title,
                    amount=m.amount,
                    due_date=m.due_date,
                    scope_verification=getattr(m, "scope_verification", None) or "",
                )
            )
        project.start_date, project.end_date = _derive_project_dates(milestone_sources)

    db.commit()
    db.refresh(project)

    # Best-effort: the project/estimate/contract package already exist and
    # are usable even if this fails, so a Drive/Sheets hiccup here doesn't
    # lose anything — it just leaves drive_folder_id/sheet_id unset (shown
    # as "Not yet created" in the UI) for the user to retry later.
    folder_name = (payload.drive_folder_name or "").strip() or payload.project_type
    try:
        if g_oauth.get_connection(db):
            drive_folder_id = google_service.create_project_folder(db, customer_name, street, folder_name)
            sheet_id = google_service.create_sheet(db, f"{customer_name} Reconciliation", parent_folder_id=drive_folder_id)
        else:
            drive_folder_id = mock_integrations.create_drive_folder(customer_name, street, folder_name)
            sheet_id = mock_integrations.create_sheet(f"{customer_name} Reconciliation")
        project.drive_folder_id = drive_folder_id
        project.sheet_id = sheet_id
        db.commit()
        db.refresh(project)
    except (g_oauth.GoogleNotConnected, google_service.GoogleApiError, httpx.HTTPError) as exc:
        db.rollback()
        logger.error("Drive folder/Sheet creation failed for project %s (%s): %s — project itself was still created.", project.id, project.name, exc)

    # Deliberately NOT auto-generating a recreated "Estimate" PDF here the
    # way this used to: source_file_id means "a real uploaded estimate
    # document" (see POST .../estimate/upload-pdf) — a reportlab recreation
    # built from extracted fields isn't that, and setting it here meant the
    # Contract Package's last page always showed that recreation (garbled
    # for a pasted-text/QuickBooks-fetched estimate with no real document
    # behind it, e.g. "QuickBooks Estimate DOC-Pasted notes") instead of
    # ever falling back to the clean "Estimate #<number>" summary page. The
    # Drive folder simply has nothing filed under this project yet besides
    # the Reconciliation Sheet until the user uploads the real PDF or
    # approves the contract package (which files the full combined PDF).
    return project
