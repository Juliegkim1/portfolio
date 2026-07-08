"""Generates PDF documents using ReportLab (pure Python, no system libs required)."""
import os
from collections import defaultdict
from datetime import date, timedelta
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, PageBreak
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

    # ── Change Order PDF ─────────────────────────────────────────────────────
    # Matches Cabrera's official "Home Improvement Change Order Form" template.
    # Shared by generate_change_order_pdf (filled with real change data) and
    # generate_blank_change_order_form_pdf (the blank reference attachment).

    def _change_order_body(self, project, contract, change_order, s, original_price=None):
        lbl_st = ParagraphStyle("co_lbl", fontSize=8, fontName="Helvetica-Bold", textColor=BRAND)
        body_st = s["body"]
        small_st = s["small"]
        bold_st = ParagraphStyle("co_bold", fontSize=8, fontName="Helvetica-Bold",
                                  textColor=colors.black, leading=12)
        BLANK = "_____________________"

        story = []
        story.append(Paragraph("HOME IMPROVEMENT CHANGE ORDER", ParagraphStyle(
            "co_hdr", fontSize=13, fontName="Helvetica-Bold", textColor=WHITE,
            backColor=BRAND, alignment=TA_CENTER, borderPadding=8, spaceAfter=2)))
        story.append(Paragraph(
            "(Business and Professions Code §7159) — Attachment to the Home Improvement Contract",
            ParagraphStyle("co_sub", fontSize=8, textColor=GREY, alignment=TA_CENTER,
                           spaceAfter=8)))

        owner_name = project.customer_name if project else BLANK
        co_number = change_order.change_order_number if change_order else BLANK
        proj_line = f"{project.name} — {project.property_address}" if project else BLANK
        co_date = str(date.today()) if change_order else BLANK
        orig_date = (str(contract.created_at) if contract and contract.created_at else BLANK)
        contractor = COMPANY["name"] if project else BLANK

        meta_t = Table([
            [Paragraph("<b>Owner's Name:</b>", lbl_st), Paragraph(owner_name, body_st),
             Paragraph("<b>Change Order No.:</b>", lbl_st), Paragraph(co_number, body_st)],
            [Paragraph("<b>Project Name and Address:</b>", lbl_st), Paragraph(proj_line, body_st),
             Paragraph("<b>Date of Change Order:</b>", lbl_st), Paragraph(co_date, body_st)],
            [Paragraph("<b>Date of Original Contract:</b>", lbl_st),
             Paragraph(orig_date, body_st),
             Paragraph("<b>Contractor:</b>", lbl_st), Paragraph(contractor, body_st)],
        ], colWidths=[1.5*inch, 2.1*inch, 1.5*inch, 2.1*inch])
        meta_t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(meta_t)
        story.append(Spacer(1, 6))

        story.append(Paragraph(
            f"This Change Order modifies the Home Improvement Contract identified above "
            f"between the Owner and {COMPANY['name']}. Extra work and change orders become "
            "part of the contract once the order is prepared in writing and signed by both "
            "parties before any work covered by the change order begins. The Owner may not "
            "be required to perform extra work without written authorization prior to the "
            "commencement of work covered by this order. To be enforceable, this order must "
            "identify, in writing, all of the following: (i) the scope of the work; (ii) the "
            "amount to be added to or subtracted from the contract; and (iii) the effect the "
            "order will have on the schedule of progress payments and the completion date.",
            small_st))

        def _sec(title):
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"  {title}", s["section_hdr"]))
            story.append(Spacer(1, 4))

        # ── 1. Scope of the Extra Work or Change ─────────────────────────────
        _sec("1. Scope of the Extra Work or Change")
        story.append(Paragraph(change_order.description if change_order else "", body_st))
        if change_order and change_order.line_items:
            item_hdr = [[
                Paragraph("<b>Description</b>", small_st), Paragraph("<b>Qty</b>", small_st),
                Paragraph("<b>Unit</b>", small_st), Paragraph("<b>Unit Price ($)</b>", small_st),
                Paragraph("<b>Total ($)</b>", small_st),
            ]]
            rows = []
            for it in change_order.line_items:
                qty = float(it.get("qty", 1) or 1)
                unit_price = float(it.get("unit_price", 0) or 0)
                rows.append([
                    Paragraph(it.get("description", ""), small_st), f"{qty:.2f}",
                    it.get("unit", "ea"), f"${unit_price:,.2f}", f"${qty * unit_price:,.2f}",
                ])
            item_t = Table(item_hdr + rows,
                            colWidths=[3.2*inch, 0.6*inch, 0.6*inch, 1.3*inch, 1.3*inch])
            item_t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("ALIGN", (1,0), (-1,-1), "RIGHT"),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f8f8")]),
            ]))
            story.append(Spacer(1, 4))
            story.append(item_t)

        # ── 2. Effect on the Contract Price ──────────────────────────────────
        _sec("2. Effect on the Contract Price")
        if change_order and original_price is not None:
            added = change_order.price_delta if change_order.price_delta >= 0 else 0
            subtracted = abs(change_order.price_delta) if change_order.price_delta < 0 else 0
            new_price = original_price + change_order.price_delta
            orig_str, add_str = f"${original_price:,.2f}", f"${added:,.2f}"
            sub_str, new_str = f"${subtracted:,.2f}", f"${new_price:,.2f}"
        else:
            orig_str = add_str = sub_str = new_str = f"${BLANK}"
        price_t = Table([
            [Paragraph("Original Contract Price:", body_st), Paragraph(orig_str, body_st)],
            [Paragraph("Amount ADDED by this Change Order:", body_st), Paragraph(add_str, body_st)],
            [Paragraph("Amount SUBTRACTED by this Change Order:", body_st), Paragraph(sub_str, body_st)],
            [Paragraph("<b>NEW Contract Price (after this Change Order):</b>", bold_st),
             Paragraph(f"<b>{new_str}</b>", bold_st)],
        ], colWidths=[4.0*inch, 3.0*inch])
        price_t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(price_t)

        # ── 3. Effect on the Schedule of Progress Payments ───────────────────
        _sec("3. Effect on the Schedule of Progress Payments")
        if change_order:
            story.append(Paragraph(
                "The contract price is adjusted as shown in Section 2 above; the schedule "
                "of progress payments is amended accordingly.", body_st))
        else:
            story.append(Paragraph("", body_st))
            story.append(Spacer(1, 20))

        # ── 4. Effect on the Completion Date ─────────────────────────────────
        _sec("4. Effect on the Completion Date")
        prior_completion = (contract.completion_date if contract and contract.completion_date
                            else BLANK)
        new_completion = BLANK
        if change_order and contract and contract.completion_date and change_order.days_delta:
            try:
                new_completion = str(date.fromisoformat(contract.completion_date)
                                     + timedelta(days=change_order.days_delta))
            except ValueError:
                pass
        story.append(Table([[
            Paragraph("Prior Approximate Completion Date", small_st),
            Paragraph("New Approximate Completion Date", small_st),
        ], [
            Paragraph(str(prior_completion), body_st), Paragraph(str(new_completion), body_st),
        ]], colWidths=[3.5*inch, 3.5*inch]))

        # ── Subcontractors ────────────────────────────────────────────────────
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>Use of Subcontractors (required disclosure – check one):</b>",
                                bold_st))
        story.append(Paragraph(
            "Will one or more subcontractors be used for this change?  [ ] Yes &nbsp;&nbsp; [ ] No",
            body_st))
        story.append(Paragraph(
            'If "Yes" is checked, the following disclosure applies and is part of this '
            "change order: one or more subcontractors will be used on this project, and "
            "the contractor is aware that a list of subcontractors is required to be "
            "provided, upon request, along with the names, contact information, license "
            "number, and classification of those subcontractors.",
            ParagraphStyle("co_sub_note", fontSize=7.5, textColor=GREY, leading=11,
                           borderPadding=4)))

        # ── Signatures ────────────────────────────────────────────────────────
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            "By signing below, the Owner and Contractor agree to the change described "
            "above. This Change Order is not effective and the changed work shall not "
            "begin until this order is signed and dated by both parties.", small_st))
        story.append(Spacer(1, 14))
        sig_data = [
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph("OWNER (SIGNATURE)", small_st), Paragraph("CONTRACTOR (SIGNATURE)", small_st)],
            [Spacer(1, 10), Spacer(1, 10)],
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph("Date", small_st), Paragraph("Date", small_st)],
        ]
        sig_t = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
        sig_t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.append(sig_t)

        return story

    def generate_change_order_pdf(self, project: Project, contract, change_order,
                                   original_price: float = None) -> str:
        """
        Generate a Home Improvement Change Order PDF referencing an existing
        contract, matching Cabrera's official Change Order form field-for-field.
        `original_price` (typically the linked estimate's total) drives the
        "Effect on the Contract Price" section; omit to leave those fields blank.
        """
        s = self._styles
        filename = f"change_order_{change_order.change_order_number.replace(' ', '_')}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)
        story += self._change_order_body(project, contract, change_order, s,
                                          original_price=original_price)
        story += _footer_para(s)
        doc.build(story)
        return path

    # ── Contract PDF (California B&P Code §7159) ──────────────────────────────
    # Transcribed from Cabrera's official "Home Improvement Contract" template
    # (fillable form), "Home Improvement Change Order Form," and "California
    # Residential Contracts — Required Attachments and Checklist."

    def generate_contract_pdf(self, project: Project, estimate=None,
                               wbs_items: list = None,
                               start_date=None, completion_date=None,
                               subcontractors: list = None,
                               project_site: str = None,
                               adobe_tags: bool = False) -> str:
        """
        Generate Cabrera's Home Improvement Contract (B&P Code §7159), matching
        the company's own fillable template field-for-field. Project description
        and payment-schedule preview are drawn from the estimate; the full
        payment schedule is a separate attachment (see
        generate_payment_schedule_attachment_pdf) referenced exactly as the
        template itself references it ("see attachment for remaining progress
        payments").

        adobe_tags: when True, embeds Adobe Acrobat Sign's text-tag syntax
        (tiny, near-invisible text Adobe auto-detects on ingest) into both
        signature points the template has — the end-of-terms signature block
        and the final execution block. Leave False for the plain print copy.
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
        tag_st   = ParagraphStyle("c_tag",   fontSize=1,  textColor=colors.white, leading=1)

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

        def _sig_cell(label, tag_id):
            if adobe_tags:
                return [Paragraph(label, small_st), Paragraph(tag_id, tag_st)]
            return Paragraph(label, small_st)

        # ── Title ─────────────────────────────────────────────────────────────
        story.append(Paragraph("HOME IMPROVEMENT CONTRACT", hdr_st))
        story.append(Paragraph("Business and Professions Code §7159", sub_st))

        today = date.today()
        agreement_line = (f"This AGREEMENT is made as of the {today.day} day of "
                           f"{today.strftime('%B')}, {today.year}, between the "
                           f"Owner and Contractor below.")
        story.append(Paragraph(agreement_line, body_st))
        story.append(Spacer(1, 4))

        # ── Owner / Contractor ────────────────────────────────────────────────
        owner_info = [
            Paragraph("<b>OWNER</b>", lbl_st),
            Paragraph(project.customer_name, body_st),
            Paragraph(project.property_address, body_st),
        ]
        contractor_info = [
            Paragraph("<b>CONTRACTOR</b>", lbl_st),
            Paragraph(COMPANY["name"], body_st),
            Paragraph(COMPANY["address"], body_st),
            Paragraph(COMPANY["license"], body_st),
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

        story.append(Paragraph(
            'The "NOTICE OF CANCELLATION" may be sent to the Contractor at the address or '
            'email address shown above. <b>You are entitled to a completely filled-in copy '
            'of this agreement, signed by both you and the Contractor, before any work may '
            'be started.</b>',
            ParagraphStyle("cancel_note", fontSize=7.5, textColor=GREY,
                           backColor=colors.HexColor("#f0f7ff"), borderPadding=5, leading=11)))

        # ── Project ───────────────────────────────────────────────────────────
        _sec("THE PROJECT IS")
        site = project_site or project.property_address
        story.append(_field_table([("Name and Address:", f"{project.name} — {site}")],
                                   [1.6*inch, 5.4*inch]))
        story.append(Spacer(1, 4))

        story.append(Paragraph(
            "Description of the Project and Significant Materials to be Used "
            "and Equipment to be Installed:", bold_st))
        if estimate and estimate.line_items:
            by_section = defaultdict(list)
            for item in estimate.line_items:
                by_section[item.section].append(item)
            desc_lines = []
            for section, items in by_section.items():
                desc_lines.append(f"<b>{section}</b>")
                for it in items:
                    desc_lines.append(f"&nbsp;&nbsp;• {it.description}  (Qty: {it.qty:g} {it.unit})")
            desc_text = "<br/>".join(desc_lines)
        else:
            desc_text = "See attached scope of work."
        story.append(Paragraph(desc_text, body_st))
        story.append(Spacer(1, 4))

        story.append(Paragraph("<b>List of Documents Attached and Incorporated into "
                                "the Contract:</b>", bold_st))
        story.append(Paragraph(
            "1. Notice of Cancellation Form<br/>"
            "2. Home Improvement Change Order Form<br/>"
            "3. California Residential Contracts – Required Attachments and Checklists<br/>"
            "4. Attachment A – Schedule of Progress Payments",
            body_st))

        # ── Contract Price & Payment ──────────────────────────────────────────
        _sec("CONTRACT PRICE & PAYMENT")
        contract_total = estimate.total if estimate else 0.0
        story.append(_field_table([
            ("Contract Price:", f"${contract_total:,.2f}"),
            ("Finance Charge (if applicable):", "$0.00"),
        ], [2.2*inch, 4.8*inch]))
        story.append(Spacer(1, 4))
        story.append(Table([[Paragraph(
            "<b>THE DOWN PAYMENT MAY NOT EXCEED $1,000 OR 10% OF THE CONTRACT PRICE, "
            "WHICHEVER IS LESS.</b>", warn_st)]], colWidths=[7.0*inch]))
        story.append(Spacer(1, 4))

        first_payment = (estimate.payment_schedule[0] if estimate and estimate.payment_schedule
                         else None)
        dp_amount = f"${first_payment.amount:,.2f}" if first_payment else "$___________"
        dp_due = (str(first_payment.due_date) if first_payment and first_payment.due_date
                  else "Upon signing")
        story.append(_field_table([
            ("Down Payment:", f"{dp_amount}  —  Due: {dp_due}"),
        ], [2.2*inch, 4.8*inch]))

        # ── Schedule of Progress Payments ────────────────────────────────────
        _sec("SCHEDULE OF PROGRESS PAYMENTS")
        pay_hdr = [[
            Paragraph("<b>Work to be completed, materials and equipment supplied</b>", small_st),
            Paragraph("<b>Amount Due</b>", small_st),
            Paragraph("<b>When Due</b>", small_st),
        ]]
        preview_rows = (estimate.payment_schedule[:2] if estimate and estimate.payment_schedule
                        else [])
        pay_rows = [[
            Paragraph(item.label + (f" — {item.description}" if item.description else ""),
                      body_st),
            f"${item.amount:,.2f}", str(item.due_date or "Per milestone"),
        ] for item in preview_rows]
        if not pay_rows:
            pay_rows = [["", "", ""]]
        pay_t = Table(pay_hdr + pay_rows, colWidths=[3.5*inch, 1.5*inch, 2.0*inch])
        pay_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(pay_t)
        story.append(Paragraph("see attachment for remaining progress payments", small_st))
        story.append(Spacer(1, 4))

        story.append(Paragraph(
            "The schedule of progress payments must specifically describe each phase of "
            "work, including the type and amount of work or services scheduled to be "
            "supplied in each phase, along with the amount of each proposed progress "
            "payment. <b>IT IS AGAINST THE LAW FOR A CONTRACTOR TO COLLECT PAYMENT FOR "
            "WORK NOT YET COMPLETED, OR FOR MATERIALS NOT YET DELIVERED. HOWEVER, A "
            "CONTRACTOR MAY REQUIRE A DOWN PAYMENT.</b>", small_st))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "Upon satisfactory payment made for any portion of the work performed, the "
            "Contractor, prior to any further payment being made, shall furnish to the "
            "Owner a full and unconditional release from any potential lien claimant claim "
            "or mechanics lien authorized pursuant to Sections 8400 and 8404 of the Civil "
            "Code for that portion of the work for which payment has been made.", small_st))

        # ── Dates ─────────────────────────────────────────────────────────────
        start_str = (str(start_date) if start_date
                     else (str(project.start_date) if project.start_date else "To be determined"))
        dur_str = f"{project.duration_days} days" if project.duration_days else None
        completion_str = (str(completion_date) if completion_date
                          else (f"Approx. {dur_str} from start" if dur_str
                                else "To be determined"))
        story.append(Spacer(1, 4))
        story.append(_field_table([
            ("Approximate Start Date:", start_str),
            ("Approximate Completion Date:", completion_str),
        ], [2.2*inch, 4.8*inch]))
        story.append(Paragraph(
            "Substantial commencement of the work shall mean when the first installation "
            "of work or delivery of materials occurs at the Project.", small_st))

        # ── Workers' Comp ─────────────────────────────────────────────────────
        _sec("WORKERS' COMPENSATION INSURANCE (check one)")
        story.append(Paragraph(
            "[ ]  This Contractor has no employees and is exempt from workers' compensation "
            "requirements.<br/>"
            "[X]  This Contractor carries workers' compensation insurance for all employees.",
            body_st))

        story.append(PageBreak())

        # ── Subcontractors ────────────────────────────────────────────────────
        _sec("USE OF SUBCONTRACTORS (required disclosure)")
        subs = subcontractors or []
        has_subs = bool(subs)
        story.append(Paragraph(
            "Will one or more subcontractors be used on this project?  " +
            ("<b>Yes</b>  [X]    No  [ ]" if has_subs else "Yes  [ ]    <b>No</b>  [X]"),
            body_st))
        if has_subs:
            story.append(Paragraph(
                "One or more subcontractors will be used on this project, and the "
                "contractor is aware that a list of subcontractors is required to be "
                "provided, upon request, along with the names, contact information, "
                "license number, and classification of those subcontractors.",
                ParagraphStyle("sub_note", fontSize=7.5, textColor=GREY,
                               backColor=colors.HexColor("#f0f7ff"), borderPadding=5,
                               leading=11, spaceBefore=4)))
            story.append(Spacer(1, 4))
            sub_data = [[
                Paragraph("<b>Subcontractor Name</b>", lbl_st),
                Paragraph("<b>License #</b>", lbl_st),
                Paragraph("<b>Classification</b>", lbl_st),
                Paragraph("<b>Scope of Work</b>", lbl_st),
            ]]
            for s_row in subs:
                sub_data.append([
                    Paragraph(s_row.get("name", ""), body_st),
                    Paragraph(s_row.get("license", ""), body_st),
                    Paragraph(s_row.get("classification", ""), body_st),
                    Paragraph(s_row.get("scope", ""), body_st),
                ])
            sub_t = Table(sub_data, colWidths=[2.0*inch, 1.0*inch, 1.2*inch, 2.8*inch])
            sub_t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ]))
            story.append(sub_t)

        # ── CGL Insurance ─────────────────────────────────────────────────────
        _sec("COMMERCIAL GENERAL LIABILITY INSURANCE (CGL) (check one)")
        story.append(Paragraph(
            "[ ]  This Contractor does not carry commercial general liability insurance.<br/>"
            "[X]  This Contractor carries commercial general liability insurance.  "
            "Insurer: Evanston &nbsp;&nbsp; Phone: (916) 482-9600<br/>"
            "[ ]  This Contractor is self-insured.<br/>"
            "[ ]  This Contractor is a limited liability company that carries liability "
            "insurance or maintains other security as required by law.",
            body_st))

        # ── Payment Terms ─────────────────────────────────────────────────────
        _sec("PAYMENT TERMS")
        story.append(Table([[Paragraph(
            "<b>Cash / Check Discount (Credit-Card-Inclusive Pricing):</b> The Contract "
            "Price stated in this Agreement is the price for payment by credit card and "
            "already includes the Contractor's cost of accepting credit cards. If the "
            "Owner pays the Contract Price, the down payment, or any progress payment by "
            "cash, check, or electronic bank transfer, that payment will be reduced by "
            "three percent (3%) as a cash discount. Payments made by credit card are "
            "charged at the full stated amount with no discount. This discount applies "
            "only in lieu of credit card payment and does not apply to debit card "
            "payments. Before processing any payment, the Contractor will state both the "
            "discounted (cash/check) amount and the non-discounted (credit card) amount.",
            ParagraphStyle("pay_terms", fontSize=7.5, textColor=GREY,
                           backColor=colors.HexColor("#f0f7ff"), borderPadding=6,
                           leading=11))]], colWidths=[7.0*inch]))

        # ── Terms and Conditions ──────────────────────────────────────────────
        _sec("TERMS AND CONDITIONS")
        tc_items = [
            ("Responsibility for Completion:",
             "The Contractor is the prime (direct) contractor and is responsible for "
             "completion of the project in accordance with this home improvement "
             "contract, the plans, and the specifications. The use of subcontractors "
             "does not relieve the Contractor of this responsibility, nor does it excuse "
             "any subcontractor or home improvement salesperson from administrative "
             "discipline for violations of the home improvement contract laws."),
            ("Plans and Specifications:",
             "The project shall be constructed according to the Plans, Drawings, and "
             "Specifications. Contractor shall be entitled to rely on the accuracy of the "
             "Plans, Drawings, and Specifications provided by Owner. Contractor shall be "
             "entitled to a change in the Contract Sum and Contract Time if the Plans, "
             "Drawings and Specifications contain errors."),
            ("Property Insurance:",
             "Owner shall purchase and maintain, until final payment is due, property "
             "insurance in the amount of the initial Contract Sum plus subsequent "
             "modifications for the entire Work at the site written on an All-Risk policy "
             "form and shall name Contractor as an additional insured. If the Project, or "
             "any portion thereof, is destroyed or damaged by accident, disaster or "
             "calamity resulting from any cause, Contractor shall nevertheless be paid for "
             "all Work completed, Work in progress, and the cost of the Work as of the "
             "date of the calamity, to the extent covered by said all-risk policy."),
            ("Waiver of Subrogation:",
             "The Owner and Contractor waive all rights against each other and any of "
             "their subcontractors, agents and employees for damages caused by fire or "
             "other causes of loss to the extent covered by property insurance applicable "
             "to the work."),
            ("Right to Stop Work:",
             "Contractor shall have the right to cease work on the Project if any amount "
             "due Contractor has not been paid when due."),
            ("Permits:",
             "Contractor shall obtain and pay for all required building permits. Owner "
             "shall be responsible for all taxes, assessments and charges required by "
             "public agencies."),
            ("Attorneys' Fees:",
             "In any dispute relating to the interpretation or enforcement of this "
             "Agreement, the prevailing party shall be entitled to its costs and "
             "attorneys' fees."),
            ("Bankruptcy:",
             "If either party files for Bankruptcy or makes an assignment for creditors, "
             "the other party has the right to cancel this Agreement."),
            ("Assignment:",
             "Neither party shall assign its rights or delegate its duties under this "
             "Agreement without prior written consent of the other."),
            ("Delay:",
             "Contractor shall be excused for any delay and may be entitled to an "
             "increase in the Contract Time due to any event beyond the reasonable "
             "control of Contractor, including: acts of God; acts of neglect of Owner; "
             "failure of Owner to promptly process submittals, payment applications, or "
             "change orders; delays caused by work not the responsibility of Contractor; "
             "acts of neglect of separate contractors employed by Owner; delays caused by "
             "public utilities or government bodies; materials embargoes; labor troubles; "
             "fire; delays in transportation; changes ordered in the Work; wrongful "
             "failure of Owner to make payments required under the Contract Documents; or "
             "other causes beyond Contractor's reasonable control."),
            ("Bond:",
             "The Owner, or tenant, shall have the right to require Contractor to procure "
             "a performance and payment bond."),
        ]
        tc_lbl_st = ParagraphStyle("tc_lbl", fontSize=8, fontName="Helvetica-Bold",
                                    textColor=BRAND, spaceAfter=1)
        tc_body_st = ParagraphStyle("tc_body", fontSize=8, textColor=GREY,
                                     leading=11, spaceAfter=5)
        for label, text in tc_items:
            story.append(Paragraph(label, tc_lbl_st))
            story.append(Paragraph(text, tc_body_st))

        # ── First signature point (end of Terms and Conditions) ──────────────
        story.append(Spacer(1, 12))
        sig1_data = [
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [_sig_cell("OWNER SIGN HERE", "{{Sig_es_:signer2:signature}}"),
             _sig_cell("CONTRACTOR OR AGENT SIGN HERE", "{{Sig_es_:signer1:signature}}")],
            [Spacer(1, 10), Spacer(1, 10)],
            [HRFlowable(width="100%", thickness=0.5, color=GREY), Paragraph("", small_st)],
            [Paragraph("If More Than One Owner, Second Owner Sign Here", small_st),
             Paragraph("", small_st)],
        ]
        sig1_t = Table(sig1_data, colWidths=[3.5*inch, 3.5*inch])
        sig1_t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.append(sig1_t)

        story.append(PageBreak())

        # ── Note About Extra Work and Change Orders ──────────────────────────
        _sec("NOTE ABOUT EXTRA WORK AND CHANGE ORDERS")
        story.append(Paragraph(
            "Extra Work and Change Orders become part of the contract once the order is "
            "prepared in writing and signed by the parties prior to the commencement of "
            "any work covered by the new change order. The order must describe the scope "
            "of the extra work or change, the cost to be added or subtracted from the "
            "contract, and the effect the order will have on the schedule of progress "
            "payments. The Owner may not require the Contractor to perform extra work "
            "without written authorization prior to the commencement of work covered by "
            "the new change order. Extra work or a change order is not enforceable "
            "against the Owner unless it identifies, in writing, prior to commencement of "
            "the covered work: (i) the scope of work encompassed by the order; (ii) the "
            "amount to be added or subtracted from the contract; (iii) the effect the "
            "order will make in the progress payments or the completion date.", body_st))

        # ── Mechanics Lien Warning ────────────────────────────────────────────
        _sec("MECHANICS LIEN WARNING")
        lien_t = Table([[Paragraph(
            "Anyone who helps improve your property, but who is not paid, may record what "
            "is called a <b>mechanics lien</b> on your property. A mechanics lien is a "
            "claim, like a mortgage or home equity loan, made against your property and "
            "recorded with the county recorder.<br/><br/>"
            "Even if you pay your contractor in full, unpaid subcontractors, suppliers, "
            "and laborers who helped to improve your property may record mechanics liens "
            "and sue you in court to foreclose the lien. If a court finds the lien is "
            "valid, you could be forced to pay twice or have a court officer sell your "
            "home to pay the lien.<br/><br/>"
            "To preserve their right to record a lien, each subcontractor and material "
            "supplier must provide you with a document called a 'Preliminary Notice.' "
            "<b>BE CAREFUL.</b> The Preliminary Notice can be sent up to 20 days after the "
            "subcontractor starts work or the supplier provides material.<br/><br/>"
            "<b>PROTECT YOURSELF FROM LIENS.</b> Get a list from your contractor of all "
            "subcontractors and material suppliers on your project, find out when they "
            "started work or delivered goods, then wait 20 days, paying attention to the "
            "Preliminary Notices you receive. <b>PAY WITH JOINT CHECKS</b> payable to both "
            "the contractor and the subcontractor or material supplier.<br/><br/>"
            "<b>REMEMBER, IF YOU DO NOTHING, YOU RISK HAVING A LIEN PLACED ON YOUR HOME.</b> "
            "For more information visit www.cslb.ca.gov or call CSLB at 800-321-CSLB (2752).",
            ParagraphStyle("lien", fontSize=7.5, textColor=GREY, leading=11,
                           backColor=colors.HexColor("#fff8e1"),
                           borderPadding=6))]], colWidths=[7.0*inch])
        lien_t.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.5, ORANGE),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(lien_t)

        # ── CSLB Info ─────────────────────────────────────────────────────────
        _sec("INFORMATION ABOUT THE CONTRACTORS' STATE LICENSE BOARD (CSLB)")
        story.append(Paragraph(
            "CSLB is the state consumer protection agency that licenses and regulates "
            "construction contractors. Use only licensed contractors. If you file a "
            "complaint against a licensed contractor within the legal deadline (usually "
            "four years), CSLB has authority to investigate the complaint. If you use an "
            "unlicensed contractor, CSLB may not be able to help you resolve your "
            "complaint.<br/><br/>"
            "Visit CSLB's website at www.cslb.ca.gov · Call CSLB at 800-321-CSLB (2752) · "
            "Write CSLB at P.O. Box 26000, Sacramento, CA 95826", body_st))

        story.append(PageBreak())

        # ── Arbitration ───────────────────────────────────────────────────────
        _sec("ARBITRATION OF DISPUTES")
        arb_t = Table([[Paragraph(
            "Any dispute arising out of or relating to the negotiation, award, "
            "construction, performance or non-performance of any aspect of this "
            "agreement shall be settled by binding arbitration in accordance with the "
            "Construction Industry Rules of the American Arbitration Association.<br/><br/>"
            "<b>NOTICE: BY INITIALING BELOW YOU ARE AGREEING TO HAVE ANY DISPUTE DECIDED "
            "BY NEUTRAL ARBITRATION AS PROVIDED BY CALIFORNIA LAW AND YOU ARE GIVING UP "
            "ANY RIGHTS YOU MIGHT POSSESS TO HAVE THE DISPUTE LITIGATED IN A COURT OR "
            "JURY TRIAL. YOUR AGREEMENT TO THIS ARBITRATION PROVISION IS VOLUNTARY.</b>",
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
        story.append(Table([[
            Paragraph("Owner's Initials: _______", body_st),
            Paragraph("Contractor's Initials: _______", body_st),
        ]], colWidths=[3.5*inch, 3.5*inch]))

        # ── Right to Cancel ───────────────────────────────────────────────────
        _sec("THREE / FIVE¹ / SEVEN² DAY RIGHT TO CANCEL")
        story.append(Paragraph(
            "You, the Owner, have the right to cancel this contract within three, five "
            "or seven business days. You may cancel by e-mailing, mailing, faxing, or "
            "delivering a written notice to the Contractor at the Contractor's place of "
            "business by midnight of the applicable business day after you received a "
            "signed and dated copy of the contract that includes this notice.<br/><br/>"
            "If you cancel, the Contractor must return to you anything you paid within 10 "
            "days of receiving the notice of cancellation.", body_st))
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>Acknowledgement of receipt of Right to Cancel Notice:</b>",
                                bold_st))
        story.append(Table([[
            Paragraph("Owner's Signature: _______________________________", body_st),
            Paragraph("Date: _______________", body_st),
        ]], colWidths=[4.5*inch, 2.5*inch]))
        story.append(Paragraph(
            "¹ Five day cancellation notice is only available to an Owner (or buyer) who "
            "is a senior citizen. &nbsp;&nbsp; ² Seven day cancellation notice is only "
            "used for contracts for the repair or restoration of a residential premises "
            "damaged by a disaster upon which a state of emergency has been declared.",
            small_st))

        # ── Final Signatures ──────────────────────────────────────────────────
        _sec("AGREEMENT & SIGNATURES")
        story.append(Table([[Paragraph(
            "THIS AGREEMENT IS ENTERED INTO AS OF THE DAY AND YEAR STATED ABOVE. THIS "
            "AGREEMENT EXPRESSLY INCORPORATES ALL TERMS AND CONDITIONS SET FORTH HEREIN, "
            "AND ANY ATTACHMENTS OR EXHIBITS ATTACHED HERETO. THIS AGREEMENT IS EXECUTED "
            "IN AT LEAST TWO ORIGINAL COPIES, OF WHICH ONE IS TO BE DELIVERED TO THE "
            "CONTRACTOR AND ONE TO THE OWNER.",
            ParagraphStyle("ag_notice", fontSize=8, fontName="Helvetica-Bold",
                           textColor=BRAND, alignment=TA_CENTER,
                           backColor=colors.HexColor("#f0f7ff"),
                           borderPadding=5))]], colWidths=[7.0*inch]))
        story.append(Spacer(1, 14))

        sig2_data = [
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [_sig_cell("OWNER (SIGNATURE)", "{{Sig_es_:signer2:signature}}"),
             _sig_cell("CONTRACTOR (SIGNATURE)", "{{Sig_es_:signer1:signature}}")],
            [Spacer(1, 10), Spacer(1, 10)],
            [HRFlowable(width="100%", thickness=0.5, color=GREY),
             HRFlowable(width="100%", thickness=0.5, color=GREY)],
            [Paragraph(f"OWNER (PRINT NAME AND TITLE):<br/>{project.customer_name}",
                       small_st),
             Paragraph(f"CONTRACTOR (PRINT NAME AND TITLE):<br/>{COMPANY['representative']}"
                       f"  —  {COMPANY['name']}", small_st)],
        ]
        sig2_t = Table(sig2_data, colWidths=[3.5*inch, 3.5*inch])
        sig2_t.setStyle(TableStyle([
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(sig2_t)
        story.append(Spacer(1, 10))

        story.append(Paragraph(
            f"{COMPANY['representative']}  ·  {COMPANY['name']}  ·  {COMPANY['license']}  ·  "
            f"Tel: {COMPANY['phone']}  ·  {COMPANY['email']}  ·  {COMPANY['address']}",
            ParagraphStyle("footer_co", fontSize=7, textColor=GREY,
                           alignment=TA_CENTER, spaceBefore=4)))

        doc.build(story)
        return path

    # ── Payment Schedule Attachment ───────────────────────────────────────────

    def generate_payment_schedule_attachment_pdf(self, project: Project, estimate) -> str:
        """"Attachment A – Schedule of Progress Payments," referenced by the
        contract's own "see attachment for remaining progress payments" note."""
        s = self._styles
        filename = f"attachment_payment_schedule_{project.name.replace(' ', '_')}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)

        story.append(Paragraph("ATTACHMENT A", ParagraphStyle(
            "att_hdr", fontSize=13, fontName="Helvetica-Bold", textColor=WHITE,
            backColor=BRAND, alignment=TA_CENTER, borderPadding=8, spaceAfter=2)))
        story.append(Paragraph("Schedule of Progress Payments", ParagraphStyle(
            "att_sub", fontSize=10, textColor=GREY, alignment=TA_CENTER, spaceAfter=8)))
        story.append(Paragraph(f"{project.name} — {project.property_address}",
                                ParagraphStyle("att_proj", fontSize=9, textColor=GREY,
                                               alignment=TA_CENTER, spaceAfter=10)))

        rows = [[
            Paragraph("<b>Work to be completed, materials and equipment supplied</b>",
                      s["small"]),
            Paragraph("<b>Amount Due</b>", s["small"]),
            Paragraph("<b>When Due</b>", s["small"]),
        ]]
        schedule = estimate.payment_schedule if estimate else []
        for item in schedule:
            rows.append([
                Paragraph(item.label + (f" — {item.description}" if item.description else ""),
                          s["small"]),
                f"${item.amount:,.2f}", str(item.due_date or "Per milestone"),
            ])
        total = sum(item.amount for item in schedule)
        rows.append([Paragraph("<b>TOTAL</b>", s["small"]), f"<b>${total:,.2f}</b>", ""])

        t = Table(rows, colWidths=[3.7*inch, 1.5*inch, 1.8*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), LIGHT_BLUE),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f8f8f8")]),
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#f0f0f0")),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "IT IS AGAINST THE LAW FOR A CONTRACTOR TO COLLECT PAYMENT FOR WORK NOT YET "
            "COMPLETED, OR FOR MATERIALS NOT YET DELIVERED. HOWEVER, A CONTRACTOR MAY "
            "REQUIRE A DOWN PAYMENT.",
            ParagraphStyle("att_notice", fontSize=7.5, fontName="Helvetica-Bold",
                           textColor=RED, backColor=colors.HexColor("#fff3cd"),
                           borderPadding=5, leading=11)))

        story += _footer_para(s)
        doc.build(story)
        return path

    # ── Notice of Cancellation ────────────────────────────────────────────────

    def generate_notice_of_cancellation_pdf(self, project: Project) -> str:
        """Standalone Notice of Cancellation, printed twice (two pages) since
        the source form is explicitly "to be provided in duplicate."""
        s = self._styles
        filename = f"notice_of_cancellation_{project.name.replace(' ', '_')}.pdf"
        doc, path = self._make_doc(filename)
        story = []

        def _copy():
            copy_story = []
            copy_story.append(Paragraph("NOTICE OF CANCELLATION", ParagraphStyle(
                "noc_hdr", fontSize=13, fontName="Helvetica-Bold", alignment=TA_CENTER,
                textColor=BRAND, spaceAfter=2)))
            copy_story.append(Paragraph("(to be provided in duplicate)", ParagraphStyle(
                "noc_sub", fontSize=8, textColor=GREY, alignment=TA_CENTER, spaceAfter=8)))
            copy_story.append(Paragraph(
                f'The "Notice of Cancellation" may be sent to the Contractor at the '
                f'address or email address below.<br/>'
                f'<b>{COMPANY["name"]}</b> | {COMPANY["address"]} | {COMPANY["phone"]} | '
                f'{COMPANY["email"]}', s["small"]))
            copy_story.append(Spacer(1, 8))
            copy_story.append(Paragraph(f"Date of Transaction: {date.today()}", s["body"]))
            copy_story.append(Spacer(1, 4))
            copy_story.append(Paragraph(
                "You may cancel this transaction, without any penalty or obligation, "
                "within three (3), five (5) or seven (7) business days from the above "
                "date.", s["body"]))
            copy_story.append(Paragraph(
                "If you cancel, any property traded in, any payments made by you under "
                "the contract or sale, and any negotiable instrument executed by you will "
                "be returned within 10 days following receipt by the Contractor of your "
                "cancellation notice, and any security interest arising out of the "
                "transaction will be canceled.", s["small"]))
            copy_story.append(Paragraph(
                "If you cancel, you must make available to the Contractor at your "
                "residence, in substantially as good condition as when received, any "
                "goods delivered to you under this contract.", s["small"]))
            copy_story.append(Spacer(1, 12))
            copy_story.append(Paragraph("I, Owner, hereby cancel this transaction:",
                                         s["body"]))
            copy_story.append(Spacer(1, 20))
            copy_story.append(HRFlowable(width="60%", thickness=0.5, color=GREY))
            copy_story.append(Paragraph("Date", s["small"]))
            copy_story.append(Spacer(1, 16))
            copy_story.append(HRFlowable(width="60%", thickness=0.5, color=GREY))
            copy_story.append(Paragraph("Owner's Signature", s["small"]))
            return copy_story

        story += _company_header(s)
        story += _copy()
        story.append(PageBreak())
        story += _company_header(s)
        story += _copy()

        doc.build(story)
        return path

    # ── Blank Change Order Form (reference attachment) ───────────────────────

    def generate_blank_change_order_form_pdf(self, project: Project) -> str:
        """The blank Change Order form itself, attached as a reference document
        per the contract's "List of Documents Attached" — distinct from
        generate_change_order_pdf, which fills one in with real change data."""
        s = self._styles
        filename = f"blank_change_order_form_{project.name.replace(' ', '_')}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)
        story += self._change_order_body(project, contract=None, change_order=None, s=s)
        doc.build(story)
        return path

    # ── Required Attachments Checklist ────────────────────────────────────────

    def generate_required_attachments_checklist_pdf(self, project: Project,
                                                      contract_number: str = "") -> str:
        """Reproduces Cabrera's "California Residential Contracts – Required
        Attachments and Checklist" — a working document Sam reviews and checks
        off by hand; the app doesn't attempt to verify individual items."""
        s = self._styles
        filename = f"checklist_{project.name.replace(' ', '_')}.pdf"
        doc, path = self._make_doc(filename)
        story = []
        story += _company_header(s)

        story.append(Paragraph("CALIFORNIA RESIDENTIAL CONTRACTS", ParagraphStyle(
            "chk_hdr", fontSize=14, fontName="Helvetica-Bold", alignment=TA_CENTER,
            textColor=BRAND, spaceAfter=2)))
        story.append(Paragraph(
            "Required Attachments and Compliance Checklist · Home Improvement (B&amp;P Code §7159)",
            ParagraphStyle("chk_sub", fontSize=9, textColor=GREY, alignment=TA_CENTER,
                           spaceAfter=8)))

        story.append(Table([[
            Paragraph("<b>Owner:</b>", s["small"]), Paragraph(project.customer_name, s["body"]),
            Paragraph("<b>Contract Date:</b>", s["small"]), Paragraph(str(date.today()), s["body"]),
        ], [
            Paragraph("<b>Project Address:</b>", s["small"]),
            Paragraph(project.property_address, s["body"]),
            Paragraph("<b>Contract #:</b>", s["small"]), Paragraph(contract_number or "—", s["body"]),
        ]], colWidths=[1.1*inch, 2.4*inch, 1.1*inch, 2.4*inch]))
        story.append(Spacer(1, 8))

        story.append(Paragraph(
            "Use this checklist to confirm the Home Improvement Contract contains every "
            "element required by California law and that all required documents are "
            "attached before the contract is signed and before work begins. Items marked "
            "<b>(2026)</b> reflect changes effective January 1, 2026 (SB 517 / AB 1327).",
            s["small"]))

        def _section(title, items):
            story.append(Paragraph(f"  {title}", s["section_hdr"]))
            story.append(Spacer(1, 3))
            for item in items:
                story.append(Paragraph(f"[ ]  {item}", ParagraphStyle(
                    "chk_item", fontSize=8, textColor=colors.black, leading=11,
                    spaceAfter=3)))
            story.append(Spacer(1, 4))

        _section("A. Required Contract Contents (B&amp;P §7159)", [
            "Contract is in writing, signed and dated by both Owner and Contractor, with "
            "a completely filled-in copy given to the Owner before any work begins.",
            "Contractor's name, business address, and CSLB license number.",
            "Section titled \"Contract Price\" stating the total price.",
            "Description of the project and significant materials/equipment.",
            "Down payment does not exceed the lesser of $1,000 or 10% of the contract "
            "price, with the required down-payment notice.",
            "Schedule of progress payments describing each phase and amount.",
            "Approximate start date and approximate completion date.",
            "\"Note About Extra Work and Change Orders\" included.",
            "Mechanics Lien Warning included.",
            "Information about the CSLB included.",
            "Three-day Notice of Cancellation language, plus the separate Notice of "
            "Cancellation form provided in duplicate.",
            "CGL insurance disclosure (check one option).",
            "Workers' Compensation insurance disclosure (check one option).",
            "Arbitration of Disputes provision, if included, carries the required "
            "statutory notice and initial lines.",
        ])
        _section("B. New for 2026 (SB 517 / AB 1327)", [
            "(2026) Subcontractor disclosure checkbox present.",
            "(2026) If \"Yes,\" the required subcontractor disclaimer is stated in the "
            "contract and on every change order.",
            "(2026) Statement that the prime (direct) contractor is responsible for "
            "completion in accordance with the contract, plans, and specifications.",
            "(2026) Contract states the contractor's name, address, and email address, "
            "plus a phone number to help the buyer complete the cancellation form.",
            "(2026) Notice of Cancellation allows cancellation by email, in addition to "
            "mail and fax.",
        ])
        _section("C. Documents Attached and Incorporated", [
            "Notice of Cancellation form (provided in duplicate).",
            "Home Improvement Change Order form.",
            "This \"Required Attachments and Checklist\" document.",
            "Plans, drawings, and specifications, if any.",
            "Lien release / waiver forms to be used at each progress payment "
            "(Civil Code §§8400, 8404).",
        ])

        story.append(Spacer(1, 10))
        story.append(Table([[
            Paragraph("Reviewed By (Signature): _______________________________", s["small"]),
            Paragraph("Date: _______________", s["small"]),
        ]], colWidths=[4.5*inch, 2.5*inch]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "This checklist is a compliance aid based on California Business and "
            "Professions Code §7159 and related law; it is not legal advice and does not "
            "list every one of the statute's requirements. The Contractor is responsible "
            "for reviewing the current statute in full and should have contract forms "
            "reviewed by a California construction attorney.",
            ParagraphStyle("chk_disclaimer", fontSize=6.5, textColor=GREY, leading=9)))

        story += _footer_para(s)
        doc.build(story)
        return path

    # ── PDF Merging ────────────────────────────────────────────────────────────

    def merge_pdfs(self, paths: list, output_filename: str) -> str:
        """Merges multiple generated PDFs (in order) into one packet file."""
        from pypdf import PdfWriter
        writer = PdfWriter()
        for p in paths:
            writer.append(p)
        out_path = os.path.join(PDF_OUTPUT_DIR, output_filename)
        with open(out_path, "wb") as f:
            writer.write(f)
        return out_path
