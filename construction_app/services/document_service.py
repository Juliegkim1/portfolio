"""Generates PDF documents using ReportLab (pure Python, no system libs required)."""
import os
from collections import defaultdict
from datetime import date
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

from config import COMPANY, PDF_OUTPUT_DIR
from models import Estimate, Invoice, Project
from models.invoice import Invoice

BRAND = colors.HexColor("#1a3a5c")
LIGHT_BLUE = colors.HexColor("#dce6f1")
WHITE = colors.white
GREY = colors.HexColor("#555555")
GREEN = colors.HexColor("#155724")
ORANGE = colors.HexColor("#856404")
RED = colors.HexColor("#721c24")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("company", fontSize=16, textColor=BRAND, alignment=TA_CENTER,
                          spaceAfter=2, fontName="Helvetica-Bold"))
    s.add(ParagraphStyle("sub", fontSize=8, textColor=GREY, alignment=TA_CENTER, spaceAfter=1))
    s.add(ParagraphStyle("section_hdr", fontSize=9, textColor=WHITE, fontName="Helvetica-Bold",
                          backColor=BRAND, leftIndent=4, spaceAfter=0, spaceBefore=4))
    s.add(ParagraphStyle("small", fontSize=8, textColor=GREY, spaceAfter=2))
    s.add(ParagraphStyle("small_right", fontSize=8, textColor=GREY, alignment=TA_RIGHT))
    s.add(ParagraphStyle("body", fontSize=9, spaceAfter=2))
    s.add(ParagraphStyle("total_label", fontSize=10, fontName="Helvetica-Bold",
                          textColor=WHITE, alignment=TA_RIGHT))
    s.add(ParagraphStyle("total_val", fontSize=10, fontName="Helvetica-Bold",
                          textColor=WHITE, alignment=TA_RIGHT))
    return s


def _company_header(styles) -> list:
    return [
        Paragraph(COMPANY["name"], styles["company"]),
        Paragraph(COMPANY["license"], styles["sub"]),
        Paragraph(COMPANY["address"], styles["sub"]),
        Paragraph(f"Tel: {COMPANY['phone']}  ·  {COMPANY['email']}", styles["sub"]),
        HRFlowable(width="100%", thickness=2, color=BRAND, spaceAfter=6),
    ]


def _footer_para(styles) -> list:
    text = (f"{COMPANY['representative']}  |  {COMPANY['name']}  |  "
            f"{COMPANY['license']}  |  Tel: {COMPANY['phone']}  |  {COMPANY['email']}")
    return [
        HRFlowable(width="100%", thickness=0.5, color=GREY, spaceBefore=8),
        Paragraph(text, styles["small"]),
    ]


