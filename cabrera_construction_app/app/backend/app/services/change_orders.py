"""Change-order math (CLAUDE.md "Business rules" and Design Document §04/§09).

- Revised contract = estimate total + sum(signed CO added - subtracted).
- A CO only affects totals/milestones/dates once BOTH parties have signed.
- "Previously Signed Contract Price" = revised contract as of just before this CO.
"""

from __future__ import annotations

from .milestones import _d


def is_signed(change_order) -> bool:
    return change_order.owner_signed_at is not None and change_order.contractor_signed_at is not None


def revised_contract_total(estimate_total: float, change_orders: list) -> float:
    total = _d(estimate_total)
    for co in change_orders:
        if is_signed(co):
            total += _d(co.amount_added) - _d(co.amount_subtracted)
    return float(total)


def previously_signed_contract_price(estimate_total: float, change_orders: list, before_number: int) -> float:
    """Revised contract total counting only signed COs numbered before `before_number`."""
    prior = [co for co in change_orders if co.number < before_number]
    return revised_contract_total(estimate_total, prior)


def new_contract_price_for(estimate_total: float, change_orders: list, this_co) -> float:
    """What the contract price becomes if `this_co` is (or were) signed, given all other signed COs."""
    prior_total = previously_signed_contract_price(estimate_total, change_orders, this_co.number)
    return float(_d(prior_total) + _d(this_co.amount_added) - _d(this_co.amount_subtracted))


def latest_completion_date(default_date, change_orders: list):
    """The most recent signed CO's new_completion_date, else the default (scope schedule) date."""
    signed_with_date = [co for co in change_orders if is_signed(co) and co.new_completion_date]
    if not signed_with_date:
        return default_date
    return max(signed_with_date, key=lambda co: co.number).new_completion_date
