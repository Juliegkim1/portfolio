"""Real Google Drive + Sheets calls (read/write — this one does make real
writes, unlike the QuickBooks integration, since creating folders/files is
the whole point and isn't a risk to Cabrera's live accounting data the way
invoice/payment writes to QuickBooks would be).

Folder layout matches CLAUDE.md / README: a top-level "Projects" folder
(found-or-created once, then cached), with one subfolder per project named
"{Customer} – {Street}".
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from sqlalchemy.orm import Session

from . import google_oauth as g_oauth

logger = logging.getLogger("cabrera.google")

DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"
FOLDER_MIME = "application/vnd.google-apps.folder"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# A native Google Sheet (created in Sheets, not an uploaded .xlsx) has this
# mimeType and typically no file extension in its name at all — it has no
# bytes of its own to download via `alt=media` (Drive returns 403 for native
# Google Workspace files); it has to be rendered via the /export endpoint
# instead. See export_file below.
SHEET_MIME = "application/vnd.google-apps.spreadsheet"


class GoogleApiError(Exception):
    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _extract_error_message(resp: httpx.Response) -> str:
    try:
        return resp.json().get("error", {}).get("message", resp.text[:300])
    except ValueError:
        return resp.text[:300] or f"Google API returned {resp.status_code}"


def _request(db: Session, method: str, url: str, **kwargs) -> httpx.Response:
    access_token = g_oauth.get_valid_access_token(db)
    headers = {"Authorization": f"Bearer {access_token}", **kwargs.pop("headers", {})}
    resp = httpx.request(method, url, headers=headers, timeout=30, **kwargs)

    if resp.status_code == 401:
        logger.error("Google 401 on %s %s", method, url)
        raise g_oauth.GoogleNotConnected("Google rejected the access token. Reconnect Google Workspace and try again.")
    if resp.status_code >= 400:
        message = _extract_error_message(resp)
        logger.error("Google API error on %s %s status=%s message=%s", method, url, resp.status_code, message)
        raise GoogleApiError(message, status_code=resp.status_code)

    logger.info("Google %s %s status=%s", method, url, resp.status_code)
    return resp


def _get_or_create_projects_root(db: Session) -> str:
    conn = g_oauth.get_connection(db)
    if conn and conn.projects_root_folder_id:
        return conn.projects_root_folder_id

    # Scoped to 'root' in parents (a direct child of My Drive) — without it,
    # this matches ANY folder named "Projects" anywhere in the account, not
    # just the intended top-level one (see get_or_create_receipts_root below
    # for the real-world bug this exact pattern caused).
    query = f"'root' in parents and name = 'Projects' and mimeType = '{FOLDER_MIME}' and trashed = false"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name)"})
    matches = resp.json().get("files", [])

    if matches:
        folder_id = matches[0]["id"]
    else:
        create_resp = _request(db, "POST", f"{DRIVE_API}/files", json={"name": "Projects", "mimeType": FOLDER_MIME})
        folder_id = create_resp.json()["id"]

    conn = g_oauth.get_connection(db)
    if conn:
        conn.projects_root_folder_id = folder_id
        db.commit()
    return folder_id


RECEIPTS_ROOT_NAME = "Receipts"
_RECEIPT_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".heic", ".webp")


def get_or_create_receipts_root(db: Session) -> str:
    """Sibling of Projects (_get_or_create_projects_root above), directly
    under My Drive — not a subfolder of Projects. This is where the owner
    drops phone photos of paper receipts; see services/receipt_sync.py for
    what scans it.

    'root' in parents matters here more than it might look: every project
    that's had a matched receipt filed gets its OWN subfolder also named
    "Receipts" (get_or_create_project_receipts_folder below). An unscoped
    name match can return one of those instead of the real top-level inbox
    — and since the result is cached on GoogleConnection, a wrong match
    sticks forever, silently scanning the wrong folder (one existing file)
    on every future sync instead of the real inbox (this actually happened
    in production — see main.py's _run_light_migrations for the one-time
    cache reset that self-heals an already-wrong cached value)."""
    conn = g_oauth.get_connection(db)
    if conn and conn.receipts_root_folder_id:
        return conn.receipts_root_folder_id

    query = f"'root' in parents and name = '{RECEIPTS_ROOT_NAME}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name)"})
    matches = resp.json().get("files", [])

    if matches:
        folder_id = matches[0]["id"]
    else:
        create_resp = _request(db, "POST", f"{DRIVE_API}/files", json={"name": RECEIPTS_ROOT_NAME, "mimeType": FOLDER_MIME})
        folder_id = create_resp.json()["id"]

    conn = g_oauth.get_connection(db)
    if conn:
        conn.receipts_root_folder_id = folder_id
        db.commit()
    return folder_id


def _is_image_file(f: dict) -> bool:
    """Drive's own query-side mimeType filtering below is a soft
    narrowing, not a guarantee -- in production it let a folder and a PDF
    through a query that should only have matched images, so every
    caller re-checks here rather than trusting the query alone."""
    mime = (f.get("mimeType") or "").lower()
    if mime == FOLDER_MIME:
        return False
    if mime.startswith("image/"):
        return True
    return f.get("name", "").lower().endswith(tuple(_RECEIPT_IMAGE_EXTENSIONS))


def list_receipt_images(db: Session, folder_id: str) -> list[dict]:
    """Image files directly inside a folder (not subfolders) — the "new
    receipts to process" set for receipt_sync.py. Deliberately shallow
    (not recursive): once a receipt's been filed into a month subfolder or
    a project's own Receipts subfolder, it's no longer "new" and shouldn't
    be rescanned just because it's still somewhere under the Receipts
    root."""
    mime_clause = " or ".join(f"name contains '{ext}'" for ext in _RECEIPT_IMAGE_EXTENSIONS)
    query = f"'{folder_id}' in parents and trashed = false and (mimeType contains 'image/' or ({mime_clause}))"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name,mimeType)", "pageSize": 100})
    return [f for f in resp.json().get("files", []) if _is_image_file(f)]


def move_file(db: Session, file_id: str, new_parent_id: str, old_parent_id: str) -> None:
    """Re-parents a file — same addParents/removeParents PATCH create_sheet
    already uses to relocate a newly-created Sheet, generalized to move any
    existing file. Drive files can have multiple parents in principle, but
    every file this app creates or scans has exactly one, so this is a
    clean cut-and-paste, not an additional share."""
    _request(db, "PATCH", f"{DRIVE_API}/files/{file_id}", params={"addParents": new_parent_id, "removeParents": old_parent_id, "fields": "id,parents"})


def get_or_create_month_subfolder(db: Session, parent_id: str, for_date) -> str:
    """{parent_id}/YYYY-MM — where an unmatched receipt (no readable
    handwritten name, or one that didn't match any project) gets filed
    within the Receipts inbox, so the inbox itself stays short even as
    unmatched business-expense receipts accumulate month over month."""
    return _find_or_create_subfolder(db, parent_id, for_date.strftime("%Y-%m"))


def get_or_create_project_receipts_folder(db: Session, project_drive_folder_id: str) -> str:
    """{project folder}/Receipts — where a receipt confidently matched to a
    project gets moved, alongside whatever else lives in that project's
    own Drive folder."""
    return _find_or_create_subfolder(db, project_drive_folder_id, "Receipts")


def _escape_query_literal(value: str) -> str:
    """Drive API query strings are single-quoted; a literal apostrophe in a
    customer name (e.g. "O'Brien") needs escaping or it breaks the query
    syntax entirely (and worse, since this goes straight into a query
    string, unescaped user-derived text here would be a query-injection
    vector — same reasoning as parameterizing SQL)."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _find_subfolder(db: Session, parent_id: str, name: str) -> str | None:
    query = f"'{parent_id}' in parents and name = '{_escape_query_literal(name)}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name)"})
    matches = resp.json().get("files", [])
    return matches[0]["id"] if matches else None


