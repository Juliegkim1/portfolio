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

        # Summary cards
        cards = [
            ["Original Contract", f"${contract_amount:,.2f}"],
            ["Total Paid", f"${total_paid:,.2f}"],
            ["Change Orders", f"${net_adjustments:,.2f}"],
            ["BALANCE DUE", f"${balance_due:,.2f}"],
        ]
        cards_table = Table([cards], colWidths=[1.75*inch]*4)
        cards_table.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BACKGROUND", (0,0), (2,0), LIGHT_BLUE),
            ("BACKGROUND", (3,0), (3,0), BRAND),
            ("TEXTCOLOR", (3,0), (3,0), WHITE),
            ("BOX", (0,0), (-1,-1), 0.5, GREY),
            ("INNERGRID", (0,0), (-1,-1), 0.5, GREY),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
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
