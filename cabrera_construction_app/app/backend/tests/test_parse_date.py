"""_parse_date is asked for ISO (YYYY-MM-DD) in every extraction prompt,
but a receipt's own printed date is often MM/DD/YY on the register tape
itself -- a model occasionally echoes that literal format instead of
converting it. Falling straight to None on any non-ISO format (as this
used to) meant that case silently became "no date" -- and downstream,
receipt_sync.py treats no date as today's date, which reads as a wrong
parse rather than a missing one."""

import datetime as dt

from app.services.gemini_service import _parse_date


def test_parses_iso_format():
    assert _parse_date("2026-09-16") == dt.date(2026, 9, 16)


def test_parses_us_slash_format_with_four_digit_year():
    assert _parse_date("09/16/2026") == dt.date(2026, 9, 16)


def test_parses_us_slash_format_with_two_digit_year():
    assert _parse_date("9/16/26") == dt.date(2026, 9, 16)


def test_parses_us_dash_format():
    assert _parse_date("09-16-2026") == dt.date(2026, 9, 16)


def test_returns_none_for_unparseable_value():
    assert _parse_date("not a date") is None


def test_returns_none_for_empty_value():
    assert _parse_date(None) is None
    assert _parse_date("") is None
