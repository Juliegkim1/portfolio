"""POST /projects (create_project_from_estimate) — covers two behaviors
added alongside the combine-notes feature: an overridable Drive folder
name (independent of project_type) and scope_verification flowing from a
combined estimate's milestones into the real, persisted Milestone rows."""

from app import models


def _estimate_payload(**overrides):
    defaults = dict(
        found=True,
        estimate_number="1042",
        customer_name="Jane Doe",
        property_address="123 Main St, Springfield, CA 90000",
        total=10000,
        line_items=[{"section": "materials", "description": "Cabinets", "qty": 1, "unit": "ea", "unit_price": 10000}],
        milestones=[],
    )
    defaults.update(overrides)
    return defaults


def test_drive_folder_name_override_changes_the_created_folder(client):
    # No Google connection in a fresh test DB, so this exercises the
    # mock_integrations fallback — deterministic given its inputs, so two
    # different folder names for the same customer/address must produce
    # two different fake folder ids.
    resp1 = client.post("/api/projects", json={"project_type": "Kitchen Remodel", "estimate": _estimate_payload(), "drive_folder_name": "Kitchen Remodel - Phase 1"})
    resp2 = client.post(
        "/api/projects",
        json={
            "project_type": "Kitchen Remodel",
            "estimate": {**_estimate_payload(), "customer_name": "Jane Doe", "property_address": "123 Main St, Springfield, CA 90000"},
            "drive_folder_name": "Kitchen Remodel - Phase 2",
        },
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["drive_folder_id"] != resp2.json()["drive_folder_id"]


def test_drive_folder_name_defaults_to_project_type_when_omitted(client):
    with_override = client.post("/api/projects", json={"project_type": "Bathroom Remodel", "estimate": _estimate_payload(), "drive_folder_name": "Bathroom Remodel"})
    without_override = client.post(
        "/api/projects",
        json={"project_type": "Bathroom Remodel", "estimate": {**_estimate_payload(), "customer_name": "John Smith"}},
    )
    assert with_override.status_code == 200
    assert without_override.status_code == 200
    # Different customers, so folder ids differ regardless — this just
    # confirms omitting drive_folder_name doesn't error and still creates a folder.
    assert without_override.json()["drive_folder_id"]


def test_scope_verification_persists_from_combined_milestones(db, client):
    resp = client.post(
        "/api/projects",
        json={
            "project_type": "Kitchen Remodel",
            "estimate": _estimate_payload(
                milestones=[
                    {"number": 0, "title": "Deposit", "amount": 1000, "scope_verification": "Covers initial cabinet order deposit."},
                    {"number": 1, "title": "Final", "amount": 9000, "scope_verification": None},
                ]
            ),
        },
    )
    assert resp.status_code == 200
    project_id = resp.json()["id"]

    milestones = (
        db.query(models.Milestone)
        .join(models.ScopeSchedule)
        .filter(models.ScopeSchedule.project_id == project_id)
        .order_by(models.Milestone.number)
        .all()
    )
    assert len(milestones) == 2
    assert milestones[0].scope_verification == "Covers initial cabinet order deposit."
    assert milestones[1].scope_verification == ""  # None coerced to "" (NOT NULL column), never crashes
