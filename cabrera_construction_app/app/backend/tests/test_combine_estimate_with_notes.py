"""combine_estimate_with_notes — combines a contractor's pasted notes with
an already-fetched/extracted estimate in ONE AI call that sees both the
estimate's own language and the notes together, so phases (from the notes)
get a scope_verification summary drawn from the estimate's scope/line-item
language. See app/services/gemini_service.py for the design. The actual
provider call (_extract_with_fallback) is mocked throughout — this suite
never makes a real network call."""

from app.schemas import EstimateFetchResult, EstimateLineItemIn, MilestonePreview
from app.services import gemini_service


def _fallback_response(**overrides):
    defaults = dict(found=True, milestones=[], line_items=[])
    defaults.update(overrides)
    return defaults


def test_combined_milestones_get_scope_verification_and_are_renumbered(monkeypatch):
    existing = EstimateFetchResult(
        found=True,
        estimate_number="1042",
        customer_name="Jane Doe",
        total=10000,
        line_items=[EstimateLineItemIn(section="materials", description="Cabinets", qty=1, unit="ea", unit_price=10000)],
        milestones=[],  # QuickBooks-style estimate: cost breakdown, no payment schedule
    )
    captured_files = {}

    def fake_fallback(files, **kwargs):
        captured_files["files"] = files
        return _fallback_response(
            milestones=[
                {"number": 5, "title": "Deposit", "amount": 1000, "scope_verification": "Initial deposit to begin the cabinet order."},
                {"number": 9, "title": "Final", "amount": 9000, "scope_verification": "Final payment once cabinets are installed."},
            ]
        )

    monkeypatch.setattr(gemini_service, "_extract_with_fallback", fake_fallback)

    result = gemini_service.combine_estimate_with_notes(existing, "deposit $1000, final $9000 on install")

    assert [m.number for m in result.milestones] == [0, 1]
    assert result.milestones[0].scope_verification == "Initial deposit to begin the cabinet order."
    assert result.milestones[1].scope_verification == "Final payment once cabinets are installed."
    # Both documents (estimate language + notes) were sent together in one call.
    assert len(captured_files["files"]) == 2
    assert captured_files["files"][1][0] == b"deposit $1000, final $9000 on install"


def test_line_items_and_total_are_never_touched_by_the_model(monkeypatch):
    existing_line_items = [EstimateLineItemIn(section="materials", description="Cabinets", qty=1, unit="ea", unit_price=10000)]
    existing = EstimateFetchResult(found=True, estimate_number="1042", total=10000, line_items=existing_line_items)

    def fake_fallback(files, **kwargs):
        # Even if the model tries to invent new line items / a different total, they must be ignored.
        return _fallback_response(
            line_items=[{"section": "labor", "description": "Invented by the model", "qty": 1, "unit": "ea", "unit_price": 99999}],
            total=1,
            milestones=[{"number": 0, "title": "Deposit", "amount": 1000, "scope_verification": None}],
        )

    monkeypatch.setattr(gemini_service, "_extract_with_fallback", fake_fallback)

    result = gemini_service.combine_estimate_with_notes(existing, "deposit $1000")

    assert result.line_items == existing_line_items
    assert result.total == 10000


def test_empty_notes_text_raises_without_calling_the_model(monkeypatch):
    existing = EstimateFetchResult(found=True, estimate_number="1042", total=5000)
    called = []
    monkeypatch.setattr(gemini_service, "_extract_with_fallback", lambda *a, **k: called.append(1))

    try:
        gemini_service.combine_estimate_with_notes(existing, "   ")
        assert False, "expected GeminiExtractionError"
    except gemini_service.GeminiExtractionError:
        pass
    assert called == []


def test_falls_back_to_existing_milestones_when_model_returns_none(monkeypatch):
    existing_milestones = [MilestonePreview(number=0, title="Deposit", amount=500)]
    existing = EstimateFetchResult(found=True, estimate_number="1042", total=5000, milestones=existing_milestones)
    monkeypatch.setattr(gemini_service, "_extract_with_fallback", lambda *a, **k: _fallback_response(milestones=[]))

    result = gemini_service.combine_estimate_with_notes(existing, "notes with no schedule info")

    assert len(result.milestones) == 1
    assert result.milestones[0].title == "Deposit"


def test_existing_fields_are_not_overwritten_by_the_model(monkeypatch):
    existing = EstimateFetchResult(found=True, estimate_number="1042", customer_name="Jane Doe (confirmed)", total=5000)
    monkeypatch.setattr(
        gemini_service, "_extract_with_fallback", lambda *a, **k: _fallback_response(customer_name="Some Other Name")
    )

    result = gemini_service.combine_estimate_with_notes(existing, "notes")

    assert result.customer_name == "Jane Doe (confirmed)"


def test_blank_fields_fall_back_to_the_model_result(monkeypatch):
    existing = EstimateFetchResult(found=True, estimate_number="1042", customer_name="", scope_text=None, total=5000)
    monkeypatch.setattr(
        gemini_service,
        "_extract_with_fallback",
        lambda *a, **k: _fallback_response(customer_name="Jane Doe", scope_text="Full kitchen remodel"),
    )

    result = gemini_service.combine_estimate_with_notes(existing, "notes mentioning Jane Doe")

    assert result.customer_name == "Jane Doe"
    assert result.scope_text == "Full kitchen remodel"


def test_estimate_text_blob_includes_existing_milestones_for_context():
    existing = EstimateFetchResult(
        found=True,
        estimate_number="1042",
        scope_text="Kitchen remodel.",
        line_items=[EstimateLineItemIn(section="materials", description="Cabinets", qty=1, unit="ea", unit_price=5000)],
        milestones=[MilestonePreview(number=0, title="Deposit", amount=1000)],
    )
    blob = gemini_service._estimate_text_blob(existing)

    assert "Kitchen remodel." in blob
    assert "Cabinets" in blob
    assert "Deposit" in blob  # existing schedule included so the model knows it's there
