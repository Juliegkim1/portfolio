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

import httpx
from sqlalchemy.orm import Session

from . import google_oauth as g_oauth

logger = logging.getLogger("cabrera.google")

DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"
FOLDER_MIME = "application/vnd.google-apps.folder"


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

    query = f"name = 'Projects' and mimeType = '{FOLDER_MIME}' and trashed = false"
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


def _escape_query_literal(value: str) -> str:
    """Drive API query strings are single-quoted; a literal apostrophe in a
    customer name (e.g. "O'Brien") needs escaping or it breaks the query
    syntax entirely (and worse, since this goes straight into a query
    string, unescaped user-derived text here would be a query-injection
    vector — same reasoning as parameterizing SQL)."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _find_or_create_subfolder(db: Session, parent_id: str, name: str) -> str:
    query = f"'{parent_id}' in parents and name = '{_escape_query_literal(name)}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name)"})
    matches = resp.json().get("files", [])
    if matches:
        return matches[0]["id"]
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


def create_sheet(db: Session, name: str, parent_folder_id: str | None = None) -> str:
    resp = _request(db, "POST", f"{SHEETS_API}/spreadsheets", json={"properties": {"title": name}})
    sheet_id = resp.json()["spreadsheetId"]
    if parent_folder_id:
        # Sheets created via the Sheets API land in "My Drive" root by default —
        # move it into the project folder explicitly.
        _request(db, "PATCH", f"{DRIVE_API}/files/{sheet_id}", params={"addParents": parent_folder_id, "removeParents": "root", "fields": "id,parents"})
    return sheet_id


_IMPORTABLE_EXTENSIONS = (".pdf", ".docx")


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
    """PDF/DOCX files directly inside a folder — the ones extraction can
    actually read. Ignores subfolders, images, spreadsheets, etc."""
    query = f"'{folder_id}' in parents and trashed = false"
    resp = _request(db, "GET", f"{DRIVE_API}/files", params={"q": query, "fields": "files(id,name,mimeType)", "pageSize": 50})
    files = resp.json().get("files", [])
    return [f for f in files if f.get("name", "").lower().endswith(_IMPORTABLE_EXTENSIONS)]


def get_file_name(db: Session, file_id: str) -> str:
    resp = _request(db, "GET", f"{DRIVE_API}/files/{file_id}", params={"fields": "name"})
    return resp.json().get("name", file_id)


def download_file(db: Session, file_id: str) -> bytes:
    resp = _request(db, "GET", f"{DRIVE_API}/files/{file_id}", params={"alt": "media"})
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
