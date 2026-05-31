import uuid

import pytest

from app.utils.advisor_utils import (
    advisor_retrieval_settings,
    build_story_context,
    build_advisor_world_context,
    build_fallback_advisor_suggestions,
    classify_intent_fast,
    classify_response_type,
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


def test_advisor_retrieval_settings_use_continuity_profile_for_consistency_and_world_mode():
    assert advisor_retrieval_settings("consistency", None) == (12, 0.22)
    assert advisor_retrieval_settings("general", "gap_detection") == (12, 0.22)


def test_advisor_retrieval_settings_use_general_profile_by_default():
    assert advisor_retrieval_settings("general", None) == (8, 0.28)


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


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_warning_marker():
    result = await classify_response_type(None, "⚠️ This contradicts chapter 3")
    assert result == "warning"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_contradiction_inline():
    result = await classify_response_type(None, "Here is an analysis. ⚠️ Contradiction in the timeline")
    assert result == "warning"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_opportunity_marker():
    result = await classify_response_type(None, "✨ Here is a chance to expand the lore")
    assert result == "opportunity"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_opportunity_inline():
    result = await classify_response_type(None, "Take a look. ✨ Opportunity: unused side character")
    assert result == "opportunity"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_tradeoff_marker():
    result = await classify_response_type(None, "🔀 Option A: Kill the king. Option B: Spare him.")
    assert result == "tradeoff"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_fallback_to_standard():
    result = await classify_response_type(None, "Here is some general advice about your story pacing.")
    assert result == "standard"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_empty_reply():
    result = await classify_response_type(None, "")
    assert result == "standard"


def test_classify_intent_fast_plothole_exact():
    assert classify_intent_fast("I found a plot hole in chapter 3") == "plothole"


def test_classify_intent_fast_plothole_contradiction():
    assert classify_intent_fast("This contradicts what happened in chapter 1") == "plothole"


def test_classify_intent_fast_plothole_inconsistency():
    assert classify_intent_fast("There is an inconsistency in the timeline") == "plothole"
    assert classify_intent_fast("This doesn't make sense given the lore") == "plothole"


def test_classify_intent_fast_direction_what_should():
    assert classify_intent_fast("What should happen next in the story?") == "direction"


def test_classify_intent_fast_direction_stuck():
    assert classify_intent_fast("I am stuck on this chapter, where do I go from here?") == "direction"


def test_classify_intent_fast_direction_next_step():
    assert classify_intent_fast("What is the next step for my protagonist?") == "direction"


def test_classify_intent_fast_opportunity_potential():
    assert classify_intent_fast("Is there untapped potential in this side character?") == "opportunity"


def test_classify_intent_fast_opportunity_expand():
    assert classify_intent_fast("Could I expand the magic system further?") == "opportunity"


def test_classify_intent_fast_consistency_canon():
    assert classify_intent_fast("Does this new chapter stay consistent with the canon?") == "consistency"


def test_classify_intent_fast_consistency_rules():
    assert classify_intent_fast("Are there any worldbuilding rules I'm breaking?") == "consistency"


def test_classify_intent_fast_consistency_timeline():
    assert classify_intent_fast("Check the timeline for continuity errors") == "consistency"


def test_classify_intent_fast_general_unknown():
    assert classify_intent_fast("Hello, how are you doing today?") == "general"


def test_classify_intent_fast_general_empty_string():
    assert classify_intent_fast("") == "general"


def test_classify_intent_fast_general_none():
    assert classify_intent_fast(None) == "general"


def test_classify_intent_fast_mixed_case():
    assert classify_intent_fast("I FOUND A PLOT HOLE in my manuscript") == "plothole"


def test_classify_intent_fast_whitespace_only():
    assert classify_intent_fast("   ") == "general"


def test_classify_intent_fast_direction_should_i():
    assert classify_intent_fast("Should I kill off this character in chapter 5?") == "direction"
