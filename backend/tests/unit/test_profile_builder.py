import uuid
from types import SimpleNamespace

from app.engine.character.profile_builder import (
    build_character_profile,
    build_description,
    merge_trait_states,
    update_profile,
)
from app.utils.characters.governance import is_author_curated_character


def test_update_profile_keeps_cited_claims_and_incoming_mention_evidence():
    book_id = uuid.uuid4()
    initial = {
        "name": "Mara Vale",
        "goal": "find the gate",
        "fears": [],
        "traits": {},
        "evidence": {
            "mention_count": 2,
            "profile_claims": {
                "goal": {"quote": "Mara sought the gate.", "source_batch_key": "book:1:1"}
            },
        },
    }
    existing = SimpleNamespace(**build_character_profile(initial, book_id, 1))

    updated = update_profile(
        existing,
        {
            "name": "Mara Vale",
            "first_chapter": 2,
            "goal": "find the gate",
            "fears": ["the dark"],
            "traits": {},
            "evidence": {
                "mention_count": 3,
                "strong_mention_count": 2,
                "profile_claims": {
                    "fears": {
                        "the dark": {
                            "quote": "Mara feared the dark.",
                            "source_batch_key": "book:2:1",
                        }
                    }
                },
            },
        },
    )

    claims = updated["analysis_metadata"]["profile_claims"]
    assert {(claim["field"], claim["chapter_number"]) for claim in claims} == {
        ("goal", 1),
        ("fears", 2),
    }
    assert updated["analysis_metadata"]["evidence_count"] == 5
    assert updated["analysis_metadata"]["strong_mention_count"] == 2
    assert updated["analysis_metadata"]["grounding_coverage"] == 0.4


def test_profile_quality_uses_accumulated_chapter_evidence_instead_of_latest_only():
    initial = build_character_profile(
        {
            "name": "Mara Vale",
            "traits": {},
            "evidence": {"mention_count": 1, "strong_mention_count": 1},
        },
        uuid.uuid4(),
        1,
    )
    assert set(initial["analysis_metadata"]["quality_flags"]) == {
        "generic_summary",
        "light_grounding",
        "no_dialogue_or_action",
    }

    second = update_profile(
        SimpleNamespace(**initial),
        {
            "name": "Mara Vale",
            "first_chapter": 2,
            "arc_summary": "Mara learns to trust her sister.",
            "traits": {},
            "evidence": {
                "mention_count": 2,
                "strong_mention_count": 1,
                "has_dialogue_or_action": True,
            },
        },
    )
    third = update_profile(
        SimpleNamespace(**{**initial, **second}),
        {
            "name": "Mara Vale",
            "first_chapter": 3,
            "traits": {},
            "evidence": {"mention_count": 1, "strong_mention_count": 0},
        },
    )

    assert third["arc_summary"] == "Mara learns to trust her sister."
    assert third["analysis_metadata"]["evidence_count"] == 4
    assert third["analysis_metadata"]["strong_mention_count"] == 2
    assert third["analysis_metadata"]["grounding_coverage"] == 0.5
    assert third["analysis_metadata"]["quality_flags"] == []
    assert third["analysis_metadata"]["needs_review"] is False
    assert third["analysis_metadata"]["summary_quality"] == "grounded"


def test_profile_grounding_is_unknown_when_legacy_prior_strong_count_is_missing():
    initial = build_character_profile(
        {"name": "Mara Vale", "traits": {}, "evidence": {"mention_count": 2}},
        uuid.uuid4(),
        1,
    )
    initial["analysis_metadata"].pop("strong_mention_count")

    updated = update_profile(
        SimpleNamespace(**initial),
        {
            "name": "Mara Vale",
            "first_chapter": 2,
            "traits": {},
            "evidence": {"mention_count": 1, "strong_mention_count": 1},
        },
    )

    assert updated["analysis_metadata"]["evidence_count"] == 3
    assert updated["analysis_metadata"]["strong_mention_count"] is None
    assert updated["analysis_metadata"]["grounding_coverage"] is None


def test_profile_strong_mentions_cannot_exceed_verified_mentions():
    profile = build_character_profile(
        {
            "name": "Mara Vale",
            "evidence": {"mention_count": 1, "strong_mention_count": 8},
        },
        uuid.uuid4(),
        1,
    )

    assert profile["analysis_metadata"]["evidence_count"] == 1
    assert profile["analysis_metadata"]["strong_mention_count"] == 1
    assert profile["analysis_metadata"]["grounding_coverage"] == 1.0


