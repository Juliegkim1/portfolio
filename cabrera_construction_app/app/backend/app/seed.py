"""Seed data: a handful of realistic projects across different stages, plus
business receipts and bank transactions for Operational Reconciliation.

Run standalone with `python -m app.seed`, or automatically on startup when
SEED_ON_STARTUP=true (see app.config / app.main).
"""

from __future__ import annotations

import datetime as dt

from .db import Base, SessionLocal, engine
from .services import mock_integrations
from .services import reconciliation as recon_rules
from . import models


def _milestones(total: float, deposit: float, splits: list[float]) -> list[float]:
    """deposit + amounts split across `splits` (fractions summing to 1), remainder absorbed by the last."""
    remaining = round(total - deposit, 2)
    amounts = [deposit]
    running = 0.0
    for frac in splits[:-1]:
        amt = round(remaining * frac, 2)
        amounts.append(amt)
        running += amt
    amounts.append(round(remaining - running, 2))
    return amounts


def _make_estimate(db, project, number, date_issued, tax_rate, permit_fees, discount, scope_text, line_items):
    estimate = models.Estimate(
        project_id=project.id,
        estimate_number=number,
        date_issued=date_issued,
        tax_rate=tax_rate,
        permit_fees=permit_fees,
        discount=discount,
        scope_text=scope_text,
    )
    db.add(estimate)
    db.flush()
    for section, description, qty, unit, unit_price in line_items:
        db.add(models.EstimateLineItem(estimate_id=estimate.id, section=section, description=description, qty=qty, unit=unit, unit_price=unit_price))
    db.flush()
    db.refresh(estimate)
    return estimate


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Project).first():
            print("Seed data already present — skipping.")
            return

        # --- Users -----------------------------------------------------------
        db.add_all(
            [
                models.User(name="Samuel Cabrera", email="samuel@cabreraconstruction.com", role="owner", status="active", last_active_at=dt.datetime.now()),
                models.User(name="Jordan Alvarez", email="jordan@cabreraconstruction.com", role="project_manager", status="active", last_active_at=dt.datetime.now() - dt.timedelta(hours=3)),
                models.User(name="Priya Shah", email="priya@cabreraconstruction.com", role="project_manager", status="invited"),
            ]
        )

        # --- Project 1: Elena Ortiz — signed, mid-construction ----------------
        ortiz = models.Project(
            name="Elena Ortiz — 512 Maple Ave",
            project_type="Kitchen Remodel",
            customer_name="Elena Ortiz",
            customer_phone="(510) 555-0133",
            customer_email="elena.ortiz@example.com",
            property_address="512 Maple Ave, Oakland, CA 94610",
            start_date=dt.date(2026, 7, 1),
            end_date=dt.date(2026, 10, 15),
            status="active",
            drive_folder_id=mock_integrations.create_drive_folder("Elena Ortiz", "512 Maple Ave"),
            sheet_id=mock_integrations.create_sheet("Elena Ortiz Reconciliation"),
        )
        db.add(ortiz)
        db.flush()

        ortiz_estimate = _make_estimate(
            db, ortiz, "EST-3301", dt.date(2026, 6, 15), 0.0875, 500.0, 0.0,
            "Full kitchen remodel: demo existing cabinetry and flooring, new cabinets/countertops/backsplash, new flooring, repaint.",
            [
                ("demolition", "Remove existing cabinets and countertops", 1, "ea", 1100),
                ("demolition", "Remove existing flooring", 200, "sq ft", 4.5),
                ("materials", "Custom cabinetry", 1, "ea", 13800),
                ("materials", "Quartz countertops", 40, "sq ft", 95),
                ("materials", "Luxury vinyl plank flooring", 200, "sq ft", 6.75),
                ("labor", "Cabinet installation", 24, "hr", 95),
                ("labor", "Flooring installation", 200, "sq ft", 5.5),
                ("additional_work", "Under-cabinet lighting", 1, "ea", 1600),
            ],
        )

        ortiz_scope = models.ScopeSchedule(
            project_id=ortiz.id,
            contract_date=dt.date(2026, 6, 20),
            drive_file_id=mock_integrations.create_sheet("Ortiz Scope Schedule"),
            warranty_terms="Cabrera Construction warrants labor for 2 years from completion; manufacturer warranties apply to materials.",
        )
        db.add(ortiz_scope)
        db.flush()

        amounts = _milestones(ortiz_estimate.total, 1000.0, [0.35, 0.35, 0.30])
        titles = ["Deposit – Project Start", "Demo & Rough-In Complete", "Cabinets & Countertops Installed", "Final Walkthrough & Punch List"]
        due_offsets = [0, 30, 60, 90]
        ortiz_milestones = []
        for i, (title, amount, offset) in enumerate(zip(titles, amounts, due_offsets)):
            m = models.Milestone(
                scope_schedule_id=ortiz_scope.id,
                number=i,
                title=title,
                deliverable=title,
                scope_verification="PM sign-off with dated photos.",
                due_date=ortiz.start_date + dt.timedelta(days=offset),
                amount=amount,
                status="scheduled",
            )
            db.add(m)
            ortiz_milestones.append(m)
        db.flush()

        db.add(models.MaterialItem(scope_schedule_id=ortiz_scope.id, category="Cabinetry", qty="1 set", supplied_by="contractor", installed_by="contractor"))
        db.add(models.MaterialItem(scope_schedule_id=ortiz_scope.id, category="Appliances", qty="1 set", supplied_by="owner", installed_by="contractor", notes="Owner-purchased; contractor installs"))

        ortiz_cp = models.ContractPackage(
            project_id=ortiz.id,
            description=ortiz_estimate.scope_text,
            attachments=[
                {"label": "Contract pp. 1-4", "kind": "contract"},
                {"label": "Att. 1 Notice of Cancellation", "kind": "noc"},
                {"label": "Att. 2 Change Order Form", "kind": "change_order_form"},
                {"label": "Att. 3 CA Checklist", "kind": "ca_checklist"},
                {"label": "Att. 4 Scope & Payment Schedule", "kind": "scope_schedule"},
                {"label": "Att. 5 QuickBooks Estimate", "kind": "estimate"},
            ],
            status="signed",
            approved_by="Jordan Alvarez",
            approved_at=dt.datetime(2026, 6, 22, 14, 30),
            drive_file_id=mock_integrations.create_drive_folder("Elena Ortiz", "contract-package"),
            adobe_agreement_id="agreement-ortiz-001",
        )
        db.add(ortiz_cp)

        # A signed change order: +$2,000 electrical work, applied to milestone 2.
        ortiz_co = models.ChangeOrder(
            project_id=ortiz.id,
            number=1,
            owner_signed_at=dt.datetime(2026, 8, 1, 10, 0),
            contractor_signed_at=dt.datetime(2026, 8, 1, 15, 0),
            parts_changed=["scope", "price"],
            scope="Add dedicated 20A circuits and additional recessed lighting in the kitchen ceiling.",
            amount_added=2000.0,
            amount_subtracted=0.0,
            milestone_changes=[{"milestone_id": ortiz_milestones[2].id, "delta": 2000.0}],
            status="signed",
            created_at=dt.datetime(2026, 7, 28, 9, 0),
        )
        db.add(ortiz_co)
        ortiz_milestones[2].amount = float(ortiz_milestones[2].amount) + 2000.0

        db.flush()

        # Milestones 0 & 1 invoiced and paid; milestone 2 invoiced (incl. the signed CO delta); milestone 3 still scheduled.
        for i in (0, 1, 2):
            m = ortiz_milestones[i]
            inv = models.Invoice(
                milestone_id=m.id,
                invoice_number=f"INV-{ortiz.id:04d}-{m.number:02d}",
                amount=float(m.amount),
                date_issued=m.due_date,
                due_date=m.due_date + dt.timedelta(days=15),
                status="paid" if i < 2 else "open",
                qb_invoice_id=f"qb-inv-{ortiz.id}-{m.id}",
            )
            db.add(inv)
            m.status = "paid" if i < 2 else "invoiced"
        db.flush()

        ortiz_payment_receipts = []
        for i in (0, 1):
            m = ortiz_milestones[i]
            r = models.Receipt(
                project_id=ortiz.id,
                milestone_id=m.id,
                date=m.due_date + dt.timedelta(days=5),
                description=f"Elena Ortiz — {m.title} payment",
                amount=float(m.amount),
                type="payment",
                source="quickbooks",
            )
            db.add(r)
            ortiz_payment_receipts.append(r)
        ortiz_expense_receipt = models.Receipt(
            project_id=ortiz.id,
            date=dt.date(2026, 7, 10),
            description="Home Depot — lumber, drywall and fasteners",
            amount=612.44,
            type="expense",
            source="manual",
        )
        db.add(ortiz_expense_receipt)

        # --- Project 2: Lily Chen — contract out for signature -----------------
        chen = models.Project(
            name="Lily Chen — 88 Bayview Ter",
            project_type="Bathroom Remodel",
            customer_name="Lily Chen",
            customer_phone="(415) 555-0177",
            customer_email="lily.chen@example.com",
            property_address="88 Bayview Ter, San Francisco, CA 94131",
            start_date=dt.date(2026, 11, 3),
            end_date=dt.date(2027, 1, 20),
            status="active",
            drive_folder_id=mock_integrations.create_drive_folder("Lily Chen", "88 Bayview Ter"),
            sheet_id=mock_integrations.create_sheet("Lily Chen Reconciliation"),
        )
        db.add(chen)
        db.flush()

        chen_estimate = _make_estimate(
            db, chen, "EST-3305", dt.date(2026, 9, 12), 0.0925, 300.0, 0.0,
            "Primary bathroom remodel: walk-in shower, new vanity and fixtures, tile work.",
            [
                ("demolition", "Demo tub, shower enclosure and tile", 1, "ea", 900),
                ("materials", "Walk-in shower kit and glass panel", 1, "ea", 4100),
                ("materials", "Vanity, sink and fixtures", 1, "ea", 2500),
                ("materials", "Porcelain tile", 110, "sq ft", 7.25),
                ("labor", "Waterproofing and tile setting", 30, "hr", 90),
                ("labor", "Plumbing fixture installation", 12, "hr", 140),
            ],
        )
        chen_scope = models.ScopeSchedule(project_id=chen.id, contract_date=dt.date(2026, 9, 20), drive_file_id=mock_integrations.create_sheet("Chen Scope Schedule"))
        db.add(chen_scope)
        db.flush()

        chen_amounts = _milestones(chen_estimate.total, 1000.0, [0.5, 0.5])
        for i, (title, amount) in enumerate(zip(["Deposit – Project Start", "Rough-In Complete", "Final Walkthrough"], chen_amounts)):
            db.add(
                models.Milestone(
                    scope_schedule_id=chen_scope.id,
                    number=i,
                    title=title,
                    due_date=chen.start_date + dt.timedelta(days=30 * i),
                    amount=amount,
                    status="scheduled",
                )
            )

        db.add(
            models.ContractPackage(
                project_id=chen.id,
                description=chen_estimate.scope_text,
                attachments=[
                    {"label": "Contract pp. 1-4", "kind": "contract"},
                    {"label": "Att. 4 Scope & Payment Schedule", "kind": "scope_schedule"},
                    {"label": "Att. 5 QuickBooks Estimate", "kind": "estimate"},
                ],
                status="out_for_signature",
                approved_by="Jordan Alvarez",
                approved_at=dt.datetime(2026, 9, 22, 11, 0),
                drive_file_id=mock_integrations.create_drive_folder("Lily Chen", "contract-package"),
                adobe_agreement_id="agreement-chen-002",
            )
        )

        # --- Project 3: David Nguyen — closed ----------------------------------
        nguyen = models.Project(
            name="David Nguyen — 2217 Camino Real",
            project_type="Deck Rebuild",
            customer_name="David Nguyen",
            customer_phone="(408) 555-0188",
            customer_email="d.nguyen@example.com",
            property_address="2217 Camino Real, San Jose, CA 95126",
            start_date=dt.date(2026, 4, 1),
            end_date=dt.date(2026, 5, 20),
            status="completed",
            drive_folder_id=mock_integrations.create_drive_folder("David Nguyen", "2217 Camino Real"),
            sheet_id=mock_integrations.create_sheet("David Nguyen Reconciliation"),
        )
        db.add(nguyen)
        db.flush()

        nguyen_estimate = _make_estimate(
            db, nguyen, "EST-3298", dt.date(2026, 3, 10), 0.0875, 250.0, 0.0,
            "Deck rebuild: remove existing deck, install composite decking and railing.",
            [
                ("demolition", "Remove existing deck", 1, "ea", 1200),
                ("materials", "Composite decking and railing", 1, "ea", 8600),
                ("labor", "Deck framing and installation", 36, "hr", 95),
            ],
        )
        nguyen_scope = models.ScopeSchedule(project_id=nguyen.id, contract_date=dt.date(2026, 3, 15), drive_file_id=mock_integrations.create_sheet("Nguyen Scope Schedule"))
        db.add(nguyen_scope)
        db.flush()

        nguyen_amounts = _milestones(nguyen_estimate.total, 1000.0, [0.5, 0.5])
        nguyen_milestones = []
        for i, (title, amount) in enumerate(zip(["Deposit – Project Start", "Framing Complete", "Final Walkthrough"], nguyen_amounts)):
            m = models.Milestone(
                scope_schedule_id=nguyen_scope.id,
                number=i,
                title=title,
                due_date=nguyen.start_date + dt.timedelta(days=25 * i),
                amount=amount,
                status="paid",
            )
            db.add(m)
            nguyen_milestones.append(m)
        db.flush()

        db.add(
            models.ContractPackage(
                project_id=nguyen.id,
                description=nguyen_estimate.scope_text,
                status="signed",
                approved_by="Samuel Cabrera",
                approved_at=dt.datetime(2026, 3, 18, 9, 0),
                drive_file_id=mock_integrations.create_drive_folder("David Nguyen", "contract-package"),
                adobe_agreement_id="agreement-nguyen-003",
            )
        )

        nguyen_payment_receipts = []
        for m in nguyen_milestones:
            inv = models.Invoice(
                milestone_id=m.id,
                invoice_number=f"INV-{nguyen.id:04d}-{m.number:02d}",
                amount=float(m.amount),
                date_issued=m.due_date,
                due_date=m.due_date + dt.timedelta(days=15),
                status="paid",
                qb_invoice_id=f"qb-inv-{nguyen.id}-{m.id}",
            )
            db.add(inv)
            r = models.Receipt(
                project_id=nguyen.id,
                milestone_id=m.id,
                date=m.due_date + dt.timedelta(days=3),
                description=f"David Nguyen — {m.title} payment",
                amount=float(m.amount),
                type="payment",
                source="quickbooks",
            )
            db.add(r)
            nguyen_payment_receipts.append(r)

        # --- Business (non-project) expense receipts ---------------------------
        db.add_all(
            [
                models.Receipt(date=dt.date(2026, 8, 5), description="Office Depot — printer paper and ink", amount=84.50, type="expense", source="manual"),
                models.Receipt(date=dt.date(2026, 8, 18), description="Shell — company truck fuel", amount=62.10, type="expense", source="manual"),
                models.Receipt(date=dt.date(2026, 9, 2), description="Costco — unidentified purchase", amount=215.30, type="expense", source="drive_folder", needs_project=True),
            ]
        )

        db.flush()

        # --- Bank transactions (Operational Reconciliation) ---------------------
        def txn(posted_date, description, amount, **kw):
            return models.BankTransaction(
                import_id="import-seed-001",
                account="4821",
                posted_date=posted_date,
                description=description,
                amount=amount,
                vendor=recon_rules.normalize_vendor_display(description),
                fingerprint=recon_rules.fingerprint(posted_date, amount, description),
                **kw,
            )

        # Exact match: Ortiz milestone-1 payment, same amount, vendor + date within 3 days.
        m1_receipt = ortiz_payment_receipts[1]
        db.add(
            txn(
                m1_receipt.date + dt.timedelta(days=1),
                "ONLINE BANKING TRANSFER FROM ELENA ORTIZ",
                float(m1_receipt.amount),
                receipt_id=m1_receipt.id,
                project_id=ortiz.id,
                match_status="matched",
            )
        )

        # Possible match: Nguyen final payment, vendor matches but posted 9 days later.
        final_receipt = nguyen_payment_receipts[-1]
        db.add(
            txn(
                final_receipt.date + dt.timedelta(days=9),
                "DEPOSIT DAVID NGUYEN CHECK 1042",
                float(final_receipt.amount),
                receipt_id=final_receipt.id,
                project_id=nguyen.id,
                match_status="possible",
            )
        )

        # Needs attention: a debit with no receipt on file at all.
        db.add(txn(dt.date(2026, 9, 15), "THE HOME DEPOT #4521 OAKLAND CA", -340.12, match_status="unmatched"))

        # Matched business expense: Office Depot receipt above.
        office_receipt = db.query(models.Receipt).filter(models.Receipt.description.like("Office Depot%")).first()
        db.add(
            txn(
                dt.date(2026, 8, 6),
                "OFFICE DEPOT #1187 DES:PURCHASE",
                -84.50,
                receipt_id=office_receipt.id,
                match_status="matched",
            )
        )

        db.commit()
        print("Seed data created: 3 projects, 3 users, business + bank reconciliation fixtures.")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
