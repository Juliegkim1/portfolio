"""Google Sheets integration — creates reconciliation sheets using gspread."""
import os
from datetime import date

from config import GCS_CREDENTIALS_FILE, COMPANY


class GoogleSheetsService:
    def __init__(self):
        self._creds_file = GCS_CREDENTIALS_FILE

    def _client(self):
        import gspread
        if self._creds_file and os.path.exists(self._creds_file):
            return gspread.service_account(filename=self._creds_file)
        # Fall back to Application Default Credentials
        import google.auth
        creds, _ = google.auth.default(
            scopes=["https://spreadsheets.google.com/feeds",
                    "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)

    def create_reconciliation_sheet(self, project, invoices, contract_amount,
                                    notes="") -> str:
        """
        Build a Google Sheet with full reconciliation data.
        Returns the sheet URL.
        """
        gc = self._client()
        title = f"Reconciliation – {project.name} – {date.today()}"
        sh = gc.create(title)
        # Make it readable by anyone with the link
        sh.share(None, perm_type="anyone", role="reader")

        ws = sh.sheet1
        ws.update_title("Reconciliation")

        paid_invoices = [inv for inv in invoices if inv.status == "paid"]
        total_paid = sum(inv.total for inv in paid_invoices)
        balance_due = contract_amount - total_paid

        rows = []

        # ── Title block ───────────────────────────────────────────────────────
        rows.append([COMPANY["name"], "", "", "", ""])
        rows.append(["PROJECT ACCOUNT RECONCILIATION", "", "", "", ""])
        rows.append([f"Generated: {date.today()}", "", "", "", ""])
        rows.append(["", "", "", "", ""])

        # ── Project info ──────────────────────────────────────────────────────
        rows.append(["PROJECT INFORMATION", "", "", "", ""])
        rows.append(["Project Name", project.name, "", "Status", project.status.replace("_", " ").title()])
        rows.append(["Customer", project.customer_name, "", "Type", project.project_type or ""])
        rows.append(["Address", project.property_address, "", "Est. Start", str(project.start_date or "")])
        rows.append(["Phone", project.customer_phone or "", "", "Est. Duration",
                     f"{project.duration_days} days" if project.duration_days else ""])
        rows.append(["Email", project.customer_email, "", "", ""])
        rows.append(["", "", "", "", ""])

        # ── Summary card ──────────────────────────────────────────────────────
        rows.append(["FINANCIAL SUMMARY", "", "", "", ""])
        rows.append(["Original Contract", "Total Paid", "Change Orders", "BALANCE DUE", ""])
        rows.append([f"${contract_amount:,.2f}", f"${total_paid:,.2f}", "$0.00",
                     f"${balance_due:,.2f}", ""])
        rows.append(["", "", "", "", ""])

        # ── Payment history ───────────────────────────────────────────────────
        rows.append(["PAYMENT HISTORY", "", "", "", ""])
        rows.append(["#", "Description / Milestone", "Payment Date",
                     "Amount Paid ($)", "Status"])
        for i, inv in enumerate(invoices):
            rows.append([
                str(i + 1),
                inv.description,
                str(inv.payment_date or "—"),
                f"${inv.total:,.2f}" if inv.status == "paid" else "—",
                inv.status.upper(),
            ])
        rows.append(["", "TOTALS", "", f"${total_paid:,.2f}", ""])
        rows.append(["", "", "", "", ""])

        # ── Summary table ─────────────────────────────────────────────────────
        rows.append(["SUMMARY", "", "", "", ""])
        rows.append(["Original Contract Amount", f"${contract_amount:,.2f}", "", "", ""])
        rows.append(["Total Payments Received", f"${total_paid:,.2f}", "", "", ""])
        rows.append(["BALANCE DUE", f"${balance_due:,.2f}", "", "", ""])

        if notes:
            rows.append(["", "", "", "", ""])
            rows.append(["Notes", notes, "", "", ""])

        # Write all rows in one API call
        ws.update(f"A1:E{len(rows)}", rows)

        # ── Formatting ────────────────────────────────────────────────────────
        try:
            import gspread.utils as gu
            # Bold title rows
            for r in [1, 2, 12, 13, 16, 17, 26]:
                ws.format(f"A{r}:E{r}", {"textFormat": {"bold": True}})
            # Freeze first column header row
            sh.batch_update({"requests": [{
                "updateSheetProperties": {
                    "properties": {"sheetId": ws.id,
                                   "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            }]})
        except Exception:
            pass  # formatting is best-effort

        return sh.url
