"""Real QuickBooks Online estimate lookup and invoice lookup (both read-only).

Per CLAUDE.md / README "QuickBooks Online" integration notes: the number a
user types is the estimate's DocNumber, not its internal Id — looked up via
the query endpoint, accepting "1042", "EST-1042" or "#1042". Customer phone
isn't on the Estimate itself, so a second call fetches the Customer.

This intentionally does NOT implement invoice *creation* or the payment
webhook (write operations) — this app's own "Send Invoice" button only ever
creates a local record (see routers/invoices.py), never a real QuickBooks
invoice. list_invoices_for_customer() below is a genuine API call, but a
read: it shows what's actually been sent in QuickBooks, for comparison
against (not replacement of) this app's own invoice records.
"""

from __future__ import annotations

import datetime as dt
import logging

import httpx
from sqlalchemy.orm import Session

from ..schemas import EstimateFetchResult, EstimateLineItemIn
from . import gemini_service
from . import quickbooks_oauth as qb_oauth

logger = logging.getLogger("cabrera.quickbooks")


class QuickBooksApiError(Exception):
    """A non-auth error response from the Accounting API (validation, syntax,
    rate limit, upstream 5xx, ...). Carries the `intuit_tid` response header
    Intuit asks integrators to capture — quoting it is the fastest way their
    support team can look up what happened on their side."""

    def __init__(self, message: str, *, status_code: int, intuit_tid: str | None):
        super().__init__(message)
        self.status_code = status_code
        self.intuit_tid = intuit_tid


_SECTION_KEYWORDS = {
    "demolition": "demolition",
    "demo": "demolition",
    "preparation": "demolition",
    "material": "materials",
    "labor": "labor",
    "labour": "labor",
}


def _normalize_doc_number(raw: str) -> str:
    return raw.strip().upper().removeprefix("EST-").removeprefix("#")


def _section_for(label: str, current: str) -> str:
    key = label.strip().lower()
    for keyword, section in _SECTION_KEYWORDS.items():
        if keyword in key:
            return section
    return current


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


def _extract_fault_message(resp: httpx.Response) -> str:
    """Intuit's error body shape: {"Fault": {"Error": [{"Message", "Detail", "code"}], "type"}}."""
    try:
        fault = resp.json().get("Fault", {})
        errors = fault.get("Error", [])
        if errors:
            first = errors[0]
            return f"{first.get('Message', 'QuickBooks API error')} ({first.get('Detail', '')}) [{fault.get('type', '')}]".strip()
    except (ValueError, KeyError):
        pass
    return resp.text[:300] or f"QuickBooks API returned {resp.status_code}"


def _request(db: Session, method: str, path: str, **kwargs) -> httpx.Response:
    access_token, realm_id = qb_oauth.get_valid_access_token(db)
    base = qb_oauth.api_base_url()
    resp = httpx.request(method, f"{base}/v3/company/{realm_id}{path}", headers=_headers(access_token), timeout=20, **kwargs)
    # Intuit asks integrators to capture this trace ID — it's the fastest way
    # their support team can look up a request when troubleshooting.
    intuit_tid = resp.headers.get("intuit_tid")

    if resp.status_code == 401:
        logger.error("QuickBooks 401 on %s %s realm=%s intuit_tid=%s", method, path, realm_id, intuit_tid)
        raise qb_oauth.QuickBooksNotConnected("QuickBooks rejected the access token. Reconnect QuickBooks and try again.")

    if resp.status_code >= 400:
        message = _extract_fault_message(resp)
        logger.error(
            "QuickBooks API error on %s %s realm=%s status=%s intuit_tid=%s message=%s",
            method, path, realm_id, resp.status_code, intuit_tid, message,
        )
        raise QuickBooksApiError(
            f"{message} (intuit_tid: {intuit_tid or 'none'})", status_code=resp.status_code, intuit_tid=intuit_tid
        )

    logger.info("QuickBooks %s %s realm=%s status=%s intuit_tid=%s", method, path, realm_id, resp.status_code, intuit_tid)
    return resp


