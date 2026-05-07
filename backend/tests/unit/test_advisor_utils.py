from app.utils.advisor_utils import (
    build_advisor_world_context,
    build_fallback_advisor_suggestions,
    detect_advisor_world_mode,
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
