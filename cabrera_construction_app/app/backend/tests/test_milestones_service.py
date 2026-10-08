"""Milestone/balance business rules — see app/services/milestones.py and
CLAUDE.md "Business rules". Pure functions, no DB."""

from app.services import milestones


def test_check_balanced_exact_match():
    ok, note = milestones.check_balanced([1000, 2000, 3000], 6000)
    assert ok is True
    assert "Balanced" in note


def test_check_balanced_short():
    ok, note = milestones.check_balanced([1000, 2000], 6000)
    assert ok is False
    assert "Short by $3,000.00" in note


def test_check_balanced_over():
    ok, note = milestones.check_balanced([1000, 2000, 3500], 6000)
    assert ok is False
    assert "Over by $500.00" in note


def test_check_deposit_within_dollar_cap():
    # 10% of a $50,000 contract would be $5,000, but the cap is min($1,000, 10%).
    ok, note = milestones.check_deposit(1000, 50000)
    assert ok is True
    assert "$1,000.00" in note


def test_check_deposit_within_percent_cap_on_small_contract():
    # 10% of a $5,000 contract is $500 — stricter than the flat $1,000 cap.
    ok, note = milestones.check_deposit(500, 5000)
    assert ok is True


def test_check_deposit_exceeds_percent_cap_on_small_contract():
    ok, note = milestones.check_deposit(600, 5000)
    assert ok is False
    assert "exceeds" in note


def test_check_deposit_exceeds_dollar_cap():
    ok, note = milestones.check_deposit(1500, 50000)
    assert ok is False


def test_milestone_percent():
    assert milestones.milestone_percent(2500, 10000) == 25.0


def test_milestone_percent_zero_contract_total_guard():
    assert milestones.milestone_percent(2500, 0) == 0.0


def test_project_balance_no_payments_yet():
    assert milestones.project_balance(10000, []) == 10000.0


def test_project_balance_after_partial_payment():
    assert milestones.project_balance(10000, [2500]) == 7500.0


def test_project_balance_fully_paid():
    assert milestones.project_balance(10000, [2500, 7500]) == 0.0
