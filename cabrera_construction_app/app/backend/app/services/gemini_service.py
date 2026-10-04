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
import io
import json
import logging
import time

import docx
import httpx

from ..config import settings
from ..schemas import EstimateFetchResult, EstimateLineItemIn

logger = logging.getLogger("cabrera.gemini")

_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_MAX_RETRIES = 2  # 3 attempts total
_RETRY_DELAY_SECONDS = 2.0


def _post_with_retry(url: str, json_body: dict, timeout: float) -> httpx.Response:
    """Retries transient failures (network errors, 5xx — e.g. the 503s
    Gemini returns under load) a couple of times with a short delay. A 4xx
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
            time.sleep(_RETRY_DELAY_SECONDS)

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
    replaces the old hardcoded demo data. Accepts a PDF or a .docx. Raises
    GeminiNotConfigured / GeminiExtractionError on failure rather than
    silently returning fake data, since unlike summarize_scope, there's no
    honest fallback here: this function *is* the feature."""
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set in app/backend/.env — required to parse an uploaded estimate/notes document.")

    url = _API_URL_TEMPLATE.format(model=settings.gemini_model)
    try:
        document_part = _build_document_part(file_bytes, filename, content_type)
        resp = _post_with_retry(
            url,
            {
                "contents": [{"parts": [document_part, {"text": _EXTRACTION_PROMPT}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": _EXTRACTION_SCHEMA},
            },
            timeout=60,
        )
        if resp.status_code >= 400:
            message = _extract_error_message(resp)
            logger.error("Gemini document extraction failed for %s: %s", filename, message)
            raise GeminiExtractionError(f"Could not extract an estimate from this document: {message}")
        body = resp.json()
        data = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
    except GeminiExtractionError:
        raise
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.error("Gemini document extraction failed for %s: %s", filename, exc)
        raise GeminiExtractionError(f"Could not extract an estimate from this document: {exc}") from exc

    if not data.get("found") or not data.get("line_items"):
        raise GeminiExtractionError("Gemini couldn't find usable estimate/job information in this document.")

    line_items = [EstimateLineItemIn(**li) for li in data["line_items"]]
    subtotal = round(sum(li.qty * li.unit_price for li in line_items), 2)
    total = float(data.get("total") or subtotal)

    logger.info("Gemini extracted estimate from %s: %d line items, total=%.2f", filename, len(line_items), total)
    return EstimateFetchResult(
        found=True,
        estimate_number=f"DOC-{filename[:20]}",
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
