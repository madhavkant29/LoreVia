import uuid

from app.models.character import Character
from app.services.extraction_chapter_content_service import _prepare_chapter_rich_content
from app.services.extraction_character_decision_service import (
    _can_auto_save_character,
    _character_save_decision,
    _should_update_existing_character,
)
from app.services.extraction_character_persistence_service import (
    _blocked_character_ids,
    _merge_alias_in_memory,
)
from app.services.extraction_relationship_service import (
    _relationship_resolution_candidates,
)


def test_can_auto_save_character_requires_strong_single_mention_evidence():
    entity = {
        "name": "Aikawa Junya",
        "entity_type": "person",
        "confidence": 0.85,
        "mention_count": 1,
        "evidence": {
            "mention_count": 1,
            "has_dialogue_or_action": False,
            "has_physical_description": False,
            "appears_multiple_times": False,
        },
    }

    assert _can_auto_save_character(entity) is False


def test_prepare_chapter_rich_content_extracts_editor_images_and_retains_stored_media():
    prepared = _prepare_chapter_rich_content(
        {
            "number": 1,
            "text": "Intro Outro",
            "html": (
                "<p>Intro</p>"
                '<p><img src="/api/v1/reader/media/1" alt="[[IMAGE:kept]]"></p>'
                '<p><img src="data:image/png;base64,QUJD" alt="New map"></p>'
                "<p>Outro</p>"
            ),
            "images": [
                {
                    "marker": "[[IMAGE:kept]]",
                    "storage_key": "chapter-media/book/kept.png",
                    "content_type": "image/png",
                    "caption": "Kept image",
                },
                {
                    "marker": "[[IMAGE:removed]]",
                    "storage_key": "chapter-media/book/removed.png",
                    "content_type": "image/png",
                },
            ],
        }
    )

    assert prepared["_lorevia_persist_rich_content"] is True
    assert "data:image/png" not in prepared["html"]
    assert "[[IMAGE:kept]]" in prepared["text"]
    assert "Outro" in prepared["text"]
    assert [image["marker"] for image in prepared["images"][:1]] == ["[[IMAGE:kept]]"]
    assert prepared["images"][0]["storage_key"] == "chapter-media/book/kept.png"
    assert prepared["images"][1]["bytes"] == b"ABC"
    assert prepared["images"][1]["content_type"] == "image/png"


def test_can_auto_save_character_allows_multi_mention_person():
    entity = {
        "name": "Aikawa Junya",
        "entity_type": "person",
        "confidence": 0.82,
        "mention_count": 2,
        "evidence": {
            "mention_count": 2,
            "chapter_numbers": [1, 2],
            "has_dialogue_or_action": True,
            "has_physical_description": False,
            "appears_multiple_times": True,
            "verifier": {
                "local": {
                    "person_ner_mentions": 1,
                    "mid_sentence_mentions": 2,
                },
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": ["local_person_context"],
                },
            },
        },
    }

    assert _can_auto_save_character(entity) is True


def test_can_auto_save_character_allows_grounded_full_name_without_explicit_verifier_payload():
    entity = {
        "name": "Gregor Samsa",
        "entity_type": "person",
        "confidence": 0.95,
        "evidence": {
            "mention_count": 2,
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "has_physical_description": True,
            "appears_multiple_times": True,
        },
    }

    assert _can_auto_save_character(entity) is True


def test_can_auto_save_character_holds_title_surname_for_review():
    entity = {
        "name": "Mr. Samsa",
        "entity_type": "person",
        "confidence": 0.96,
        "evidence": {
            "mention_count": 6,
            "strong_mention_count": 4,
            "has_dialogue_or_action": True,
            "has_physical_description": True,
            "appears_multiple_times": True,
        },
    }

    assert _can_auto_save_character(entity) is False


def test_can_auto_save_character_blocks_single_token_even_with_profile_signal_when_cross_chapter_support_is_missing():
    entity = {
        "name": "Gregor",
        "entity_type": "person",
        "confidence": 0.94,
        "mention_count": 1,
        "arc_summary": "Gregor wakes to a life-altering change and immediately spirals into anxious self-surveillance.",
        "personality_tags": ["anxious"],
        "motivations": ["protect his family"],
        "evidence": {
            "mention_count": 1,
            "has_dialogue_or_action": False,
            "has_physical_description": False,
            "appears_multiple_times": False,
            "verifier": {
                "local": {
                    "person_ner_mentions": 1,
                    "mid_sentence_mentions": 1,
                },
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": ["llm_confirmed_person"],
                },
            },
        },
    }

    assert _can_auto_save_character(entity) is False


def test_can_auto_save_character_sends_low_confidence_new_character_to_review():
    entity = {
        "name": "Anna",
        "entity_type": "person",
        "confidence": 0.32,
        "arc_summary": "A background character.",
        "evidence": {
            "mention_count": 1,
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "has_physical_description": False,
            "appears_multiple_times": False,
        },
    }

    assert _can_auto_save_character(entity) is False


def test_can_auto_save_character_blocks_role_only_reference_without_named_cluster_support():
    entity = {
        "name": "chief clerk",
        "entity_type": "person",
        "confidence": 0.96,
        "evidence": {
            "mention_count": 2,
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "appears_multiple_times": True,
            "cluster_names": ["chief clerk"],
        },
    }

    assert _can_auto_save_character(entity) is False


