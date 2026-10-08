"""clean_up_line_item_descriptions + the two /estimate/line-items endpoints
— lets an already-created project's messy line-item descriptions (e.g. a
real estimate with long rambling per-item text, extracted before the
extraction prompt's own clean-up rule existed) get cleaned up after the
fact, either via AI or by hand. The AI call is mocked at the
_extract_with_fallback level — this suite never makes a real network call.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services import gemini_service
from tests.factories import make_estimate, make_line_item, make_project


def _fallback_response(line_items):
    return {"found": True, "line_items": line_items, "milestones": []}


# --- gemini_service.clean_up_line_item_descriptions -------------------------


def test_clean_up_returns_cleaned_descriptions_in_order(monkeypatch):
    items = [
        SimpleNamespace(section="demolition", description="Heter floorin. for the bathroom", qty=1, unit="ea", unit_price=3000),
        SimpleNamespace(section="materials", description="New bathroom Construction of new walls...", qty=1, unit="ea", unit_price=25000),
    ]
    monkeypatch.setattr(
        gemini_service,
        "_extract_with_fallback",
        lambda *a, **k: _fallback_response(
            [
                {"section": "demolition", "description": "Heated flooring for the bathroom.", "qty": 1, "unit": "ea", "unit_price": 3000},
                {"section": "materials", "description": "Construction of new bathroom walls.", "qty": 1, "unit": "ea", "unit_price": 25000},
            ]
        ),
    )

    result = gemini_service.clean_up_line_item_descriptions(items)

    assert result == ["Heated flooring for the bathroom.", "Construction of new bathroom walls."]


def test_clean_up_empty_list_short_circuits_without_calling_the_model(monkeypatch):
    called = []
    monkeypatch.setattr(gemini_service, "_extract_with_fallback", lambda *a, **k: called.append(1))

    assert gemini_service.clean_up_line_item_descriptions([]) == []
    assert called == []


def test_clean_up_raises_on_count_mismatch_rather_than_misapplying(monkeypatch):
    items = [
        SimpleNamespace(section="demolition", description="A", qty=1, unit="ea", unit_price=100),
        SimpleNamespace(section="materials", description="B", qty=1, unit="ea", unit_price=200),
    ]
    # Model merged two items into one -- must not apply positionally onto the wrong rows.
    monkeypatch.setattr(
        gemini_service,
        "_extract_with_fallback",
        lambda *a, **k: _fallback_response([{"section": "demolition", "description": "A and B", "qty": 1, "unit": "ea", "unit_price": 100}]),
    )

    try:
        gemini_service.clean_up_line_item_descriptions(items)
        assert False, "expected GeminiExtractionError"
    except gemini_service.GeminiExtractionError as exc:
        assert "Expected 2" in str(exc)


def test_clean_up_falls_back_to_original_when_model_omits_a_description(monkeypatch):
    items = [SimpleNamespace(section="demolition", description="Original text", qty=1, unit="ea", unit_price=100)]
    monkeypatch.setattr(
        gemini_service,
        "_extract_with_fallback",
        lambda *a, **k: _fallback_response([{"section": "demolition", "description": "", "qty": 1, "unit": "ea", "unit_price": 100}]),
    )

    result = gemini_service.clean_up_line_item_descriptions(items)

    assert result == ["Original text"]


# --- API endpoints ------------------------------------------------------------


def test_clean_up_endpoint_updates_descriptions_and_never_touches_pricing(db, client, monkeypatch):
    project = make_project(db)
    estimate = make_estimate(db, project)
    li1 = make_line_item(db, estimate, section="demolition", description="Heter floorin. for the bathroom", qty=1, unit="ea", unit_price=3000)
    li2 = make_line_item(db, estimate, section="materials", description="New bathroom Construction of new walls...", qty=1, unit="ea", unit_price=25000)
    db.commit()

    monkeypatch.setattr(
        gemini_service,
        "_extract_with_fallback",
        lambda *a, **k: _fallback_response(
            [
                {"section": "demolition", "description": "Heated flooring for the bathroom.", "qty": 999, "unit": "boxes", "unit_price": 1},
                {"section": "materials", "description": "Construction of new bathroom walls.", "qty": 999, "unit": "boxes", "unit_price": 1},
            ]
        ),
    )

    resp = client.post(f"/api/projects/{project.id}/estimate/line-items/clean-up")
    assert resp.status_code == 200
    body = resp.json()
    descriptions = {li["id"]: li["description"] for li in body["line_items"]}
    assert descriptions[li1.id] == "Heated flooring for the bathroom."
    assert descriptions[li2.id] == "Construction of new bathroom walls."

    db.expire_all()
    # The model's attempt to change qty/unit/unit_price must have been ignored entirely.
    assert float(db.get(type(li1), li1.id).unit_price) == 3000
    assert float(db.get(type(li2), li2.id).unit_price) == 25000


def test_clean_up_endpoint_404_without_line_items(db, client):
    project = make_project(db)
    make_estimate(db, project)
    db.commit()

    resp = client.post(f"/api/projects/{project.id}/estimate/line-items/clean-up")
    assert resp.status_code == 404


def test_manual_update_endpoint_changes_only_description(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    li = make_line_item(db, estimate, description="Original", unit_price=500)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/estimate/line-items", json={"items": [{"id": li.id, "description": "Edited by hand"}]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["line_items"][0]["description"] == "Edited by hand"
    assert body["line_items"][0]["unit_price"] == 500


def test_manual_update_skips_unknown_ids_without_erroring(db, client):
    project = make_project(db)
    estimate = make_estimate(db, project)
    make_line_item(db, estimate)
    db.commit()

    resp = client.patch(f"/api/projects/{project.id}/estimate/line-items", json={"items": [{"id": 999999, "description": "Doesn't exist"}]})
    assert resp.status_code == 200
