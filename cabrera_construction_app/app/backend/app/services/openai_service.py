"""GPT (OpenAI) as an extraction provider — tried last by gemini_service's
orchestration, after Gemini and Claude, when neither is configured or
neither finds usable information. Authenticated with a plain API key from
platform.openai.com (OPENAI_API_KEY). Uses the Responses API (not the
older Chat Completions API) specifically because it supports both native
PDF input (`input_file` with inline base64 data — Chat Completions has no
document-input content type) and Structured Outputs (`text.format:
json_schema` with `strict: true`, which guarantees the response matches
`schema` exactly rather than hoping a prompt-only instruction is honored).

OpenAI's exact Responses API field names have moved in the past and may
move again — if this provider's requests start failing after working
before, that's the first thing to check against OpenAI's current API
reference, not a sign the whole multi-provider approach is broken (the
other providers are unaffected by an OpenAI-side API change).
"""

from __future__ import annotations

import base64
import json
import logging

import httpx

from ..config import settings
from .document_text import DocumentReadError, DocumentPart, PdfPart, TextPart, build_document_parts

logger = logging.getLogger("cabrera.openai")

_API_URL = "https://api.openai.com/v1/responses"
_SCHEMA_NAME = "project_extraction"


class OpenAIExtractionError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.openai_api_key)


def _content_part(part: DocumentPart) -> dict:
    if isinstance(part, TextPart):
        return {"type": "input_text", "text": part.text}
    if isinstance(part, PdfPart):
        b64 = base64.b64encode(part.data).decode("ascii")
        return {"type": "input_file", "filename": "document.pdf", "file_data": f"data:application/pdf;base64,{b64}"}
    raise TypeError(f"Unknown document part type: {type(part)!r}")


def extract(files: list[tuple[bytes, str, str]], prompt: str, schema: dict, timeout: float = 45) -> dict:
    """files: (bytes, filename, content_type) triples. Returns the raw
    extracted dict (same shape as Gemini's/Claude's parsed response).
    Raises OpenAIExtractionError on any failure — the caller treats that as
    "this provider couldn't help, try the next one" (or, for OpenAI, the
    last one — surface the aggregated error if this was the final try)."""
    if not settings.openai_api_key:
        raise OpenAIExtractionError("OPENAI_API_KEY is not set.")
    if not files:
        raise OpenAIExtractionError("No documents to extract from.")

    try:
        parts = build_document_parts(files)
    except DocumentReadError as exc:
        raise OpenAIExtractionError(str(exc)) from exc

    content = [_content_part(p) for p in parts] + [{"type": "input_text", "text": prompt}]
    names = ", ".join(f[1] for f in files)

    try:
        resp = httpx.post(
            _API_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.openai_model,
                "input": [{"role": "user", "content": content}],
                "text": {"format": {"type": "json_schema", "name": _SCHEMA_NAME, "schema": schema, "strict": True}},
            },
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        logger.error("GPT extraction request failed for %s: %s", names, exc)
        raise OpenAIExtractionError(f"OpenAI request failed: {exc}") from exc

    if resp.status_code >= 400:
        message = _extract_error_message(resp)
        logger.error("GPT extraction failed for %s: %s", names, message)
        raise OpenAIExtractionError(f"OpenAI API error: {message}")

    try:
        body = resp.json()
        message_item = next(item for item in body["output"] if item.get("type") == "message")
        text_block = next(block for block in message_item["content"] if block.get("type") == "output_text")
        data = json.loads(text_block["text"])
    except (ValueError, KeyError, StopIteration) as exc:
        logger.error("GPT returned an unexpected response shape for %s: %s", names, exc)
        raise OpenAIExtractionError(f"OpenAI returned an unexpected response: {exc}") from exc

    logger.info("GPT extracted from %s", names)
    return data


def _extract_error_message(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
        return f"{err.get('message', 'OpenAI API error')} ({err.get('type', resp.status_code)})"
    except ValueError:
        return resp.text[:300] or f"OpenAI API returned {resp.status_code}"
