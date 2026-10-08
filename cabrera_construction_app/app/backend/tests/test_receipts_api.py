"""DELETE /receipts/{id} — lets a mis-entered receipt (business expense,
project expense, or payment) be removed outright. See
routers/receipts.py's delete_receipt for the cleanup rules: a matched bank
transaction is unlinked, not deleted, and a milestone's paid status is
recomputed from whatever payment receipts remain."""

import datetime as dt

from app import models
from tests.factories import make_estimate, make_project


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
