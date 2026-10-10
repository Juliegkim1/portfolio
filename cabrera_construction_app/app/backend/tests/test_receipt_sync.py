"""receipt_sync.py — scans My Drive/Receipts, reads each new photo,
matches any handwritten customer name against existing projects, and
files + records the result. Every Drive call and every AI call is mocked
throughout this suite — it never makes a real network request and never
needs a real Google connection, matching the pattern already used for
the AI extraction fallback chain and the combine-notes tests."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock

from app import models
from app.schemas import ReceiptExtractionResult
from app.services import gemini_service, google_service, receipt_sync
from app.services import google_oauth as g_oauth
from tests.factories import make_project


def _stub_connected(monkeypatch):
    """Google "connected" check only looks at whether get_connection
    returns truthy — a plain non-None stand-in is enough, since every
    actual Drive call this suite exercises is itself mocked separately."""
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: SimpleNamespace(id=1))


def _stub_provider_configured(monkeypatch):
    monkeypatch.setattr(gemini_service, "any_provider_configured", lambda: True)


# --- _match_project -----------------------------------------------------------


def test_match_project_first_name_substring(db):
    make_project(db, customer_name="Francisco C. Rodriguez")
    db.commit()

    project = receipt_sync._match_project(db, "francisco")
    assert project is not None
    assert project.customer_name == "Francisco C. Rodriguez"


def test_match_project_no_handwriting_returns_none(db):
    make_project(db, customer_name="Francisco C. Rodriguez")
    db.commit()

    assert receipt_sync._match_project(db, None) is None
    assert receipt_sync._match_project(db, "   ") is None


def test_match_project_ambiguous_multiple_matches_returns_none(db):
    make_project(db, customer_name="Francisco Rodriguez", property_address="1 A St, SF, CA 94100")
    make_project(db, customer_name="Maria Francisco", property_address="2 B St, SF, CA 94100")
    db.commit()

    assert receipt_sync._match_project(db, "francisco") is None


def test_match_project_no_match_returns_none(db):
    make_project(db, customer_name="Jane Doe")
    db.commit()

    assert receipt_sync._match_project(db, "nonexistent name") is None


def test_match_project_falls_back_to_written_address_when_no_name(db):
    """A materials yard (e.g. Golden State Lumber) commonly writes the
    job-site address on a delivery slip instead of a customer name."""
    project = make_project(db, customer_name="Elena Ortiz", property_address="116 Mountain Road, Reno, NV 89501")
    db.commit()

    matched = receipt_sync._match_project(db, None, "116 Mountain Road")
    assert matched is not None
    assert matched.id == project.id


def test_match_project_address_off_by_one_digit_does_not_match(db):
    """Deliberately NOT fuzzy/tolerant of a wrong digit -- a store clerk's
    typo (115 written on the receipt, 116 is the real address) must not
    silently resolve to a guess; the receipt stays unmatched for the
    owner to notice and correct by hand."""
    make_project(db, customer_name="Elena Ortiz", property_address="116 Mountain Road, Reno, NV 89501")
    db.commit()

    assert receipt_sync._match_project(db, None, "115 Mountain Road") is None


def test_match_project_prefers_name_over_address_when_both_present(db):
    name_match = make_project(db, customer_name="Francisco Rodriguez", property_address="1 A St, SF, CA 94100")
    make_project(db, customer_name="Someone Else", property_address="2 B St, SF, CA 94100")
    db.commit()

    matched = receipt_sync._match_project(db, "francisco", "2 B St")
    assert matched is not None
    assert matched.id == name_match.id


# --- _describe -----------------------------------------------------------


def test_describe_omits_address_when_not_passed():
    assert receipt_sync._describe("Golden State Lumber", "Lumber delivery") == "Golden State Lumber — Lumber delivery"


def test_describe_includes_written_address_so_owner_can_spot_a_typo():
    described = receipt_sync._describe("Golden State Lumber", "Lumber delivery", "115 Mountain Road")
    assert described == "Golden State Lumber — Lumber delivery (115 Mountain Road)"


# --- sync_receipts_from_drive --------------------------------------------------


def test_sync_raises_when_google_not_connected(db, monkeypatch):
    _stub_provider_configured(monkeypatch)
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: None)

    try:
        receipt_sync.sync_receipts_from_drive(db)
        assert False, "expected GoogleNotConnected"
    except g_oauth.GoogleNotConnected:
        pass


def test_sync_raises_when_no_ai_provider_configured(db, monkeypatch):
    _stub_connected(monkeypatch)
    monkeypatch.setattr(gemini_service, "any_provider_configured", lambda: False)

    try:
        receipt_sync.sync_receipts_from_drive(db)
        assert False, "expected GeminiNotConfigured"
    except gemini_service.GeminiNotConfigured:
        pass


def test_sync_matches_receipt_to_project_moves_file_and_records_expense(db, monkeypatch):
    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)
    project = make_project(db, customer_name="Francisco C. Rodriguez", drive_folder_id="project-folder-1")
    db.commit()

    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [{"id": "file-1", "name": "receipt.jpg", "mimeType": "image/jpeg"}])
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-bytes")
    monkeypatch.setattr(
        gemini_service,
        "extract_receipt_from_image",
        lambda *a, **k: ReceiptExtractionResult(found=True, vendor="Sherwin-Williams", date=dt.date(2026, 9, 16), amount=383.73, description="Paint and supplies", handwritten_name="francisco"),
    )
    move_calls = []
    monkeypatch.setattr(google_service, "get_or_create_project_receipts_folder", lambda db, folder_id: "project-receipts-folder")
    monkeypatch.setattr(google_service, "move_file", lambda db, file_id, new_parent, old_parent: move_calls.append((file_id, new_parent, old_parent)))

    result = receipt_sync.sync_receipts_from_drive(db)

    assert result.scanned == 1
    assert result.matched_to_project == 1
    assert result.filed_as_business_expense == 0
    assert result.matched_project_names == ["Francisco C. Rodriguez"]
    assert move_calls == [("file-1", "project-receipts-folder", "inbox-id")]

    receipt = db.query(models.Receipt).filter(models.Receipt.drive_file_id == "file-1").one()
    assert receipt.project_id == project.id
    assert receipt.needs_project is False
    assert receipt.source == "drive_folder"
    assert float(receipt.amount) == 383.73
    assert receipt.description == "Sherwin-Williams — Paint and supplies"
    assert receipt.date == dt.date(2026, 9, 16)


def test_sync_files_unmatched_receipt_as_business_expense_by_month(db, monkeypatch):
    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)
    make_project(db, customer_name="Jane Doe")  # no project named in the handwriting
    db.commit()

    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [{"id": "file-2", "name": "receipt2.jpg", "mimeType": "image/jpeg"}])
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-bytes")
    monkeypatch.setattr(
        gemini_service,
        "extract_receipt_from_image",
        lambda *a, **k: ReceiptExtractionResult(found=True, vendor="Home Depot", date=dt.date(2026, 8, 5), amount=84.50, description="Lumber", handwritten_name=None),
    )
    move_calls = []
    monkeypatch.setattr(google_service, "get_or_create_month_subfolder", lambda db, parent_id, for_date: f"month-{for_date.isoformat()}")
    monkeypatch.setattr(google_service, "move_file", lambda db, file_id, new_parent, old_parent: move_calls.append((file_id, new_parent, old_parent)))

    result = receipt_sync.sync_receipts_from_drive(db)

    assert result.matched_to_project == 0
    assert result.filed_as_business_expense == 1
    assert move_calls == [("file-2", "month-2026-08-05", "inbox-id")]

    receipt = db.query(models.Receipt).filter(models.Receipt.drive_file_id == "file-2").one()
    assert receipt.project_id is None
    assert receipt.needs_project is True


def test_sync_skips_already_processed_files(db, monkeypatch):
    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)
    existing = models.Receipt(date=dt.date(2026, 1, 1), description="Already filed", amount=10, type="expense", source="drive_folder", drive_file_id="file-3")
    db.add(existing)
    db.commit()

    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [{"id": "file-3", "name": "receipt3.jpg", "mimeType": "image/jpeg"}])
    extract_calls = []
    monkeypatch.setattr(gemini_service, "extract_receipt_from_image", lambda *a, **k: extract_calls.append(1))

    result = receipt_sync.sync_receipts_from_drive(db)

    assert result.already_processed == 1
    assert result.scanned == 1
    assert extract_calls == []  # never even downloaded/extracted a file already on record


def test_sync_counts_unreadable_receipt_and_files_it_by_current_month(db, monkeypatch):
    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)

    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [{"id": "file-4", "name": "blurry.jpg", "mimeType": "image/jpeg"}])
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-bytes")

    def _raise(*a, **k):
        raise gemini_service.GeminiExtractionError("Couldn't read this as a receipt.")

    monkeypatch.setattr(gemini_service, "extract_receipt_from_image", _raise)
    move_calls = []
    monkeypatch.setattr(google_service, "get_or_create_month_subfolder", lambda db, parent_id, for_date: "month-folder")
    monkeypatch.setattr(google_service, "move_file", lambda db, file_id, new_parent, old_parent: move_calls.append((file_id, new_parent, old_parent)))

    result = receipt_sync.sync_receipts_from_drive(db)

    assert result.unreadable == 1
    assert result.matched_to_project == 0
    assert result.filed_as_business_expense == 0
    assert move_calls == [("file-4", "month-folder", "inbox-id")]
    # No Receipt record for a file that couldn't be read at all -- nothing usable to show.
    assert db.query(models.Receipt).filter(models.Receipt.drive_file_id == "file-4").first() is None


def test_sync_matched_project_without_drive_folder_still_records_receipt(db, monkeypatch):
    """A project created before Google was ever connected (or whose folder
    creation failed) has no drive_folder_id -- the receipt still gets
    correctly recorded against that project even though there's nowhere
    to move the file to."""
    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)
    project = make_project(db, customer_name="Francisco C. Rodriguez", drive_folder_id=None)
    db.commit()

    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [{"id": "file-5", "name": "receipt.jpg", "mimeType": "image/jpeg"}])
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-bytes")
    monkeypatch.setattr(
        gemini_service,
        "extract_receipt_from_image",
        lambda *a, **k: ReceiptExtractionResult(found=True, vendor="Sherwin-Williams", date=dt.date(2026, 9, 16), amount=100, description="Paint", handwritten_name="francisco"),
    )
    move_mock = MagicMock()
    monkeypatch.setattr(google_service, "move_file", move_mock)

    result = receipt_sync.sync_receipts_from_drive(db)

    assert result.matched_to_project == 1
    assert result.matched_not_filed == 1
    move_mock.assert_not_called()
    receipt = db.query(models.Receipt).filter(models.Receipt.drive_file_id == "file-5").one()
    assert receipt.project_id == project.id


def test_sync_counts_matched_not_filed_when_move_fails(db, monkeypatch):
    """A matched project WITH a drive_folder_id, but the move itself fails
    (a transient Drive error) -- still recorded correctly, still counted
    as matched_not_filed so the owner finds out from the sync summary."""
    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)
    project = make_project(db, customer_name="Francisco C. Rodriguez", drive_folder_id="project-folder-1")
    db.commit()

    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [{"id": "file-10", "name": "receipt.jpg", "mimeType": "image/jpeg"}])
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-bytes")
    monkeypatch.setattr(
        gemini_service,
        "extract_receipt_from_image",
        lambda *a, **k: ReceiptExtractionResult(found=True, vendor="Sherwin-Williams", date=dt.date(2026, 9, 16), amount=100, description="Paint", handwritten_name="francisco"),
    )
    monkeypatch.setattr(google_service, "get_or_create_project_receipts_folder", lambda db, folder_id: "project-receipts-folder")

    def _raise_api_error(db, file_id, new_parent, old_parent):
        raise google_service.GoogleApiError("transient failure", status_code=500)

    monkeypatch.setattr(google_service, "move_file", _raise_api_error)

    result = receipt_sync.sync_receipts_from_drive(db)

    assert result.matched_to_project == 1
    assert result.matched_not_filed == 1
    receipt = db.query(models.Receipt).filter(models.Receipt.drive_file_id == "file-10").one()
    assert receipt.project_id == project.id


# --- API endpoint --------------------------------------------------------------


def test_sync_endpoint_returns_409_when_google_not_connected(client, monkeypatch):
    monkeypatch.setattr(gemini_service, "any_provider_configured", lambda: True)
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: None)

    resp = client.post("/api/receipts/sync-from-drive")
    assert resp.status_code == 409


def test_sync_endpoint_returns_400_when_no_provider_configured(client, monkeypatch):
    monkeypatch.setattr(gemini_service, "any_provider_configured", lambda: False)

    resp = client.post("/api/receipts/sync-from-drive")
    assert resp.status_code == 400


def test_sync_endpoint_returns_summary_on_success(client, monkeypatch):
    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)
    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [])

    resp = client.post("/api/receipts/sync-from-drive")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "scanned": 0,
        "matched_to_project": 0,
        "filed_as_business_expense": 0,
        "unreadable": 0,
        "already_processed": 0,
        "matched_project_names": [],
        "matched_not_filed": 0,
    }


def test_matched_receipt_shows_up_in_project_reconciliation(db, client, monkeypatch):
    """Feature 2 (reconciliation): once a synced receipt's project_id is
    set, it must show up on that project's own Reconciliation tab with no
    further wiring -- GET /projects/{id}/reconciliation already includes
    every Receipt on the project relationship (both payment and expense
    types), so this is really a regression test confirming receipt_sync
    setting project_id is sufficient, not a new feature of its own."""
    from tests.factories import make_estimate

    _stub_connected(monkeypatch)
    _stub_provider_configured(monkeypatch)
    project = make_project(db, customer_name="Francisco C. Rodriguez", drive_folder_id="project-folder-1")
    make_estimate(db, project)
    db.commit()

    monkeypatch.setattr(google_service, "get_or_create_receipts_root", lambda db: "inbox-id")
    monkeypatch.setattr(google_service, "list_receipt_images", lambda db, folder_id: [{"id": "file-6", "name": "receipt.jpg", "mimeType": "image/jpeg"}])
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-bytes")
    monkeypatch.setattr(
        gemini_service,
        "extract_receipt_from_image",
        lambda *a, **k: ReceiptExtractionResult(found=True, vendor="Sherwin-Williams", date=dt.date(2026, 9, 16), amount=383.73, description="Paint and supplies", handwritten_name="francisco"),
    )
    monkeypatch.setattr(google_service, "get_or_create_project_receipts_folder", lambda db, folder_id: "project-receipts-folder")
    monkeypatch.setattr(google_service, "move_file", lambda db, file_id, new_parent, old_parent: None)

    sync_resp = client.post("/api/receipts/sync-from-drive")
    assert sync_resp.status_code == 200
    assert sync_resp.json()["matched_to_project"] == 1

    recon_resp = client.get(f"/api/projects/{project.id}/reconciliation")
    assert recon_resp.status_code == 200
    receipts = recon_resp.json()["receipts"]
    assert len(receipts) == 1
    assert receipts[0]["description"] == "Sherwin-Williams — Paint and supplies"
    assert receipts[0]["amount"] == 383.73
    assert receipts[0]["type"] == "expense"
