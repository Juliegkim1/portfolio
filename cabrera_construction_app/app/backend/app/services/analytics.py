"""Analytics: project timeline, weekly concurrency, revenue projection.

Rules (CLAUDE.md / Design Document §04, §09):
- Concurrency = number of signed (and optionally pending) projects whose
  start-end range overlaps each week.
- Revenue projection counts signed contracts only, split into collected
  (paid milestones) vs. scheduled (unpaid milestones), by month.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict


def _week_start(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def weekly_concurrency(projects: list, include_pending: bool = False) -> list[dict]:
    """projects: list of objects with .start_date, .end_date, .status ('active'|'completed'|'on_hold')."""
    ranged = [p for p in projects if p.start_date and p.end_date]
    if not ranged:
        return []

    def counts_project(p) -> bool:
        if include_pending:
            return True
        return p.status in ("active", "completed")

    min_week = _week_start(min(p.start_date for p in ranged))
    max_week = _week_start(max(p.end_date for p in ranged))

    weeks = []
    w = min_week
    while w <= max_week:
        weeks.append(w)
        w += dt.timedelta(days=7)

    result = []
    for week in weeks:
        week_end = week + dt.timedelta(days=6)
        overlapping = [p for p in ranged if counts_project(p) and p.start_date <= week_end and p.end_date >= week]
        result.append({"week_start": week, "count": len(overlapping), "projects": overlapping})
    return result


def peak_weeks(concurrency: list[dict]) -> list[dt.date]:
    if not concurrency:
        return []
    peak = max(row["count"] for row in concurrency)
    if peak == 0:
        return []
    return [row["week_start"] for row in concurrency if row["count"] == peak]


def monthly_revenue_projection(signed_projects_with_milestones: list[tuple]) -> list[dict]:
    """signed_projects_with_milestones: list of (project, milestones) for signed-contract projects only.

    Returns rows keyed by month (YYYY-MM) with collected vs scheduled totals,
    based on each milestone's due_date and status.
    """
    by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"collected": 0.0, "scheduled": 0.0})
    for _project, milestones in signed_projects_with_milestones:
        for m in milestones:
            if not m.due_date:
                continue
            key = f"{m.due_date.year:04d}-{m.due_date.month:02d}"
            bucket = "collected" if m.status == "paid" else "scheduled"
            by_month[key][bucket] += float(m.amount)

    return [
        {"month": month, "collected": round(v["collected"], 2), "scheduled": round(v["scheduled"], 2)}
        for month, v in sorted(by_month.items())
    ]
