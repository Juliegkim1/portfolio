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
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

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
        "completion_date": _fmt_date(project.end_date),
        "agreement_year": str(contract_date.year) if contract_date else "",
        "agreement_month": contract_date.strftime("%B") if contract_date else "",
        "agreement_day": str(contract_date.day) if contract_date else "",
        "pp_attach": "/Yes",
        "wc_carries": "/Yes",
        cancel_field: "/Yes",
        noc_field: "/Yes",
        "sub_no": "/Yes",
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


def generate_scope_schedule_pdf(*, project, scope_schedule, contract_total: float) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - inch

    def line(text: str, size: int = 11, dy: int = 16, bold: bool = False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(inch, y, text)
        y -= dy

    line("Project Scope & Payment Schedule", 16, 24, bold=True)
    line(f"{project.name} — {project.property_address}")
    line(f"Client: {project.customer_name}    Contract total: {_fmt_money(contract_total)}")
    y -= 8
    line("Milestones", 13, 18, bold=True)
    for m in sorted(scope_schedule.milestones, key=lambda m: m.number):
        pct = (float(m.amount) / contract_total * 100) if contract_total else 0
        line(f"{m.number}. {m.title} — {_fmt_money(float(m.amount))} ({pct:.1f}%) — due {_fmt_date(m.due_date)} — {m.status}")
    y -= 8
    line("Material Supply & Responsibility Matrix", 13, 18, bold=True)
    for mi in scope_schedule.materials:
        line(f"{mi.category}: supplied by {mi.supplied_by}, installed by {mi.installed_by} ({mi.qty})")
    y -= 8
    line("Workmanship Warranty", 13, 18, bold=True)
    for para in (scope_schedule.warranty_terms or "").split("\n"):
        line(para, 10, 14)
    c.showPage()
    c.save()
    return buf.getvalue()


def generate_estimate_pdf(*, project, estimate) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - inch

    def line(text: str, size: int = 11, dy: int = 16, bold: bool = False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(inch, y, text)
        y -= dy

    line(f"QuickBooks Estimate {estimate.estimate_number}", 16, 24, bold=True)
    line(f"{project.customer_name} — {project.property_address}")
    y -= 8
    for section in ("demolition", "materials", "labor", "additional_work"):
        items = [li for li in estimate.line_items if li.section == section]
        if not items:
            continue
        line(section.replace("_", " ").title(), 13, 18, bold=True)
        for li in items:
            line(f"  {li.description} — {li.qty} {li.unit} x {_fmt_money(float(li.unit_price))} = {_fmt_money(li.total)}", 10, 14)
        y -= 4
    y -= 4
    line(f"Subtotal: {_fmt_money(estimate.subtotal)}", 12, 16, bold=True)
    line(f"Tax + permits - discount: {_fmt_money(estimate.total - estimate.subtotal)}", 10, 14)
    line(f"Total: {_fmt_money(estimate.total)}", 13, 18, bold=True)
    c.showPage()
    c.save()
    return buf.getvalue()


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        writer.append(PdfReader(io.BytesIO(pdf_bytes)))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def build_contract_package_pdf(*, project, estimate, scope_schedule, contract_package, cancel_days: int = 3) -> bytes:
    """Merges, in order: contract + Notice of Cancellation + Change Order form + CA
    checklist (all from the template, filled), then the generated Scope &
    Payment Schedule, then the estimate — matching the README's merge order."""
    contract_part = fill_contract_pages(
        project=project, estimate=estimate, scope_schedule=scope_schedule, contract_package=contract_package, cancel_days=cancel_days
    )
    scope_part = generate_scope_schedule_pdf(project=project, scope_schedule=scope_schedule, contract_total=estimate.total)
    estimate_part = generate_estimate_pdf(project=project, estimate=estimate)
    return merge_pdfs([contract_part, scope_part, estimate_part])
