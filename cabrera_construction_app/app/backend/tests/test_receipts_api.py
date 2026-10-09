"""DELETE /receipts/{id} — lets a mis-entered receipt (business expense,
project expense, or payment) be removed outright. See
routers/receipts.py's delete_receipt for the cleanup rules: a matched bank
transaction is unlinked, not deleted, and a milestone's paid status is
recomputed from whatever payment receipts remain."""

import datetime as dt
from types import SimpleNamespace

from app import models
from app.schemas import ReceiptExtractionResult
from app.services import gemini_service, google_service
from app.services import google_oauth as g_oauth
from tests.factories import make_estimate, make_project


# --- PATCH /receipts/{id} --------------------------------------------------
# Lets the owner correct a receipt's date/description/amount by hand --
# e.g. AI misread a date, or a vendor name/description came out wrong.


def test_update_receipt_date_description_and_amount(db, client):
    receipt = models.Receipt(date=dt.date(2026, 1, 1), description="Golden State Lumber — Lumber delivery (115 Mountain Road)", amount=200, type="expense", source="drive_folder", drive_file_id="file-1")
    db.add(receipt)
    db.commit()

    resp = client.patch(f"/api/receipts/{receipt.id}", json={"date": "2026-01-05", "description": "Golden State Lumber — Lumber delivery", "amount": 215.40})
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == "2026-01-05"
    assert body["description"] == "Golden State Lumber — Lumber delivery"
    assert body["amount"] == 215.40


def test_update_receipt_partial_only_touches_given_fields(db, client):
    receipt = models.Receipt(date=dt.date(2026, 1, 1), description="Office supplies", amount=50, type="expense", source="manual")
    db.add(receipt)
    db.commit()

    resp = client.patch(f"/api/receipts/{receipt.id}", json={"amount": 75})
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount"] == 75
    assert body["date"] == "2026-01-01"
    assert body["description"] == "Office supplies"


def test_update_receipt_404_for_missing_receipt(client):
    resp = client.patch("/api/receipts/999999", json={"amount": 10})
    assert resp.status_code == 404


def test_update_payment_amount_recomputes_milestone_status(db, client):
    project = make_project(db)
    scope_schedule = models.ScopeSchedule(project_id=project.id, contract_type="Fixed-Price Agreement")
    db.add(scope_schedule)
    db.flush()
    milestone = models.Milestone(scope_schedule_id=scope_schedule.id, number=0, title="Deposit", amount=1000)
    db.add(milestone)
    db.commit()

    create_resp = client.post(
        "/api/receipts",
        json={"project_id": project.id, "milestone_id": milestone.id, "date": "2026-01-01", "description": "Partial deposit", "amount": 400, "type": "payment"},
    )
    receipt_id = create_resp.json()["id"]
    db.refresh(milestone)
    assert milestone.status == "partial"

    resp = client.patch(f"/api/receipts/{receipt_id}", json={"amount": 1000})
    assert resp.status_code == 200

    db.expire_all()
    updated_milestone = db.get(models.Milestone, milestone.id)
    assert updated_milestone.status == "paid"


def test_delete_business_expense_receipt(db, client):
    receipt = models.Receipt(date=dt.date(2026, 1, 1), description="Office supplies", amount=50, type="expense", source="manual")
    db.add(receipt)
    db.commit()
    receipt_id = receipt.id

    resp = client.delete(f"/api/receipts/{receipt_id}")
    assert resp.status_code == 204
    assert db.get(models.Receipt, receipt_id) is None


def test_delete_404_for_missing_receipt(client):
    resp = client.delete("/api/receipts/999999")
    assert resp.status_code == 404


def test_delete_unlinks_matched_bank_transaction_instead_of_deleting_it(db, client):
    project = make_project(db)
    db.commit()
    receipt = models.Receipt(project_id=project.id, date=dt.date(2026, 1, 1), description="Home Depot", amount=100, type="expense", source="manual")
    db.add(receipt)
    db.flush()
    txn = models.BankTransaction(
        import_id="batch-1",
        posted_date=dt.date(2026, 1, 1),
        description="HOME DEPOT #42",
        amount=-100,
        receipt_id=receipt.id,
        match_status="matched",
        fingerprint="2026-01-01|100.00|home depot #42",
    )
    db.add(txn)
    db.commit()
    receipt_id, txn_id = receipt.id, txn.id

    resp = client.delete(f"/api/receipts/{receipt_id}")
    assert resp.status_code == 204

    db.expire_all()
    surviving_txn = db.get(models.BankTransaction, txn_id)
    assert surviving_txn is not None  # the transaction itself is never deleted
    assert surviving_txn.receipt_id is None
    assert surviving_txn.match_status == "unmatched"


def _make_milestone(db, project, amount=1000):
    scope_schedule = models.ScopeSchedule(project_id=project.id, contract_type="Fixed-Price Agreement")
    db.add(scope_schedule)
    db.flush()
    milestone = models.Milestone(scope_schedule_id=scope_schedule.id, number=0, title="Deposit", amount=amount)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


