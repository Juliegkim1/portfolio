"""google_service.py's root-folder lookups ("Projects", "Receipts") must be
scoped to 'root' in parents (a direct child of My Drive) -- without it, the
query matches ANY folder with that name anywhere in the account. This
actually happened in production: every project that's had a matched
receipt filed gets its own subfolder also named "Receipts"
(get_or_create_project_receipts_folder), and the unscoped lookup picked one
of those instead of the real top-level inbox, then cached the wrong folder
forever on GoogleConnection -- so every later sync scanned the wrong
folder's one file instead of the real inbox's several. httpx.request is
mocked throughout; no real network call."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from app.services import google_oauth as g_oauth
from app.services import google_service


def _stub_request_capturing_query(monkeypatch, captured: list[str]):
    monkeypatch.setattr(g_oauth, "get_valid_access_token", lambda db: "fake-token")

    def _fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured.append(kwargs.get("params", {}).get("q", ""))
        return MagicMock(spec=httpx.Response, status_code=200, json=lambda: {"files": []}, headers={})

    monkeypatch.setattr(httpx, "request", _fake_request)


def test_get_or_create_receipts_root_query_is_scoped_to_my_drive_root(db, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: SimpleNamespace(receipts_root_folder_id=None, projects_root_folder_id=None))
    queries: list[str] = []
    _stub_request_capturing_query(monkeypatch, queries)

    # No cached GoogleConnection row to persist the created folder onto, but
    # the lookup query itself is what this test cares about -- it's
    # captured before the create-folder fallback even runs.
    try:
        google_service.get_or_create_receipts_root(db)
    except Exception:
        pass

    assert queries, "expected at least one Drive query"
    assert "'root' in parents" in queries[0]
    assert "name = 'Receipts'" in queries[0]


def test_get_or_create_projects_root_query_is_scoped_to_my_drive_root(db, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: SimpleNamespace(receipts_root_folder_id=None, projects_root_folder_id=None))
    queries: list[str] = []
    _stub_request_capturing_query(monkeypatch, queries)

    try:
        google_service._get_or_create_projects_root(db)
    except Exception:
        pass

    assert queries, "expected at least one Drive query"
    assert "'root' in parents" in queries[0]
    assert "name = 'Projects'" in queries[0]


# --- _is_image_file / post-filtering ---------------------------------------
# Drive's own query-side mimeType filtering is a soft narrowing, not a
# guarantee -- in production, a query built to match only images also
# returned a folder and a PDF. Every caller re-checks the actual mimeType
# (or, failing that, the filename extension) in Python rather than trusting
# the query alone.


def test_is_image_file_accepts_real_image_mime_types():
    assert google_service._is_image_file({"name": "IMG_0001.heic", "mimeType": "image/heic"})
    assert google_service._is_image_file({"name": "receipt.jpg", "mimeType": "image/jpeg"})


def test_is_image_file_rejects_folder():
    assert not google_service._is_image_file({"name": "2026-09", "mimeType": google_service.FOLDER_MIME})


def test_is_image_file_rejects_pdf_and_other_documents():
    assert not google_service._is_image_file({"name": "Contract Package.pdf", "mimeType": "application/pdf"})
    assert not google_service._is_image_file({"name": "Reconciliation", "mimeType": "application/vnd.google-apps.spreadsheet"})


def test_list_receipt_images_filters_out_non_image_results_drive_returned(db, monkeypatch):
    """Reproduces the production bug directly: Drive's query returned a
    month subfolder and a PDF alongside real photos; list_receipt_images
    must not hand either of those to the extraction pipeline."""
    monkeypatch.setattr(g_oauth, "get_valid_access_token", lambda db: "fake-token")
    mixed_results = [
        {"id": "folder-1", "name": "2026-09", "mimeType": google_service.FOLDER_MIME},
        {"id": "pdf-1", "name": "Jan Hofwegen - Contract Package.pdf", "mimeType": "application/pdf"},
        {"id": "img-1", "name": "IMG_0001.heic", "mimeType": "image/heic"},
    ]
    monkeypatch.setattr(httpx, "request", lambda *a, **k: MagicMock(spec=httpx.Response, status_code=200, json=lambda: {"files": mixed_results}, headers={}))

    results = google_service.list_receipt_images(db, "inbox-id")
    assert [r["id"] for r in results] == ["img-1"]


def test_search_images_filters_out_non_image_results_drive_returned(db, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_valid_access_token", lambda db: "fake-token")
    mixed_results = [
        {"id": "folder-1", "name": "2026-10", "mimeType": google_service.FOLDER_MIME},
        {"id": "img-1", "name": "IMG_0002.jpg", "mimeType": "image/jpeg"},
    ]
    monkeypatch.setattr(httpx, "request", lambda *a, **k: MagicMock(spec=httpx.Response, status_code=200, json=lambda: {"files": mixed_results}, headers={}))

    results = google_service.search_images(db)
    assert [r["id"] for r in results] == ["img-1"]


# --- extract_drive_folder_id ------------------------------------------------


def test_extract_drive_folder_id_from_full_url():
    assert google_service.extract_drive_folder_id("https://drive.google.com/drive/folders/1AbC-xyz?usp=sharing") == "1AbC-xyz"


def test_extract_drive_folder_id_from_open_id_url():
    assert google_service.extract_drive_folder_id("https://drive.google.com/open?id=1AbC-xyz") == "1AbC-xyz"


def test_extract_drive_folder_id_from_bare_id():
    assert google_service.extract_drive_folder_id("1AbC-xyz") == "1AbC-xyz"
