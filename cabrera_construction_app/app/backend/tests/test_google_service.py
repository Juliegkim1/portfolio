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
