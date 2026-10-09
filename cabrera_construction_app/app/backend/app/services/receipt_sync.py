"""Scans My Drive/Receipts for new receipt photos, reads each one (vendor,
date, amount, and — the whole point — any handwritten customer name on
it), matches that name against existing projects, and files the result:
a confident single match gets moved into that project's own Drive folder
(under a "Receipts" subfolder) and recorded as a project expense; anything
else stays in the Receipts inbox, gets moved into a YYYY-MM subfolder so
the inbox itself stays short, and gets recorded as a business expense
flagged for manual review (Receipt.needs_project), same as any other
unassigned expense already works in this app.

Triggered by POST /receipts/sync-from-drive — a button today ("Sync
Receipts Now"), with real daily automation (Cloud Scheduler) a deliberate
later phase, not built here.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from .. import models, schemas
from . import gemini_service, google_service
from . import google_oauth as g_oauth

logger = logging.getLogger("cabrera.receipt_sync")


def _match_project(db: Session, handwritten_name: str | None) -> models.Project | None:
    """Matches a handwritten note (usually just a first name, e.g.
    "francisco") against every project's customer_name — case-insensitive
    substring, either direction, so "francisco" matches "Francisco C.
    Rodriguez" and a handwritten full name would still match a
    shorter name on file. Returns a project ONLY when exactly one matches:
    zero or several candidates are both treated as "not confident enough"
    rather than guessing, since a wrong guess here means a real client's
    receipt lands in the wrong project's Drive folder."""
    if not handwritten_name or not handwritten_name.strip():
        return None
    needle = handwritten_name.strip().lower()
    projects = db.query(models.Project).all()
    matches = [p for p in projects if needle in p.customer_name.lower() or p.customer_name.lower() in needle]
    return matches[0] if len(matches) == 1 else None


def _describe(vendor: str, description: str) -> str:
    vendor = vendor.strip()
    description = description.strip()
    if vendor and description:
        return f"{vendor} — {description}"
    return vendor or description or "Receipt"


def sync_receipts_from_drive(db: Session) -> schemas.ReceiptSyncResult:
    """Runs one full pass over the Receipts inbox. Raises GoogleNotConnected
    (via google_service's calls) or GeminiNotConfigured immediately — both
    are "nothing in this batch can proceed" conditions, not a per-file
    problem. A single file's extraction failing (blurry photo, not
    actually a receipt) is routine and handled per-file instead: it's
    filed into the inbox's current month subfolder and counted as
    `unreadable`, not raised.

    Commits after EACH file (not once at the end) so that a later file
    failing never loses an earlier file's already-correct Receipt record
    — and so a file that's recorded but whose Drive move then fails still
    shows up as "already processed" on the next sync (its drive_file_id is
    already on a Receipt row) instead of being silently reprocessed."""
    if not gemini_service.any_provider_configured():
        raise gemini_service.GeminiNotConfigured(
            "No AI extraction provider is configured — set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in app/backend/.env."
        )
    if not g_oauth.get_connection(db):
        raise g_oauth.GoogleNotConnected("Connect Google Workspace first.")

    inbox_id = google_service.get_or_create_receipts_root(db)
    images = google_service.list_receipt_images(db, inbox_id)

    matched_count = 0
    filed_business_count = 0
    unreadable_count = 0
    already_count = 0
    matched_names: list[str] = []

    for image in images:
        file_id = image["id"]
        already = db.query(models.Receipt.id).filter(models.Receipt.drive_file_id == file_id).first()
        if already:
            already_count += 1
            continue

        try:
            file_bytes = google_service.download_file(db, file_id)
            content_type = image.get("mimeType") or "image/jpeg"
            result = gemini_service.extract_receipt_from_image(file_bytes, image.get("name", file_id), content_type)
        except gemini_service.GeminiExtractionError as exc:
            logger.info("Receipt %s unreadable: %s", file_id, exc)
            unreadable_count += 1
            try:
                month_folder = google_service.get_or_create_month_subfolder(db, inbox_id, dt.date.today())
                google_service.move_file(db, file_id, month_folder, inbox_id)
            except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as move_exc:
                logger.error("Couldn't file unreadable receipt %s out of the inbox: %s", file_id, move_exc)
            continue

        project = _match_project(db, result.handwritten_name)
        receipt_date = result.date or dt.date.today()
        description = _describe(result.vendor, result.description)

        receipt = models.Receipt(
            project_id=project.id if project else None,
            date=receipt_date,
            description=description,
            amount=result.amount,
            type="expense",
            needs_project=project is None,
            source="drive_folder",
            drive_file_id=file_id,
        )
        db.add(receipt)
        db.commit()

        if project:
            matched_count += 1
            matched_names.append(project.customer_name)
        else:
            filed_business_count += 1

        # Best-effort: the Receipt record above is already correct and
        # committed either way — a failed move here just leaves the file
        # sitting in the inbox (annoying, not incorrect), and it won't be
        # rescanned since its drive_file_id is already on a Receipt row.
        try:
            if project and project.drive_folder_id:
                target = google_service.get_or_create_project_receipts_folder(db, project.drive_folder_id)
                google_service.move_file(db, file_id, target, inbox_id)
            elif not project:
                target = google_service.get_or_create_month_subfolder(db, inbox_id, receipt_date)
                google_service.move_file(db, file_id, target, inbox_id)
        except (g_oauth.GoogleNotConnected, google_service.GoogleApiError) as exc:
            logger.error("Receipt %s recorded but couldn't be filed in Drive: %s", file_id, exc)

    return schemas.ReceiptSyncResult(
        scanned=len(images),
        matched_to_project=matched_count,
        filed_as_business_expense=filed_business_count,
        unreadable=unreadable_count,
        already_processed=already_count,
        matched_project_names=matched_names,
    )