def test_character_save_decision_rejects_review_band_from_mention_verifier():
    entity = {
        "name": "Mother",
        "entity_type": "person",
        "confidence": 0.88,
        "evidence": {
            "mention_count": 1,
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "appears_multiple_times": False,
            "verifier": {
                "final": {
                    "confidence_band": "review",
                    "is_person_like": False,
                    "reasons": ["ambiguous_single_token_mention"],
                }
            },
        },
    }

    decision = _character_save_decision(entity)

    assert decision.allowed is False
    assert "mention_verifier_review" in decision.reasons


def test_can_auto_save_character_blocks_first_pass_single_token_even_when_verifier_accepts_it():
    entity = {
        "name": "Grete",
        "entity_type": "person",
        "confidence": 0.94,
        "evidence": {
            "mention_count": 3,
            "chapter_numbers": [1, 2],
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "has_physical_description": False,
            "appears_multiple_times": True,
            "verifier": {
                "local": {
                    "person_ner_mentions": 1,
                    "mid_sentence_mentions": 2,
                },
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": ["llm_confirmed_person"],
                },
            },
        },
    }

    assert _can_auto_save_character(entity) is False
    assert _should_update_existing_character(entity) is True


def test_can_auto_save_character_allows_strong_deterministic_fallback_single_token_with_full_name_alias():
    entity = {
        "name": "Gregor",
        "aliases": ["Gregor Samsa"],
        "entity_type": "person",
        "confidence": 0.94,
        "evidence": {
            "mention_count": 3,
            "strong_mention_count": 2,
            "has_dialogue_or_action": True,
            "has_physical_description": False,
            "appears_multiple_times": True,
            "deterministic_fallback": True,
            "cluster_names": ["Gregor", "Gregor Samsa"],
            "verifier": {
                "local": {
                    "person_ner_mentions": 0,
                    "mid_sentence_mentions": 1,
                },
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": [],
                },
            },
        },
    }

    assert _can_auto_save_character(entity) is True


def test_should_update_existing_character_allows_borderline_but_supported_updates():
    entity = {
        "name": "Houko-chan",
        "confidence": 0.60,
        "evidence": {
            "has_dialogue_or_action": True,
            "has_physical_description": False,
            "appears_multiple_times": False,
        },
    }

    assert _should_update_existing_character(entity) is True


def test_should_update_existing_character_allows_profile_only_enrichment():
    entity = {
        "name": "Gregor",
        "confidence": 0.57,
        "arc_summary": "His sense of duty keeps colliding with his new body.",
        "evidence": {
            "has_dialogue_or_action": False,
            "has_physical_description": False,
            "appears_multiple_times": False,
        },
    }

    assert _should_update_existing_character(entity) is True


def test_blocked_character_ids_respects_anti_merge_names():
    blocked = Character(
        id=uuid.uuid4(), book_id=uuid.uuid4(), name="Saitou Masami", first_chapter=1
    )
    allowed = Character(
        id=uuid.uuid4(), book_id=blocked.book_id, name="Saitou Kengo", first_chapter=1
    )

    entity = {
        "name": "Saitou Kengo",
        "anti_merge_names": ["Saitou Masami"],
    }

    blocked_ids = _blocked_character_ids([blocked, allowed], entity)

    assert blocked.id in blocked_ids
    assert allowed.id not in blocked_ids


def test_merge_alias_in_memory_rejects_unrelated_single_token_alias():
    gregor = Character(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        name="Gregor Samsa",
        aliases=["Gregor"],
        first_chapter=1,
    )

    _merge_alias_in_memory(gregor, "Grete")

    assert gregor.aliases == ["Gregor"]


def test_relationship_resolution_candidates_ignores_non_visible_character():
    book_id = uuid.uuid4()
    hidden = Character(
        id=uuid.uuid4(),
        book_id=book_id,
        name="Mr. Samsa",
        aliases=[],
        first_chapter=1,
        visibility_state="noise",
        approval_state="rejected",
    )
    visible = Character(
        id=uuid.uuid4(),
        book_id=book_id,
        name="Gregor Samsa",
        aliases=["Gregor"],
        first_chapter=1,
        visibility_state="visible",
        approval_state="approved",
    )
    grete = Character(
        id=uuid.uuid4(),
        book_id=book_id,
        name="Grete",
        aliases=[],
        first_chapter=1,
        visibility_state="visible",
        approval_state="approved",
    )

    assert _relationship_resolution_candidates([hidden, visible, grete], "Mr. Samsa") == []
    assert _relationship_resolution_candidates([hidden, visible, grete], "Gregor") == [visible.id]
    assert _relationship_resolution_candidates(
        [hidden, visible, grete],
        "Gregor's sister",
        context_text="Grete, Gregor's sister, pleaded with him to eat something.",
    ) == [grete.id]
    assert (
        _relationship_resolution_candidates(
            [hidden, visible, grete],
            "Gregor's mother",
            context_text="Gregor's mother cares for him but struggles with the changes in their relationship.",
        )
        == []
    )