def test_profile_mention_count_accumulates_verified_source_occurrences_across_chapters():
    initial = build_character_profile(
        {
            "name": "Mara Vale",
            "cluster_size": 3,
            "evidence": {
                "source_mention_count_verified": True,
                "mention_count": 2,
                "cluster_size": 3,
            },
        },
        uuid.uuid4(),
        1,
    )
    assert initial["mention_count"] == 2

    existing = SimpleNamespace(**initial)
    updated = update_profile(
        existing,
        {
            "name": "Mara Vale",
            "first_chapter": 2,
            "cluster_size": 4,
            "evidence": {
                "source_mention_count_verified": True,
                "mention_count": 3,
                "cluster_size": 4,
            },
        },
    )
    assert updated["mention_count"] == 5


def test_explicit_first_person_self_identification_keeps_its_source_across_chapters():
    book_id = uuid.uuid4()
    initial = build_character_profile(
        {
            "name": "Arun Vale",
            "traits": {},
            "evidence": {
                "mention_count": 1,
                "strong_mention_count": 1,
                "narrator_self_identification": "I was Arun Vale",
            },
        },
        book_id,
        1,
    )
    existing = SimpleNamespace(**initial)

    updated = update_profile(
        existing,
        {"name": "Arun Vale", "first_chapter": 2, "traits": {}, "evidence": {"mention_count": 2}},
    )

    assert updated["analysis_metadata"]["first_person_self_identification"] == {
        "chapter_number": 1,
        "excerpt": "I was Arun Vale",
    }


def test_tentative_narrator_address_keeps_its_source_without_becoming_explicit():
    initial = build_character_profile(
        {
            "name": "Arun Vale",
            "traits": {},
            "evidence": {
                "mention_count": 1,
                "narrator_addressed_as": "you here, Arun Vale",
            },
        },
        uuid.uuid4(),
        1,
    )

    updated = update_profile(
        SimpleNamespace(**initial),
        {"name": "Arun Vale", "first_chapter": 2, "traits": {}, "evidence": {"mention_count": 2}},
    )

    assert updated["analysis_metadata"]["first_person_addressed_as"] == {
        "chapter_number": 1,
        "excerpt": "you here, Arun Vale",
        "attribution_confidence": "contextual",
    }
    assert "first_person_self_identification" not in updated["analysis_metadata"]


def test_update_profile_preserves_author_curated_fields_during_reprocess():
    existing = SimpleNamespace(
        **build_character_profile(
            {
                "name": "Mara Vale",
                "aliases": ["Captain Vale"],
                "goal": "protect her sister",
                "traits": {"hair": {"value": "black", "confidence": 0.9}},
            },
            uuid.uuid4(),
            1,
        )
    )
    existing.is_manual = False
    existing.analysis_metadata = {
        **existing.analysis_metadata,
        "user_curated": True,
        "review_note": "Keep this interpretation",
    }

    updated = update_profile(
        existing,
        {
            "name": "Mara Vale",
            "first_chapter": 2,
            "aliases": ["The Captain"],
            "goal": "seek a crown and forget her family",
            "traits": {"hair": {"value": "red", "confidence": 0.99}},
            "evidence": {"mention_count": 3},
        },
    )

    assert is_author_curated_character(existing) is True
    assert updated["aliases"] == ["Captain Vale"]
    assert updated["goal"] == "protect her sister"
    assert updated["trait_state"] == existing.trait_state
    assert updated["analysis_metadata"] == existing.analysis_metadata
    assert updated["mention_count"] > existing.mention_count


def test_subjective_trait_capped():
    traits = {"face": {"value": "plain", "confidence": 0.8, "type": "subjective"}}
    result = merge_trait_states({}, traits)
    assert result["face"]["confidence"] <= 0.50


def test_merge_boosts_matching_traits():
    existing = {"hair": {"value": "black", "confidence": 0.6, "type": "objective"}}
    new = {"hair": {"value": "black", "confidence": 0.65, "type": "objective"}}
    result = merge_trait_states(existing, new)
    assert result["hair"]["confidence"] > 0.6


def test_merge_replaces_on_higher_confidence():
    existing = {"hair": {"value": "brown", "confidence": 0.4, "type": "objective"}}
    new = {"hair": {"value": "black", "confidence": 0.9, "type": "objective"}}
    result = merge_trait_states(existing, new)
    assert result["hair"]["value"] == "black"


def test_build_description_uses_archetype_when_sparse():
    desc = build_description({}, "japanese high school boy")
    assert "japanese" in desc.lower() or "school" in desc.lower()


def test_build_description_omits_placeholder_when_no_traits_or_archetype():
    assert build_description({}, None) == ""


def test_build_description_uses_traits():
    trait_state = {
        "hair": {"value": "black", "confidence": 0.9, "type": "objective"},
        "eyes": {"value": "tired", "confidence": 0.8, "type": "objective"},
    }
    desc = build_description(trait_state, None)
    assert "black" in desc
    assert "tired" in desc
