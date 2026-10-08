from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services import analytics as analytics_rules
from ..services import change_orders as co_rules

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics")
def get_analytics(include_pending: bool = False, db: Session = Depends(get_db)):
    projects = db.query(models.Project).all()
    signed_projects = [p for p in projects if p.contract_package and p.contract_package.status == "signed"]
    pending_projects = [p for p in projects if p.contract_package and p.contract_package.status != "signed"]

    today = dt.date.today()
    in_progress_today = sum(1 for p in signed_projects if p.start_date and p.end_date and p.start_date <= today <= p.end_date)

    signed_contract_value = 0.0
    revenue_rows: list[tuple] = []
    for p in signed_projects:
        estimate_total = p.estimate.total if p.estimate else 0.0
        all_cos = sorted(p.change_orders, key=lambda c: c.number)
        revised = co_rules.revised_contract_total(estimate_total, all_cos)
        signed_contract_value += revised
        if p.scope_schedule:
            revenue_rows.append((p, p.scope_schedule.milestones))

    collected_to_date = sum(
        float(m.amount) for _p, milestones in revenue_rows for m in milestones if m.status == "paid"
    )
    projected_remaining = signed_contract_value - collected_to_date

    ninety_days_out = today + dt.timedelta(days=90)
    due_next_90 = sum(
        float(m.amount)
        for _p, milestones in revenue_rows
        for m in milestones
        if m.status != "paid" and m.due_date and today <= m.due_date <= ninety_days_out
    )

    concurrency_pool = signed_projects + (pending_projects if include_pending else [])
    concurrency = analytics_rules.weekly_concurrency(concurrency_pool, include_pending=include_pending)
    peaks = analytics_rules.peak_weeks(concurrency)
    revenue_projection = analytics_rules.monthly_revenue_projection(revenue_rows)

    def project_row(p: models.Project) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "signed": p in signed_projects,
        }

    return {
        "kpis": {
            "in_progress_today": in_progress_today,
            "signed_contract_value": round(signed_contract_value, 2),
            "projected_remaining": round(projected_remaining, 2),
            "due_next_90_days": round(due_next_90, 2),
            "collected_to_date": round(collected_to_date, 2),
        },
        "timeline": [project_row(p) for p in projects if p.start_date and p.end_date],
        "concurrency": [
            {
                "week_start": row["week_start"],
                "count": row["count"],
                "projects": [
                    {"id": p.id, "name": p.name, "customer_name": p.customer_name, "property_address": p.property_address}
                    for p in row["projects"]
                ],
            }
            for row in concurrency
        ],
        "peak_weeks": peaks,
        "revenue_projection": revenue_projection,
        "revenue_by_project": [
            {
                "project_id": p.id,
                "project_name": p.name,
                "total": round(co_rules.revised_contract_total(p.estimate.total if p.estimate else 0.0, sorted(p.change_orders, key=lambda c: c.number)), 2),
                "collected": round(sum(float(m.amount) for m in milestones if m.status == "paid"), 2),
            }
            for p, milestones in revenue_rows
        ],
    }
