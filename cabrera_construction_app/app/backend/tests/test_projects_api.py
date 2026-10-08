"""API-level tests for the Projects endpoints — these hit a real Postgres
test database (see conftest.py) through FastAPI's TestClient, the same way
every fix in this app has been dry-run verified by hand so far, just
permanent and automated now."""

import datetime as dt

from app import models
from tests.factories import make_estimate, make_line_item, make_project


def test_list_projects_empty(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_project_404_for_missing_id(client):
    resp = client.get("/api/projects/999999")
    assert resp.status_code == 404


def test_get_project_returns_seeded_project(db, client):
    project = make_project(db)
    db.commit()

    resp = client.get(f"/api/projects/{project.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_name"] == "Jane Doe"
    assert body["project_type"] == "Kitchen Remodel"


# --- PATCH .../type ---------------------------------------------------------


def test_update_project_type_persists(db, client):
    project = make_project(db)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/type", json={"project_type": "Bathroom Remodel"})
    assert resp.status_code == 200
    assert resp.json()["project_type"] == "Bathroom Remodel"

    # Round-trips through a fresh GET, not just the PATCH response.
    resp2 = client.get(f"/api/projects/{project.id}")
    assert resp2.json()["project_type"] == "Bathroom Remodel"


def test_update_project_type_rejects_empty_string(db, client):
    project = make_project(db)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/type", json={"project_type": "   "})
    assert resp.status_code == 400

    # Original value must be untouched after the rejected update.
    resp2 = client.get(f"/api/projects/{project.id}")
    assert resp2.json()["project_type"] == "Kitchen Remodel"


def test_update_project_type_404_for_missing_project(client):
    resp = client.patch("/api/projects/999999/type", json={"project_type": "Bathroom Remodel"})
    assert resp.status_code == 404


# --- PATCH .../dates ---------------------------------------------------------


def test_update_project_dates(db, client):
    project = make_project(db, start_date=None, end_date=None)
    db.commit()

    resp = client.patch(
        f"/api/projects/{project.id}/dates",
        json={"start_date": "2026-02-01", "end_date": "2026-04-15"},
    )
    assert resp.status_code == 200
    assert resp.json()["start_date"] == "2026-02-01"
    assert resp.json()["end_date"] == "2026-04-15"


def test_update_project_dates_accepts_nulls_to_clear(db, client):
    project = make_project(db)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/dates", json={"start_date": None, "end_date": None})
    assert resp.status_code == 200
    assert resp.json()["start_date"] is None
    assert resp.json()["end_date"] is None


# --- PATCH .../drive-folder --------------------------------------------------


def test_update_drive_folder_accepts_bare_id(db, client):
    project = make_project(db)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/drive-folder", json={"drive_folder_link": "abc123XYZ"})
    assert resp.status_code == 200
    assert resp.json()["drive_folder_id"] == "abc123XYZ"


def test_update_drive_folder_extracts_id_from_folders_url(db, client):
    project = make_project(db)
    db.commit()

    resp = client.patch(
        f"/api/projects/{project.id}/drive-folder",
        json={"drive_folder_link": "https://drive.google.com/drive/folders/abc123XYZ?usp=sharing"},
    )
    assert resp.status_code == 200
    assert resp.json()["drive_folder_id"] == "abc123XYZ"


def test_update_drive_folder_extracts_id_from_open_url(db, client):
    project = make_project(db)
    db.commit()

    resp = client.patch(
        f"/api/projects/{project.id}/drive-folder",
        json={"drive_folder_link": "https://drive.google.com/open?id=abc123XYZ"},
    )
    assert resp.status_code == 200
    assert resp.json()["drive_folder_id"] == "abc123XYZ"


# --- PATCH .../estimate (total_override tristate) ---------------------------


def test_override_estimate_total_sets_override(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=1000)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/estimate", json={"total_override": 5000})
    assert resp.status_code == 200
    assert resp.json()["total"] == 5000.0


def test_override_estimate_updating_only_estimate_number_leaves_override_untouched(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=1000)
    db.commit()

    client.patch(f"/api/projects/{project.id}/estimate", json={"total_override": 5000})
    resp = client.patch(f"/api/projects/{project.id}/estimate", json={"estimate_number": "9999"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["estimate_number"] == "9999"
    assert body["total"] == 5000.0  # override must survive an update that never mentioned it


def test_override_estimate_explicit_null_clears_it(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=1000, qty=2)  # subtotal 2000
    db.commit()

    client.patch(f"/api/projects/{project.id}/estimate", json={"total_override": 5000})
    resp = client.patch(f"/api/projects/{project.id}/estimate", json={"total_override": None})

    assert resp.status_code == 200
    assert resp.json()["total"] == 2000.0  # back to the computed subtotal


def test_override_estimate_404_without_estimate(db, client):
    project = make_project(db)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/estimate", json={"total_override": 5000})
    assert resp.status_code == 404


# --- DELETE -------------------------------------------------------------------


def test_delete_project_cascades_estimate_and_unassigns_receipts(db, client):
    project = make_project(db)
    make_estimate(db, project)
    receipt = models.Receipt(
        project_id=project.id,
        date=dt.date(2026, 1, 1),
        description="Home Depot — Cabinets",
        amount=100,
        type="expense",
    )
    db.add(receipt)
    db.commit()
    receipt_id = receipt.id

    resp = client.delete(f"/api/projects/{project.id}")
    assert resp.status_code == 204

    assert db.get(models.Project, project.id) is None

    db.expire_all()
    orphaned_receipt = db.get(models.Receipt, receipt_id)
    assert orphaned_receipt is not None  # receipts are never deleted, only unassigned
    assert orphaned_receipt.project_id is None
    assert orphaned_receipt.needs_project is True


def test_delete_project_404_for_missing_id(client):
    resp = client.delete("/api/projects/999999")
    assert resp.status_code == 404
