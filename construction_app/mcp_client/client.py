"""
MCP Client — two implementations:
1. DirectClient: used by the Kivy UI — calls DB and services directly (no subprocess overhead)
2. ConstructionMCPClient: async MCP client for AI/agent use via stdio servers
"""
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import COMPANY
from database import Database
from models import (Project, Estimate, EstimateLineItem, PaymentScheduleItem, Invoice,
                     WorkBreakdownItem, Contract, ChangeOrder)
from services import (DocumentService, StripeService, CloudStorageService, QuickenService,
                      GoogleSheetsService, EstimateParserService, AdobeSignService)

db = Database()
doc_svc = DocumentService()
stripe_svc = StripeService()
storage_svc = CloudStorageService()
quicken_svc = QuickenService()
sheets_svc = GoogleSheetsService()
parser_svc = EstimateParserService()
adobe_svc = AdobeSignService(db)


class DirectClient:
    """
    Synchronous client used by the Kivy UI.
    Calls DB and services directly — no subprocess/stdio overhead.
    """

    # ── Projects ──────────────────────────────────────────────────────────────

    def create_project(self, name, property_address, customer_name, customer_email,
                       customer_phone="", project_type="General", start_date="",
                       duration_days="", notes=""):
        p = Project(
            id=None, name=name, property_address=property_address,
            customer_name=customer_name, customer_phone=customer_phone,
            customer_email=customer_email, project_type=project_type,
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=None,
            duration_days=int(duration_days) if str(duration_days).strip().isdigit() else None,
            notes=notes,
        )
        project_id = db.create_project(p)
        try:
            folders = storage_svc.setup_project_folders(name)
            db.update_project_drive_folders(
                project_id, folders["folder_id"],
                folders["invoices_folder_id"], folders["estimates_folder_id"],
            )
        except Exception:
            pass
        return {"project_id": project_id, "message": f"Project '{name}' created successfully."}

    def list_projects(self):
        projects = db.list_projects()
        return [{"id": p.id, "name": p.name, "customer": p.customer_name,
                 "status": p.status, "address": p.property_address} for p in projects]

    def get_project(self, project_id):
        p = db.get_project(project_id)
        if not p:
            return {"error": "Project not found"}
        return {"id": p.id, "name": p.name, "customer_name": p.customer_name,
                "customer_email": p.customer_email, "customer_phone": p.customer_phone,
                "property_address": p.property_address, "project_type": p.project_type,
                "start_date": str(p.start_date or ""),
                "duration_days": p.duration_days,
                "status": p.status, "notes": p.notes}

    def update_project_status(self, project_id, status):
        db.update_project_status(project_id, status)
        return {"message": "Status updated."}

    def update_project(self, project_id, name, property_address, customer_name,
                       customer_phone="", customer_email="", project_type="General",
                       notes="", start_date="", duration_days=""):
        dd = int(duration_days) if str(duration_days).strip().isdigit() else None
        db.update_project(project_id, name, property_address, customer_name,
                          customer_phone, customer_email, project_type, notes,
                          start_date=start_date, duration_days=dd)
        return {"message": "Project updated."}

    def delete_project(self, project_id):
        db.delete_project(project_id)
        return {"message": "Project deleted."}

    # ── Estimates ─────────────────────────────────────────────────────────────

    def create_estimate(self, project_id, line_items, payment_schedule=None,
                        tax_rate=0, permit_fees=0, discount=0, source_pdf_path=None):
        today = date.today()
        existing = db.list_estimates(project_id)
        est_num = f"EST-{project_id:03d}-{len(existing)+1:02d}"
        items = [
            EstimateLineItem(id=None, estimate_id=None, section=li["section"],
                             line_number=i+1, description=li["description"],
                             qty=li["qty"], unit=li["unit"], unit_price=li["unit_price"])
            for i, li in enumerate(line_items)
        ]
        schedule = [
            PaymentScheduleItem(id=None, estimate_id=None, payment_number=i+1,
                                label=ps.get("label", str(i+1)),
                                description=ps.get("description", ""),
                                due_date=date.fromisoformat(ps["due_date"]) if ps.get("due_date") else None,
                                amount=ps.get("amount", 0))
            for i, ps in enumerate(payment_schedule or [])
        ]
        est = Estimate(id=None, project_id=project_id, estimate_number=est_num,
                       date_issued=today, valid_until=today + timedelta(days=30),
                       prepared_by="Samuel Cabrera", tax_rate=tax_rate,
                       permit_fees=permit_fees, discount=discount,
                       line_items=items, payment_schedule=schedule,
                       source_pdf_path=source_pdf_path)
        est_id = db.create_estimate(est)
        return {"estimate_id": est_id, "estimate_number": est_num, "total": est.total}

    # ── Estimate Upload / Parsing ────────────────────────────────────────────

    def parse_estimate_pdf(self, local_path):
        """Best-effort scope-of-work extraction from an uploaded estimate PDF —
        always reviewed/edited in EstimateScreen before anything is saved."""
        return parser_svc.parse(local_path)

    def save_estimate_upload(self, project_id, local_path):
        """Copy the raw uploaded estimate PDF into UPLOAD_DIR for traceability.
        Returns the stored path to pass through as create_estimate(source_pdf_path=...)."""
        import shutil
        from config import UPLOAD_DIR
        filename = f"project{project_id}_{os.path.basename(local_path)}"
        dest = os.path.join(UPLOAD_DIR, filename)
        shutil.copy(local_path, dest)
        return {"stored_path": dest}

    def get_estimate(self, estimate_id):
        est = db.get_estimate(estimate_id)
        if not est:
            return {"error": "Estimate not found"}
        return {
            "id": est.id, "estimate_number": est.estimate_number,
            "total": est.total, "subtotal": est.subtotal,
            "tax_rate": est.tax_rate, "permit_fees": est.permit_fees,
            "discount": est.discount, "status": est.status,
            "date_issued": str(est.date_issued),
            "line_items": [
                {"section": i.section, "description": i.description,
                 "qty": i.qty, "unit": i.unit, "unit_price": i.unit_price}
                for i in est.line_items
            ],
            "payment_schedule": [
                {"label": ps.label, "description": ps.description,
                 "amount": ps.amount, "due_date": str(ps.due_date or "")}
                for ps in est.payment_schedule
            ],
        }

    def list_estimates(self, project_id):
        return [{"id": e.id, "estimate_number": e.estimate_number,
                 "total": e.total, "status": e.status, "date_issued": str(e.date_issued)}
                for e in db.list_estimates(project_id)]

    def update_estimate(self, estimate_id, line_items, payment_schedule=None,
                        tax_rate=0, permit_fees=0, discount=0):
        est = db.get_estimate(estimate_id)
        if not est:
            return {"error": "Estimate not found"}
        from datetime import date as _date
        est.tax_rate    = tax_rate
        est.permit_fees = permit_fees
        est.discount    = discount
        est.line_items  = [
            EstimateLineItem(id=None, estimate_id=estimate_id, line_number=i + 1,
                             section=it["section"], description=it["description"],
                             qty=float(it.get("qty", 1)),
                             unit=it.get("unit", "ea"),
                             unit_price=float(it.get("unit_price", 0)))
            for i, it in enumerate(line_items)
        ]
        est.payment_schedule = [
            PaymentScheduleItem(id=None, estimate_id=estimate_id, payment_number=i + 1,
                                label=ps["label"], description=ps.get("description", ""),
                                amount=float(ps["amount"]),
                                due_date=(_date.fromisoformat(ps["due_date"])
                                          if ps.get("due_date") else None))
            for i, ps in enumerate(payment_schedule or [])
        ]
        db.update_estimate(est)
        return {"message": "Estimate updated.", "estimate_number": est.estimate_number,
                "total": est.total}

    def delete_estimate(self, estimate_id):
        db.delete_estimate(estimate_id)
        return {"message": "Estimate deleted."}

    def generate_estimate_pdf(self, estimate_id):
        est = db.get_estimate(estimate_id)
        project = db.get_project(est.project_id)
        pdf_path = doc_svc.generate_estimate_pdf(project, est)
        drive_file_id = None
        drive_link = None
        if project.drive_estimates_folder_id:
            try:
                drive_file_id = storage_svc.upload_estimate(
                    pdf_path, est.estimate_number, project.drive_estimates_folder_id)
                db.update_estimate_drive_file(est.id, drive_file_id)
                drive_link = storage_svc.get_file_link(drive_file_id)
            except Exception:
                pass
        return {"pdf_path": pdf_path, "drive_link": drive_link}

    # ── Invoices ──────────────────────────────────────────────────────────────

    def create_invoice(self, project_id, description, amount, estimate_id=None,
                       tax_amount=0, due_date="", notes=""):
        project = db.get_project(project_id)
        existing = db.list_invoices(project_id)
        inv_num = f"INV-{project_id:03d}-{len(existing)+1:02d}"
        inv = Invoice(id=None, project_id=project_id, estimate_id=estimate_id,
                      invoice_number=inv_num, stripe_invoice_id=None, stripe_invoice_url=None,
                      customer_name=project.customer_name, customer_email=project.customer_email,
                      description=description, amount=amount, tax_amount=tax_amount,
                      date_issued=date.today(),
                      due_date=date.fromisoformat(due_date) if due_date else None,
                      notes=notes)
        inv_id = db.create_invoice(inv)
        return {"invoice_id": inv_id, "invoice_number": inv_num, "total": inv.total}

    def list_invoices(self, project_id):
        return [{"id": i.id, "invoice_number": i.invoice_number, "total": i.total,
                 "status": i.status, "due_date": str(i.due_date or ""),
                 "stripe_invoice_url": i.stripe_invoice_url or "",
                 "stripe_invoice_id":  i.stripe_invoice_id or "",
                 "stripe_invoice_number": i.stripe_invoice_number or ""}
                for i in db.list_invoices(project_id)]

    def delete_invoice(self, invoice_id):
        db.delete_invoice(invoice_id)
        return {"message": "Invoice deleted."}

    def generate_invoice_pdf(self, invoice_id):
        inv = db.get_invoice(invoice_id)
        project = db.get_project(inv.project_id)
        pdf_path = doc_svc.generate_invoice_pdf(project, inv)
        drive_link = None
        if project.drive_invoices_folder_id:
            try:
                fid = storage_svc.upload_invoice(pdf_path, inv.invoice_number,
                                               project.drive_invoices_folder_id)
                db.update_invoice_drive_file(inv.id, fid)
                drive_link = storage_svc.get_file_link(fid)
            except Exception:
                pass
        return {"pdf_path": pdf_path, "drive_link": drive_link}

    def update_invoice(self, invoice_id, description, amount, tax_amount=0,
                       due_date="", notes="", estimate_id=None):
        db.update_invoice(invoice_id, description, float(amount), float(tax_amount),
                          due_date or None, notes,
                          estimate_id=int(estimate_id) if estimate_id else None)
        return {"message": "Invoice updated."}

    def get_invoice(self, invoice_id):
        inv = db.get_invoice(invoice_id)
        if not inv:
            return {"error": "Invoice not found"}
        return {"id": inv.id, "invoice_number": inv.invoice_number,
                "estimate_id": inv.estimate_id,
                "description": inv.description, "amount": inv.amount,
                "tax_amount": inv.tax_amount, "total": inv.total,
                "due_date": str(inv.due_date or ""), "status": inv.status,
                "notes": inv.notes, "stripe_invoice_url": inv.stripe_invoice_url}

    # ── Stripe ────────────────────────────────────────────────────────────────

    def push_invoice_to_stripe(self, invoice_id, days_until_due=30):
        inv = db.get_invoice(invoice_id)
        project = db.get_project(inv.project_id)
        result = stripe_svc.create_invoice(project, inv, days_until_due=days_until_due)
        db.update_invoice_stripe(
            inv.id,
            result["stripe_invoice_id"],
            result["stripe_invoice_url"],
            result["status"],
            stripe_invoice_number=result.get("stripe_invoice_number", ""),
        )
        return result

    def sync_invoice_status(self, invoice_id):
        inv = db.get_invoice(invoice_id)
        result = stripe_svc.sync_invoice_status(inv.stripe_invoice_id)
        db.update_invoice_status(inv.id, result["status"], result.get("payment_date"))
        return result

    def void_stripe_invoice(self, invoice_id):
        inv = db.get_invoice(invoice_id)
        result = stripe_svc.void_invoice(inv.stripe_invoice_id)
        db.update_invoice_status(inv.id, "void")
        return result

    # ── Quicken ───────────────────────────────────────────────────────────────

    def export_to_quicken(self, project_id, account_name="Checking"):
        project = db.get_project(project_id)
        invoices = db.list_invoices(project_id)
        filepath = quicken_svc.export_project_invoices_to_qif(project, invoices, account_name)
        return {"qif_file": filepath}

    def generate_reconciliation_report(self, project_id, contract_amount=0, notes=""):
        project = db.get_project(project_id)
        invoices = db.list_invoices(project_id)
        if contract_amount == 0:
            ests = db.list_estimates(project_id)
            accepted = [e for e in ests if e.status == "accepted"]
            if accepted:
                contract_amount = accepted[0].total
        pdf_path = doc_svc.generate_reconciliation_pdf(project, invoices, contract_amount, notes)

        drive_link = None
        if project.drive_invoices_folder_id:
            try:
                fid = storage_svc.upload_reconciliation(pdf_path, project.name,
                                                       project.drive_invoices_folder_id)
                drive_link = storage_svc.get_file_link(fid)
            except Exception:
                pass

        sheet_url = None
        try:
            sheet_url = sheets_svc.create_reconciliation_sheet(
                project, invoices, contract_amount, notes)
        except Exception:
            pass

        return {"pdf_path": pdf_path, "drive_link": drive_link, "sheet_url": sheet_url}

    def reconcile_with_quicken(self, project_id, qif_filepath):
        invoices = db.list_invoices(project_id)
        return quicken_svc.reconcile_with_quicken(invoices, qif_filepath)

    def list_project_pdfs(self, project_id):
        """Return list of {name, path} dicts for PDFs generated for this project."""
        import glob as _glob
        from config import PDF_OUTPUT_DIR
        project = db.get_project(project_id)
        safe_name = project.name.replace(" ", "_") if project else ""
        pid_prefix = f"{project_id:03d}"
        patterns = [
            f"*EST-{pid_prefix}-*.pdf",
            f"*INV-{pid_prefix}-*.pdf",
            f"*{safe_name}*.pdf",
        ]
        seen = set()
        results = []
        for pat in patterns:
            for path in _glob.glob(os.path.join(PDF_OUTPUT_DIR, pat)):
                if path not in seen:
                    seen.add(path)
                    results.append({"name": os.path.basename(path), "path": path})
        results.sort(key=lambda f: os.path.getmtime(f["path"]), reverse=True)
        return results

    def generate_project_summary(self, project_id):
        project = db.get_project(project_id)
        estimates = db.list_estimates(project_id)
        invoices = db.list_invoices(project_id)
        wbs_items = db.list_wbs(project_id)
        pdf_path = doc_svc.generate_project_summary_pdf(project, estimates, invoices, wbs_items)
        drive_link = None
        if project.drive_folder_id:
            try:
                fid = storage_svc.upload_file(pdf_path,
                                             f"ProjectSummary_{project.name.replace(' ', '_')}.pdf",
                                             project.drive_folder_id)
                drive_link = storage_svc.get_file_link(fid)
            except Exception:
                pass
        return {"pdf_path": pdf_path, "drive_link": drive_link}

    def _build_contract_packet(self, project, estimate, wbs_items, start_date, completion_date,
                                subcontractors, project_site, adobe_tags=False):
        """Assembles the full contract packet: the filled contract, the payment-
        schedule attachment, the Notice of Cancellation, the blank Change Order
        form, and the Required Attachments Checklist — matching the contract's
        own "List of Documents Attached and Incorporated" section. Returns the
        merged PDF path."""
        contract_pdf = doc_svc.generate_contract_pdf(
            project, estimate, wbs_items,
            start_date=start_date, completion_date=completion_date,
            subcontractors=subcontractors, project_site=project_site,
            adobe_tags=adobe_tags,
        )
        attachment_pdf = doc_svc.generate_payment_schedule_attachment_pdf(project, estimate)
        notice_pdf = doc_svc.generate_notice_of_cancellation_pdf(project)
        blank_co_pdf = doc_svc.generate_blank_change_order_form_pdf(project)
        checklist_pdf = doc_svc.generate_required_attachments_checklist_pdf(project)
        packet_filename = f"Contract_Packet_{project.name.replace(' ', '_')}_{date.today()}.pdf"
        return doc_svc.merge_pdfs(
            [contract_pdf, attachment_pdf, notice_pdf, blank_co_pdf, checklist_pdf],
            packet_filename,
        )

    def generate_contract(self, project_id, estimate_id=None,
                           start_date=None, completion_date=None,
                           subcontractors=None, project_site=None):
        """Generate the contract packet from project overview, estimates, and work
        plan, and persist a Contract row so the Contract tab can show it later.
        Updates the existing contract in place while it's still a draft (repeated
        clicks while tweaking the form); once sent for signature, a new one is
        created."""
        project = db.get_project(project_id)
        estimates = db.list_estimates(project_id)
        wbs_items = db.list_wbs(project_id)
        if estimate_id:
            estimate = next((e for e in estimates if e.id == estimate_id), None)
        else:
            accepted = [e for e in estimates if e.status == "accepted"]
            estimate = accepted[0] if accepted else (estimates[0] if estimates else None)
        pdf_path = self._build_contract_packet(
            project, estimate, wbs_items, start_date, completion_date,
            subcontractors, project_site,
        )
        drive_link = None
        drive_file_id = None
        if project.drive_folder_id:
            try:
                drive_file_id = storage_svc.upload_file(
                    pdf_path,
                    f"Contract_Packet_{project.name.replace(' ', '_')}.pdf",
                    project.drive_folder_id)
                drive_link = storage_svc.get_file_link(drive_file_id)
            except Exception:
                pass

        resolved_estimate_id = estimate_id or (estimate.id if estimate else None)
        existing = db.get_contract_by_project(project_id)
        if existing and existing.status == "draft":
            db.update_contract(existing.id, resolved_estimate_id, pdf_path, drive_file_id,
                                start_date, completion_date, project_site, subcontractors or [])
        else:
            contract_number = f"C-{project_id:03d}-{len(db.list_contracts(project_id))+1:02d}"
            contract = Contract(
                id=None, project_id=project_id, estimate_id=resolved_estimate_id,
                contract_number=contract_number, pdf_path=pdf_path, drive_file_id=drive_file_id,
                start_date=start_date, completion_date=completion_date,
                project_site=project_site, subcontractors=subcontractors or [],
            )
            db.create_contract(contract)

        return {"pdf_path": pdf_path, "drive_link": drive_link}

    def get_contract(self, project_id):
        """The most recently generated contract for this project, or None if
        none has been generated yet — the Contract tab shows "Not available"."""
        c = db.get_contract_by_project(project_id)
        return self._contract_to_dict(c) if c else None

    def _contract_to_dict(self, c):
        return {
            "id": c.id, "project_id": c.project_id, "estimate_id": c.estimate_id,
            "contract_number": c.contract_number, "pdf_path": c.pdf_path,
            "start_date": c.start_date, "completion_date": c.completion_date,
            "project_site": c.project_site, "subcontractors": c.subcontractors,
            "status": c.status, "adobe_agreement_id": c.adobe_agreement_id,
            "adobe_agreement_status": c.adobe_agreement_status,
        }

    # ── Adobe Acrobat Sign ───────────────────────────────────────────────────

    def get_adobe_auth_url(self):
        return {"url": adobe_svc.get_authorization_url()}

    def get_adobe_status(self):
        return {"authorized": adobe_svc.is_authorized()}

    def exchange_adobe_code(self, code):
        """Called by the FastAPI OAuth callback endpoint after Adobe redirects back
        with an authorization code — never called by the Kivy UI directly."""
        return adobe_svc.exchange_code_for_token(code)

    def send_contract_for_signature(self, contract_id):
        contract = db.get_contract(contract_id)
        if not contract:
            return {"error": "Contract not found"}
        project = db.get_project(contract.project_id)
        estimates = db.list_estimates(contract.project_id)
        estimate = next((e for e in estimates if e.id == contract.estimate_id), None)
        wbs_items = db.list_wbs(contract.project_id)
        # Regenerate the full packet with Adobe Sign text tags embedded in the
        # contract's signature blocks — the plain packet served for
        # download/print is left untouched.
        pdf_path = self._build_contract_packet(
            project, estimate, wbs_items, contract.start_date, contract.completion_date,
            contract.subcontractors, contract.project_site, adobe_tags=True,
        )
        result = adobe_svc.create_agreement_from_pdf(
            pdf_path, contract.contract_number,
            sender_name=COMPANY["representative"], sender_email=COMPANY["email"],
            recipient_name=project.customer_name, recipient_email=project.customer_email,
        )
        db.update_contract_adobe_status(
            contract.id, result["status"], adobe_agreement_id=result["adobe_agreement_id"])
        return result

    def sync_contract_status(self, contract_id):
        contract = db.get_contract(contract_id)
        if not contract or not contract.adobe_agreement_id:
            return {"error": "No Adobe agreement associated with this contract"}
        result = adobe_svc.get_agreement_status(contract.adobe_agreement_id)
        db.update_contract_adobe_status(
            contract.id, result["status"],
            adobe_agreement_status=result["adobe_agreement_status"])
        return result

    # ── Change Orders ────────────────────────────────────────────────────────

    def create_change_order(self, contract_id, description, line_items, days_delta=0):
        contract = db.get_contract(contract_id)
        if not contract:
            return {"error": "Contract not found"}
        project = db.get_project(contract.project_id)
        original_price = None
        if contract.estimate_id:
            estimate = db.get_estimate(contract.estimate_id)
            original_price = estimate.total if estimate else None
        price_delta = sum(float(it.get("qty", 1) or 1) * float(it.get("unit_price", 0) or 0)
                           for it in line_items)
        existing = db.list_change_orders(contract_id)
        co_number = f"{contract.contract_number}-CO{len(existing)+1:02d}"
        co = ChangeOrder(id=None, contract_id=contract_id, change_order_number=co_number,
                          description=description, line_items=line_items,
                          price_delta=price_delta, days_delta=int(days_delta or 0))
        pdf_path = doc_svc.generate_change_order_pdf(project, contract, co,
                                                       original_price=original_price)
        co.pdf_path = pdf_path
        co_id = db.create_change_order(co)
        return {"change_order_id": co_id, "change_order_number": co_number,
                "price_delta": price_delta, "pdf_path": pdf_path}

    def list_change_orders(self, contract_id):
        return [{"id": c.id, "change_order_number": c.change_order_number,
                  "description": c.description, "price_delta": c.price_delta,
                  "days_delta": c.days_delta, "status": c.status, "pdf_path": c.pdf_path}
                for c in db.list_change_orders(contract_id)]

    # ── Cloud Storage ─────────────────────────────────────────────────────────

    def setup_storage_bucket(self, project_id):
        project = db.get_project(project_id)
        folders = storage_svc.setup_project_folders(project.name)
        db.update_project_drive_folders(project_id, folders["folder_id"],
                                         folders["invoices_folder_id"],
                                         folders["estimates_folder_id"])
        return folders

    # Keep old name as alias
    def setup_drive_folders(self, project_id):
        return self.setup_storage_bucket(project_id)

    def get_storage_info(self, project_id):
        project = db.get_project(project_id)
        return {
            "project_prefix":    project.drive_folder_id,
            "invoices_prefix":   project.drive_invoices_folder_id,
            "estimates_prefix":  project.drive_estimates_folder_id,
            "project_folder_link": storage_svc.get_folder_link(project.drive_folder_id)
                                   if project.drive_folder_id else None,
        }

    # Keep old name as alias so existing callers don't break
    def get_drive_info(self, project_id):
        return self.get_storage_info(project_id)

    # ── WBS ───────────────────────────────────────────────────────────────────

    def add_wbs_item(self, project_id, phase, task, assigned_to="",
                     estimated_hours=0, start_date="", end_date=""):
        item = WorkBreakdownItem(id=None, project_id=project_id, phase=phase, task=task,
                                  assigned_to=assigned_to, estimated_hours=estimated_hours,
                                  start_date=start_date or None, end_date=end_date or None)
        item_id = db.create_wbs_item(item)
        return {"item_id": item_id}

    def list_wbs(self, project_id):
        return [{"id": i.id, "phase": i.phase, "task": i.task, "status": i.status,
                 "assigned_to": i.assigned_to, "estimated_hours": i.estimated_hours,
                 "actual_hours": i.actual_hours}
                for i in db.list_wbs(project_id)]

    def update_wbs_status(self, item_id, status, actual_hours=None):
        db.update_wbs_status(item_id, status, actual_hours)
        return {"message": "Updated."}

    def update_wbs_item(self, item_id, phase, task, assigned_to="",
                        estimated_hours=0, start_date="", end_date=""):
        db.update_wbs_item(item_id, phase, task, assigned_to,
                           float(estimated_hours), start_date or None, end_date or None)
        return {"message": "Updated."}

    def delete_wbs_item(self, item_id):
        db.delete_wbs_item(item_id)
        return {"message": "Deleted."}


