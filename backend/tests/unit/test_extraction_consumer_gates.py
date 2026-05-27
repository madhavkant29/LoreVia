import uuid

from app.models.character import Character
from app.workers.consumers.extraction_consumer import (
    _blocked_character_ids,
    _can_auto_save_character,
    _character_save_decision,
    _should_update_existing_character,
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


def test_can_auto_save_character_allows_multi_mention_person():
    entity = {
        "name": "Aikawa Junya",
        "entity_type": "person",
        "confidence": 0.82,
        "mention_count": 2,
        "evidence": {
            "mention_count": 2,
            "has_dialogue_or_action": True,
            "has_physical_description": False,
            "appears_multiple_times": True,
            "verifier": {
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": ["local_person_context"],
                }
            },
        },
    }

    assert _can_auto_save_character(entity) is True


def test_can_auto_save_character_allows_strong_single_mention_with_profile_signal():
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
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": ["single_token_has_grounded_action_context"],
                }
            },
        },
    }

    assert _can_auto_save_character(entity) is True


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


def test_can_auto_save_character_allows_accept_band_from_mention_verifier():
    entity = {
        "name": "Grete",
        "entity_type": "person",
        "confidence": 0.94,
        "evidence": {
            "mention_count": 1,
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "has_physical_description": False,
            "appears_multiple_times": False,
            "verifier": {
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": ["llm_confirmed_person"],
                }
            },
        },
    }

    assert _can_auto_save_character(entity) is True
    assert _should_update_existing_character(entity) is True


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
    blocked = Character(id=uuid.uuid4(), book_id=uuid.uuid4(), name="Saitou Masami", first_chapter=1)
    allowed = Character(id=uuid.uuid4(), book_id=blocked.book_id, name="Saitou Kengo", first_chapter=1)

    entity = {
        "name": "Saitou Kengo",
        "anti_merge_names": ["Saitou Masami"],
    }

    blocked_ids = _blocked_character_ids([blocked, allowed], entity)

    assert blocked.id in blocked_ids
    assert allowed.id not in blocked_ids
