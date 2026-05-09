import uuid

from app.models.character import Character
from app.workers.consumers.extraction_consumer import (
    _blocked_character_ids,
    _can_auto_save_character,
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
