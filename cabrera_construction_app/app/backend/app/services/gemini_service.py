"""Summarizes a QuickBooks estimate's raw memo/line-item text into a clean
project scope description, via the Gemini API.

This isn't wired into any OAuth flow — the Gemini API (generativelanguage.
googleapis.com) authenticates with a plain API key from
aistudio.google.com/apikey, a different product from the Drive/Sheets OAuth
client in google_oauth.py. If GEMINI_API_KEY isn't set, summarize() just
returns the input unchanged — callers don't need to branch on whether it's
configured.
"""

from __future__ import annotations

import base64
import datetime as dt
import io
import json
import logging
import time

import docx
import httpx

from ..config import settings
from ..schemas import DriveImportPreview, EstimateFetchResult, EstimateLineItemIn, MilestonePreview

logger = logging.getLogger("cabrera.gemini")

_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_MAX_RETRIES = 3  # 4 attempts total
_RETRY_BASE_DELAY_SECONDS = 2.0  # doubles each attempt (2s, 4s, 8s) — a 503
# "high demand" error is usually a minutes-scale spike, not instantly over,
# so a flat 2s delay between all attempts barely helps; backing off further
# each time gives it more room to clear without the user having to retry by hand.


def _post_with_retry(url: str, json_body: dict, timeout: float) -> httpx.Response:
    """Retries transient failures (network errors, 5xx — e.g. the 503s
    Gemini returns under load) a few times with exponential backoff. A 4xx
    is deterministic (bad key, wrong model, bad request) and is returned
    as-is for the caller to handle — retrying it would just waste time."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        resp: httpx.Response | None = None
        try:
            resp = httpx.post(url, params={"key": settings.gemini_api_key}, json=json_body, timeout=timeout)
        except httpx.TransportError as exc:
            last_error = exc

        if resp is not None:
            if resp.status_code < 500:
                return resp
            last_error = httpx.HTTPStatusError(f"Gemini returned {resp.status_code}", request=resp.request, response=resp)
            logger.info("Gemini %s, retrying (attempt %d/%d)", resp.status_code, attempt + 1, _MAX_RETRIES + 1)

        if attempt < _MAX_RETRIES:
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))

    assert last_error is not None
    if isinstance(last_error, httpx.HTTPStatusError):
        return last_error.response
    raise last_error


def _extract_error_message(resp: httpx.Response) -> str:
    """Google's error body shape: {"error": {"code", "message", "status"}}.
    raise_for_status() alone only gives a generic "404 Not Found" with none
    of this detail — surfacing it directly is what actually tells you *why*
    (bad key, API not enabled, wrong model, quota, ...) instead of guessing."""
    try:
        err = resp.json().get("error", {})
        return f"{err.get('message', 'Gemini API error')} ({err.get('status', resp.status_code)})"
    except ValueError:
        return resp.text[:300] or f"Gemini API returned {resp.status_code}"


class GeminiNotConfigured(Exception):
    pass


class GeminiExtractionError(Exception):
    pass

_PROMPT = (
    "You are drafting the project scope description for a residential construction "
    "contract. Rewrite the following QuickBooks estimate details into a clear, "
    "specific 2-4 sentence project scope description — the kind that goes in a "
    "contract's 'Description of the Project and Significant Materials' field. "
    "Name the actual work and materials involved. Do not invent details that "
    "aren't in the source text, and do not add pricing. Return only the "
    "description text, with no preamble or markdown.\n\n---\n\n"
)


def summarize_scope(raw_text: str) -> str:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return raw_text
    if not settings.gemini_api_key:
        logger.info("GEMINI_API_KEY not set — using the raw estimate text as-is, unsummarized.")
        return raw_text

    url = _API_URL_TEMPLATE.format(model=settings.gemini_model)
    try:
        resp = _post_with_retry(url, {"contents": [{"parts": [{"text": _PROMPT + raw_text}]}]}, timeout=30)
        if resp.status_code >= 400:
            raise ValueError(_extract_error_message(resp))
        body = resp.json()
        summary = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        if not summary:
            raise ValueError("Gemini returned an empty summary")
        logger.info("Gemini summarized estimate scope text (%d chars -> %d chars)", len(raw_text), len(summary))
        return summary
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        # Summarization is a nice-to-have on top of real QuickBooks data, not
        # something that should block creating a project if Gemini hiccups —
        # fall back to the raw text rather than raising.
        logger.error("Gemini summarization failed, falling back to raw text: %s", exc)
        return raw_text


def _extract_docx_text(docx_bytes: bytes) -> str:
    """Flattens a .docx's paragraphs and table cells into plain text, in
    document order, for the pieces Gemini actually needs here. .docx has no
    equivalent to sending a PDF as inline_data — Gemini's document
    understanding only covers PDF/image/etc. — so this text is sent as a
    plain text part instead (see extract_estimate_from_document)."""
    document = docx.Document(io.BytesIO(docx_bytes))
    parts: list[str] = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


_EXTRACTION_PROMPT = (
    "This document is either a QuickBooks-exported estimate or informal notes written by a "
    "general contractor (sometimes handwritten-style, with typos, shorthand, or mixed "
    "English/Spanish — extract the intent, don't fix or judge the writing). Extract a "
    "structured project estimate from it.\n\n"
    "Rules:\n"
    "- Only extract information actually present in the document. Leave a field empty "
    "(or omit it) rather than inventing a customer name, address, phone, or email that "
    "isn't there.\n"
    "- Every priced item becomes one line item. Classify each into exactly one section: "
    "'demolition' (demo/removal/prep work), 'materials', 'labor', or 'additional_work' "
    "(anything else, e.g. a line that's clearly a flat task without materials/labor split "
    "out). If a line bundles labor and material together with one price, you can put it "
    "under whichever section best matches its main description, or 'additional_work' if "
    "ambiguous.\n"
    "- qty defaults to 1 and unit to 'ea' when the document doesn't break those out "
    "separately — put the full line price in unit_price in that case.\n"
    "- scope_text: write a clear 2-4 sentence project scope description covering the "
    "actual work, as if for a contract's project description field — not a copy of the "
    "line items verbatim.\n"
    "- total: the document's own stated total if present; otherwise the sum of all line "
    "item prices.\n"
)

_EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "found": {"type": "BOOLEAN", "description": "false only if this document has no usable estimate/job information at all"},
        "customer_name": {"type": "STRING"},
        "customer_phone": {"type": "STRING"},
        "customer_email": {"type": "STRING"},
        "property_address": {"type": "STRING"},
        "scope_text": {"type": "STRING"},
        "total": {"type": "NUMBER"},
        "line_items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section": {"type": "STRING", "enum": ["demolition", "materials", "labor", "additional_work"]},
                    "description": {"type": "STRING"},
                    "qty": {"type": "NUMBER"},
                    "unit": {"type": "STRING"},
                    "unit_price": {"type": "NUMBER"},
                },
                "required": ["section", "description", "qty", "unit", "unit_price"],
            },
        },
    },
    "required": ["found", "line_items"],
}


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _build_document_part(file_bytes: bytes, filename: str, content_type: str) -> dict:
    """PDFs go to Gemini as-is (inline_data) so it can use real document
    understanding — layout, tables, etc. — not just raw text. .docx has no
    such support, so it's flattened to plain text locally first (python-docx)
    and sent as an ordinary text part instead."""
    is_docx = content_type == _DOCX_MIME or filename.lower().endswith(".docx")
    if is_docx:
        text = _extract_docx_text(file_bytes)
        if not text.strip():
            raise GeminiExtractionError("This .docx file appears to have no readable text.")
        return {"text": "Document contents:\n\n" + text}
    return {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(file_bytes).decode("ascii")}}


def extract_estimate_from_document(file_bytes: bytes, filename: str, content_type: str = "application/pdf") -> EstimateFetchResult:
    """Real extraction for the "no QuickBooks estimate number" upload path —
    replaces the old hardcoded demo data. Accepts a PDF or a .docx."""
    return extract_estimate_from_documents([(file_bytes, filename, content_type)])


def extract_estimate_from_documents(files: list[tuple[bytes, str, str]]) -> EstimateFetchResult:
    """Same extraction, but from several documents at once — e.g. every
    PDF/DOCX found in an existing Drive project folder (contract, estimate,
    notes, ...) — sent to Gemini together in one request so it can combine
    information across all of them into one result, rather than extracting
    each file in isolation and having to merge the results ourselves.

    Raises GeminiNotConfigured / GeminiExtractionError on failure rather
    than silently returning fake data — unlike summarize_scope, there's no
    honest fallback here: this function *is* the feature."""
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set in app/backend/.env — required to read these documents.")
    if not files:
        raise GeminiExtractionError("No documents to extract from.")

    names = ", ".join(f[1] for f in files)
    url = _API_URL_TEMPLATE.format(model=settings.gemini_model)
    try:
        document_parts = [_build_document_part(fb, fn, ct) for fb, fn, ct in files]
        prompt = _EXTRACTION_PROMPT if len(files) == 1 else _EXTRACTION_PROMPT + "\nThese are multiple documents for the same job — combine information across all of them into one result.\n"
        resp = _post_with_retry(
            url,
            {
                "contents": [{"parts": [*document_parts, {"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": _EXTRACTION_SCHEMA},
            },
            timeout=90,
        )
        if resp.status_code >= 400:
            message = _extract_error_message(resp)
            logger.error("Gemini document extraction failed for %s: %s", names, message)
            raise GeminiExtractionError(f"Could not extract an estimate from this: {message}")
        body = resp.json()
        data = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
    except GeminiExtractionError:
        raise
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.error("Gemini document extraction failed for %s: %s", names, exc)
        raise GeminiExtractionError(f"Could not extract an estimate from this: {exc}") from exc

    if not data.get("found") or not data.get("line_items"):
        raise GeminiExtractionError("Gemini couldn't find usable estimate/job information in these documents.")

    line_items = [EstimateLineItemIn(**li) for li in data["line_items"]]
    subtotal = round(sum(li.qty * li.unit_price for li in line_items), 2)
    total = float(data.get("total") or subtotal)

    logger.info("Gemini extracted estimate from %s: %d line items, total=%.2f", names, len(line_items), total)
    return EstimateFetchResult(
        found=True,
        estimate_number=f"DOC-{files[0][1][:20]}",
        customer_name=data.get("customer_name") or "",
        customer_phone=data.get("customer_phone") or "",
        customer_email=data.get("customer_email") or "",
        property_address=data.get("property_address") or "",
        scope_text=data.get("scope_text") or "",
        tax_rate=max(0.0, round((total - subtotal) / subtotal, 6)) if subtotal else 0.0,
        permit_fees=0.0,
        discount=0.0,
        line_items=line_items,
        total=total,
    )


_HISTORICAL_PROMPT = (
    "These documents are the complete file for a residential construction project that was "
    "created BEFORE this app existed — e.g. a signed contract, the original estimate, and/or a "
    "Scope & Payment Schedule. Extract a complete historical record from them so the project's "
    "contact info, scope, and payment schedule can be reconstructed. These documents may be some "
    "combination of a signed contract, an estimate, and a payment schedule — combine information "
    "across all of them into one result.\n\n"
    "Rules:\n"
    "- Only extract information actually present in the documents. Leave a field empty rather "
    "than inventing a customer name, address, phone, email, contract date, or payment terms that "
    "aren't there.\n"
    "- Every priced item on the estimate becomes one line item, classified into 'demolition', "
    "'materials', 'labor', or 'additional_work' as best fits.\n"
    "- milestones: the payment schedule's line items (e.g. 'Deposit', 'Rough-in complete', "
    "'Final payment'), each with its own amount. number starts at 0 for the initial "
    "deposit/payment and increases in the order they appear. If no payment schedule document is "
    "present, leave milestones empty rather than guessing a schedule.\n"
    "- contract_date: the date the contract was signed, if stated.\n"
    "- payment_terms / warranty_terms: copy the actual contract language if present, don't "
    "paraphrase.\n"
    "- scope_text: a clear 2-4 sentence project scope description covering the actual work.\n"
    "- total: the contract's stated total if present; otherwise the sum of all line item prices.\n"
)

_HISTORICAL_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "found": {"type": "BOOLEAN", "description": "false only if these documents have no usable project information at all"},
        "customer_name": {"type": "STRING"},
        "customer_phone": {"type": "STRING"},
        "customer_email": {"type": "STRING"},
        "property_address": {"type": "STRING"},
        "scope_text": {"type": "STRING"},
        "total": {"type": "NUMBER"},
        "contract_date": {"type": "STRING", "description": "ISO date (YYYY-MM-DD) if known"},
        "payment_terms": {"type": "STRING"},
        "warranty_terms": {"type": "STRING"},
        "line_items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section": {"type": "STRING", "enum": ["demolition", "materials", "labor", "additional_work"]},
                    "description": {"type": "STRING"},
                    "qty": {"type": "NUMBER"},
                    "unit": {"type": "STRING"},
                    "unit_price": {"type": "NUMBER"},
                },
                "required": ["section", "description", "qty", "unit", "unit_price"],
            },
        },
        "milestones": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "number": {"type": "INTEGER"},
                    "title": {"type": "STRING"},
                    "amount": {"type": "NUMBER"},
                    "due_date": {"type": "STRING", "description": "ISO date (YYYY-MM-DD) if known"},
                },
                "required": ["number", "title", "amount"],
            },
        },
    },
    "required": ["found"],
}


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def extract_historical_project(folder_id: str, folder_name: str, files: list[tuple[bytes, str, str]]) -> DriveImportPreview:
    """Reads a pre-existing Drive project folder (signed contract, estimate,
    payment schedule — whatever's in there) into a full historical record,
    not just estimate fields — this feeds the dedicated Drive-import
    pipeline (see routers/projects.py), which creates a complete, already-
    signed project rather than running it through the new-estimate wizard."""
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set in app/backend/.env — required to read these documents.")
    if not files:
        raise GeminiExtractionError("No documents to extract from.")

    names = ", ".join(f[1] for f in files)
    url = _API_URL_TEMPLATE.format(model=settings.gemini_model)
    try:
        document_parts = [_build_document_part(fb, fn, ct) for fb, fn, ct in files]
        resp = _post_with_retry(
            url,
            {
                "contents": [{"parts": [*document_parts, {"text": _HISTORICAL_PROMPT}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": _HISTORICAL_SCHEMA},
            },
            timeout=90,
        )
        if resp.status_code >= 400:
            message = _extract_error_message(resp)
            logger.error("Gemini historical-project extraction failed for %s: %s", names, message)
            raise GeminiExtractionError(f"Could not extract an estimate from this: {message}")
        body = resp.json()
        data = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
    except GeminiExtractionError:
        raise
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.error("Gemini historical-project extraction failed for %s: %s", names, exc)
        raise GeminiExtractionError(f"Could not extract an estimate from this: {exc}") from exc

    if not data.get("found"):
        raise GeminiExtractionError("Gemini couldn't find usable project information in this Drive folder.")

    line_items = [EstimateLineItemIn(**li) for li in data.get("line_items", [])]
    subtotal = round(sum(li.qty * li.unit_price for li in line_items), 2)
    total = float(data.get("total") or subtotal)
    milestones = [
        MilestonePreview(number=m["number"], title=m["title"], amount=m["amount"], due_date=_parse_date(m.get("due_date")))
        for m in data.get("milestones", [])
    ]

    logger.info("Gemini extracted historical project from %s: %d line items, %d milestones, total=%.2f", names, len(line_items), len(milestones), total)
    return DriveImportPreview(
        folder_id=folder_id,
        folder_name=folder_name,
        customer_name=data.get("customer_name") or "",
        customer_phone=data.get("customer_phone") or "",
        customer_email=data.get("customer_email") or "",
        property_address=data.get("property_address") or "",
        scope_text=data.get("scope_text") or "",
        total=total,
        line_items=line_items,
        contract_date=_parse_date(data.get("contract_date")),
        payment_terms=data.get("payment_terms") or "",
        warranty_terms=data.get("warranty_terms") or "",
        milestones=milestones,
    )
