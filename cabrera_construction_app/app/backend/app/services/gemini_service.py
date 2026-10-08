"""Document/estimate extraction, tried across multiple AI providers in
order — Gemini first, then Claude (Anthropic), then GPT (OpenAI) — so one
provider's models being unreliable for a given document, or the account
being unconfigured, isn't a hard stop. Each provider is tried only if its
API key is set (see config.py); the first one to return genuinely usable
data (found=true with at least one line item or milestone) wins. If every
configured provider comes up empty, the error explains what each one
said, not just the last one tried.

This module is still named after Gemini (the original, single-provider
implementation) rather than something like "extraction_service" — a
rename would touch every router import for a purely cosmetic reason, so
it stayed put; the multi-provider orchestration lives here regardless of
the name. GeminiNotConfigured/GeminiExtractionError are the stable public
exception types routers already catch — they're raised by the
orchestrator now, not literally Gemini-specific, but keeping the names
avoids an unnecessary breaking rename for the same reason.

Also home to summarize_scope() — a real but separate Gemini-only feature
(cleaning up a QuickBooks estimate's memo text), not part of the
extraction fallback chain: it already degrades gracefully to the raw
text when Gemini isn't configured or hiccups, so there's no "all
providers failed" case to design for there.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import time

import httpx

from ..config import settings
from ..schemas import DriveImportPreview, EstimateFetchResult, EstimateLineItemIn, MilestonePreview
from . import ai_schema, anthropic_service, openai_service
from .document_text import DocumentPart, DocumentReadError, PdfPart, TextPart, build_document_parts

logger = logging.getLogger("cabrera.gemini")

_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_MAX_RETRIES = 2  # 3 attempts total
_RETRY_BASE_DELAY_SECONDS = 2.0  # doubles each attempt (2s, 4s)
# This runs synchronously inside a user-facing request (someone's waiting on
# the Import from Drive or Estimate Upload screen) behind a load balancer
# with its own timeout — a 503 "high demand" spike can genuinely last
# minutes, and no amount of retrying here will out-wait that while someone
# is staring at a spinner. So this budget is deliberately bounded (a few
# retries, not enough to out-wait a real outage) rather than maximized:
# fail with a clear "try again" error in under a couple of minutes, not
# hang for six. See also the per-call `timeout` below.


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


_EXTRACTION_PROMPT = ai_schema.EXTRACTION_PROMPT

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
                    "scope_verification": {
                        "type": "STRING",
                        "description": "Only when combining an estimate with separate notes: a short 1-3 sentence summary of what this phase's work actually covers, drawn from the estimate's own scope/line-item language. Leave empty otherwise.",
                    },
                },
                "required": ["number", "title", "amount"],
            },
        },
    },
    "required": ["found", "line_items"],
}


def _total_mismatch_message(declared_total: float | None, line_item_subtotal: float) -> str | None:
    """Flags when the document's own stated total disagrees with the sum of
    the line items extracted from it — e.g. a missed/misread line item,
    rather than silently picking one number over the other and hoping it's
    right. Tolerance: the greater of $1 or 1%, to absorb rounding noise
    without flagging genuinely matching totals."""
    if declared_total is None or not line_item_subtotal:
        return None
    diff = declared_total - line_item_subtotal
    if abs(diff) <= max(1.0, line_item_subtotal * 0.01):
        return None
    direction = "higher than" if diff > 0 else "lower than"
    return (
        f"The document states a total of ${declared_total:,.2f}, which is ${abs(diff):,.2f} "
        f"{direction} the ${line_item_subtotal:,.2f} sum of its extracted line items — double-check "
        f"before creating the project."
    )


def _to_gemini_part(part: DocumentPart) -> dict:
    """PDFs go to Gemini as-is (inline_data) so it can use real document
    understanding — layout, tables, etc. .docx/.xlsx/pasted text arrive
    pre-flattened to plain text by document_text.build_document_parts
    (shared with the other providers), since Gemini has no more native
    understanding of spreadsheet/Word formats than Claude or GPT do."""
    if isinstance(part, TextPart):
        return {"text": part.text}
    if isinstance(part, PdfPart):
        return {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(part.data).decode("ascii")}}
    raise TypeError(f"Unknown document part type: {type(part)!r}")


def _call_gemini(files: list[tuple[bytes, str, str]], prompt: str, schema: dict, timeout: float) -> dict:
    """One Gemini call. Returns the raw extracted dict (parsed from the
    response's JSON-as-text, since Gemini wraps structured output in a text
    part rather than returning it as a native object the way Claude's
    tool-use does). Raises GeminiExtractionError on any failure — the
    orchestrator below treats that as "this provider couldn't help"."""
    parts = build_document_parts(files)
    document_parts = [_to_gemini_part(p) for p in parts]
    url = _API_URL_TEMPLATE.format(model=settings.gemini_model)
    resp = _post_with_retry(
        url,
        {
            "contents": [{"parts": [*document_parts, {"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema},
        },
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise GeminiExtractionError(_extract_error_message(resp))
    body = resp.json()
    return json.loads(body["candidates"][0]["content"]["parts"][0]["text"])


def any_provider_configured() -> bool:
    """Used by routers to decide whether to attempt real extraction at all
    or fall back to the clearly-labeled mock_integrations demo data — the
    same role settings.gemini_api_key played before Claude/GPT existed as
    options, just checking all three instead of just one."""
    return bool(settings.gemini_api_key) or anthropic_service.is_configured() or openai_service.is_configured()


def _extract_with_fallback(
    files: list[tuple[bytes, str, str]],
    *,
    gemini_prompt: str,
    gemini_schema: dict,
    gemini_timeout: float,
    standard_prompt: str,
    standard_schema: dict,
    not_found_message: str,
) -> dict:
    """Tries each configured provider in order (Gemini, Claude, GPT),
    returning the first one's raw extracted dict once it actually found
    something usable (found=true, at least one line item or milestone).
    Raises GeminiNotConfigured if nothing is configured at all, or
    GeminiExtractionError with every attempted provider's reason if all
    configured ones failed or came up empty — not just the last one tried,
    since which provider struggles with a given document varies."""
    if not files:
        raise GeminiExtractionError("No documents to extract from.")
    try:
        build_document_parts(files)  # validate once, up front — a docx/xlsx that can't be read fails identically for every provider, so there's no point spending an API call (paid, on whichever provider is tried first) to discover that
    except DocumentReadError as exc:
        raise GeminiExtractionError(str(exc)) from exc

    providers: list[tuple[str, object]] = []
    if settings.gemini_api_key:
        providers.append(("Gemini", lambda f, p, s: _call_gemini(f, p, s, gemini_timeout)))
    if anthropic_service.is_configured():
        providers.append(("Claude", anthropic_service.extract))
    if openai_service.is_configured():
        providers.append(("GPT", openai_service.extract))

    if not providers:
        raise GeminiNotConfigured(
            "No AI extraction provider is configured — set GEMINI_API_KEY, ANTHROPIC_API_KEY, "
            "or OPENAI_API_KEY in app/backend/.env."
        )

    names = ", ".join(f[1] for f in files)
    reasons: list[str] = []
    for provider_name, call in providers:
        prompt = gemini_prompt if provider_name == "Gemini" else standard_prompt
        schema = gemini_schema if provider_name == "Gemini" else standard_schema
        try:
            data = call(files, prompt, schema)
        except Exception as exc:  # noqa: BLE001 — any provider failure just means "try the next one"
            logger.info("%s extraction attempt failed for %s: %s", provider_name, names, exc)
            reasons.append(f"{provider_name}: {exc}")
            continue
        if not data.get("found") or (not data.get("line_items") and not data.get("milestones")):
            logger.info("%s found nothing usable for %s", provider_name, names)
            reasons.append(f"{provider_name}: {not_found_message}")
            continue
        logger.info("%s extracted from %s", provider_name, names)
        return data

    raise GeminiExtractionError(f"{not_found_message} Tried: " + " · ".join(reasons))


def extract_estimate_from_document(file_bytes: bytes, filename: str, content_type: str = "application/pdf") -> EstimateFetchResult:
    """Real extraction for the "no QuickBooks estimate number" upload path —
    replaces the old hardcoded demo data. Accepts a PDF, .docx, or .xlsx."""
    return extract_estimate_from_documents([(file_bytes, filename, content_type)])


def extract_estimate_from_text(raw_text: str) -> EstimateFetchResult:
    """Same extraction, but from text pasted directly into the app instead
    of an uploaded file. The fallback for a .docx/.xlsx that fails to parse
    (not actually a valid Office document — common for an old .doc renamed,
    or a quirky export from some other app) — but also just a faster path
    when a contractor's notes are already sitting in a text message or
    email and exporting them to a file first would be pure friction."""
    if not raw_text.strip():
        raise GeminiExtractionError("Paste some text to extract from.")
    return extract_estimate_from_documents([(raw_text.encode("utf-8"), "Pasted notes", "text/plain")])


def extract_estimate_from_documents(files: list[tuple[bytes, str, str]]) -> EstimateFetchResult:
    """Same extraction, but from several documents at once — e.g. every
    PDF/DOCX found in an existing Drive project folder (contract, estimate,
    notes, ...) — sent to each tried provider together in one request so it
    can combine information across all of them into one result, rather than
    extracting each file in isolation and having to merge the results
    ourselves.

    Raises GeminiNotConfigured / GeminiExtractionError on failure rather
    than silently returning fake data — unlike summarize_scope, there's no
    honest fallback here: this function *is* the feature."""
    multi_note = "\nThese are multiple documents for the same job — combine information across all of them into one result.\n"
    gemini_prompt = _EXTRACTION_PROMPT if len(files) == 1 else _EXTRACTION_PROMPT + multi_note
    standard_prompt = ai_schema.EXTRACTION_PROMPT if len(files) == 1 else ai_schema.EXTRACTION_PROMPT + multi_note

    data = _extract_with_fallback(
        files,
        gemini_prompt=gemini_prompt,
        gemini_schema=_EXTRACTION_SCHEMA,
        gemini_timeout=45,
        # Bounded well under the load balancer's request timeout even in the
        # worst case (this + retry backoff, Gemini only — Claude/GPT below
        # aren't retried the same way) — someone's waiting on this screen,
        # so failing clearly in a couple of minutes beats hanging for six.
        standard_prompt=standard_prompt,
        standard_schema=ai_schema.EXTRACTION_SCHEMA,
        not_found_message="Couldn't find usable estimate/job information in these documents.",
    )

    milestones = [
        MilestonePreview(
            number=m["number"],
            title=m["title"],
            amount=m["amount"],
            due_date=_parse_date(m.get("due_date")),
            scope_verification=m.get("scope_verification") or None,
        )
        for m in data.get("milestones", [])
    ]
    line_items = [EstimateLineItemIn(**li) for li in data.get("line_items", [])]
    declared_total = data.get("total")
    if line_items:
        subtotal = round(sum(li.qty * li.unit_price for li in line_items), 2)
    else:
        # No cost breakdown — the payment schedule's own total stands in for
        # it, and a single synthetic line item keeps the project-creation
        # screen's "at least one line item" check satisfied without
        # pretending there's a cost breakdown that was never extracted.
        subtotal = round(sum(m.amount for m in milestones), 2)
        total_for_synthetic = float(declared_total or subtotal)
        line_items = [EstimateLineItemIn(section="additional_work", description="Project total (from payment schedule)", qty=1, unit="ea", unit_price=total_for_synthetic)]
    total = float(declared_total or subtotal)
    mismatch = _total_mismatch_message(declared_total, subtotal)

    names = ", ".join(f[1] for f in files)
    logger.info("Extracted estimate from %s: %d line items, %d milestones, total=%.2f", names, len(line_items), len(milestones), total)
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
        milestones=milestones,
        contract_date=_parse_date(data.get("contract_date")),
        payment_terms=data.get("payment_terms") or None,
        warranty_terms=data.get("warranty_terms") or None,
        total_mismatch=mismatch,
    )


_COMBINE_NOTE = (
    "\nThe FIRST document below is the job's own estimate language (its project scope "
    "description plus its itemized cost breakdown) — its line items and their dollar amounts "
    "are already fixed; do not invent new ones or change their prices. The SECOND document is "
    "supplementary notes from the contractor, which usually describe the ACTUAL payment "
    "schedule/phases more accurately than the estimate does (the estimate may have no payment "
    "schedule at all, or a less accurate one). Determine the milestones (the payment schedule) "
    "primarily from the notes — each one is a real phase of work with its own payment amount. "
    "For EVERY milestone, also fill in scope_verification: a short 1-3 sentence summary of what "
    "that phase's work actually covers, written by combining the matching parts of the first "
    "document's scope/line-item language with anything the notes themselves say about that "
    "phase — this is what ties the payment to the work, not a restatement of the amount or due "
    "date. If the notes don't mention a schedule at all, fall back to the estimate's own "
    "milestones (if it has any) and still fill in scope_verification the same way.\n"
)


def _estimate_text_blob(existing: EstimateFetchResult) -> str:
    """Reconstructs the estimate's own language from its already-extracted
    fields — combine_estimate_with_notes only has the structured result on
    screen (not the original file bytes), but scope_text plus each line
    item's own description is the same language a human would read off the
    estimate, and is what scope_verification summaries get drawn from.
    Also includes any payment schedule already on `existing` (e.g. from an
    earlier combine), since the model otherwise has no way to know one
    already exists — without this, notes that only tweak one phase would
    look to the model like "no schedule mentioned at all"."""
    parts = [existing.scope_text or ""]
    parts += [f"{li.description} — ${li.qty * li.unit_price:,.2f} ({li.section})" for li in existing.line_items]
    if existing.milestones:
        parts.append("Current payment schedule (already on file — keep or revise based on the notes, don't discard without reason):")
        parts += [f"{m.number}. {m.title} — ${m.amount:,.2f}" for m in existing.milestones]
    return "\n".join(p for p in parts if p.strip())


def combine_estimate_with_notes(existing: EstimateFetchResult, notes_text: str) -> EstimateFetchResult:
    """Combines a contractor's supplementary notes with an already-fetched/
    extracted estimate in ONE AI call that sees both documents together —
    the common case where the estimate (a QuickBooks lookup or an uploaded
    document) has the cost breakdown but no payment schedule, or a less
    accurate one, and separate notes (the contractor's own text) describe
    the real phases. Unlike a plain two-step merge, this lets the model
    actually cross-reference the two: the resulting milestones come
    primarily from the notes (renumbered 0..N for clean phase numbers), and
    each one gets a scope_verification summary synthesized from the
    estimate's own scope/line-item language — "line items come from the
    estimate, phases from the notes, summarized per phase" in one pass.

    Line items and the total are NOT touched by the model at all — they're
    kept exactly as `existing` already had them, since dollar amounts on
    the cost breakdown should never be re-invented by an LLM call whose job
    here is the payment schedule, not pricing.
    """
    if not notes_text.strip():
        raise GeminiExtractionError("Paste some notes to combine.")

    files = [
        (_estimate_text_blob(existing).encode("utf-8"), "Estimate (scope and line items)", "text/plain"),
        (notes_text.encode("utf-8"), "Supplementary notes", "text/plain"),
    ]

    data = _extract_with_fallback(
        files,
        gemini_prompt=_EXTRACTION_PROMPT + _COMBINE_NOTE,
        gemini_schema=_EXTRACTION_SCHEMA,
        gemini_timeout=45,
        standard_prompt=ai_schema.EXTRACTION_PROMPT + _COMBINE_NOTE,
        standard_schema=ai_schema.EXTRACTION_SCHEMA,
        not_found_message="Couldn't combine the estimate and notes into a usable payment schedule.",
    )

    combined_milestones = [
        MilestonePreview(
            number=i,
            title=m["title"],
            amount=m["amount"],
            due_date=_parse_date(m.get("due_date")),
            scope_verification=m.get("scope_verification") or None,
        )
        for i, m in enumerate(data.get("milestones", []))
    ]

    def _or(current, fallback):
        return current if current else fallback

    logger.info(
        "Combined notes into existing estimate: %d phases, each with a scope summary; %d line items kept from the estimate",
        len(combined_milestones),
        len(existing.line_items),
    )
    return EstimateFetchResult(
        found=True,
        estimate_number=existing.estimate_number,
        customer_name=_or(existing.customer_name, data.get("customer_name")),
        customer_phone=_or(existing.customer_phone, data.get("customer_phone")),
        customer_email=_or(existing.customer_email, data.get("customer_email")),
        property_address=_or(existing.property_address, data.get("property_address")),
        date_issued=existing.date_issued,
        scope_text=_or(existing.scope_text, data.get("scope_text")),
        tax_rate=existing.tax_rate,
        permit_fees=existing.permit_fees,
        discount=existing.discount,
        line_items=existing.line_items,
        total=existing.total,
        retrieved_at=existing.retrieved_at,
        milestones=combined_milestones if combined_milestones else existing.milestones,
        contract_date=_or(existing.contract_date, _parse_date(data.get("contract_date"))),
        payment_terms=_or(existing.payment_terms, data.get("payment_terms")),
        warranty_terms=_or(existing.warranty_terms, data.get("warranty_terms")),
        total_mismatch=existing.total_mismatch,
    )


_CLEANUP_NOTE = (
    "\nThis is NOT a new document — these are already-extracted line items from an estimate "
    "that need their descriptions cleaned up: correct typos, OCR garbling, and grammar "
    "mistakes, and tighten anything long-winded or rambling into a clear, well-written "
    "description, while keeping every real technical/scope detail each one actually states. "
    "Return the SAME line items in the SAME order, with the SAME section, qty, unit, and "
    "unit_price values exactly as given in each item's own listing below — only the "
    "description text should change. Do not add, remove, merge, or split any line items; "
    "there must be exactly as many line items in your answer as were given to you.\n"
)


def clean_up_line_item_descriptions(line_items: list) -> list[str]:
    """Rewrites each line item's own description — correcting typos/OCR
    garbling/grammar and tightening rambling text into something clear —
    for line items that were already extracted before this clean-up rule
    existed on the extraction prompt itself (or still came out messy
    anyway). Returns just the cleaned description strings, in the same
    order as the input. section/qty/unit/unit_price are never touched
    here, by design — same reasoning as combine_estimate_with_notes: a
    description clean-up pass has no business touching pricing, and the
    caller is expected to apply these strings back onto the existing rows
    positionally rather than trust anything else the model echoes back."""
    if not line_items:
        return []
    blob = "\n\n".join(
        f"{i + 1}. [{li.section}] {li.description} (qty={li.qty} {li.unit}, unit_price=${li.unit_price})"
        for i, li in enumerate(line_items)
    )
    data = _extract_with_fallback(
        [(blob.encode("utf-8"), "Existing line items", "text/plain")],
        gemini_prompt=_EXTRACTION_PROMPT + _CLEANUP_NOTE,
        gemini_schema=_EXTRACTION_SCHEMA,
        gemini_timeout=45,
        standard_prompt=ai_schema.EXTRACTION_PROMPT + _CLEANUP_NOTE,
        standard_schema=ai_schema.EXTRACTION_SCHEMA,
        not_found_message="Couldn't clean up these line items.",
    )
    cleaned = data.get("line_items", [])
    if len(cleaned) != len(line_items):
        raise GeminiExtractionError(
            f"Expected {len(line_items)} line items back, got {len(cleaned)} — not applying, to avoid "
            "mismatching cleaned descriptions to the wrong items."
        )
    return [c.get("description") or original.description for c, original in zip(cleaned, line_items)]


_HISTORICAL_PROMPT = ai_schema.HISTORICAL_PROMPT

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
    data = _extract_with_fallback(
        files,
        gemini_prompt=_HISTORICAL_PROMPT,
        gemini_schema=_HISTORICAL_SCHEMA,
        # Bounded well under the load balancer's request timeout even in the
        # worst case (this + retry backoff) — someone's waiting on this
        # screen, so failing clearly in ~2.5 min beats hanging for six.
        # Raised from 45s since a folder can send up to _MAX_FOLDER_DOCUMENTS
        # (20) documents in one call — a bigger payload genuinely needs more
        # processing time.
        gemini_timeout=60,
        standard_prompt=ai_schema.HISTORICAL_PROMPT,
        standard_schema=ai_schema.HISTORICAL_SCHEMA,
        not_found_message="Couldn't find usable project information in this Drive folder.",
    )

    line_items = [EstimateLineItemIn(**li) for li in data.get("line_items", [])]
    milestones = [
        MilestonePreview(
            number=m["number"],
            title=m["title"],
            amount=m["amount"],
            due_date=_parse_date(m.get("due_date")),
            scope_verification=m.get("scope_verification") or None,
        )
        for m in data.get("milestones", [])
    ]
    declared_total = data.get("total")
    subtotal = round(sum(li.qty * li.unit_price for li in line_items), 2) or round(sum(m.amount for m in milestones), 2)
    total = float(declared_total or subtotal)
    mismatch = _total_mismatch_message(declared_total, subtotal)

    # A real Scope & Payment Schedule document (like Cabrera's own template)
    # is milestone-centric with no separate per-item cost breakdown at
    # all — every dollar figure lives on the milestones, not a materials/
    # labor line-item table. Leaving line_items empty in that case used to
    # block import entirely ("at least one line item" was required to
    # confirm) even though the project's financials were already complete
    # via milestones — synthesize one summary line item from the total so
    # that requirement is satisfied honestly rather than needing the user
    # to invent cost-breakdown data that was never in the source documents.
    if not line_items and milestones:
        line_items = [EstimateLineItemIn(section="additional_work", description="Project total (from payment schedule)", qty=1, unit="ea", unit_price=total)]

    names = ", ".join(f[1] for f in files)
    logger.info("Extracted historical project from %s: %d line items, %d milestones, total=%.2f", names, len(line_items), len(milestones), total)
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
        total_mismatch=mismatch,
    )