def _find_or_create_subfolder(db: Session, parent_id: str, name: str) -> str:
    existing = _find_subfolder(db, parent_id, name)
    if existing:
        return existing
    create_resp = _request(db, "POST", f"{DRIVE_API}/files", json={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]})
    return create_resp.json()["id"]


def create_project_folder(db: Session, customer_name: str, street: str, project_type: str) -> str:
    """Projects/{Customer} – {Street}/{Project Type} — one customer/address
    can have more than one project over time (e.g. a kitchen remodel, later
    a separate bathroom job), so the project-specific folder is a subfolder
    of a shared customer+address folder, not a folder of its own directly
    under Projects. Both levels are found-or-created, so creating a second
    project at an existing address reuses that address's folder rather than
    making a sibling with a near-duplicate name."""
    projects_root = _get_or_create_projects_root(db)
    address_name = f"{customer_name} – {street}" if street else customer_name
    address_folder_id = _find_or_create_subfolder(db, projects_root, address_name)
    return _find_or_create_subfolder(db, address_folder_id, project_type)


def find_existing_customer_folder(db: Session, customer_name: str, street: str) -> dict | None:
    """Read-only check (no creation) used to warn the user before creating a
    project: if a Drive folder for this customer+address already exists,
    the new project will land as a sibling subfolder next to whatever
    project types are already there, not get a folder of its own. Returns
    None when no such folder exists yet (the common case — a brand-new
    customer)."""
    projects_root = _get_or_create_projects_root(db)
    address_name = f"{customer_name} – {street}" if street else customer_name
    folder_id = _find_subfolder(db, projects_root, address_name)
    if not folder_id:
        return None
    existing_project_types = [f["name"] for f in _list_subfolders(db, folder_id)]
    return {"folder_id": folder_id, "existing_project_types": existing_project_types}


