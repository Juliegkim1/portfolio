"""Multi-provider AI extraction fallback (Gemini -> Claude -> GPT) — see
app/services/gemini_service.py's _extract_with_fallback. Every provider
call is monkeypatched here; this suite must never make a real network call,
so it runs in CI with no API keys configured at all.
"""

from __future__ import annotations

import pytest

from app.services import gemini_service


@pytest.fixture(autouse=True)
def _bypass_document_parsing(monkeypatch):
    # These tests exercise provider ordering/fallback, not real document
    # parsing — a throwaway file list is enough once validation is a no-op.
    monkeypatch.setattr(gemini_service, "build_document_parts", lambda files: files)


@pytest.fixture
def _no_providers(monkeypatch):
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", "")
    monkeypatch.setattr(gemini_service.anthropic_service, "is_configured", lambda: False)
    monkeypatch.setattr(gemini_service.openai_service, "is_configured", lambda: False)


def _found(**overrides):
    data = {"found": True, "line_items": [{"description": "Cabinets"}]}
    data.update(overrides)
    return data


def _not_found():
    return {"found": False, "line_items": [], "milestones": []}


FILES = [(b"fake-bytes", "estimate.pdf", "application/pdf")]


def test_raises_not_configured_when_no_provider_is_set(_no_providers):
    with pytest.raises(gemini_service.GeminiNotConfigured):
        gemini_service._extract_with_fallback(
            FILES,
            gemini_prompt="p",
            gemini_schema={},
            gemini_timeout=1,
            standard_prompt="p",
            standard_schema={},
            not_found_message="nothing usable",
        )


def test_no_files_raises_before_checking_providers(_no_providers):
    with pytest.raises(gemini_service.GeminiExtractionError, match="No documents"):
        gemini_service._extract_with_fallback(
            [],
            gemini_prompt="p",
            gemini_schema={},
            gemini_timeout=1,
            standard_prompt="p",
            standard_schema={},
            not_found_message="nothing usable",
        )


def test_gemini_succeeds_claude_and_gpt_never_called(monkeypatch):
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(gemini_service, "_call_gemini", lambda f, p, s, t: _found(line_items=[{"description": "Gemini"}]))

    claude_calls = []
    gpt_calls = []
    monkeypatch.setattr(gemini_service.anthropic_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service.anthropic_service, "extract", lambda *a, **k: claude_calls.append(1) or _found())
    monkeypatch.setattr(gemini_service.openai_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service.openai_service, "extract", lambda *a, **k: gpt_calls.append(1) or _found())

    result = gemini_service._extract_with_fallback(
        FILES, gemini_prompt="p", gemini_schema={}, gemini_timeout=1, standard_prompt="p", standard_schema={}, not_found_message="x"
    )

    assert result["line_items"][0]["description"] == "Gemini"
    assert claude_calls == []
    assert gpt_calls == []


def test_gemini_fails_falls_through_to_claude(monkeypatch):
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(gemini_service, "_call_gemini", lambda f, p, s, t: (_ for _ in ()).throw(gemini_service.GeminiExtractionError("rate limited")))
    monkeypatch.setattr(gemini_service.anthropic_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service.anthropic_service, "extract", lambda *a, **k: _found(line_items=[{"description": "Claude"}]))
    monkeypatch.setattr(gemini_service.openai_service, "is_configured", lambda: False)

    result = gemini_service._extract_with_fallback(
        FILES, gemini_prompt="p", gemini_schema={}, gemini_timeout=1, standard_prompt="p", standard_schema={}, not_found_message="x"
    )
    assert result["line_items"][0]["description"] == "Claude"


def test_gemini_not_configured_skips_straight_to_gpt(monkeypatch):
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", "")
    monkeypatch.setattr(gemini_service.anthropic_service, "is_configured", lambda: False)
    monkeypatch.setattr(gemini_service.openai_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service.openai_service, "extract", lambda *a, **k: _found(line_items=[{"description": "GPT"}]))

    result = gemini_service._extract_with_fallback(
        FILES, gemini_prompt="p", gemini_schema={}, gemini_timeout=1, standard_prompt="p", standard_schema={}, not_found_message="x"
    )
    assert result["line_items"][0]["description"] == "GPT"


def test_all_providers_fail_or_find_nothing_raises_with_every_reason(monkeypatch):
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(gemini_service, "_call_gemini", lambda f, p, s, t: (_ for _ in ()).throw(RuntimeError("gemini boom")))
    monkeypatch.setattr(gemini_service.anthropic_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service.anthropic_service, "extract", lambda *a, **k: _not_found())
    monkeypatch.setattr(gemini_service.openai_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service.openai_service, "extract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gpt boom")))

    with pytest.raises(gemini_service.GeminiExtractionError) as exc_info:
        gemini_service._extract_with_fallback(
            FILES, gemini_prompt="p", gemini_schema={}, gemini_timeout=1, standard_prompt="p", standard_schema={}, not_found_message="nothing usable"
        )

    message = str(exc_info.value)
    assert "Gemini: gemini boom" in message
    assert "Claude: nothing usable" in message
    assert "GPT: gpt boom" in message
