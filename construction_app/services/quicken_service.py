"""
Quicken integration via QIF (Quicken Interchange Format) file exchange.

Workflow:
  - Export: app writes a .qif file → user imports into Quicken
  - Import: user exports from Quicken as .qif/.ofx → app reads it for reconciliation
"""
import os
from datetime import date
from typing import List, Optional

from config import QUICKEN_EXPORT_DIR
from models import Invoice, Project


class QuickenService:
    def __init__(self, export_dir: str = QUICKEN_EXPORT_DIR):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    # ── Export to Quicken ─────────────────────────────────────────────────────

    def export_project_invoices_to_qif(
        self,
        project: Project,
        invoices: List[Invoice],
        account_name: str = "Checking",
    ) -> str:
        """
        Write a QIF file containing all paid invoices as income transactions.
        Returns the file path.
        """
        lines = [f"!Account\nN{account_name}\nTBank\n^\n!Type:Bank\n"]
        for inv in invoices:
            if inv.status != "paid":
                continue
            txn_date = inv.payment_date or inv.date_issued or date.today()
            lines.append(
                f"D{txn_date.strftime('%m/%d/%Y')}\n"
                f"T{inv.total:.2f}\n"
                f"P{project.customer_name}\n"
                f"M{project.name} - {inv.description} [{inv.invoice_number}]\n"
                f"LIncome:Construction Revenue\n"
                f"^\n"
            )

        filename = f"quicken_{project.name.replace(' ', '_')}_{date.today()}.qif"
        filepath = os.path.join(self.export_dir, filename)
        with open(filepath, "w") as f:
            f.write("".join(lines))
        return filepath

    def export_estimate_to_qif(
        self,
        project: Project,
        amount: float,
        description: str,
        account_name: str = "Accounts Receivable",
    ) -> str:
        """Write a QIF file for an estimate (receivable). Returns file path."""
        lines = [
            f"!Account\nN{account_name}\nTOth A\n^\n!Type:Oth A\n",
            f"D{date.today().strftime('%m/%d/%Y')}\n"
            f"T{amount:.2f}\n"
            f"P{project.customer_name}\n"
            f"M{project.name} - {description}\n"
            f"LAccounts Receivable\n"
            f"^\n",
        ]
        filename = f"estimate_{project.name.replace(' ', '_')}_{date.today()}.qif"
        filepath = os.path.join(self.export_dir, filename)
        with open(filepath, "w") as f:
            f.write("".join(lines))
        return filepath

    # ── Import from Quicken ───────────────────────────────────────────────────

    def import_qif(self, filepath: str) -> List[dict]:
        """
        Parse a QIF file exported from Quicken.
        Returns list of transaction dicts with keys: date, amount, payee, memo, category.
        """
        transactions = []
        current: dict = {}
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("!"):
                    continue
                tag, value = line[0], line[1:]
                if tag == "D":
                    current["date"] = value
                elif tag == "T":
                    try:
                        current["amount"] = float(value.replace(",", ""))
                    except ValueError:
                        current["amount"] = 0.0
                elif tag == "P":
                    current["payee"] = value
                elif tag == "M":
                    current["memo"] = value
                elif tag == "L":
                    current["category"] = value
                elif tag == "^":
                    if current:
                        transactions.append(current)
                    current = {}
        return transactions

    def reconcile_with_quicken(
        self, invoices: List[Invoice], qif_filepath: str
    ) -> dict:
        """
        Compare paid invoices against Quicken transactions from a QIF export.
        Returns reconciliation summary.
        """
        transactions = self.import_qif(qif_filepath)
        qif_total = sum(t.get("amount", 0) for t in transactions if t.get("amount", 0) > 0)
        app_total = sum(inv.total for inv in invoices if inv.status == "paid")
        difference = round(app_total - qif_total, 2)
        return {
            "app_total_paid": app_total,
            "quicken_total": qif_total,
            "difference": difference,
            "balanced": abs(difference) < 0.01,
            "quicken_transactions": len(transactions),
            "paid_invoices": len([i for i in invoices if i.status == "paid"]),
        }
