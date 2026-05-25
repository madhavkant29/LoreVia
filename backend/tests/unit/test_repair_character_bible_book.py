from types import SimpleNamespace
import uuid

import pytest

from scripts import repair_character_bible_book


def _character(**overrides):
    payload = {
        "id": uuid.uuid4(),
        "name": "Aikawa",
        "aliases": [],
        "trait_state": {},
        "analysis_metadata": {},
        "is_manual": False,
        "mention_count": 1,
        "states": [],
        "voice_profile": None,
        "role": None,
        "personality_tags": [],
        "motivations": [],
        "fears": [],
        "archetype": None,
        "arc_summary": None,
        "goal": None,
        "lie_they_believe": None,
        "backstory_wound": None,
        "arc_type": None,
        "relationships_as_a": [],
        "relationships_as_b": [],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_is_protected_character_marks_manual_characters_as_untouchable():
    character = _character(is_manual=True)

    assert repair_character_bible_book._is_protected_character(character) is True


def test_is_protected_character_marks_manual_description_edits_as_untouchable():
    character = _character(
        trait_state={
            "manual_description": {
                "value": "User wrote a custom profile here.",
                "confidence": 1.0,
                "type": "abstract",
            }
        }
    )

    assert repair_character_bible_book._is_protected_character(character) is True


def test_auto_mergeable_skips_pairs_that_touch_protected_characters():
    suggestion = SimpleNamespace(
        status="pending",
        confidence=96,
        reasons=["Exact name match"],
    )
    primary = _character(is_manual=True)
    secondary = _character()

    assert repair_character_bible_book._auto_mergeable(suggestion, primary=primary, secondary=secondary) is False


def test_auto_mergeable_keeps_unprotected_high_confidence_duplicates():
    suggestion = SimpleNamespace(
        status="pending",
        confidence=96,
        reasons=["Exact name match"],
    )
    primary = _character(name="Aikawa", mention_count=1)
    secondary = _character(name="Aikawa", mention_count=1)

    assert repair_character_bible_book._auto_mergeable(suggestion, primary=primary, secondary=secondary) is True


def test_is_protected_character_respects_curated_metadata_flags():
    character = _character(analysis_metadata={"user_curated": True})

    assert repair_character_bible_book._is_protected_character(character) is True


def test_parse_args_keeps_dry_run_default(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["repair_character_bible_book.py", "--book-id", "00000000-0000-0000-0000-000000000001"],
    )

    args = repair_character_bible_book._parse_args()

    assert args.apply is False
    assert args.allow_merge_safe_pairs is False
    assert args.allow_demote_obvious_noise is False


@pytest.mark.asyncio
async def test_repair_session_reuses_injected_db():
    db = object()

    async with repair_character_bible_book._repair_session(db) as session:
        assert session is db