def _flatten_lines(lines: list[dict], section: str) -> list[EstimateLineItemIn]:
    items: list[EstimateLineItemIn] = []
    for line in lines:
        detail_type = line.get("DetailType")
        if detail_type == "GroupLineDetail":
            group = line["GroupLineDetail"]
            group_label = group.get("GroupItemRef", {}).get("name", "") or line.get("Description", "")
            items.extend(_flatten_lines(group.get("Line", []), _section_for(group_label, section)))
        elif detail_type == "DescriptionOnly":
            # Often used as a section header row in hand-organized estimates.
            section = _section_for(line.get("Description", ""), section)
        elif detail_type == "SalesItemLineDetail":
            detail = line["SalesItemLineDetail"]
            qty = float(detail.get("Qty", 1) or 1)
            unit_price = float(detail.get("UnitPrice", line.get("Amount", 0) / qty if qty else 0))
            description = line.get("Description") or detail.get("ItemRef", {}).get("name", "Line item")
            items.append(EstimateLineItemIn(section=section, description=description, qty=qty, unit="ea", unit_price=unit_price))
    return items


def _raw_scope_text(est: dict, line_items: list[EstimateLineItemIn]) -> str:
    """CustomerMemo/PrivateNote are often left blank in practice — if neither
    has anything, fall back to the line-item descriptions themselves so
    there's always real text to show (and to summarize via Gemini) instead
    of silently showing nothing."""
    memo = est.get("CustomerMemo", {}).get("value") or est.get("PrivateNote", "")
    if memo.strip():
        return memo
    if line_items:
        return "; ".join(f"{li.description} ({li.qty} {li.unit})" for li in line_items)
    return ""


def _format_address(addr: dict | None) -> str:
    if not addr:
        return ""
    parts = [addr.get("Line1", ""), addr.get("City", ""), addr.get("CountrySubDivisionCode", ""), addr.get("PostalCode", "")]
    city_state_zip = " ".join(p for p in parts[1:] if p)
    return ", ".join(p for p in [parts[0], city_state_zip] if p)


def lookup_estimate(db: Session, raw_number: str) -> EstimateFetchResult:
    doc_number = _normalize_doc_number(raw_number)
    query = f"select * from Estimate where DocNumber = '{doc_number}'"
    resp = _request(db, "GET", "/query", params={"query": query, "minorversion": "75"})
    estimates = resp.json().get("QueryResponse", {}).get("Estimate", [])

    if len(estimates) != 1:
        return EstimateFetchResult(found=False, estimate_number=raw_number)

    est = estimates[0]
    line_items = _flatten_lines(est.get("Line", []), "additional_work")
    subtotal = round(sum(li.qty * li.unit_price for li in line_items), 2)
    total_amt = float(est.get("TotalAmt", subtotal))
    tax_rate = max(0.0, round((total_amt - subtotal) / subtotal, 6)) if subtotal else 0.0

    customer_name = est.get("CustomerRef", {}).get("name", "")
    customer_phone = ""
    customer_email = est.get("BillEmail", {}).get("Address", "")
    customer_ref_id = est.get("CustomerRef", {}).get("value")
    if customer_ref_id:
        try:
            cust_resp = _request(db, "GET", f"/customer/{customer_ref_id}")
            customer = cust_resp.json().get("Customer", {})
            customer_phone = customer.get("PrimaryPhone", {}).get("FreeFormNumber", "")
            customer_email = customer_email or customer.get("PrimaryEmailAddr", {}).get("Address", "")
        except httpx.HTTPError:
            pass  # non-fatal — proceed without phone/email rather than failing the whole fetch

    txn_date = est.get("TxnDate")
    date_issued = dt.date.fromisoformat(txn_date) if txn_date else None

    return EstimateFetchResult(
        found=True,
        estimate_number=est.get("DocNumber", doc_number),
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        property_address=_format_address(est.get("ShipAddr") or est.get("BillAddr")),
        date_issued=date_issued,
        scope_text=gemini_service.summarize_scope(_raw_scope_text(est, line_items)),
        tax_rate=tax_rate,
        permit_fees=0.0,
        discount=0.0,
        line_items=line_items,
        total=total_amt,
        retrieved_at=dt.datetime.now(),
    )


