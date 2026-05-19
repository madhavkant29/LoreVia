from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.utils.tag_utils import (
    ENTITY_TYPE_NOTE,
    can_manage_tag_target,
    canonical_entity_type,
    normalize_custom_tags,
)


def test_normalize_custom_tags_dedupes_and_cleans():
    tags = normalize_custom_tags([" Needs Rewrite ", "foreshadowing", "needs rewrite", "beta_feedback"])

    assert tags == ["needs rewrite", "foreshadowing", "beta feedback"]


def test_normalize_custom_tags_rejects_oversized_values():
    with pytest.raises(HTTPException) as exc:
        normalize_custom_tags(["x" * 65])

    assert exc.value.status_code == 400


def test_canonical_entity_type_maps_comment_to_note():
    assert canonical_entity_type("comment") == ENTITY_TYPE_NOTE


def test_collaborator_can_only_tag_their_own_comment_notes():
    collaborator = SimpleNamespace(
        permissions={"can_comment": True},
        role="commenter",
        scope={"chapter_start": 1, "chapter_end": 3},
    )
    user_id = uuid.uuid4()

    assert can_manage_tag_target(
        collaborator=collaborator,
        public_entity_type="comment",
        target_chapter_number=2,
        target_owner_user_id=user_id,
        current_user_id=user_id,
    )
    assert not can_manage_tag_target(
        collaborator=collaborator,
        public_entity_type="comment",
        target_chapter_number=2,
        target_owner_user_id=uuid.uuid4(),
        current_user_id=user_id,
    )
