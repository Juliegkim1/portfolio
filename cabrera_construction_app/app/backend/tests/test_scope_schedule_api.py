"""PUT /projects/{id}/scope-schedule — see app/routers/scope_schedules.py.

Balance (schedule must sum to 100% of contract) is a hard block. Deposit cap
(<= min($1,000, 10%)) is advisory only: it's reported back for the UI to
warn with, but never blocks the save — a real contract (e.g. Drive-imported)
can already carry a deposit above this guideline, and blocking the save made
it impossible to even record that project's actual numbers."""

from tests.factories import make_estimate, make_line_item, make_project


def _schedule_payload(milestones):
    return {
        "contract_date": None,
        "contract_type": "Fixed-Price Agreement",
        "payment_terms": "Due on milestone completion, net 15",
        "warranty_terms": "",
        "milestones": milestones,
        "materials": [],
    }


def test_save_succeeds_with_deposit_over_the_cap(db, client):
    # $10,000 contract — cap is min($1,000, 10%) = $1,000 — deposit here is $5,000.
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=10000)
    db.commit()

    payload = _schedule_payload(
        [
            {"number": 0, "title": "Deposit", "amount": 5000},
            {"number": 1, "title": "Final Walkthrough", "amount": 5000},
        ]
    )
    resp = client.put(f"/api/projects/{project.id}/scope-schedule", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["deposit_ok"] is False  # still reported, just not enforced
    assert "exceeds" in body["deposit_note"]
    assert len(body["milestones"]) == 2


def test_save_blocked_when_schedule_not_balanced(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=10000)
    db.commit()

    payload = _schedule_payload([{"number": 0, "title": "Deposit", "amount": 500}])  # far short of $10,000
    resp = client.put(f"/api/projects/{project.id}/scope-schedule", json=payload)

    assert resp.status_code == 400
    assert "not balanced" in resp.json()["detail"]


def test_save_succeeds_when_balanced_and_deposit_within_cap(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=10000)
    db.commit()

    payload = _schedule_payload(
        [
            {"number": 0, "title": "Deposit", "amount": 1000},
            {"number": 1, "title": "Final Walkthrough", "amount": 9000},
        ]
    )
    resp = client.put(f"/api/projects/{project.id}/scope-schedule", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["deposit_ok"] is True
    assert body["balanced"] is True


def test_editing_an_already_saved_schedule_still_allows_over_cap_deposit(db, client):
    """Reproduces the user's report: a project already has a schedule saved,
    then they edit a milestone amount so the deposit now exceeds the cap —
    re-saving must still succeed, not revert to blocking."""
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=10000)
    db.commit()

    first_save = _schedule_payload(
        [
            {"number": 0, "title": "Deposit", "amount": 1000},
            {"number": 1, "title": "Final Walkthrough", "amount": 9000},
        ]
    )
    resp1 = client.put(f"/api/projects/{project.id}/scope-schedule", json=first_save)
    assert resp1.status_code == 200

    edited = _schedule_payload(
        [
            {"number": 0, "title": "Deposit", "amount": 3000},
            {"number": 1, "title": "Final Walkthrough", "amount": 7000},
        ]
    )
    resp2 = client.put(f"/api/projects/{project.id}/scope-schedule", json=edited)
    assert resp2.status_code == 200
    assert resp2.json()["deposit_ok"] is False