def test_delete_payment_receipt_reverts_milestone_from_paid_to_scheduled(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    db.commit()
    milestone = _make_milestone(db, project, amount=1000)

    create_resp = client.post(
        "/api/receipts",
        json={"project_id": project.id, "milestone_id": milestone.id, "date": "2026-01-01", "description": "Deposit payment", "amount": 1000, "type": "payment"},
    )
    assert create_resp.status_code == 200
    receipt_id = create_resp.json()["id"]

    db.refresh(milestone)
    assert milestone.status == "paid"

    resp = client.delete(f"/api/receipts/{receipt_id}")
    assert resp.status_code == 204

    db.expire_all()
    reverted = db.get(models.Milestone, milestone.id)
    assert reverted.status == "scheduled"


def test_delete_one_of_two_payments_reverts_milestone_to_partial(db, client):
    project = make_project(db)
    make_estimate(db, project)
    db.commit()
    milestone = _make_milestone(db, project, amount=1000)

    r1 = client.post(
        "/api/receipts",
        json={"project_id": project.id, "milestone_id": milestone.id, "date": "2026-01-01", "description": "Partial payment 1", "amount": 400, "type": "payment"},
    ).json()
    client.post(
        "/api/receipts",
        json={"project_id": project.id, "milestone_id": milestone.id, "date": "2026-01-15", "description": "Partial payment 2", "amount": 600, "type": "payment"},
    )
    db.refresh(milestone)
    assert milestone.status == "paid"

    resp = client.delete(f"/api/receipts/{r1['id']}")
    assert resp.status_code == 204

    db.expire_all()
    reverted = db.get(models.Milestone, milestone.id)
    assert reverted.status == "partial"


# --- GET /drive/files/{id}/content -----------------------------------------
# Generic Drive file proxy -- shows a synced receipt's original photo, and
# previews a not-yet-imported candidate in the "import from Drive" picker.


def test_drive_file_content_streams_bytes_and_content_type(client, monkeypatch):
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-jpeg-bytes")
    monkeypatch.setattr(google_service, "get_file_mime_type", lambda db, file_id: "image/jpeg")

    resp = client.get("/api/drive/files/file-1/content")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == b"fake-jpeg-bytes"


def test_drive_file_content_returns_409_when_google_not_connected(client, monkeypatch):
    def _raise_not_connected(db, file_id):
        raise g_oauth.GoogleNotConnected("Connect Google Workspace first.")

    monkeypatch.setattr(google_service, "download_file", _raise_not_connected)

    resp = client.get("/api/drive/files/file-1/content")
    assert resp.status_code == 409


# --- GET /drive/receipt-images & POST /receipts/import-from-drive/{id} ----
# The manual picker: browse/search Drive for a receipt photo directly, for
# when the automatic Receipts-inbox scan hasn't caught it, then import one.


def test_search_receipt_images_returns_409_when_not_connected(client, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: None)

    resp = client.get("/api/drive/receipt-images")
    assert resp.status_code == 409


def test_search_receipt_images_returns_matching_files(client, monkeypatch):
    monkeypatch.setattr(g_oauth, "get_connection", lambda db: SimpleNamespace(id=1))
    monkeypatch.setattr(
        google_service,
        "search_images",
        lambda db, search=None: [{"id": "file-9", "name": "IMG_0001.jpg", "mimeType": "image/jpeg", "modifiedTime": "2026-09-16T00:00:00Z"}],
    )

    resp = client.get("/api/drive/receipt-images")
    assert resp.status_code == 200
    assert resp.json() == [{"id": "file-9", "name": "IMG_0001.jpg", "modified_time": "2026-09-16T00:00:00Z"}]


def test_import_receipt_from_drive_matches_and_records_expense(db, client, monkeypatch):
    project = make_project(db, customer_name="Francisco C. Rodriguez", drive_folder_id="project-folder-1")
    db.commit()

    monkeypatch.setattr(g_oauth, "get_connection", lambda db: SimpleNamespace(id=1))
    monkeypatch.setattr(google_service, "get_file_name", lambda db, file_id: "IMG_0001.jpg")
    monkeypatch.setattr(google_service, "get_file_mime_type", lambda db, file_id: "image/jpeg")
    monkeypatch.setattr(google_service, "download_file", lambda db, file_id: b"fake-bytes")
    monkeypatch.setattr(
        gemini_service,
        "extract_receipt_from_image",
        lambda *a, **k: ReceiptExtractionResult(
            found=True, vendor="Sherwin-Williams", date=dt.date(2026, 9, 16), amount=383.73, description="Paint and supplies", handwritten_name="francisco"
        ),
    )
    monkeypatch.setattr(google_service, "get_file_parents", lambda db, file_id: ["some-other-folder"])
    monkeypatch.setattr(google_service, "get_or_create_project_receipts_folder", lambda db, folder_id: "project-receipts-folder")
    monkeypatch.setattr(google_service, "move_file", lambda db, file_id, new_parent, old_parent: None)

    resp = client.post("/api/receipts/import-from-drive/file-9")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == project.id
    assert body["amount"] == 383.73
    assert body["source"] == "drive_folder"


def test_import_receipt_from_drive_rejects_duplicate(db, client, monkeypatch):
    receipt = models.Receipt(date=dt.date(2026, 1, 1), description="Already here", amount=10, type="expense", source="drive_folder", drive_file_id="file-9")
    db.add(receipt)
    db.commit()

    monkeypatch.setattr(g_oauth, "get_connection", lambda db: SimpleNamespace(id=1))

    resp = client.post("/api/receipts/import-from-drive/file-9")
    assert resp.status_code == 409