def _escape_qb_query_literal(value: str) -> str:
    """QBO's query language escapes an embedded quote by doubling it (SQL-
    style), not backslash-escaping — same reasoning as the Drive API query
    escaping in google_service.py: unescaped, a customer name with an
    apostrophe (e.g. "O'Brien") breaks the query, and worse, unescaped
    user-derived text in a query string is an injection vector."""
    return value.replace("'", "''")


def lookup_invoice(db: Session, raw_number: str) -> dict | None:
    """A single QuickBooks invoice by its DocNumber (the number printed on
    the invoice / shown to the customer, not QB's internal Id) — the
    Invoices page's "look up a specific QuickBooks invoice" entry point,
    mirroring how estimate lookup works by DocNumber. Returns None rather
    than raising when nothing matches, same as lookup_estimate."""
    doc_number = _normalize_doc_number(raw_number)
    query = f"select * from Invoice where DocNumber = '{_escape_qb_query_literal(doc_number)}'"
    resp = _request(db, "GET", "/query", params={"query": query, "minorversion": "75"})
    invoices = resp.json().get("QueryResponse", {}).get("Invoice", [])
    if len(invoices) != 1:
        return None
    inv = invoices[0]
    total = float(inv.get("TotalAmt", 0))
    balance = float(inv.get("Balance", 0))
    status = "paid" if balance <= 0 else ("partial" if balance < total else "open")
    return {
        "doc_number": inv.get("DocNumber", doc_number),
        "txn_date": inv.get("TxnDate"),
        "due_date": inv.get("DueDate"),
        "total_amt": total,
        "balance": balance,
        "status": status,
        "email_status": inv.get("EmailStatus", ""),
    }


def list_invoices_for_customer(db: Session, customer_name: str) -> list[dict]:
    """Real, read-only: what QuickBooks actually has on file as sent for
    this customer — shown on the Invoices page next to this app's own
    local invoice records, not instead of them (this app never writes
    invoices to QuickBooks — see this module's docstring). Returns []
    rather than erroring when there's no matching QuickBooks customer,
    e.g. a Drive-imported project whose customer was never in QuickBooks
    at all — that's an expected case here, not a failure."""
    safe_name = _escape_qb_query_literal(customer_name)
    cust_resp = _request(
        db, "GET", "/query", params={"query": f"select Id from Customer where DisplayName = '{safe_name}'", "minorversion": "75"}
    )
    customers = cust_resp.json().get("QueryResponse", {}).get("Customer", [])
    if not customers:
        return []
    customer_id = customers[0]["Id"]

    inv_resp = _request(
        db,
        "GET",
        "/query",
        params={
            "query": f"select * from Invoice where CustomerRef = '{customer_id}' orderby TxnDate desc maxresults 50",
            "minorversion": "75",
        },
    )
    invoices = inv_resp.json().get("QueryResponse", {}).get("Invoice", [])

    results = []
    for inv in invoices:
        total = float(inv.get("TotalAmt", 0))
        balance = float(inv.get("Balance", 0))
        status = "paid" if balance <= 0 else ("partial" if balance < total else "open")
        results.append(
            {
                "doc_number": inv.get("DocNumber", ""),
                "txn_date": inv.get("TxnDate"),
                "due_date": inv.get("DueDate"),
                "total_amt": total,
                "balance": balance,
                "status": status,
                "email_status": inv.get("EmailStatus", ""),
            }
        )
    return results
