"""Operational Reconciliation: vendor normalization and bank-transaction matching.

Rules (CLAUDE.md "Business rules" and Design Document §06):
- A debit matches an expense receipt, a deposit matches a payment receipt.
- Exact match: amounts equal to the cent AND vendor matches AND date within 3 days.
- Possible match: amounts equal AND ((vendor matches AND date 4-14 days apart)
  OR (vendor doesn't match AND date within 3 days)) -- needs user confirmation.
- "Vendor matches": the normalized receipt vendor (text before " -- ", letters
  only, lowercased) is contained in the normalized bank description, or the reverse.
- Each receipt can match only one transaction. Dedupe re-imports by
  date + amount + description fingerprint.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

_VENDOR_ALIASES = {
    "thehomedepot": "Home Depot",
    "homedepotcrc": "Home Depot",
    "homedepot": "Home Depot",
    "lowes": "Lowe's",
    "lowescrc": "Lowe's",
    "ferguson": "Ferguson",
    "sherwinwilliams": "Sherwin-Williams",
    "acehardware": "Ace Hardware",
}

_STORE_NUMBER_RE = re.compile(r"#\d+")
_PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
_DES_SUFFIX_RE = re.compile(r"\bDES:.*$", re.IGNORECASE)
# A city is at most two words, so this can't eat into a multi-word vendor name.
_TRAILING_LOCATION_RE = re.compile(r"\s+[A-Za-z]+(?:\s[A-Za-z]+)?\s+[A-Z]{2}$")


def letters_only(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalpha())


def normalize_vendor_display(description: str) -> str:
    """Human-readable normalized vendor for the reconciliation table."""
    # Check the alias table against the raw description first: a substring match
    # is immune to trailing store numbers/city/state, so it doesn't need the
    # (lossier) cleanup below to have already run.
    raw_key = letters_only(description)
    for alias_key, canonical in _VENDOR_ALIASES.items():
        if alias_key in raw_key:
            return canonical

    text = _DES_SUFFIX_RE.sub("", description)
    text = _STORE_NUMBER_RE.sub("", text)
    text = _PHONE_RE.sub("", text)
    text = _TRAILING_LOCATION_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else description.title()


def receipt_vendor_key(receipt_description: str) -> str:
    vendor_part = receipt_description.split(" — ")[0]
    return letters_only(vendor_part)


def vendor_matches(receipt_description: str, bank_description: str) -> bool:
    vendor_key = receipt_vendor_key(receipt_description)
    bank_key = letters_only(bank_description)
    if not vendor_key or not bank_key:
        return False
    return vendor_key in bank_key or bank_key in vendor_key


def fingerprint(posted_date: dt.date, amount: float, description: str) -> str:
    return f"{posted_date.isoformat()}|{Decimal(str(amount)).quantize(Decimal('0.01'))}|{description.strip().lower()}"


def match_status_for(txn_amount: float, txn_date: dt.date, txn_description: str, receipt) -> str | None:
    """Returns 'matched', 'possible', or None (no relationship) for one txn/receipt pair."""
    expected_type = "expense" if txn_amount < 0 else "payment"
    if receipt.type != expected_type:
        return None
    if Decimal(str(abs(txn_amount))) != Decimal(str(receipt.amount)).quantize(Decimal("0.01")):
        return None

    days_apart = abs((txn_date - receipt.date).days)
    matches_vendor = vendor_matches(receipt.description, txn_description)

    if matches_vendor and days_apart <= 3:
        return "matched"
    if (matches_vendor and 4 <= days_apart <= 14) or (not matches_vendor and days_apart <= 3):
        return "possible"
    return None


def find_best_match(txn_amount: float, txn_date: dt.date, txn_description: str, candidate_receipts: list):
    """Picks the best-matching unmatched receipt for a transaction, if any.

    Returns (receipt_or_None, status_or_None). Prefers an exact match over a possible one.
    """
    best_receipt = None
    best_status = None
    for receipt in candidate_receipts:
        status = match_status_for(txn_amount, txn_date, txn_description, receipt)
        if status == "matched":
            return receipt, status
        if status == "possible" and best_status is None:
            best_receipt, best_status = receipt, status
    return best_receipt, best_status