class HTTPClient:
    """
    HTTP client for the Kivy UI when API_BASE_URL is set.
    Mirrors DirectClient's interface exactly — calls the Cloud Run FastAPI backend.
    """

    def __init__(self, base_url: str):
        import requests as _req
        self._s = _req.Session()
        self._base = base_url.rstrip("/")

    def _get(self, path, **params):
        r = self._s.get(f"{self._base}{path}", params=params or None)
        r.raise_for_status()
        return r.json()

    def _post(self, path, data=None):
        r = self._s.post(f"{self._base}{path}", json=data or {})
        r.raise_for_status()
        return r.json()

    def _put(self, path, data):
        r = self._s.put(f"{self._base}{path}", json=data)
        r.raise_for_status()
        return r.json()

    def _patch(self, path, data):
        r = self._s.patch(f"{self._base}{path}", json=data)
        r.raise_for_status()
        return r.json()

    def _delete(self, path):
        r = self._s.delete(f"{self._base}{path}")
        r.raise_for_status()
        return r.json()

    def _post_file(self, path, filepath):
        with open(filepath, "rb") as f:
            r = self._s.post(f"{self._base}{path}",
                             files={"file": (os.path.basename(filepath), f, "application/pdf")})
        r.raise_for_status()
        return r.json()

    # ── Projects ──────────────────────────────────────────────────────────────

    def create_project(self, name, property_address, customer_name, customer_email,
                       customer_phone="", project_type="General", start_date="",
                       duration_days="", notes=""):
        return self._post("/api/v1/projects", dict(name=name, property_address=property_address,
            customer_name=customer_name, customer_email=customer_email,
            customer_phone=customer_phone, project_type=project_type,
            start_date=start_date, duration_days=str(duration_days), notes=notes))

    def list_projects(self):
        return self._get("/api/v1/projects")

    def get_project(self, project_id):
        return self._get(f"/api/v1/projects/{project_id}")

    def update_project_status(self, project_id, status):
        return self._patch(f"/api/v1/projects/{project_id}/status", {"status": status})

    def update_project(self, project_id, name, property_address, customer_name,
                       customer_phone="", customer_email="", project_type="General",
                       notes="", start_date="", duration_days=""):
        return self._put(f"/api/v1/projects/{project_id}", dict(name=name,
            property_address=property_address, customer_name=customer_name,
            customer_email=customer_email, customer_phone=customer_phone,
            project_type=project_type, notes=notes,
            start_date=start_date, duration_days=str(duration_days)))

    def delete_project(self, project_id):
        return self._delete(f"/api/v1/projects/{project_id}")

    # ── Estimates ─────────────────────────────────────────────────────────────

    def create_estimate(self, project_id, line_items, payment_schedule=None,
                        tax_rate=0, permit_fees=0, discount=0, source_pdf_path=None):
        return self._post("/api/v1/estimates", dict(project_id=project_id,
            line_items=line_items, payment_schedule=payment_schedule or [],
            tax_rate=tax_rate, permit_fees=permit_fees, discount=discount,
            source_pdf_path=source_pdf_path))

    def parse_estimate_pdf(self, local_path):
        return self._post_file("/api/v1/estimates/parse", local_path)

    def save_estimate_upload(self, project_id, local_path):
        # The Cloud Run container has no durable local disk and parse_estimate_pdf
        # already reads the file bytes directly — nothing additional to persist
        # server-side in HTTP mode, so there's no stored path to report.
        return {"stored_path": None}

    def get_estimate(self, estimate_id):
        return self._get(f"/api/v1/estimates/{estimate_id}")

    def list_estimates(self, project_id):
        return self._get(f"/api/v1/projects/{project_id}/estimates")

    def generate_estimate_pdf(self, estimate_id):
        return self._post(f"/api/v1/estimates/{estimate_id}/pdf")

    def update_estimate(self, estimate_id, line_items, payment_schedule=None,
                        tax_rate=0, permit_fees=0, discount=0):
        return self._put(f"/api/v1/estimates/{estimate_id}", dict(
            line_items=line_items, payment_schedule=payment_schedule or [],
            tax_rate=tax_rate, permit_fees=permit_fees, discount=discount))

    def delete_estimate(self, estimate_id):
        return self._delete(f"/api/v1/estimates/{estimate_id}")

    # ── Invoices ──────────────────────────────────────────────────────────────

    def create_invoice(self, project_id, description, amount, estimate_id=None,
                       tax_amount=0, due_date="", notes=""):
        return self._post("/api/v1/invoices", dict(project_id=project_id,
            description=description, amount=amount, estimate_id=estimate_id,
            tax_amount=tax_amount, due_date=due_date, notes=notes))

    def list_invoices(self, project_id):
        return self._get(f"/api/v1/projects/{project_id}/invoices")

    def generate_invoice_pdf(self, invoice_id):
        return self._post(f"/api/v1/invoices/{invoice_id}/pdf")

    def delete_invoice(self, invoice_id):
        return self._delete(f"/api/v1/invoices/{invoice_id}")

    def update_invoice(self, invoice_id, description, amount, tax_amount=0,
                       due_date="", notes="", estimate_id=None):
        return self._put(f"/api/v1/invoices/{invoice_id}", dict(description=description,
            amount=amount, tax_amount=tax_amount, due_date=due_date, notes=notes,
            estimate_id=estimate_id))

    def get_invoice(self, invoice_id):
        return self._get(f"/api/v1/invoices/{invoice_id}")

    # ── Stripe ────────────────────────────────────────────────────────────────

    def push_invoice_to_stripe(self, invoice_id, days_until_due=30):
        return self._post(f"/api/v1/invoices/{invoice_id}/stripe")

    def sync_invoice_status(self, invoice_id):
        return self._post(f"/api/v1/invoices/{invoice_id}/stripe/sync")

    def void_stripe_invoice(self, invoice_id):
        return self._delete(f"/api/v1/invoices/{invoice_id}/stripe")

    # ── Quicken ───────────────────────────────────────────────────────────────

    def export_to_quicken(self, project_id, account_name="Checking"):
        return self._post(f"/api/v1/projects/{project_id}/quicken/export")

    def generate_reconciliation_report(self, project_id, contract_amount=0, notes=""):
        return self._post(f"/api/v1/projects/{project_id}/reconciliation-report",
                          dict(contract_amount=contract_amount, notes=notes))

    def reconcile_with_quicken(self, project_id, qif_filepath):
        return self._post(f"/api/v1/projects/{project_id}/quicken/reconcile",
                          dict(qif_filepath=qif_filepath))

    def generate_project_summary(self, project_id):
        return self._post(f"/api/v1/projects/{project_id}/summary")

    def generate_contract(self, project_id, estimate_id=None,
                           start_date=None, completion_date=None,
                           subcontractors=None, project_site=None):
        payload = {}
        if estimate_id is not None:
            payload["estimate_id"] = estimate_id
        if start_date:
            payload["start_date"] = start_date
        if completion_date:
            payload["completion_date"] = completion_date
        if subcontractors:
            payload["subcontractors"] = subcontractors
        if project_site:
            payload["project_site"] = project_site
        return self._post(f"/api/v1/projects/{project_id}/contract", payload or None)

    def list_project_pdfs(self, project_id):
        return self._get(f"/api/v1/projects/{project_id}/pdfs")

    def get_contract(self, project_id):
        return self._get(f"/api/v1/projects/{project_id}/contract")

    # ── Adobe Acrobat Sign ───────────────────────────────────────────────────

    def get_adobe_auth_url(self):
        return self._get("/api/v1/adobe/authorize")

    def get_adobe_status(self):
        return self._get("/api/v1/adobe/status")

    def send_contract_for_signature(self, contract_id):
        return self._post(f"/api/v1/contracts/{contract_id}/adobe/send")

    def sync_contract_status(self, contract_id):
        return self._post(f"/api/v1/contracts/{contract_id}/adobe/sync")

    # ── Change Orders ────────────────────────────────────────────────────────

    def create_change_order(self, contract_id, description, line_items, days_delta=0):
        return self._post(f"/api/v1/contracts/{contract_id}/change-orders", dict(
            description=description, line_items=line_items, days_delta=days_delta))

    def list_change_orders(self, contract_id):
        return self._get(f"/api/v1/contracts/{contract_id}/change-orders")

    # ── Google Drive ──────────────────────────────────────────────────────────

    def setup_drive_folders(self, project_id):
        return self._post(f"/api/v1/projects/{project_id}/drive/setup")

    def get_drive_info(self, project_id):
        return self._get(f"/api/v1/projects/{project_id}/drive")

    # ── WBS ───────────────────────────────────────────────────────────────────

    def add_wbs_item(self, project_id, phase, task, assigned_to="",
                     estimated_hours=0, start_date="", end_date=""):
        return self._post("/api/v1/wbs", dict(project_id=project_id, phase=phase, task=task,
            assigned_to=assigned_to, estimated_hours=estimated_hours,
            start_date=start_date, end_date=end_date))

    def list_wbs(self, project_id):
        return self._get(f"/api/v1/projects/{project_id}/wbs")

    def update_wbs_status(self, item_id, status, actual_hours=None):
        return self._patch(f"/api/v1/wbs/{item_id}/status",
                           {"status": status, "actual_hours": actual_hours})

    def update_wbs_item(self, item_id, phase, task, assigned_to="",
                        estimated_hours=0, start_date="", end_date=""):
        return self._put(f"/api/v1/wbs/{item_id}", dict(phase=phase, task=task,
            assigned_to=assigned_to, estimated_hours=estimated_hours,
            start_date=start_date, end_date=end_date))

    def delete_wbs_item(self, item_id):
        return self._delete(f"/api/v1/wbs/{item_id}")


# Keep SyncMCPClient as an alias for backwards compatibility
SyncMCPClient = DirectClient
