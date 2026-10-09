"""GET/PATCH /integrations/google/receipts-folder -- lets the owner point
the Receipts inbox at a real Drive folder by hand, for when automatic
discovery by name (get_or_create_receipts_root) can't find the right one:
a name collision with a project's own "Receipts" subfolder, or the real
folder was shared from a different Google identity than the one connected
here, so it never shows up under this account's own Drive root."""

from types import SimpleNamespace

from app.services import google_oauth as g_oauth


def test_get_receipts_folder_returns_409_when_not_connected(client, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: None)

    resp = client.get("/api/integrations/google/receipts-folder")
    assert resp.status_code == 409


def test_get_receipts_folder_reports_auto_when_no_override_set(client, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: SimpleNamespace(receipts_root_folder_id=None))

    resp = client.get("/api/integrations/google/receipts-folder")
    assert resp.status_code == 200
    assert resp.json() == {"folder_id": None, "auto": True}


def test_set_receipts_folder_returns_409_when_not_connected(client, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: None)

    resp = client.patch("/api/integrations/google/receipts-folder", json={"drive_folder_link": "1AbC-xyz"})
    assert resp.status_code == 409


def test_set_receipts_folder_parses_full_drive_url(client, monkeypatch):
    conn = SimpleNamespace(receipts_root_folder_id=None)
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: conn)

    resp = client.patch(
        "/api/integrations/google/receipts-folder",
        json={"drive_folder_link": "https://drive.google.com/drive/folders/1AbC-xyz?usp=sharing"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"folder_id": "1AbC-xyz", "auto": False}
    assert conn.receipts_root_folder_id == "1AbC-xyz"


def test_set_receipts_folder_empty_link_clears_override(client, monkeypatch):
    conn = SimpleNamespace(receipts_root_folder_id="some-old-id")
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: conn)

    resp = client.patch("/api/integrations/google/receipts-folder", json={"drive_folder_link": "  "})
    assert resp.status_code == 200
    assert resp.json() == {"folder_id": None, "auto": True}
    assert conn.receipts_root_folder_id is None
