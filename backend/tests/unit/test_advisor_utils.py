import uuid

import pytest

from app.utils.advisor_utils import (
    build_story_context,
    build_advisor_world_context,
    build_fallback_advisor_suggestions,
    detect_advisor_world_mode,
    identify_character_mentions,
    invalidate_advisor_caches,
    invalidate_advisor_caches_for_book,
    normalize_proactive_scan_result,
)


def test_build_fallback_advisor_suggestions_returns_three_items_without_focus_thread():
    suggestions = build_fallback_advisor_suggestions(
        book_title="Lord El Melloi",
        total_chapters=50,
        character_count=18,
        open_thread_count=4,
        focus_thread=None,
    )

    assert len(suggestions) == 3
    assert suggestions[0]["type"] == "manuscript_checkpoint"
    assert suggestions[-1]["type"] == "unresolved_clue"


def test_build_fallback_advisor_suggestions_uses_focus_thread_when_available():
    suggestions = build_fallback_advisor_suggestions(
        book_title="Lord El Melloi",
        total_chapters=50,
        character_count=18,
        open_thread_count=4,
        focus_thread={
            "title": "The sealed letter",
            "introduced_at": 8,
            "description": "Mentioned repeatedly but not resolved.",
        },
    )

    assert len(suggestions) == 3
    assert suggestions[-1]["type"] == "future_direction"
    assert "sealed letter" in suggestions[-1]["title"].lower()


def test_detect_advisor_world_mode_routes_gap_questions_to_gap_detection():
    mode = detect_advisor_world_mode(
        "Are there missing worldbuilding gaps or canon contradictions in the magic system?",
        "consistency",
    )

    assert mode == "gap_detection"


def test_detect_advisor_world_mode_ignores_non_lore_questions():
    assert detect_advisor_world_mode("Should my protagonist forgive her brother?", "direction") is None


def test_detect_advisor_world_mode_routes_reaction_questions_to_story_integration():
    mode = detect_advisor_world_mode(
        "How would the river kingdom react if I introduced this trade blockade?",
        "general",
    )

    assert mode == "story_integration"


def test_build_advisor_world_context_compacts_alerts_suggestions_and_citations():
    context = build_advisor_world_context(
        {
            "mode": "gap_detection",
            "answer": "World logic scan found one major canon issue.",
            "logic_alerts": [
                {
                    "title": "Magic rule conflict",
                    "description": "The spell works in chapter 8 but the lore says it requires moonlight.",
                    "suggested_fix": "Add a moonlit source to the scene.",
                }
            ],
            "suggestions": [
                {
                    "element_name": "Moon Gate",
                    "description": "Seed the gate before the battle.",
                }
            ],
            "citations": [
                {
                    "name": "Moon Gate",
                    "element_type": "place",
                    "source_scope": "worldbuilding",
                }
            ],
            "simulation_steps": ["Canon focus: Moon Gate behaves as a place with worldbuilding support."],
        }
    )

    assert "WORLD ANALYSIS" in context
    assert "Magic rule conflict" in context
    assert "Moon Gate [place] source=worldbuilding" in context


def test_identify_character_mentions_matches_punctuation_and_possessives():
    matches = identify_character_mentions(
        "Gregor's breathing caught. Later, Grete whispered, \"Not now.\"",
        [
            {"name": "Gregor", "aliases": [], "first_chapter": 1},
            {"name": "Grete", "aliases": [], "first_chapter": 1},
            {"name": "Mother", "aliases": [], "first_chapter": 1},
        ],
    )

    assert [item["name"] for item in matches] == ["Gregor", "Grete"]


@pytest.mark.asyncio
async def test_invalidate_advisor_caches_delegates_to_namespace_invalidator(monkeypatch):
    captured = {}

    async def _fake_invalidate(*, book_id=None, series_ids=None):
        captured["book_id"] = book_id
        captured["series_ids"] = series_ids

    monkeypatch.setattr(
        "app.utils.advisor_utils.invalidate_advisor_cache_namespaces",
        _fake_invalidate,
    )

    await invalidate_advisor_caches(book_id="book-key", series_ids=["series-a"])

    assert captured == {"book_id": "book-key", "series_ids": ["series-a"]}


@pytest.mark.asyncio
async def test_invalidate_advisor_caches_for_book_expands_series_scope(monkeypatch):
    captured = {}

    async def _fake_invalidate(*, book_id=None, series_ids=None):
        captured["book_id"] = book_id
        captured["series_ids"] = series_ids

    class _FakeResult:
        def all(self):
            return [type("Row", (), {"series_id": "series-a"})(), type("Row", (), {"series_id": "series-b"})()]

    class _FakeDB:
        async def execute(self, *_args, **_kwargs):
            return _FakeResult()

    monkeypatch.setattr(
        "app.utils.advisor_utils.invalidate_advisor_caches",
        _fake_invalidate,
    )

    await invalidate_advisor_caches_for_book(_FakeDB(), book_id="12345678-1234-5678-1234-567812345678")

    assert captured == {
        "book_id": "12345678-1234-5678-1234-567812345678",
        "series_ids": ["series-a", "series-b"],
    }


def test_normalize_proactive_scan_result_keeps_valid_findings():
    payload = normalize_proactive_scan_result(
        '{"findings":[{"severity":"warning","type":"event_conflict","title":"Broken alibi","description":"The alibi fails in chapter 9.","chapter_ref":9,"action_label":"Trace the alibi","ask_prompt":"Where does the alibi break?"}],"overall_note":"One continuity risk found."}'
    )

    assert payload["overall_note"] == "One continuity risk found."
    assert payload["findings"][0]["type"] == "event_conflict"
    assert payload["findings"][0]["chapter_ref"] == 9


def test_normalize_proactive_scan_result_falls_back_on_invalid_json():
    payload = normalize_proactive_scan_result("not-json")

    assert payload["findings"] == []
    assert "not-json" in payload["overall_note"]


@pytest.mark.asyncio
async def test_build_story_context_returns_cached_payload(monkeypatch):
    book_id = "12345678-1234-5678-1234-567812345678"

    async def _fake_get_version(_book_id):
        return 0

    async def _fake_get_cache(_book_id, _version, _total_ch):
        return "cached-context"

    async def _fake_set_cache(*_args, **_kwargs):
        raise AssertionError("cache set should not run on cache hit")

    monkeypatch.setattr("app.utils.advisor_utils.get_book_cache_version", _fake_get_version)
    monkeypatch.setattr("app.utils.advisor_utils.get_story_context_cache", _fake_get_cache)
    monkeypatch.setattr("app.utils.advisor_utils.set_story_context_cache", _fake_set_cache)

    class _FailingDB:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("db should not be queried on cache hit")

    payload = await build_story_context(_FailingDB(), uuid.UUID(book_id), 12)

    assert payload == "cached-context"