class DocumentService:
    def __init__(self):
        self._styles = _styles()

    def _make_doc(self, filename: str):
        path = os.path.join(PDF_OUTPUT_DIR, filename)
        return SimpleDocTemplate(path, pagesize=letter,
                                  leftMargin=0.6*inch, rightMargin=0.6*inch,
                                  topMargin=0.5*inch, bottomMargin=0.5*inch), path

    # ── Estimate PDF ──────────────────────────────────────────────────────────

    def generate_estimate_pdf(self, project: Project, estimate: Estimate) -> str:
        s = self._styles
        filename = f"estimate_{estimate.estimate_number.replace(' ', '_')}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)

        # Title + meta
        meta_data = [
            ["ESTIMATE #", estimate.estimate_number],
            ["DATE", str(estimate.date_issued)],
            ["VALID UNTIL", str(estimate.valid_until)],
            ["PREPARED BY", estimate.prepared_by or COMPANY["representative"]],
        ]
        meta_table = Table([[
            Paragraph("PROJECT ESTIMATE", ParagraphStyle(
                "h2", fontSize=14, fontName="Helvetica-Bold", textColor=BRAND)),
            Table(meta_data, colWidths=[1.2*inch, 1.8*inch],
                  style=TableStyle([
                      ("FONTSIZE", (0,0), (-1,-1), 8),
                      ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                      ("TEXTCOLOR", (0,0), (0,-1), BRAND),
                      ("ALIGN", (0,0), (-1,-1), "LEFT"),
                      ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, colors.white]),
                  ]))
        ]], colWidths=[3.5*inch, 3.5*inch])
        meta_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.append(meta_table)
        story.append(Spacer(1, 6))

        # Bill to / job site
        bill_data = [[
            [Paragraph("<b>BILL TO</b>", ParagraphStyle("bt", fontSize=8, textColor=BRAND,
                                                         fontName="Helvetica-Bold")),
             Paragraph(project.customer_name, ParagraphStyle("bt2", fontSize=9)),
             Paragraph(project.property_address, s["small"]),
             Paragraph(project.customer_phone, s["small"]),
             Paragraph(project.customer_email, s["small"])],
            [Paragraph("<b>JOB SITE</b>", ParagraphStyle("js", fontSize=8, textColor=BRAND,
                                                           fontName="Helvetica-Bold")),
             Paragraph(project.property_address, s["small"]),
             Spacer(1, 4),
             Paragraph("<b>PROJECT TYPE</b>", ParagraphStyle("pt", fontSize=8, textColor=BRAND,
                                                              fontName="Helvetica-Bold")),
             Paragraph(project.project_type, s["small"])],
        ]]
        bill_table = Table(bill_data, colWidths=[3.5*inch, 3.5*inch])
        bill_table.setStyle(TableStyle([
            ("BOX", (0,0), (0,0), 0.5, LIGHT_BLUE),
            ("BOX", (1,0), (1,0), 0.5, LIGHT_BLUE),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(bill_table)
        story.append(Spacer(1, 8))

        # Line items
        by_section = defaultdict(list)
        for item in estimate.line_items:
            by_section[item.section].append(item)

        header_row = [
            Paragraph("<b>#</b>", s["small"]),
            Paragraph("<b>Description of Work</b>", s["small"]),
            Paragraph("<b>Qty</b>", s["small"]),
            Paragraph("<b>Unit</b>", s["small"]),
            Paragraph("<b>Unit Price ($)</b>", s["small"]),
            Paragraph("<b>Total ($)</b>", s["small"]),
        ]
        table_data = [header_row]
        table_styles = [
            ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
            ("TEXTCOLOR", (0,0), (-1,0), BRAND),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f8f8")]),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("ALIGN", (2,0), (-1,-1), "RIGHT"),
        ]
        row_idx = 1
        for section, items in by_section.items():
            table_data.append([
                Paragraph(f"  {section}", ParagraphStyle(
                    "sh", fontSize=8, fontName="Helvetica-Bold",
                    textColor=WHITE, backColor=BRAND)),
                "", "", "", "", ""
            ])
            table_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), BRAND))
            table_styles.append(("SPAN", (0, row_idx), (-1, row_idx)))
            row_idx += 1
            for item in items:
                table_data.append([
                    str(item.line_number),
                    Paragraph(item.description, s["small"]),
                    f"{item.qty:.2f}",
                    item.unit,
                    f"${item.unit_price:,.2f}",
                    f"${item.total:,.2f}",
                ])
                row_idx += 1

        line_table = Table(table_data,
                           colWidths=[0.35*inch, 2.8*inch, 0.55*inch,
                                      0.55*inch, 1.0*inch, 1.0*inch])
        line_table.setStyle(TableStyle(table_styles))
        story.append(line_table)
        story.append(Spacer(1, 4))

        # Totals
        totals = [
            ["Subtotal", f"${estimate.subtotal:,.2f}"],
            [f"Tax ({estimate.tax_rate*100:.1f}%)", f"${estimate.tax_amount:,.2f}"],
            ["Permit / Inspection Fees", f"${estimate.permit_fees:,.2f}"],
            ["Discount", f"-${estimate.discount:,.2f}"],
        ]
        totals_table = Table(totals + [["TOTAL ESTIMATE", f"${estimate.total:,.2f}"]],
                              colWidths=[2.0*inch, 1.2*inch], hAlign="RIGHT")
        totals_table.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("TEXTCOLOR", (0,0), (-1,-2), GREY),
            ("BACKGROUND", (0,-1), (-1,-1), BRAND),
            ("TEXTCOLOR", (0,-1), (-1,-1), WHITE),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,-1), (-1,-1), 11),
        ]))
        story.append(totals_table)

        # Payment schedule
        if estimate.payment_schedule:
            story.append(Spacer(1, 8))
            story.append(Paragraph("  PAYMENT SCHEDULE", s["section_hdr"]))
            ps_data = [[
                Paragraph("<b>Payment</b>", s["small"]),
                Paragraph("<b>Description</b>", s["small"]),
                Paragraph("<b>Due Date</b>", s["small"]),
                Paragraph("<b>Amount ($)</b>", s["small"]),
                Paragraph("<b>Status</b>", s["small"]),
            ]]
            for ps in estimate.payment_schedule:
                ps_data.append([
                    ps.label,
                    Paragraph(ps.description, s["small"]),
                    str(ps.due_date or "—"),
                    f"${ps.amount:,.2f}",
                    ps.status,
                ])
            ps_table = Table(ps_data, colWidths=[0.6*inch, 2.4*inch, 1.0*inch, 1.0*inch, 0.8*inch])
            ps_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f8f8")]),
            ]))
            story.append(ps_table)

        # Terms
        story.append(Spacer(1, 8))
        terms = ("1. This estimate is valid for 30 days from the date issued. "
                 "2. Any changes to the scope of work will require a written change order. "
                 "3. Cabrera Construction is not responsible for delays caused by weather or "
                 "conditions beyond our control. "
                 "4. A signed copy constitutes acceptance of the proposed scope and price.")
        story.append(Paragraph(terms, ParagraphStyle("terms", fontSize=7, textColor=GREY,
                                                      backColor=colors.HexColor("#f9f9f9"),
                                                      borderPadding=4, spaceAfter=4)))

        # Signatures
        story.append(Spacer(1, 12))
        sig_data = [
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph("Customer / Authorized Representative", s["small"]),
             Paragraph("Samuel Cabrera, Cabrera Construction", s["small"])],
            [Paragraph("Date: _______________", s["small"]),
             Paragraph("Date: _______________", s["small"])],
        ]
        sig_table = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
        sig_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.append(sig_table)

        story += _footer_para(s)
        doc.build(story)
        return path

    # ── Invoice PDF ───────────────────────────────────────────────────────────

    def generate_invoice_pdf(self, project: Project, invoice: Invoice) -> str:
        s = self._styles
        filename = f"invoice_{invoice.invoice_number.replace(' ', '_')}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)

        status_color = {"paid": GREEN, "open": ORANGE, "void": RED, "draft": GREY}.get(
            invoice.status, BRAND)

        meta_data = [
            ["INVOICE #", invoice.invoice_number],
            ["DATE ISSUED", str(invoice.date_issued or "—")],
            ["DUE DATE", str(invoice.due_date or "—")],
            ["STATUS", invoice.status.upper()],
        ]
        meta_table = Table([[
            Paragraph("INVOICE", ParagraphStyle("inv_h", fontSize=14,
                                                 fontName="Helvetica-Bold", textColor=BRAND)),
            Table(meta_data, colWidths=[1.2*inch, 1.8*inch],
                  style=TableStyle([
                      ("FONTSIZE", (0,0), (-1,-1), 8),
                      ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                      ("TEXTCOLOR", (0,0), (0,-1), BRAND),
                      ("TEXTCOLOR", (1,3), (1,3), status_color),
                      ("FONTNAME", (1,3), (1,3), "Helvetica-Bold"),
                  ]))
        ]], colWidths=[3.5*inch, 3.5*inch])
        story.append(meta_table)
        story.append(Spacer(1, 8))

        # Description + totals
        detail_data = [
            [Paragraph("<b>Description</b>", s["small"]),
             Paragraph("<b>Amount ($)</b>", s["small"])],
            [Paragraph(invoice.description, s["body"]), f"${invoice.amount:,.2f}"],
        ]
        detail_table = Table(detail_data, colWidths=[5.0*inch, 2.0*inch])
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 4))

        totals = [
            ["Subtotal", f"${invoice.amount:,.2f}"],
            ["Tax", f"${invoice.tax_amount:,.2f}"],
            ["TOTAL DUE", f"${invoice.total:,.2f}"],
        ]
        t = Table(totals, colWidths=[2.0*inch, 1.2*inch], hAlign="RIGHT")
        t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("TEXTCOLOR", (0,0), (-1,-2), GREY),
            ("BACKGROUND", (0,-1), (-1,-1), BRAND),
            ("TEXTCOLOR", (0,-1), (-1,-1), WHITE),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ]))
        story.append(t)

        if invoice.stripe_invoice_url:
            story.append(Spacer(1, 8))
            story.append(Paragraph(
                f"<b>Pay online via Stripe:</b> {invoice.stripe_invoice_url}",
                ParagraphStyle("stripe", fontSize=8, textColor=BRAND,
                                backColor=colors.HexColor("#f0f7ff"), borderPadding=6)))

        if invoice.status == "paid" and invoice.payment_date:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>Payment Received:</b> {invoice.payment_date}",
                                    ParagraphStyle("paid_note", fontSize=9,
                                                    textColor=GREEN, backColor=colors.HexColor("#d4edda"),
                                                    borderPadding=4)))

        if invoice.notes:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>Notes:</b> {invoice.notes}", s["small"]))

        story += _footer_para(s)
        doc.build(story)
        return path

    # ── Reconciliation PDF ────────────────────────────────────────────────────

    def generate_reconciliation_pdf(self, project: Project, invoices: list,
                                     contract_amount: float, notes: str = "") -> str:
        s = self._styles
        filename = f"reconciliation_{project.name.replace(' ', '_')}_{date.today()}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)

        paid_invoices = [inv for inv in invoices if inv.status == "paid"]
        total_paid = sum(inv.total for inv in paid_invoices)
        net_adjustments = 0.0
        balance_due = contract_amount + net_adjustments - total_paid

        story.append(Paragraph("PROJECT ACCOUNT RECONCILIATION",
                                ParagraphStyle("rec_h", fontSize=13, fontName="Helvetica-Bold",
                                                textColor=WHITE, backColor=BRAND,
                                                alignment=TA_CENTER, spaceAfter=4,
                                                borderPadding=6)))
        story.append(Paragraph(f"{project.property_address}  |  {project.name}",
                                ParagraphStyle("rec_sub", fontSize=9, textColor=GREY,
                                                alignment=TA_CENTER, spaceAfter=8)))

        # Summary cards — 2-row table: labels on top, values below
        _lbl_st = ParagraphStyle("cl", fontSize=8, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, textColor=GREY)
        _val_st = ParagraphStyle("cv", fontSize=11, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER)
        _val_wh = ParagraphStyle("cvw", fontSize=11, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, textColor=WHITE)
        card_labels = [Paragraph("Original Contract", _lbl_st),
                       Paragraph("Total Paid", _lbl_st),
                       Paragraph("Change Orders", _lbl_st),
                       Paragraph("BALANCE DUE", ParagraphStyle("clw", fontSize=8,
                           fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=WHITE))]
        card_values = [Paragraph(f"${contract_amount:,.2f}", _val_st),
                       Paragraph(f"${total_paid:,.2f}", _val_st),
                       Paragraph(f"${net_adjustments:,.2f}", _val_st),
                       Paragraph(f"${balance_due:,.2f}", _val_wh)]
        cards_table = Table([card_labels, card_values], colWidths=[1.75*inch]*4)
        cards_table.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BACKGROUND", (0,0), (2,-1), LIGHT_BLUE),
            ("BACKGROUND", (3,0), (3,-1), BRAND),
            ("TEXTCOLOR", (3,0), (3,-1), WHITE),
            ("BOX", (0,0), (-1,-1), 0.5, GREY),
            ("INNERGRID", (0,0), (-1,-1), 0.5, GREY),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(cards_table)
        story.append(Spacer(1, 8))

        # Payment history
        story.append(Paragraph("  PAYMENT HISTORY", s["section_hdr"]))
        hist_data = [[
            Paragraph("<b>#</b>", s["small"]),
            Paragraph("<b>Description / Milestone</b>", s["small"]),
            Paragraph("<b>Payment Date</b>", s["small"]),
            Paragraph("<b>Amount Paid ($)</b>", s["small"]),
            Paragraph("<b>Status</b>", s["small"]),
        ]]
        for i, inv in enumerate(invoices):
            hist_data.append([
                str(i+1),
                Paragraph(inv.description, s["small"]),
                str(inv.payment_date or "—"),
                f"${inv.total:,.2f}" if inv.status == "paid" else "—",
                inv.status.upper(),
            ])
        hist_data.append([
            Paragraph("<b>TOTALS</b>", s["small"]), "",
            "", Paragraph(f"<b>${total_paid:,.2f}</b>", s["small"]), ""
        ])
        hist_table = Table(hist_data, colWidths=[0.35*inch, 2.5*inch, 1.0*inch, 1.1*inch, 0.8*inch])
        hist_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f8f8f8")]),
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#f5f5f5")),
        ]))
        story.append(hist_table)
        story.append(Spacer(1, 6))

        # Summary
        summary = [
            ["Original Contract Amount", f"${contract_amount:,.2f}"],
            ["Total Change Orders / Adjustments", f"${net_adjustments:,.2f}"],
            ["Revised Contract Total", f"${contract_amount + net_adjustments:,.2f}"],
            ["Total Payments Received", f"${total_paid:,.2f}"],
            ["BALANCE DUE", f"${balance_due:,.2f}"],
        ]
        sum_table = Table(summary, colWidths=[2.5*inch, 1.2*inch], hAlign="RIGHT")
        sum_table.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("TEXTCOLOR", (0,0), (-1,-2), GREY),
            ("BACKGROUND", (0,-1), (-1,-1), BRAND),
            ("TEXTCOLOR", (0,-1), (-1,-1), WHITE),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ]))
        story.append(sum_table)

        if notes:
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"<b>Notes:</b> {notes}", s["small"]))

        # Signatures
        story.append(Spacer(1, 16))
        sig_data = [
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph("Customer", s["small"]),
             Paragraph("Cabrera Construction", s["small"])],
            [Paragraph("Date: _______________", s["small"]),
             Paragraph("Date: _______________", s["small"])],
        ]
        sig_table = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
        story.append(sig_table)

        story += _footer_para(s)
        doc.build(story)
        return path

    # ── Project Summary PDF ───────────────────────────────────────────────────

    def generate_project_summary_pdf(self, project: Project, estimates: list,
                                      invoices: list, wbs_items: list) -> str:
        s = self._styles
        filename = f"summary_{project.name.replace(' ', '_')}_{date.today()}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)

        # ── Title ─────────────────────────────────────────────────────────────
        story.append(Paragraph("PROJECT SUMMARY REPORT",
                                ParagraphStyle("ps_title", fontSize=14,
                                                fontName="Helvetica-Bold",
                                                textColor=WHITE, backColor=BRAND,
                                                alignment=TA_CENTER, spaceAfter=4,
                                                borderPadding=8)))
        story.append(Paragraph(f"Generated: {date.today()}",
                                ParagraphStyle("ps_date", fontSize=8, textColor=GREY,
                                                alignment=TA_CENTER, spaceAfter=10)))

        # ── Project Information ───────────────────────────────────────────────
        story.append(Paragraph("  PROJECT INFORMATION", s["section_hdr"]))
        story.append(Spacer(1, 4))

        dur_str = f"{project.duration_days} days" if project.duration_days else "—"
        info_data = [
            ["Project Name",    project.name,           "Status",        project.status.replace("_", " ").title()],
            ["Customer",        project.customer_name,  "Type",          project.project_type or "—"],
            ["Email",           project.customer_email, "Est. Start",    str(project.start_date or "—")],
            ["Phone",           project.customer_phone or "—", "Est. Duration", dur_str],
            ["Address",         project.property_address, "", ""],
        ]
        info_table = Table(info_data, colWidths=[1.2*inch, 2.3*inch, 1.1*inch, 2.1*inch])
        info_table.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0,0), (0,-1), BRAND),
            ("TEXTCOLOR", (2,0), (2,-1), BRAND),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, colors.HexColor("#f8f8f8")]),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e0e0e0")),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 10))

        # ── Financial Summary ─────────────────────────────────────────────────
        story.append(Paragraph("  FINANCIAL SUMMARY", s["section_hdr"]))
        story.append(Spacer(1, 4))

        total_estimated = sum(getattr(e, "total", 0) for e in estimates)
        total_invoiced = sum(getattr(i, "total", 0) for i in invoices)
        total_paid = sum(getattr(i, "total", 0) for i in invoices
                         if getattr(i, "status", "") == "paid")
        balance_due = total_invoiced - total_paid

        _lbl_st = ParagraphStyle("fs_lbl", fontSize=8, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, textColor=GREY)
        _val_st = ParagraphStyle("fs_val", fontSize=11, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER)
        _val_wh = ParagraphStyle("fs_val_w", fontSize=11, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, textColor=WHITE)
        fin_labels = [Paragraph("Total Estimated", _lbl_st),
                      Paragraph("Total Invoiced", _lbl_st),
                      Paragraph("Total Paid", _lbl_st),
                      Paragraph("BALANCE DUE", ParagraphStyle("bd_lbl", fontSize=8,
                                                                fontName="Helvetica-Bold",
                                                                alignment=TA_CENTER,
                                                                textColor=WHITE))]
        fin_values = [Paragraph(f"${total_estimated:,.2f}", _val_st),
                      Paragraph(f"${total_invoiced:,.2f}", _val_st),
                      Paragraph(f"${total_paid:,.2f}", _val_st),
                      Paragraph(f"${balance_due:,.2f}", _val_wh)]
        fin_table = Table([fin_labels, fin_values], colWidths=[1.75*inch]*4)
        fin_table.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BACKGROUND", (0,0), (2,-1), LIGHT_BLUE),
            ("BACKGROUND", (3,0), (3,-1), BRAND),
            ("BOX", (0,0), (-1,-1), 0.5, GREY),
            ("INNERGRID", (0,0), (-1,-1), 0.5, GREY),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(fin_table)
        story.append(Spacer(1, 8))

        # ── Estimates Table ───────────────────────────────────────────────────
        if estimates:
            story.append(Paragraph("  ESTIMATES", s["section_hdr"]))
            story.append(Spacer(1, 4))
            est_data = [[
                Paragraph("<b>Estimate #</b>", s["small"]),
                Paragraph("<b>Date Issued</b>", s["small"]),
                Paragraph("<b>Status</b>", s["small"]),
                Paragraph("<b>Total ($)</b>", s["small"]),
            ]]
            for e in estimates:
                est_data.append([
                    e.estimate_number,
                    str(e.date_issued),
                    e.status.title(),
                    f"${e.total:,.2f}",
                ])
            est_table = Table(est_data, colWidths=[1.8*inch, 1.3*inch, 1.2*inch, 1.2*inch])
            est_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("ALIGN", (3,0), (3,-1), "RIGHT"),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f8f8")]),
            ]))
            story.append(est_table)
            story.append(Spacer(1, 8))

        # ── Invoices Table ────────────────────────────────────────────────────
        if invoices:
            story.append(Paragraph("  INVOICES", s["section_hdr"]))
            story.append(Spacer(1, 4))
            inv_data = [[
                Paragraph("<b>Invoice #</b>", s["small"]),
                Paragraph("<b>Description</b>", s["small"]),
                Paragraph("<b>Due Date</b>", s["small"]),
                Paragraph("<b>Status</b>", s["small"]),
                Paragraph("<b>Amount ($)</b>", s["small"]),
            ]]
            for i in invoices:
                inv_data.append([
                    i.invoice_number,
                    Paragraph(i.description, s["small"]),
                    str(i.due_date or "—"),
                    i.status.upper(),
                    f"${i.total:,.2f}",
                ])
            inv_table = Table(inv_data, colWidths=[1.0*inch, 2.2*inch, 0.9*inch, 0.7*inch, 1.0*inch])
            inv_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("ALIGN", (4,0), (4,-1), "RIGHT"),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f8f8")]),
            ]))
            story.append(inv_table)
            story.append(Spacer(1, 8))

        # ── Work Plan ─────────────────────────────────────────────────────────
        if wbs_items:
            story.append(Paragraph("  WORK PLAN", s["section_hdr"]))
            story.append(Spacer(1, 4))
            wbs_data = [[
                Paragraph("<b>Phase</b>", s["small"]),
                Paragraph("<b>Task</b>", s["small"]),
                Paragraph("<b>Assigned To</b>", s["small"]),
                Paragraph("<b>Est. Hours</b>", s["small"]),
                Paragraph("<b>Status</b>", s["small"]),
            ]]
            for item in wbs_items:
                wbs_data.append([
                    Paragraph(item.phase, s["small"]),
                    Paragraph(item.task, s["small"]),
                    item.assigned_to or "—",
                    str(item.estimated_hours or "—"),
                    item.status.replace("_", " ").title(),
                ])
            total_est_hours = sum(item.estimated_hours or 0 for item in wbs_items)
            wbs_data.append([
                Paragraph("<b>TOTAL</b>", s["small"]), "", "",
                Paragraph(f"<b>{total_est_hours:.1f}h</b>", s["small"]), "",
            ])
            wbs_table = Table(wbs_data,
                               colWidths=[1.4*inch, 2.1*inch, 1.2*inch, 0.8*inch, 1.0*inch])
            wbs_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f8f8f8")]),
                ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#f0f0f0")),
            ]))
            story.append(wbs_table)

        story += _footer_para(s)
        doc.build(story)
        return path

    # ── Contract PDF (California B&P Code §7159) ──────────────────────────────

    def generate_contract_pdf(self, project: Project, estimate=None,
                               wbs_items: list = None) -> str:
        """
        Generate a California Home Improvement Contract PDF (B&P Code §7159).
        Scope and payment schedule drawn from estimate; timeline from WBS items.
        """
        from collections import defaultdict
        s = self._styles
        filename = f"contract_{project.name.replace(' ', '_')}_{date.today()}.pdf"
        doc, path = self._make_doc(filename)
        story = []

        # ── shared paragraph styles ───────────────────────────────────────────
        hdr_st   = ParagraphStyle("c_hdr",   fontSize=13, fontName="Helvetica-Bold",
                                   textColor=WHITE, backColor=BRAND,
                                   alignment=TA_CENTER, borderPadding=8, spaceAfter=2)
        sub_st   = ParagraphStyle("c_sub",   fontSize=8,  textColor=GREY,
                                   alignment=TA_CENTER, spaceAfter=6)
        sec_st   = ParagraphStyle("c_sec",   fontSize=9,  fontName="Helvetica-Bold",
                                   textColor=WHITE, backColor=BRAND,
                                   leftIndent=4, spaceAfter=0, spaceBefore=6,
                                   borderPadding=3)
        body_st  = ParagraphStyle("c_body",  fontSize=8,  textColor=GREY,
                                   leading=12, spaceAfter=4)
        bold_st  = ParagraphStyle("c_bold",  fontSize=8,  fontName="Helvetica-Bold",
                                   textColor=colors.black, leading=12, spaceAfter=3)
        warn_st  = ParagraphStyle("c_warn",  fontSize=8,  fontName="Helvetica-Bold",
                                   textColor=RED, leading=12, spaceAfter=4,
                                   backColor=colors.HexColor("#fff3cd"), borderPadding=4)
        lbl_st   = ParagraphStyle("c_lbl",   fontSize=8,  fontName="Helvetica-Bold",
                                   textColor=BRAND)
        small_st = ParagraphStyle("c_small", fontSize=7,  textColor=GREY,
                                   leading=10, spaceAfter=2)

        def _cell(text, style=None, bold=False):
            st = style or (bold_st if bold else body_st)
            return Paragraph(text, st)

        def _sec(title):
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"  {title}", sec_st))
            story.append(Spacer(1, 4))

        def _field_table(rows, col_widths):
            """Two-column label/value table."""
            data = [[Paragraph(f"<b>{lbl}</b>", lbl_st), Paragraph(val, body_st)]
                    for lbl, val in rows]
            t = Table(data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("ROWBACKGROUNDS", (0,0), (-1,-1),
                 [colors.white, colors.HexColor("#f8f8f8")]),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
                ("TOPPADDING", (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                ("LEFTPADDING", (0,0), (-1,-1), 4),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ]))
            return t

        # ── Title ─────────────────────────────────────────────────────────────
        story.append(Paragraph("HOME IMPROVEMENT CONTRACT", hdr_st))
        story.append(Paragraph(
            "California Business &amp; Professions Code §7159  ·  As Amended Effective January 1, 2026",
            sub_st))
        story.append(Spacer(1, 2))

        # Entitlement notice box
        notice_t = Table([[Paragraph(
            "<b>YOU ARE ENTITLED TO A COMPLETELY FILLED-IN COPY OF THIS AGREEMENT, "
            "SIGNED BY BOTH YOU AND THE CONTRACTOR, BEFORE ANY WORK MAY BE STARTED.</b>",
            ParagraphStyle("ntc", fontSize=8, fontName="Helvetica-Bold",
                           alignment=TA_CENTER, textColor=BRAND))]], colWidths=[7.0*inch])
        notice_t.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 1.0, BRAND),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(notice_t)
        story.append(Spacer(1, 6))

        # Agreement date / contract number row
        ag_t = Table([[
            Paragraph("<b>Agreement Date:</b>", lbl_st),
            Paragraph(str(date.today()), body_st),
            Paragraph("<b>Contract Number:</b>", lbl_st),
            Paragraph(f"{project.id or '____'}", body_st),
        ]], colWidths=[1.3*inch, 2.2*inch, 1.3*inch, 2.2*inch])
        ag_t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(ag_t)
        story.append(Spacer(1, 6))

        # ── Parties ───────────────────────────────────────────────────────────
        _sec("PARTIES TO THIS AGREEMENT")
        dur_str = f"{project.duration_days} days" if project.duration_days else "To be determined"
        owner_info = [
            Paragraph("<b>OWNER / TENANT</b>", lbl_st),
            Paragraph(project.customer_name, body_st),
            Paragraph(project.property_address, body_st),
            Paragraph(project.customer_phone or "—", body_st),
            Paragraph(project.customer_email, body_st),
        ]
        contractor_info = [
            Paragraph("<b>CONTRACTOR</b>", lbl_st),
            Paragraph(f"<b>{COMPANY['name']}</b><br/>{COMPANY['representative']}", body_st),
            Paragraph(COMPANY["address"], body_st),
            Paragraph(f"Tel: {COMPANY['phone']}", body_st),
            Paragraph(f"Email: {COMPANY['email']}", body_st),
            Paragraph(f"<b>{COMPANY['license']}  ·  B-General Building</b>", body_st),
            Paragraph("Insurance Co.: Evanston  ·  (916) 482-9600", body_st),
        ]
        parties_t = Table([[owner_info, contractor_info]], colWidths=[3.5*inch, 3.5*inch])
        parties_t.setStyle(TableStyle([
            ("BOX", (0,0), (0,0), 0.5, LIGHT_BLUE),
            ("BOX", (1,0), (1,0), 0.5, LIGHT_BLUE),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(parties_t)
        story.append(Spacer(1, 4))

        # Cancellation notice address
        cancel_t = Table([[Paragraph(
            f"<b>NOTICE OF CANCELLATION</b> may be sent to the Contractor at:<br/>"
            f"{COMPANY['representative']}  ·  {COMPANY['name']}  ·  {COMPANY['address']}<br/>"
            f"Tel: {COMPANY['phone']}  ·  Email: {COMPANY['email']}<br/>"
            "<i>(Per SB 517, effective Jan 1, 2026: cancellation may be sent by email, mail, or fax.)</i>",
            ParagraphStyle("cancel_note", fontSize=7.5, textColor=GREY,
                           backColor=colors.HexColor("#f0f7ff"),
                           borderPadding=5, leading=11))]], colWidths=[7.0*inch])
        cancel_t.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.5, LIGHT_BLUE),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(cancel_t)

        # ── Project Information ───────────────────────────────────────────────
        _sec("PROJECT INFORMATION")
        story.append(_field_table([
            ("Project Site Address:", project.property_address),
        ], [1.6*inch, 5.4*inch]))
        story.append(Spacer(1, 4))

        # Description of work / scope
        if estimate and estimate.line_items:
            by_section = defaultdict(list)
            for item in estimate.line_items:
                by_section[item.section].append(item)
            scope_lines = []
            for section, items in by_section.items():
                scope_lines.append(f"<b>{section}</b>")
                for it in items:
                    scope_lines.append(f"  • {it.description}  (Qty: {it.qty:g} {it.unit})")
            scope_text = "<br/>".join(scope_lines)
        else:
            scope_text = "See attached scope of work."

        story.append(_field_table([
            ("Project Description:", project.name),
            ("Description of Work / Scope:", scope_text),
        ], [1.6*inch, 5.4*inch]))
        story.append(Spacer(1, 4))

        story.append(Paragraph(
            "(Include significant materials, equipment, fixtures to be used/installed. "
            "Attach additional sheets if needed.)",
            small_st))
        story.append(Spacer(1, 4))

        start_str = str(project.start_date) if project.start_date else "To be determined"
        completion_str = (f"Approx. {dur_str} from start"
                          if project.duration_days else "To be determined")
        dates_t = Table([[
            Paragraph("<b>Approximate Start Date:</b>", lbl_st),
            Paragraph(start_str, body_st),
            Paragraph("<b>Approximate Completion Date:</b>", lbl_st),
            Paragraph(completion_str, body_st),
        ]], colWidths=[1.6*inch, 1.9*inch, 1.9*inch, 1.6*inch])
        dates_t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(dates_t)

        # ── Subcontractor Disclosure ──────────────────────────────────────────
        _sec("SUBCONTRACTOR DISCLOSURE  (Required — AB 1327, Eff. Jan 1, 2026)")
        story.append(Paragraph(
            "☐  No subcontractors will be used on this project.<br/>"
            "☐  One or more subcontractors will be used on this project. See list below:",
            body_st))
        sub_data = [[
            Paragraph("<b>Subcontractor Name</b>", lbl_st),
            Paragraph("<b>License #</b>", lbl_st),
            Paragraph("<b>Classification</b>", lbl_st),
            Paragraph("<b>Scope of Work</b>", lbl_st),
        ]]
        for _ in range(3):
            sub_data.append(["", "", "", ""])
        sub_t = Table(sub_data, colWidths=[2.0*inch, 1.0*inch, 1.2*inch, 2.8*inch])
        sub_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ("ROWHEIGHT", (0,1), (-1,-1), 18),
        ]))
        story.append(sub_t)

        # ── Contract Price & Payment ──────────────────────────────────────────
        _sec("CONTRACT PRICE & PAYMENT")
        contract_total = estimate.total if estimate else 0.0
        finance_charge = 0.0
        price_t = Table([[
            Paragraph("<b>Contract Price:</b>", lbl_st),
            Paragraph(f"${contract_total:,.2f}", body_st),
            Paragraph("<b>Finance Charge (if applicable):</b>", lbl_st),
            Paragraph(f"${finance_charge:,.2f}", body_st),
        ]], colWidths=[1.3*inch, 2.2*inch, 2.2*inch, 1.3*inch])
        price_t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(price_t)
        story.append(Spacer(1, 4))

        story.append(Table([[Paragraph(
            "<b>THE DOWN PAYMENT MAY NOT EXCEED $1,000 OR 10% OF THE CONTRACT PRICE, WHICHEVER IS LESS.</b>",
            warn_st)]], colWidths=[7.0*inch]))
        story.append(Spacer(1, 4))

        # Down payment row (use first payment schedule item if available)
        first_payment = (estimate.payment_schedule[0] if estimate and estimate.payment_schedule
                         else None)
        dp_amount = f"${first_payment.amount:,.2f}" if first_payment else "$___________"
        dp_due    = (str(first_payment.due_date) if first_payment and first_payment.due_date
                     else "Upon signing")
        dp_t = Table([[
            Paragraph("<b>Down Payment Amount:</b>", lbl_st),
            Paragraph(dp_amount, body_st),
            Paragraph("<b>Down Payment Due:</b>", lbl_st),
            Paragraph(dp_due, body_st),
        ]], colWidths=[1.6*inch, 2.0*inch, 1.6*inch, 1.8*inch])
        dp_t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(dp_t)

        # ── Schedule of Progress Payments ────────────────────────────────────
        _sec("SCHEDULE OF PROGRESS PAYMENTS")
        story.append(Table([[Paragraph(
            "The schedule of progress payments must specifically describe each phase of work, "
            "including the type and amount of work or services scheduled to be supplied in each "
            "phase, along with the amount of each proposed progress payment. "
            "<b>IT IS AGAINST THE LAW FOR A CONTRACTOR TO COLLECT PAYMENT FOR WORK NOT YET "
            "COMPLETED, OR FOR MATERIALS NOT YET DELIVERED. HOWEVER, A CONTRACTOR MAY REQUIRE "
            "A DOWNPAYMENT.</b>",
            small_st)]], colWidths=[7.0*inch]))
        story.append(Spacer(1, 4))

        pay_hdr = [[
            Paragraph("<b>Work / Phase Description</b>", lbl_st),
            Paragraph("<b>Amount Due ($)</b>", lbl_st),
            Paragraph("<b>When Due / Milestone</b>", lbl_st),
        ]]
        if estimate and estimate.payment_schedule:
            pay_rows = [[
                Paragraph(item.label + (f" — {item.description}" if item.description else ""),
                          body_st),
                f"${item.amount:,.2f}",
                str(item.due_date or "Per milestone"),
            ] for item in estimate.payment_schedule]
        else:
            pay_rows = [["", "", ""] for _ in range(5)]

        pay_t = Table(pay_hdr + pay_rows, colWidths=[3.5*inch, 1.5*inch, 2.0*inch])
        pay_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f8f8")]),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(pay_t)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "Upon satisfactory payment for any portion of the work performed, the Contractor "
            "shall furnish the Owner a full and unconditional release from any potential lien "
            "claimant claim or mechanics lien (Civil Code §§8400 and 8404) for that portion "
            "prior to any further payment being made.",
            small_st))

        # ── Insurance ─────────────────────────────────────────────────────────
        _sec("INSURANCE")
        story.append(Paragraph(
            "<b>WORKERS' COMPENSATION INSURANCE (check one):</b><br/>"
            "☐  This Contractor has no employees and is exempt from workers' compensation requirements.<br/>"
            "☑  This Contractor carries workers' compensation insurance for all employees.",
            body_st))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "<b>COMMERCIAL GENERAL LIABILITY INSURANCE (check one):</b><br/>"
            "☐  This Contractor does not carry commercial general liability insurance.<br/>"
            "☑  This Contractor carries CGL insurance written by: Evanston  ·  (916) 482-9600<br/>"
            "☐  This Contractor is self-insured.",
            body_st))

        # ── Extra Work & Change Orders ────────────────────────────────────────
        _sec("EXTRA WORK & CHANGE ORDERS")
        story.append(Paragraph(
            "Extra work and change orders become part of this contract once the order is prepared "
            "in writing and signed by both parties <b>PRIOR</b> to commencement of any covered work. "
            "Each change order must describe: (i) the scope of the extra work or change; "
            "(ii) the cost to be added or subtracted from the contract; and (iii) the effect on "
            "the schedule of progress payments or completion date. The Owner may not require the "
            "Contractor to perform extra work without prior written authorization.",
            body_st))

        # ── Mechanics Lien Warning ────────────────────────────────────────────
        _sec("MECHANICS LIEN WARNING")
        lien_t = Table([[Paragraph(
            "Anyone who helps improve your property, but who is not paid, may record what is called a "
            "<b>mechanics lien</b> on your property. A mechanics lien is a claim, like a mortgage or "
            "home equity loan, made against your property and recorded with the county recorder.<br/><br/>"
            "Even if you pay your contractor in full, unpaid subcontractors, suppliers, and laborers "
            "who helped to improve your property may record mechanics liens and sue you in court to "
            "foreclose the lien. If a court finds the lien is valid, you could be forced to pay twice "
            "or have a court officer sell your home to pay the lien. Liens can also affect your credit.<br/><br/>"
            "To preserve their right to record a lien, each subcontractor and material supplier must "
            "provide you with a document called a 'Preliminary Notice.' This notice is not a lien. "
            "The purpose of the notice is to let you know that the person who sends you the notice "
            "has the right to record a lien on your property if they are not paid.<br/><br/>"
            "<b>BE CAREFUL.</b> The Preliminary Notice can be sent up to 20 days after the subcontractor "
            "starts work or the supplier provides material. <b>PROTECT YOURSELF FROM LIENS</b> by getting "
            "a list from your contractor of all subcontractors and material suppliers that work on your "
            "project. Consider paying with joint checks. For more information: www.cslb.ca.gov or call "
            "CSLB at 800-321-CSLB (2752).",
            ParagraphStyle("lien", fontSize=7.5, textColor=GREY, leading=11,
                           backColor=colors.HexColor("#fff8e1"),
                           borderPadding=6))]], colWidths=[7.0*inch])
        lien_t.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.5, ORANGE),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(lien_t)

        # ── Terms and Conditions ──────────────────────────────────────────────
        _sec("TERMS AND CONDITIONS")
        tc_items = [
            ("Plans and Specifications:",
             "The project shall be constructed according to the Plans, Drawings, and Specifications "
             "provided. Contractor shall be entitled to rely on their accuracy and may be entitled "
             "to a change in Contract Sum and Contract Time if they contain errors."),
            ("Permits:",
             "Contractor shall obtain and pay for all required building permits. Owner shall be "
             "responsible for all taxes, assessments, and charges required by public agencies."),
            ("Property Insurance:",
             "Owner shall purchase and maintain property insurance for the entire work at the site, "
             "written on an All-Risk policy form, and shall name Contractor as an additional insured "
             "through final payment."),
            ("Waiver of Subrogation:",
             "Owner and Contractor waive all rights against each other, subcontractors, agents, and "
             "employees for damages caused by fire or other insured losses, to the extent covered by "
             "property insurance applicable to the work."),
            ("Right to Stop Work:",
             "Contractor shall have the right to cease work on the project if any amount due to "
             "Contractor has not been paid when due."),
            ("Cleanup:",
             "Contractor shall remove all construction debris and waste from the project site upon "
             "completion of work. Any property damage caused during the project shall be addressed "
             "by Contractor's insurance."),
            ("Delay:",
             "Contractor shall be excused for delays caused by: acts of God, owner's negligence, "
             "owner's failure to make timely payments or process change orders, acts of separate "
             "contractors, public utility delays, material embargoes, labor disputes, fire, "
             "transportation delays, or other causes beyond Contractor's reasonable control."),
            ("Attorneys' Fees:",
             "In any dispute relating to the interpretation or enforcement of this Agreement, "
             "the prevailing party shall be entitled to its costs and reasonable attorneys' fees."),
            ("Assignment:",
             "Neither party shall assign rights or delegate duties under this Agreement without "
             "prior written consent of the other party."),
            ("Bankruptcy:",
             "If either party files for bankruptcy or makes an assignment for creditors, the other "
             "party has the right to cancel this Agreement."),
            ("Bond:",
             "The Owner or tenant shall have the right to require Contractor to procure a "
             "performance and payment bond."),
            ("CSLB:",
             "Information about the Contractors' State License Board (CSLB): CSLB is the state "
             "consumer protection agency that licenses and regulates construction contractors. "
             "Use only licensed contractors. Visit www.cslb.ca.gov or call 800-321-CSLB (2752)."),
        ]
        tc_lbl_st = ParagraphStyle("tc_lbl", fontSize=8, fontName="Helvetica-Bold",
                                    textColor=BRAND, spaceAfter=1)
        tc_body_st = ParagraphStyle("tc_body", fontSize=8, textColor=GREY,
                                     leading=11, spaceAfter=5)
        for label, text in tc_items:
            story.append(Paragraph(label, tc_lbl_st))
            story.append(Paragraph(text, tc_body_st))

        # ── Arbitration ───────────────────────────────────────────────────────
        _sec("ARBITRATION OF DISPUTES")
        arb_t = Table([[Paragraph(
            "Any dispute arising out of or relating to the negotiation, award, construction, "
            "performance, or non-performance of any aspect of this Agreement shall be settled by "
            "binding arbitration in accordance with the Construction Industry Rules of the American "
            "Arbitration Association.<br/><br/>"
            "<b>NOTICE: BY INITIALING BELOW, YOU ARE AGREEING TO HAVE ANY DISPUTE DECIDED BY NEUTRAL "
            "ARBITRATION AS PROVIDED BY CALIFORNIA LAW AND ARE GIVING UP YOUR RIGHT TO A COURT OR "
            "JURY TRIAL, INCLUDING RIGHTS TO DISCOVERY AND APPEAL. YOUR AGREEMENT TO THIS "
            "ARBITRATION PROVISION IS VOLUNTARY.</b>",
            ParagraphStyle("arb", fontSize=8, textColor=GREY, leading=11,
                           backColor=colors.HexColor("#f0f7ff"),
                           borderPadding=6))]], colWidths=[7.0*inch])
        arb_t.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.5, BRAND),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(arb_t)
        story.append(Spacer(1, 6))
        init_t = Table([[
            Paragraph("Owner Initials: _______", body_st),
            Paragraph("Contractor Initials: _______", body_st),
        ]], colWidths=[3.5*inch, 3.5*inch])
        init_t.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(init_t)

        # ── Right to Cancel ───────────────────────────────────────────────────
        _sec("RIGHT TO CANCEL")
        story.append(Paragraph("<b>Cancellation Period (check one):</b>", bold_st))
        story.append(Paragraph(
            "☐  Three (3) Business Days — Standard<br/>"
            "☐  Five (5) Business Days — Senior Citizens only<br/>"
            "☐  Seven (7) Business Days — Disaster repair contracts only",
            body_st))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "You, the Owner, have the right to cancel this contract within the checked period above. "
            "You may cancel by emailing, mailing, faxing, or delivering a written notice to the "
            "Contractor at the address/email listed above by midnight of the last business day of "
            "the cancellation period after you received a signed and dated copy of the contract.<br/><br/>"
            "If you cancel, the Contractor must return to you anything you paid within 10 days of "
            "receiving the notice of cancellation. You must make available to the Contractor, in "
            "substantially as good condition as received, any goods delivered to you under this "
            "contract. If you fail to make the goods available, or if you agree to return them and "
            "fail to do so, you remain liable for performance of all obligations under the contract.",
            body_st))
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>Acknowledgement of Receipt of Right to Cancel Notice:</b>", bold_st))
        story.append(Spacer(1, 4))
        ack_t = Table([[
            Paragraph("Owner Signature: _______________________________", body_st),
            Paragraph("Date: _______________", body_st),
        ]], colWidths=[4.5*inch, 2.5*inch])
        story.append(ack_t)

        # ── Attached Documents ────────────────────────────────────────────────
        _sec("ATTACHED DOCUMENTS")
        story.append(Paragraph(
            "1.  Notice of Cancellation Form (provided in duplicate)<br/>"
            "2.  Home Improvement Change Order Form<br/>"
            "3.  California Residential Contracts – Required Attachments and Checklists<br/>"
            "4.  _______________________________________________<br/>"
            "5.  _______________________________________________",
            body_st))

        # ── Agreement & Signatures ────────────────────────────────────────────
        _sec("AGREEMENT & SIGNATURES")
        story.append(Table([[Paragraph(
            "THIS AGREEMENT IS ENTERED INTO AS OF THE DATE STATED ABOVE. THIS AGREEMENT "
            "EXPRESSLY INCORPORATES ALL TERMS AND CONDITIONS SET FORTH HEREIN AND ANY "
            "ATTACHMENTS OR EXHIBITS ATTACHED HERETO. THIS AGREEMENT IS EXECUTED IN AT LEAST "
            "TWO ORIGINAL COPIES — ONE DELIVERED TO CONTRACTOR AND ONE TO OWNER.",
            ParagraphStyle("ag_notice", fontSize=8, fontName="Helvetica-Bold",
                           textColor=BRAND, alignment=TA_CENTER,
                           backColor=colors.HexColor("#f0f7ff"),
                           borderPadding=5))]], colWidths=[7.0*inch]))
        story.append(Spacer(1, 16))

        sig_data = [
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph("Owner Signature", small_st),
             Paragraph("Contractor Signature", small_st)],
            [Spacer(1, 12), Spacer(1, 12)],
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph(f"Owner (Print Name &amp; Title):<br/>{project.customer_name}",
                       small_st),
             Paragraph(f"Contractor (Print Name &amp; Title):<br/>{COMPANY['representative']}  —  {COMPANY['name']}",
                       small_st)],
            [Spacer(1, 12), Spacer(1, 12)],
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph("Second Owner Signature (if applicable)", small_st),
             Paragraph("Date: _______________", small_st)],
        ]
        sig_t = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
        sig_t.setStyle(TableStyle([
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(sig_t)
        story.append(Spacer(1, 10))

        story.append(Paragraph(
            f"{COMPANY['representative']}  ·  {COMPANY['name']}  ·  {COMPANY['license']}  ·  "
            f"Tel: {COMPANY['phone']}  ·  {COMPANY['email']}  ·  {COMPANY['address']}",
            ParagraphStyle("footer_co", fontSize=7, textColor=GREY,
                           alignment=TA_CENTER, spaceBefore=4)))
        story.append(Paragraph(
            f"Thank you for choosing {COMPANY['name']} — Quality Craftsmanship You Can Trust.",
            ParagraphStyle("footer_tag", fontSize=7.5, fontName="Helvetica-Bold",
                           textColor=BRAND, alignment=TA_CENTER)))

        doc.build(story)
        return path
