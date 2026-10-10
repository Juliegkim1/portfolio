"""GET /projects/{id}/reconciliation -- must never 404 and hide a
project's expenses/labor just because it has no estimate yet (it used to),
and must now also surface total expenses, total labor, margin, and the
discount/scope-addition breakdown behind the "Change Orders" figure.

POST/PATCH/DELETE /projects/{id}/labor, /labor/{id} -- actual labor cost,
entered straight on the Reconciliation page."""

import datetime as dt

from app import models
from tests.factories import make_estimate, make_project


def test_reconciliation_milestones_include_due_date_from_schedule(db, client):
    """The milestone's own target due date from the Scope & Payment
    Schedule must come through here -- it used to be left off the
    reconciliation response entirely."""
    project = make_project(db)
    make_estimate(db, project)
    db.commit()
    scope_schedule = models.ScopeSchedule(project_id=project.id, contract_type="Fixed-Price Agreement")
    db.add(scope_schedule)
    db.flush()
    db.add(models.Milestone(scope_schedule_id=scope_schedule.id, number=0, title="Deposit", amount=1000, due_date=dt.date(2026, 3, 15)))
    db.add(models.Milestone(scope_schedule_id=scope_schedule.id, number=1, title="Final", amount=1000, due_date=None))
    db.commit()

    resp = client.get(f"/api/projects/{project.id}/reconciliation")
    body = resp.json()
    by_title = {m["title"]: m["due_date"] for m in body["milestones"]}
    assert by_title["Deposit"] == "2026-03-15"
    assert by_title["Final"] is None


def test_reconciliation_does_not_404_without_an_estimate(db, client):
    """This used to raise 404 and hide the whole page -- including any
    expense/labor receipts already tied to the project -- whenever a
    project had no Estimate row yet."""
    project = make_project(db)
    db.commit()

    resp = client.get(f"/api/projects/{project.id}/reconciliation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kpis"]["original"] == 0.0
    assert body["kpis"]["revised"] == 0.0
    assert body["can_close"] is False


def test_reconciliation_shows_expenses_without_an_estimate(db, client):
    project = make_project(db)
    db.commit()
    receipt = models.Receipt(project_id=project.id, date=dt.date(2026, 1, 1), description="Lumber", amount=500, type="expense", source="manual")
    db.add(receipt)
    db.commit()

    resp = client.get(f"/api/projects/{project.id}/reconciliation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kpis"]["total_expenses"] == 500.0
    assert len(body["receipts"]) == 1


def test_reconciliation_computes_margin_from_expenses_and_labor(db, client):
    project = make_project(db)
    make_estimate(db, project, discount=0)
    db.commit()
    db.add(models.Receipt(project_id=project.id, date=dt.date(2026, 1, 1), description="Lumber", amount=1000, type="expense", source="manual"))
    db.add(models.LaborEntry(project_id=project.id, person_name="Carlos", date=dt.date(2026, 1, 2), amount=2000))
    db.commit()

    resp = client.get(f"/api/projects/{project.id}/reconciliation")
    body = resp.json()
    revised = body["kpis"]["revised"]
    assert body["kpis"]["total_expenses"] == 1000.0
    assert body["kpis"]["total_labor"] == 2000.0
    assert body["kpis"]["margin"] == round(revised - 1000.0 - 2000.0, 2)


def test_reconciliation_breaks_out_discounts_from_signed_change_orders(db, client):
    """A discount is just a signed Change Order that's pure
    amount_subtracted -- any contractual change goes through Change
    Orders, but Reconciliation is where the owner looks for "how much did
    we discount this job," so it's surfaced as its own figure instead of
    being buried inside the net change_orders number."""
    project = make_project(db)
    make_estimate(db, project)
    db.commit()
    now = dt.datetime(2026, 2, 1)
    signed_discount = models.ChangeOrder(
        project_id=project.id, number=1, owner_signed_at=now, contractor_signed_at=now,
        parts_changed=["price"], amount_added=0, amount_subtracted=500, status="signed",
    )
    signed_addition = models.ChangeOrder(
        project_id=project.id, number=2, owner_signed_at=now, contractor_signed_at=now,
        parts_changed=["scope", "price"], amount_added=1200, amount_subtracted=0, status="signed",
    )
    unsigned = models.ChangeOrder(project_id=project.id, number=3, parts_changed=["price"], amount_added=0, amount_subtracted=9999, status="out_for_signature")
    db.add_all([signed_discount, signed_addition, unsigned])
    db.commit()

    resp = client.get(f"/api/projects/{project.id}/reconciliation")
    body = resp.json()
    assert body["kpis"]["discounts_given"] == 500.0
    assert body["kpis"]["scope_additions"] == 1200.0
    assert body["kpis"]["change_orders"] == 700.0  # net: 1200 added - 500 subtracted, unsigned ignored


# --- Labor ---------------------------------------------------------------


def test_create_labor_entry(db, client):
    project = make_project(db)
    db.commit()

    resp = client.post(f"/api/projects/{project.id}/labor", json={"person_name": "Carlos Mendez", "date": "2026-01-15", "amount": 800})
    assert resp.status_code == 200
    body = resp.json()
    assert body["person_name"] == "Carlos Mendez"
    assert body["amount"] == 800.0
    assert body["project_id"] == project.id


def test_create_labor_entry_404_for_missing_project(client):
    resp = client.post("/api/projects/999999/labor", json={"person_name": "Carlos", "date": "2026-01-15", "amount": 800})
    assert resp.status_code == 404


def test_update_labor_entry_partial(db, client):
    project = make_project(db)
    db.commit()
    entry = models.LaborEntry(project_id=project.id, person_name="Carlos Mendez", date=dt.date(2026, 1, 15), amount=800)
    db.add(entry)
    db.commit()

    resp = client.patch(f"/api/labor/{entry.id}", json={"amount": 950})
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount"] == 950.0
    assert body["person_name"] == "Carlos Mendez"


def test_delete_labor_entry(db, client):
    project = make_project(db)
    db.commit()
    entry = models.LaborEntry(project_id=project.id, person_name="Carlos Mendez", date=dt.date(2026, 1, 15), amount=800)
    db.add(entry)
    db.commit()
    entry_id = entry.id

    resp = client.delete(f"/api/labor/{entry_id}")
    assert resp.status_code == 204
    assert db.get(models.LaborEntry, entry_id) is None


def test_delete_labor_entry_404_for_missing(client):
    resp = client.delete("/api/labor/999999")
    assert resp.status_code == 404


def test_deleting_project_cascades_its_labor_entries(db, client):
    project = make_project(db)
    db.commit()
    db.add(models.LaborEntry(project_id=project.id, person_name="Carlos", date=dt.date(2026, 1, 15), amount=800))
    db.commit()

    resp = client.delete(f"/api/projects/{project.id}")
    assert resp.status_code == 204
    assert db.query(models.LaborEntry).filter(models.LaborEntry.project_id == project.id).count() == 0
