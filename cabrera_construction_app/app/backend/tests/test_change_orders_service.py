"""Change-order math — see app/services/change_orders.py and CLAUDE.md
"Business rules". Pure functions operating on anything with the right
attributes, so plain SimpleNamespace stand-ins work without touching the DB."""

import datetime as dt
from types import SimpleNamespace

from app.services import change_orders


def _co(number, added=0, subtracted=0, owner_signed=True, contractor_signed=True, new_completion_date=None):
    return SimpleNamespace(
        number=number,
        amount_added=added,
        amount_subtracted=subtracted,
        owner_signed_at=dt.datetime(2026, 1, number) if owner_signed else None,
        contractor_signed_at=dt.datetime(2026, 1, number) if contractor_signed else None,
        new_completion_date=new_completion_date,
    )


def test_is_signed_requires_both_parties():
    assert change_orders.is_signed(_co(1)) is True
    assert change_orders.is_signed(_co(1, owner_signed=False)) is False
    assert change_orders.is_signed(_co(1, contractor_signed=False)) is False


def test_revised_contract_total_only_counts_signed_cos():
    cos = [
        _co(1, added=1000),
        _co(2, added=500, owner_signed=False),  # unsigned — must not count
        _co(3, subtracted=200),
    ]
    assert change_orders.revised_contract_total(10000, cos) == 10800.0


def test_revised_contract_total_no_change_orders():
    assert change_orders.revised_contract_total(10000, []) == 10000.0


def test_previously_signed_contract_price_excludes_cos_at_or_after_number():
    cos = [_co(1, added=1000), _co(2, added=2000), _co(3, added=3000)]
    # Before CO-3: only CO-1 and CO-2 have landed.
    assert change_orders.previously_signed_contract_price(10000, cos, before_number=3) == 13000.0


def test_new_contract_price_for_this_co():
    cos = [_co(1, added=1000), _co(2, added=2000)]
    this_co = _co(2, added=2000)
    # Prior (CO-1 only) = 11000, plus this CO's own 2000 = 13000.
    assert change_orders.new_contract_price_for(10000, cos, this_co) == 13000.0


def test_latest_completion_date_falls_back_to_default_when_no_signed_dates():
    default = dt.date(2026, 6, 1)
    cos = [_co(1, new_completion_date=None)]
    assert change_orders.latest_completion_date(default, cos) == default


def test_latest_completion_date_falls_back_when_co_unsigned():
    default = dt.date(2026, 6, 1)
    cos = [_co(1, owner_signed=False, new_completion_date=dt.date(2026, 7, 1))]
    assert change_orders.latest_completion_date(default, cos) == default


def test_latest_completion_date_picks_highest_numbered_signed_co():
    default = dt.date(2026, 6, 1)
    cos = [
        _co(1, new_completion_date=dt.date(2026, 7, 1)),
        _co(2, new_completion_date=dt.date(2026, 8, 1)),
    ]
    assert change_orders.latest_completion_date(default, cos) == dt.date(2026, 8, 1)