def create_sheet(db: Session, name: str, parent_folder_id: str | None = None) -> str:
    resp = _request(db, "POST", f"{SHEETS_API}/spreadsheets", json={"properties": {"title": name}})
    sheet_id = resp.json()["spreadsheetId"]
    if parent_folder_id:
        # Sheets created via the Sheets API land in "My Drive" root by default —
        # move it into the project folder explicitly.
        _request(db, "PATCH", f"{DRIVE_API}/files/{sheet_id}", params={"addParents": parent_folder_id, "removeParents": "root", "fields": "id,parents"})
    return sheet_id


_IMPORTABLE_EXTENSIONS = (".pdf", ".docx", ".xlsx")


def _list_subfolders(db: Session, parent_id: str) -> list[dict]:
    query = f"'{parent_id}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name)", "pageSize": 100})
    return resp.json().get("files", [])


def list_importable_project_folders(db: Session, exclude_folder_ids: set[str]) -> list[dict]:
    """Candidates for importing a pre-existing Drive project into the app —
    i.e. folders under "Projects" not already linked to a project record.

    Two shapes both need to be recognized: new-style "{Customer} – {Street}/
    {Project Type}" subfolders (see create_project_folder), and old, flat
    "{Customer} – {Street}" folders from before this app existed at all,
    which hold documents directly with no project-type subfolder. A
    customer/address folder that already has project-type subfolders is
    itself never a candidate — only its subfolders are — since by
    definition it's not a single project."""
    projects_root = _get_or_create_projects_root(db)
    address_folders = _list_subfolders(db, projects_root)

    candidates: list[dict] = []
    for address_folder in address_folders:
        subfolders = _list_subfolders(db, address_folder["id"])
        if subfolders:
            for sub in subfolders:
                if sub["id"] not in exclude_folder_ids:
                    candidates.append({"id": sub["id"], "name": f"{address_folder['name']} › {sub['name']}"})
        elif address_folder["id"] not in exclude_folder_ids:
            candidates.append(address_folder)
    return candidates


def list_folder_documents(db: Session, folder_id: str) -> list[dict]:
    """PDF/DOCX files, plus native Google Sheets, directly inside a folder —
    the ones extraction can actually read. Ignores subfolders, images, etc.

    A native Google Sheet (e.g. a Scope & Payment Schedule someone built
    directly in Sheets rather than uploading a .pdf/.xlsx) usually has no
    file extension in its name at all, so the extension check below would
    silently skip it — matched by mimeType instead. It still needs
    export_file (not download_file) to actually read its bytes."""
    query = f"'{folder_id}' in parents and trashed = false"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name,mimeType)", "pageSize": 50})
    files = resp.json().get("files", [])
    return [f for f in files if f.get("name", "").lower().endswith(_IMPORTABLE_EXTENSIONS) or f.get("mimeType") == SHEET_MIME]


def get_file_name(db: Session, file_id: str) -> str:
    resp = _request(db, "GET", f"{DRIVE_API}/files/{file_id}", params={"fields": "name"})
    return resp.json().get("name", file_id)


def get_file_mime_type(db: Session, file_id: str) -> str:
    resp = _request(db, "GET", f"{DRIVE_API}/files/{file_id}", params={"fields": "mimeType"})
    return resp.json().get("mimeType") or "application/octet-stream"


def get_file_parents(db: Session, file_id: str) -> list[str]:
    """A file's current parent folder ID(s) — needed before move_file can
    remove them, for a file whose location isn't already known (e.g. one
    picked from anywhere in Drive via the receipt picker, as opposed to
    one found by scanning a specific folder, where the parent is already
    the folder just scanned)."""
    resp = _request(db, "GET", f"{DRIVE_API}/files/{file_id}", params={"fields": "parents"})
    return resp.json().get("parents") or []


