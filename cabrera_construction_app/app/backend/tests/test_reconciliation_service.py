"""Operational Reconciliation: vendor normalization and bank-transaction
matching — see app/services/reconciliation.py and CLAUDE.md "Business
rules". Pure functions except for the `receipt` duck-type below."""

import datetime as dt
from types import SimpleNamespace

from app.services import reconciliation


def _receipt(type_, amount, date, description):
    return SimpleNamespace(type=type_, amount=amount, date=date, description=description)


def test_normalize_vendor_display_alias_table():
    assert reconciliation.normalize_vendor_display("HOME DEPOT #4455 SAN JOSE CA") == "Home Depot"
    assert reconciliation.normalize_vendor_display("LOWES #0291") == "Lowe's"


def test_normalize_vendor_display_strips_store_number_phone_and_location():
    result = reconciliation.normalize_vendor_display("ACME SUPPLY #123 408-555-0100 San Jose CA")
    assert "#123" not in result
    assert "408" not in result
    assert not result.endswith("Ca")


def test_normalize_vendor_display_strips_des_suffix():
    result = reconciliation.normalize_vendor_display("ACME SUPPLY DES:PURCHASE INDN:JANE DOE")
    assert "DES" not in result.upper()


def test_normalize_vendor_display_falls_back_to_title_case_original():
    # A description that's nothing BUT noise (fully stripped) falls back to
    # the raw text, title-cased, rather than returning an empty string.
    result = reconciliation.normalize_vendor_display("123 408-555-0100")
    assert result


def test_vendor_matches_substring_either_direction():
    assert reconciliation.vendor_matches("Home Depot — Cabinets", "HOME DEPOT #4455") is True
    assert reconciliation.vendor_matches("Ferguson — Plumbing", "SOME UNRELATED STORE") is False


def test_vendor_matches_empty_inputs_never_match():
    assert reconciliation.vendor_matches("", "HOME DEPOT") is False
    assert reconciliation.vendor_matches("Home Depot", "") is False


def test_fingerprint_format():
    fp = reconciliation.fingerprint(dt.date(2026, 1, 15), 123.456, "  Home Depot  ")
    assert fp == "2026-01-15|123.46|home depot"


def test_match_status_exact_match_same_day_vendor_matches():
    receipt = _receipt("expense", 123.45, dt.date(2026, 1, 15), "Home Depot — Cabinets")
    status = reconciliation.match_status_for(-123.45, dt.date(2026, 1, 15), "HOME DEPOT #4455", receipt)
    assert status == "matched"


def test_match_status_wrong_sign_never_matches_wrong_receipt_type():
    # A deposit (positive amount) should only ever match a payment receipt.
    receipt = _receipt("expense", 123.45, dt.date(2026, 1, 15), "Home Depot — Cabinets")
    status = reconciliation.match_status_for(123.45, dt.date(2026, 1, 15), "HOME DEPOT #4455", receipt)
    assert status is None


def test_match_status_amount_mismatch_never_matches():
    receipt = _receipt("expense", 100.00, dt.date(2026, 1, 15), "Home Depot — Cabinets")
    status = reconciliation.match_status_for(-123.45, dt.date(2026, 1, 15), "HOME DEPOT #4455", receipt)
    assert status is None


def test_match_status_possible_vendor_matches_but_too_many_days_apart():
    receipt = _receipt("expense", 123.45, dt.date(2026, 1, 1), "Home Depot — Cabinets")
    status = reconciliation.match_status_for(-123.45, dt.date(2026, 1, 8), "HOME DEPOT #4455", receipt)
    assert status == "possible"


def test_match_status_possible_vendor_mismatch_but_close_dates():
    receipt = _receipt("expense", 123.45, dt.date(2026, 1, 1), "Ferguson — Plumbing")
    status = reconciliation.match_status_for(-123.45, dt.date(2026, 1, 2), "UNRELATED VENDOR", receipt)
    assert status == "possible"


def test_match_status_no_relationship_vendor_mismatch_and_far_apart():
    receipt = _receipt("expense", 123.45, dt.date(2026, 1, 1), "Ferguson — Plumbing")
    status = reconciliation.match_status_for(-123.45, dt.date(2026, 2, 1), "UNRELATED VENDOR", receipt)
    assert status is None


def test_find_best_match_prefers_exact_over_possible():
    exact = _receipt("expense", 100.00, dt.date(2026, 1, 1), "Home Depot — A")
    possible = _receipt("expense", 100.00, dt.date(2026, 1, 1), "Totally Different Vendor — B")
    # `possible` listed first — find_best_match must still prefer the exact match found later.
    receipt, status = reconciliation.find_best_match(-100.00, dt.date(2026, 1, 1), "HOME DEPOT #42", [possible, exact])
    assert status == "matched"
    assert receipt is exact


def test_find_best_match_returns_none_when_nothing_relates():
    receipt = _receipt("expense", 100.00, dt.date(2026, 1, 1), "Ferguson — Plumbing")
    found, status = reconciliation.find_best_match(-999.99, dt.date(2026, 1, 1), "UNRELATED", [receipt])
    assert found is None
    assert status is None
