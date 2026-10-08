"""Milestone / balance business rules (CLAUDE.md "Business rules").

- Milestone % = amount / contract total. Schedule must sum to 100% before saving.
- Deposit (milestone 0) <= min($1,000, 10% of contract) — advisory only; see
  routers/scope_schedules.py's save_scope_schedule for why this doesn't block saving.
- Invoice amount = milestone amount + signed CO deltas for that milestone.
- Balance = revised contract - sum(payment receipts). Expenses never reduce balance.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def _d(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def schedule_total(amounts: list[float]) -> Decimal:
    return sum((_d(a) for a in amounts), Decimal("0.00"))


def check_balanced(amounts: list[float], contract_total: float) -> tuple[bool, str]:
    total = schedule_total(amounts)
    target = _d(contract_total)
    if total == target:
        return True, "Balanced — 100% of contract"
    diff = total - target
    direction = "Over" if diff > 0 else "Short"
    return False, f"{direction} by ${abs(diff):,.2f}"


def check_deposit(deposit_amount: float, contract_total: float) -> tuple[bool, str]:
    cap = min(Decimal("1000.00"), _d(contract_total) * Decimal("0.10"))
    ok = _d(deposit_amount) <= cap
    note = f"Deposit within $1,000 / 10% limit (cap ${cap:,.2f})" if ok else f"Deposit exceeds the ${cap:,.2f} cap"
    return ok, note


def milestone_percent(amount: float, contract_total: float) -> float:
    if not contract_total:
        return 0.0
    return round(float(_d(amount)) / float(contract_total) * 100, 2)


def project_balance(revised_contract_total: float, payment_receipt_amounts: list[float]) -> float:
    received = schedule_total(payment_receipt_amounts)
    return float(_d(revised_contract_total) - received)
