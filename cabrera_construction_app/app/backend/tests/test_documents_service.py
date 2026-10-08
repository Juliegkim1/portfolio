"""generate_scope_schedule_pdf — mirrors every field on the Scope & Payment
Schedule screen, formatted to match templates/Project Scope & Payment
Schedule - Template.xlsx. Real PDF generation (reportlab) + real text
extraction (pypdf) — no DB needed beyond what the `db` fixture gives us to
build realistic ORM objects quickly."""

from __future__ import annotations

import datetime as dt
import io
import re

from pypdf import PdfReader

from app import models
from app.services import documents
from tests.factories import make_estimate, make_line_item, make_project


def _extract_text(pdf_bytes: bytes) -> str:
    # pypdf wraps long table-cell text at arbitrary points when extracting,
    # inserting newlines mid-sentence — collapse all whitespace to single
    # spaces so substring assertions aren't sensitive to reportlab's/pypdf's
    # exact wrapping, only to the actual words present.
    reader = PdfReader(io.BytesIO(pdf_bytes))
    raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", raw)


def _build_scope_schedule(db, project):
    scope_schedule = models.ScopeSchedule(
        project_id=project.id,
        contract_date=dt.date(2026, 1, 1),
        contract_type="Fixed-Price Agreement",
        warranty_terms="1-YEAR WORKMANSHIP WARRANTY POLICY",
    )
    db.add(scope_schedule)
    db.flush()
    db.add(
        models.Milestone(
            scope_schedule_id=scope_schedule.id,
            number=0,
            title="Deposit at Signing",
            amount=1000,
            due_date=dt.date(2026, 1, 5),
            scope_verification="Covers initial mobilization and planning.",
        )
    )
    db.add(
        models.Milestone(
            scope_schedule_id=scope_schedule.id,
            number=1,
            title="Final Walkthrough",
            amount=9000,
            due_date=dt.date(2026, 3, 1),
            scope_verification="Covers final punch list and sign-off.",
        )
    )
    db.add(
        models.MaterialItem(
            scope_schedule_id=scope_schedule.id,
            category="Custom Cabinetry",
            qty="1 set",
            supplied_by="contractor",
            installed_by="contractor",
            notes="Ordered from Riverside Millwork",
        )
    )
    db.commit()
    db.refresh(scope_schedule)
    return scope_schedule


def test_generate_scope_schedule_pdf_includes_every_page_field(db):
    project = make_project(db, property_address="123 Main St, Springfield, CA 90000")
    estimate = make_estimate(db, project, scope_text="Full kitchen remodel with custom cabinetry.")
    make_line_item(db, estimate, unit_price=10000)
    db.commit()
    scope_schedule = _build_scope_schedule(db, project)

    pdf_bytes = documents.generate_scope_schedule_pdf(project=project, estimate=estimate, scope_schedule=scope_schedule, contract_total=estimate.total)
    text = _extract_text(pdf_bytes)

    # Project details strip
    assert "123 Main St" in text
    assert estimate.estimate_number in text
    assert "Full kitchen remodel with custom cabinetry" in text

    # Milestones, each with its own Detailed Scope & Verification summary
    assert "Deposit at Signing" in text
    assert "Covers initial mobilization and planning" in text
    assert "Final Walkthrough" in text
    assert "Covers final punch list and sign" in text

    # Summary strip + totals row
    assert "10,000.00" in text
    assert "Balanced" in text

    # Material matrix
    assert "Custom Cabinetry" in text
    assert "Riverside Millwork" in text

    # Warranty + signature block (template fidelity)
    assert "WORKMANSHIP WARRANTY" in text.upper()
    assert "SIGNATURE ACKNOWLEDGMENT" in text.upper()
    assert "Sam Cabrera" in text


def test_generate_scope_schedule_pdf_flags_unbalanced_schedule(db):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=10000)
    db.commit()
    scope_schedule = models.ScopeSchedule(project_id=project.id, contract_type="Fixed-Price Agreement")
    db.add(scope_schedule)
    db.flush()
    db.add(models.Milestone(scope_schedule_id=scope_schedule.id, number=0, title="Deposit", amount=1000))
    db.commit()
    db.refresh(scope_schedule)

    pdf_bytes = documents.generate_scope_schedule_pdf(project=project, estimate=estimate, scope_schedule=scope_schedule, contract_total=estimate.total)
    text = _extract_text(pdf_bytes)

    assert "Short by" in text


def test_generate_scope_schedule_pdf_omits_material_section_when_none(db):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate, unit_price=1000)
    db.commit()
    scope_schedule = models.ScopeSchedule(project_id=project.id, contract_type="Fixed-Price Agreement")
    db.add(scope_schedule)
    db.flush()
    db.add(models.Milestone(scope_schedule_id=scope_schedule.id, number=0, title="Full Payment", amount=1000))
    db.commit()
    db.refresh(scope_schedule)

    pdf_bytes = documents.generate_scope_schedule_pdf(project=project, estimate=estimate, scope_schedule=scope_schedule, contract_total=estimate.total)
    text = _extract_text(pdf_bytes)

    assert "Material Supply" not in text
