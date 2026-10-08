"""combine_estimate_with_notes — merges a contractor's pasted notes into an
already-fetched/extracted estimate, e.g. a QuickBooks lookup that has the
cost breakdown but no payment schedule, plus notes that supply the phases.
See app/services/gemini_service.py for the merge rules. The notes'
extraction call is mocked — this suite never makes a real network call."""

from app.schemas import EstimateFetchResult, EstimateLineItemIn, MilestonePreview
from app.services import gemini_service


def _notes_result(**overrides):
    defaults = dict(found=True, estimate_number="DOC-notes", milestones=[], line_items=[])
    defaults.update(overrides)
    return EstimateFetchResult(**defaults)


def test_notes_milestones_win_and_get_renumbered(monkeypatch):
    existing = EstimateFetchResult(
        found=True,
        estimate_number="1042",
        customer_name="Jane Doe",
        total=10000,
        line_items=[EstimateLineItemIn(section="materials", description="Cabinets", qty=1, unit="ea", unit_price=10000)],
        milestones=[],  # QuickBooks-style estimate: cost breakdown, no payment schedule
    )
    notes_extraction = _notes_result(
        milestones=[
            MilestonePreview(number=5, title="Deposit", amount=1000),
            MilestonePreview(number=9, title="Final", amount=9000),
        ]
    )
    monkeypatch.setattr(gemini_service, "extract_estimate_from_text", lambda text: notes_extraction)

    result = gemini_service.combine_estimate_with_notes(existing, "deposit $1000, final $9000")

    assert [m.number for m in result.milestones] == [0, 1]
    assert [m.title for m in result.milestones] == ["Deposit", "Final"]
    assert result.line_items == existing.line_items  # estimate's cost breakdown preserved
    assert result.total == 10000


def test_existing_milestones_kept_when_notes_have_none(monkeypatch):
    existing_milestones = [MilestonePreview(number=0, title="Deposit", amount=500)]
    existing = EstimateFetchResult(found=True, estimate_number="1042", total=5000, milestones=existing_milestones)
    monkeypatch.setattr(gemini_service, "extract_estimate_from_text", lambda text: _notes_result())

    result = gemini_service.combine_estimate_with_notes(existing, "just some general notes, no schedule here")

    assert len(result.milestones) == 1
    assert result.milestones[0].title == "Deposit"


def test_notes_fill_in_missing_customer_and_scope_fields(monkeypatch):
    existing = EstimateFetchResult(found=True, estimate_number="1042", customer_name="", scope_text=None, total=5000)
    monkeypatch.setattr(
        gemini_service,
        "extract_estimate_from_text",
        lambda text: _notes_result(customer_name="Jane Doe", scope_text="Full kitchen remodel", property_address="123 Main St"),
    )

    result = gemini_service.combine_estimate_with_notes(existing, "notes mentioning Jane Doe, 123 Main St")

    assert result.customer_name == "Jane Doe"
    assert result.scope_text == "Full kitchen remodel"
    assert result.property_address == "123 Main St"


def test_existing_customer_fields_are_not_overwritten_by_notes(monkeypatch):
    existing = EstimateFetchResult(found=True, estimate_number="1042", customer_name="Jane Doe (confirmed)", total=5000)
    monkeypatch.setattr(gemini_service, "extract_estimate_from_text", lambda text: _notes_result(customer_name="Some Other Name"))

    result = gemini_service.combine_estimate_with_notes(existing, "notes")

    assert result.customer_name == "Jane Doe (confirmed)"


def test_line_items_fall_back_to_notes_when_estimate_has_none(monkeypatch):
    existing = EstimateFetchResult(found=True, estimate_number="DOC-notes-only", total=None, line_items=[])
    notes_line_items = [EstimateLineItemIn(section="labor", description="Framing", qty=1, unit="ea", unit_price=2000)]
    monkeypatch.setattr(gemini_service, "extract_estimate_from_text", lambda text: _notes_result(line_items=notes_line_items, total=2000))

    result = gemini_service.combine_estimate_with_notes(existing, "framing labor $2000")

    assert result.line_items == notes_line_items
    assert result.total == 2000


def test_total_mismatch_recomputed_against_merged_line_items(monkeypatch):
    existing = EstimateFetchResult(
        found=True,
        estimate_number="1042",
        total=10000,  # declared total disagrees with the $8,000 line-item subtotal below
        line_items=[EstimateLineItemIn(section="materials", description="Cabinets", qty=1, unit="ea", unit_price=8000)],
    )
    monkeypatch.setattr(gemini_service, "extract_estimate_from_text", lambda text: _notes_result())

    result = gemini_service.combine_estimate_with_notes(existing, "notes")

    assert result.total_mismatch is not None
