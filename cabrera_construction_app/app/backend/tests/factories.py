"""Minimal ORM object builders for tests — construct fixtures directly
against the DB instead of going through the creation endpoints, which pull
in Google/QuickBooks/AI integrations that are out of scope for these tests."""

from __future__ import annotations

import datetime as dt

from app import models


def make_project(db, **overrides) -> models.Project:
    defaults = dict(
        name="Jane Doe — 123 Main St",
        project_type="Kitchen Remodel",
        customer_name="Jane Doe",
        customer_phone="(555) 555-0100",
        customer_email="jane@example.com",
        property_address="123 Main St, Springfield, CA 90000",
        start_date=dt.date(2026, 1, 1),
        end_date=dt.date(2026, 3, 1),
        status="active",
    )
    defaults.update(overrides)
    project = models.Project(**defaults)
    db.add(project)
    db.flush()
    return project


def make_estimate(db, project: models.Project, **overrides) -> models.Estimate:
    defaults = dict(
        project_id=project.id,
        estimate_number="1042",
        date_issued=dt.date(2026, 1, 1),
        tax_rate=0.0,
        permit_fees=0,
        discount=0,
        scope_text="Full kitchen remodel.",
    )
    defaults.update(overrides)
    estimate = models.Estimate(**defaults)
    db.add(estimate)
    db.flush()
    return estimate


def make_line_item(db, estimate: models.Estimate, **overrides) -> models.EstimateLineItem:
    defaults = dict(
        estimate_id=estimate.id,
        section="materials",
        description="Cabinets",
        qty=1,
        unit="ea",
        unit_price=5000,
    )
    defaults.update(overrides)
    item = models.EstimateLineItem(**defaults)
    db.add(item)
    db.flush()
    return item
