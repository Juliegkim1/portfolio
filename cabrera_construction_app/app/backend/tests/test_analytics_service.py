"""Project timeline / concurrency / revenue projection — see
app/services/analytics.py and CLAUDE.md "Business rules". Pure functions
operating on anything with the right attributes."""

import datetime as dt
from types import SimpleNamespace

from app.services import analytics


def _project(start, end, status="active"):
    return SimpleNamespace(start_date=start, end_date=end, status=status)


def _milestone(due_date, amount, status):
    return SimpleNamespace(due_date=due_date, amount=amount, status=status)


def test_weekly_concurrency_empty_without_dated_projects():
    assert analytics.weekly_concurrency([]) == []
    assert analytics.weekly_concurrency([_project(None, None)]) == []


def test_weekly_concurrency_counts_overlap_across_weeks():
    # Jan 5 and Jan 12, 2026 are both Mondays — two full-week projects,
    # overlapping for exactly the Jan 12 week.
    projects = [
        _project(dt.date(2026, 1, 5), dt.date(2026, 1, 18)),  # weeks of Jan 5 & Jan 12
        _project(dt.date(2026, 1, 12), dt.date(2026, 1, 25)),  # weeks of Jan 12 & Jan 19
    ]
    rows = analytics.weekly_concurrency(projects)
    counts = {row["week_start"]: row["count"] for row in rows}
    assert counts[dt.date(2026, 1, 5)] == 1  # only the first project
    assert counts[dt.date(2026, 1, 12)] == 2  # both overlap
    assert counts[dt.date(2026, 1, 19)] == 1  # only the second project


def test_weekly_concurrency_excludes_pending_by_default():
    projects = [_project(dt.date(2026, 1, 1), dt.date(2026, 1, 7), status="pending")]
    rows = analytics.weekly_concurrency(projects)
    assert all(row["count"] == 0 for row in rows)


def test_weekly_concurrency_includes_pending_when_asked():
    projects = [_project(dt.date(2026, 1, 1), dt.date(2026, 1, 7), status="pending")]
    rows = analytics.weekly_concurrency(projects, include_pending=True)
    assert any(row["count"] == 1 for row in rows)


def test_weekly_concurrency_projects_list_carries_actual_objects():
    p = _project(dt.date(2026, 1, 1), dt.date(2026, 1, 7))
    rows = analytics.weekly_concurrency([p])
    assert rows[0]["projects"] == [p]


def test_peak_weeks_returns_weeks_matching_max_count():
    concurrency = [
        {"week_start": dt.date(2026, 1, 5), "count": 1},
        {"week_start": dt.date(2026, 1, 12), "count": 3},
        {"week_start": dt.date(2026, 1, 19), "count": 3},
    ]
    assert analytics.peak_weeks(concurrency) == [dt.date(2026, 1, 12), dt.date(2026, 1, 19)]


def test_peak_weeks_empty_input():
    assert analytics.peak_weeks([]) == []


def test_monthly_revenue_projection_buckets_by_paid_status_and_month():
    milestones = [
        _milestone(dt.date(2026, 1, 15), 1000, "paid"),
        _milestone(dt.date(2026, 1, 20), 2000, "scheduled"),
        _milestone(dt.date(2026, 2, 1), 500, "invoiced"),
        _milestone(None, 999, "paid"),  # no due_date — excluded entirely
    ]
    rows = analytics.monthly_revenue_projection([(None, milestones)])
    by_month = {row["month"]: row for row in rows}
    assert by_month["2026-01"]["collected"] == 1000.0
    assert by_month["2026-01"]["scheduled"] == 2000.0
    assert by_month["2026-02"]["scheduled"] == 500.0
    assert "collected" in by_month["2026-02"] and by_month["2026-02"]["collected"] == 0.0


def test_monthly_revenue_projection_empty_input():
    assert analytics.monthly_revenue_projection([]) == []
