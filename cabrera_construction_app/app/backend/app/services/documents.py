"""Contract Package PDF assembly.

Real, local PDF work (no external API needed): `templates/Cabrera_Construction_Home_Improvement_Contract.pdf`
is a genuinely fillable AcroForm (contract pages, Notice of Cancellation,
Change Order form, CA checklist all in one file). We fill its blanks with
pypdf and keep every other word exactly as the template has it, per the
"template text used verbatim" rule. The Scope & Payment Schedule and
Estimate pages are generated with reportlab (there's no real xlsx-render or
QuickBooks-PDF pipeline yet) and merged in after the contract.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import settings


def _default_templates_dir() -> Path:
    # Only valid for local dev, where this file sits 4 levels under
    # cabrera_construction_app/ — a packaged/deployed layout (e.g. the
    # Cloud Run image) doesn't have that many parent directories and must
    # set TEMPLATES_DIR instead, which is why this is computed lazily
    # (only called below when settings.templates_dir is unset) rather than
    # eagerly at import time — eagerly, it would crash on import in prod
    # before the "or" even got a chance to prefer the env var.
    return Path(__file__).resolve().parents[4] / "templates"


TEMPLATE_PATH = Path(settings.templates_dir or _default_templates_dir()) / "Cabrera_Construction_Home_Improvement_Contract.pdf"

_CANCEL_DAY_FIELDS = {3: ("rc_three", "noc_three"), 5: ("rc_five", "noc_five"), 7: ("rc_seven", "noc_seven")}


def _fmt_money(amount: float) -> str:
    return f"${amount:,.2f}"


def _fmt_date(d) -> str:
    return d.strftime("%m/%d/%Y") if d else ""


def _split_street_csz(address: str) -> tuple[str, str]:
    """Splits "148 Willow Creek Dr, Fremont, CA 94536" into the street line
    and the city/state/zip line — the template has these as two separate
    fields (owner_street, owner_csz), and dumping the whole address into
    owner_street while leaving owner_csz blank was a real bug on signed
    contracts. property_address is always "street, city, state zip" (see
    how it's constructed throughout routers/projects.py), so the first
    comma is the real split point."""
    if "," not in address:
        return address, ""
    street, _, rest = address.partition(",")
    return street.strip(), rest.strip()


def _fill_template(field_values: dict) -> bytes:
    reader = PdfReader(str(TEMPLATE_PATH))
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, field_values)
    if writer._root_object.get("/AcroForm"):
        writer.set_need_appearances_writer(True)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def fill_contract_pages(*, project, estimate, scope_schedule, contract_package, cancel_days: int = 3) -> bytes:
    """Fills the contract, Notice of Cancellation and CA checklist fields (pages 1-7 of the template)."""
    milestones = sorted(scope_schedule.milestones, key=lambda m: m.number)[:3]
    pp_fields: dict[str, str] = {}
    for i, m in enumerate(milestones, start=1):
        pp_fields[f"pp_desc_{i}"] = m.title
        pp_fields[f"pp_amt_{i}"] = _fmt_money(float(m.amount))
        pp_fields[f"pp_due_{i}"] = _fmt_date(m.due_date)

    down_payment = float(milestones[0].amount) if milestones else 0.0
    contract_date = scope_schedule.contract_date
    owner_street, owner_csz = _split_street_csz(project.property_address)

    # The approximate completion date is the LAST milestone's own due date,
    # not project.end_date — that field is usually derived from milestone
    # due dates at creation time, but can go stale (a milestone date edited
    # afterward, an older project from before that derivation existed) and
    # this is the one place a wrong completion date actually ends up on a
    # signed document, so it's computed fresh from the schedule itself
    # rather than trusted from the Project row.
    all_milestones_by_date = sorted((m for m in scope_schedule.milestones if m.due_date), key=lambda m: m.due_date)
    completion_date = all_milestones_by_date[-1].due_date if all_milestones_by_date else project.end_date

    cancel_field, noc_field = _CANCEL_DAY_FIELDS.get(cancel_days, _CANCEL_DAY_FIELDS[3])

    values = {
        "project": project.name,
        "description": contract_package.description,
        "owner_name": project.customer_name,
        "owner_street": owner_street,
        "owner_csz": owner_csz,
        "contract_price": _fmt_money(estimate.total),
        "down_payment": _fmt_money(down_payment),
        "finance_charge": _fmt_money(0.0),
        "start_date": _fmt_date(project.start_date),
        "completion_date": _fmt_date(completion_date),
        "agreement_year": str(contract_date.year) if contract_date else "",
        "agreement_month": contract_date.strftime("%B") if contract_date else "",
        "agreement_day": str(contract_date.day) if contract_date else "",
        "pp_attach": "/Yes",
        # Documents 1-3 are the template's own fixed attachments (Notice of
        # Cancellation, Change Order form, CA checklist); 4 and 5 are blank
        # text fields on the template meant for whatever this contract
        # actually attaches — always the Scope & Payment Schedule and the
        # Estimate here, matching the combined PDF's own merge order below.
        "doc4": "Project Scope and Payment Schedule",
        "doc5": "Estimate",
        "wc_carries": "/Yes",
        cancel_field: "/Yes",
        noc_field: "/Yes",
        # Subcontractors: always "No" for now (per the business, not derived
        # from any per-project data yet) — explicitly clearing sub_yes
        # matters because the template ships with it pre-checked by default
        # (confirmed via the template's own field defaults), and it's a
        # separate checkbox widget from sub_no, not one radio group where
        # checking one automatically clears the other.
        "sub_no": "/Yes",
        "sub_yes": "/Off",
        "cl_owner": project.customer_name,
        "cl_project": project.name,
        "cl_contract_date": _fmt_date(contract_date),
        "cl_prepared_by": "Cabrera Construction",
        **pp_fields,
    }
    return _fill_template(values)


def fill_change_order_pages(
    *, project, change_order, contract_date, original_price: float, previously_signed_price: float, new_price: float
) -> bytes:
    values = {
        "co_owner": project.customer_name,
        "co_project": project.name,
        "co_number": str(change_order.number),
        "co_date": _fmt_date(change_order.created_at.date() if change_order.created_at else None),
        "co_contract_date": _fmt_date(contract_date),
        "co_contractor": "Cabrera Construction",
        "co_scope": change_order.scope,
        "co_orig_price": _fmt_money(original_price),
        "co_add": _fmt_money(float(change_order.amount_added)),
        "co_sub": _fmt_money(float(change_order.amount_subtracted)),
        "co_new_price": _fmt_money(new_price),
        "co_old_completion": _fmt_date(project.end_date),
        "co_new_completion": _fmt_date(change_order.new_completion_date),
        "co_pp_effect": "See revised Project Scope & Payment Schedule.",
        "co_sub_yes" if change_order.uses_subcontractors else "co_sub_no": "/Yes",
    }
    # co_orig_price on the form is meant to read the *previously* signed price label-wise;
    # keep both numbers available via co_orig_price/co_add/co_sub/co_new_price per the template.
    values["co_orig_price"] = _fmt_money(previously_signed_price)
    return _fill_template(values)


_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("CabreraTitle", parent=_STYLES["Title"], fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=2, textColor=colors.black)
_SUBTITLE_STYLE = ParagraphStyle("CabreraSubtitle", parent=_STYLES["Normal"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=colors.HexColor("#444444"))
_SECTION_STYLE = ParagraphStyle("CabreraSection", parent=_STYLES["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, spaceBefore=16, spaceAfter=6, textColor=colors.black)
_BODY_STYLE = ParagraphStyle("CabreraBody", parent=_STYLES["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.black)
_CELL_STYLE = ParagraphStyle("CabreraCell", parent=_BODY_STYLE, fontSize=9, leading=12)
_CELL_STYLE_RIGHT = ParagraphStyle("CabreraCellRight", parent=_CELL_STYLE, alignment=TA_CENTER)

_TABLE_GRID = colors.HexColor("#b8b8b8")
_TABLE_HEADER_TEXT = colors.black

# Deliberately no fill colors anywhere in this document — white page, black
# text, hairline rules only. "Professional" here means real tables with
# aligned columns and consistent spacing, not a colored/branded look.


def _letterhead(title: str, project, extra_line: str | None = None) -> list:
    flow = [
        Paragraph(title, _TITLE_STYLE),
        Paragraph(f"{project.name} &mdash; {project.property_address}", _SUBTITLE_STYLE),
    ]
    if extra_line:
        flow.append(Paragraph(extra_line, _SUBTITLE_STYLE))
    flow.append(Spacer(1, 6))
    flow.append(HRFlowable(width="100%", thickness=1.1, color=colors.black, spaceAfter=10))
    return flow


def _cell(text: str, style: ParagraphStyle = _CELL_STYLE) -> Paragraph:
    # Wrapped in a Paragraph (not a bare string) so long text — a milestone
    # title, a material notes column — wraps within its column instead of
    # overflowing or forcing the table wider than the page.
    return Paragraph(text if text else "&nbsp;", style)


def generate_scope_schedule_pdf(*, project, scope_schedule, contract_total: float) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch, topMargin=0.85 * inch, bottomMargin=0.75 * inch,
    )
    story: list = _letterhead(
        "Project Scope & Payment Schedule",
        project,
        f"Client: {project.customer_name} &nbsp;&nbsp;|&nbsp;&nbsp; Contract Total: {_fmt_money(contract_total)}",
    )

    story.append(Paragraph("Payment Milestones", _SECTION_STYLE))
    milestone_rows = [["#", "Milestone", "Amount", "%", "Due Date", "Status"]]
    for m in sorted(scope_schedule.milestones, key=lambda m: m.number):
        pct = (float(m.amount) / contract_total * 100) if contract_total else 0
        milestone_rows.append([
            _cell(str(m.number)),
            _cell(m.title),
            _cell(_fmt_money(float(m.amount))),
            _cell(f"{pct:.1f}%"),
            _cell(_fmt_date(m.due_date) or "—"),
            _cell((m.status or "").replace("_", " ").title()),
        ])
    milestone_table = Table(milestone_rows, colWidths=[0.3 * inch, 2.5 * inch, 0.95 * inch, 0.55 * inch, 0.95 * inch, 0.85 * inch], repeatRows=1)
    milestone_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), _TABLE_HEADER_TEXT),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, _TABLE_GRID),
        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(milestone_table)

    if scope_schedule.materials:
        story.append(Paragraph("Material Supply &amp; Responsibility Matrix", _SECTION_STYLE))
        material_rows = [["Category", "Qty", "Supplied By", "Installed By", "Notes"]]
        for mi in scope_schedule.materials:
            material_rows.append([
                _cell(mi.category),
                _cell(mi.qty or "—"),
                _cell((mi.supplied_by or "").title()),
                _cell((mi.installed_by or "").title()),
                _cell(mi.notes or "—"),
            ])
        material_table = Table(material_rows, colWidths=[1.6 * inch, 0.7 * inch, 1.15 * inch, 1.15 * inch, 1.6 * inch], repeatRows=1)
        material_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, _TABLE_GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(material_table)

    story.append(Paragraph("Workmanship Warranty", _SECTION_STYLE))
    for para in (scope_schedule.warranty_terms or "").split("\n"):
        if para.strip():
            story.append(Paragraph(para, _BODY_STYLE))
        else:
            story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()


def generate_estimate_summary_page(*, estimate) -> bytes:
    """The Contract Package's last-page fallback when no real estimate PDF
    has been uploaded (see POST /projects/{id}/estimate/upload-pdf) — just
    the estimate number and total, not a reconstructed line-item breakdown.
    A prior version tried to recreate the full estimate from extracted
    data, which looked fine for a real QuickBooks DocNumber but produced a
    visibly synthetic label for anything else (e.g. "QuickBooks Estimate
    DOC-Pasted notes" for a pasted-text estimate) — this is deliberately
    minimal instead of trying to paper over that gap."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.85 * inch, rightMargin=0.85 * inch, topMargin=1.2 * inch, bottomMargin=1.2 * inch)
    story = [
        Paragraph("Estimate", _TITLE_STYLE),
        HRFlowable(width="100%", thickness=1.1, color=colors.black, spaceAfter=18, spaceBefore=6),
        Paragraph(f"Estimate #: {estimate.estimate_number}", _SECTION_STYLE),
        Paragraph(f"Total: {_fmt_money(estimate.total)}", _BODY_STYLE),
    ]
    doc.build(story)
    return buf.getvalue()


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        writer.append(PdfReader(io.BytesIO(pdf_bytes)))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def build_contract_package_pdf(
    *, project, estimate, scope_schedule, contract_package, cancel_days: int = 3, estimate_pdf_bytes: bytes | None = None
) -> bytes:
    """Merges, in order: contract + Notice of Cancellation + Change Order form + CA
    checklist (all from the template, filled), then the generated Scope &
    Payment Schedule, then the estimate — matching the README's merge order
    and the "doc4"/"doc5" labels filled on page 1 above.

    estimate_pdf_bytes is the REAL estimate document (see
    routers/projects.py's POST .../estimate/upload-pdf) when the caller has
    one — callers are responsible for fetching it from Drive via
    estimate.source_file_id before calling this, since this module has no
    Drive/DB access of its own. Falls back to generate_estimate_summary_page
    (just the estimate number and total) when there's no real document to
    attach, rather than reconstructing a recreation from extracted data."""
    contract_part = fill_contract_pages(
        project=project, estimate=estimate, scope_schedule=scope_schedule, contract_package=contract_package, cancel_days=cancel_days
    )
    scope_part = generate_scope_schedule_pdf(project=project, scope_schedule=scope_schedule, contract_total=estimate.total)
    estimate_part = estimate_pdf_bytes if estimate_pdf_bytes else generate_estimate_summary_page(estimate=estimate)
    return merge_pdfs([contract_part, scope_part, estimate_part])
