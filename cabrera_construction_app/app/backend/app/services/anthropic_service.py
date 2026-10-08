"""Claude (Anthropic) as an extraction provider — tried by gemini_service's
orchestration when Gemini is unset or doesn't find usable information in a
given document/paste. Authenticated with a plain API key from
console.anthropic.com (ANTHROPIC_API_KEY), unrelated to any OAuth flow in
this app. Structured JSON output uses forced tool-use (Claude has no
separate "response schema" mode the way Gemini/OpenAI do — a single tool
with `tool_choice` forcing its use is the standard way to get back
guaranteed-shaped JSON) rather than parsing free-form text, so there's no
JSON-parsing step the way there is for Gemini's text-wrapped response.
"""

from __future__ import annotations

import base64
import logging

import httpx

from ..config import settings
from .document_text import DocumentReadError, DocumentPart, PdfPart, TextPart, build_document_parts

logger = logging.getLogger("cabrera.anthropic")

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_TOOL_NAME = "extract_project_info"
_MAX_TOKENS = 8192


class AnthropicExtractionError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.anthropic_api_key)


def _content_block(part: DocumentPart) -> dict:
    if isinstance(part, TextPart):
        return {"type": "text", "text": part.text}
    if isinstance(part, PdfPart):
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(part.data).decode("ascii")}}
    raise TypeError(f"Unknown document part type: {type(part)!r}")


def extract(files: list[tuple[bytes, str, str]], prompt: str, schema: dict, timeout: float = 45) -> dict:
    """files: (bytes, filename, content_type) triples. Returns the raw
    extracted dict (same shape as Gemini's parsed response — found,
    customer_name, line_items, milestones, ...). Raises
    AnthropicExtractionError on any failure (not configured, network, API
    error, malformed response) — the caller (gemini_service's orchestrator)
    treats that as "this provider couldn't help, try the next one"."""
    if not settings.anthropic_api_key:
        raise AnthropicExtractionError("ANTHROPIC_API_KEY is not set.")
    if not files:
        raise AnthropicExtractionError("No documents to extract from.")

    try:
        parts = build_document_parts(files)
    except DocumentReadError as exc:
        raise AnthropicExtractionError(str(exc)) from exc

    content = [_content_block(p) for p in parts] + [{"type": "text", "text": prompt}]
    names = ", ".join(f[1] for f in files)

    try:
        resp = httpx.post(
            _API_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": _API_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": _MAX_TOKENS,
                "messages": [{"role": "user", "content": content}],
                "tools": [{"name": _TOOL_NAME, "description": "Record the extracted project/estimate information.", "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": _TOOL_NAME},
            },
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        logger.error("Claude extraction request failed for %s: %s", names, exc)
        raise AnthropicExtractionError(f"Claude request failed: {exc}") from exc

    if resp.status_code >= 400:
        message = _extract_error_message(resp)
        logger.error("Claude extraction failed for %s: %s", names, message)
        raise AnthropicExtractionError(f"Claude API error: {message}")

    try:
        body = resp.json()
        tool_use = next(block for block in body["content"] if block.get("type") == "tool_use")
        data = tool_use["input"]
    except (ValueError, KeyError, StopIteration) as exc:
        logger.error("Claude returned an unexpected response shape for %s: %s", names, exc)
        raise AnthropicExtractionError(f"Claude returned an unexpected response: {exc}") from exc

    logger.info("Claude extracted from %s", names)
    return data


def _extract_error_message(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
        return f"{err.get('message', 'Claude API error')} ({err.get('type', resp.status_code)})"
    except ValueError:
        return resp.text[:300] or f"Claude API returned {resp.status_code}"