def search_images(db: Session, search: str | None = None, limit: int = 20) -> list[dict]:
    """Image files anywhere in the connected Drive account, with thumbnails
    — the "pick a receipt photo from Google Drive" route on Business
    Expenses, for a receipt the automatic Receipts-inbox scan hasn't
    caught (filed somewhere else, synced to an unexpected folder, etc.).
    Not scoped to any one folder, mirroring search_documents' same
    "anywhere in the account" reach for picking an estimate document."""
    mime_clause = " or ".join(f"name contains '{ext}'" for ext in _RECEIPT_IMAGE_EXTENSIONS)
    query = f"trashed = false and (mimeType contains 'image/' or ({mime_clause}))"
    if search and search.strip():
        query += f" and name contains '{_escape_query_literal(search.strip())}'"
    resp = _request(
        db,
        "GET",
        f"{DRIVE_API}/files",
        # Over-fetches relative to `limit` since the post-filter below can
        # drop some of what Drive's own query-side filtering let through.
        params={"q": query, "fields": "files(id,name,mimeType,modifiedTime)", "orderBy": "modifiedTime desc", "pageSize": max(limit * 4, 100)},
    )
    files = [f for f in resp.json().get("files", []) if _is_image_file(f)]
    return files[:limit]


def download_file(db: Session, file_id: str) -> bytes:
    resp = _request(db, "GET", f"{DRIVE_API}/files/{file_id}", params={"alt": "media"})
    return resp.content


def export_file(db: Session, file_id: str, export_mime_type: str = "application/pdf") -> bytes:
    """Renders a native Google Workspace file (Sheet, Doc, Slides — no bytes
    of its own) via Drive's /export endpoint. download_file's `alt=media`
    doesn't work on these; Drive returns 403. Exporting a Sheet to PDF
    (rather than e.g. CSV) preserves its layout — merged cells, section
    headers — which matters for a formatted Scope & Payment Schedule, and
    lets the result reuse Gemini's existing PDF document-understanding path
    with no separate parsing."""
    resp = _request(db, "GET", f"{DRIVE_API}/files/{file_id}/export", params={"mimeType": export_mime_type})
    return resp.content


def upload_file(db: Session, name: str, content: bytes, mime_type: str, parent_folder_id: str) -> str:
    """Multipart upload — the simplest reliable way to create a Drive file
    with content in one call (vs. Drive's resumable-upload protocol, which
    isn't worth the complexity for documents this size)."""
    metadata = {"name": name, "parents": [parent_folder_id]}
    files = {
        "metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"),
        "file": (name, content, mime_type),
    }
    resp = _request(db, "POST", f"{DRIVE_UPLOAD_API}/files", params={"uploadType": "multipart"}, files=files)
    return resp.json()["id"]


def search_documents(db: Session, search: str | None = None, limit: int = 20) -> list[dict]:
    """PDF/DOCX files anywhere in the connected account's Drive (not scoped
    to the Projects folder) — the "choose from Google Drive" route on the
    Estimate Upload screen, for picking an estimate/job-notes document that
    lives elsewhere in Drive rather than requiring a local download first.
    `search` filters by filename (Drive's `contains` operator); omitted,
    returns the most recently modified matching files."""
    mime_clause = f"(mimeType = '{DOCX_MIME}' or mimeType = '{XLSX_MIME}' or mimeType = 'application/pdf')"
    query = f"{mime_clause} and trashed = false"
    if search and search.strip():
        query += f" and name contains '{_escape_query_literal(search.strip())}'"
    resp = _request(
        db,
        "GET",
        f"{DRIVE_API}/files",
        params={"q": query, "fields": "files(id,name,mimeType,modifiedTime)", "orderBy": "modifiedTime desc", "pageSize": limit},
    )
    return resp.json().get("files", [])


_DRIVE_FOLDER_LINK_PATTERNS = (re.compile(r"/folders/([a-zA-Z0-9_-]+)"), re.compile(r"[?&]id=([a-zA-Z0-9_-]+)"))


def extract_drive_folder_id(link_or_id: str) -> str:
    """Accepts a pasted Drive folder URL in any of its common shapes, or a
    bare folder ID — shared by every "manually point this at a real Drive
    folder" field in the app (a project's drive-folder override, and the
    Receipts inbox override), since automatic folder discovery by NAME
    (see get_or_create_receipts_root) can genuinely fail to find the
    right one — a name collision, or a folder shared from a different
    Google identity than the one connected here, so it never shows up
    under this account's own 'root' in parents."""
    trimmed = link_or_id.strip()
    for pattern in _DRIVE_FOLDER_LINK_PATTERNS:
        if m := pattern.search(trimmed):
            return m.group(1)
    return trimmed
