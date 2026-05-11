import pytest
from fastapi import HTTPException

from app.schemas.books import CollaborationScope
from app.utils.book_utils import (
    collaboration_allows_chapter,
    normalize_collaboration_email,
    normalize_collaboration_role,
    normalize_collaboration_scope,
)


class _Collaborator:
    def __init__(self, scope):
        self.scope = scope


def test_normalize_collaboration_scope_keeps_story_resources():
    scope = normalize_collaboration_scope(
        CollaborationScope(
            chapter_start=1,
            chapter_end=10,
            character_bible=True,
            continuity_report=True,
            reader_confusion_report=False,
        )
    )

    assert scope == {
        "chapter_start": 1,
        "chapter_end": 10,
        "character_bible": True,
        "continuity_report": True,
        "reader_confusion_report": False,
    }


def test_normalize_collaboration_scope_rejects_inverted_chapter_range():
    with pytest.raises(HTTPException) as exc:
        normalize_collaboration_scope({"chapter_start": 10, "chapter_end": 1})

    assert exc.value.status_code == 400


def test_collaboration_allows_chapters_inside_scope_only():
    collaborator = _Collaborator({"chapter_start": 2, "chapter_end": 4})

    assert collaboration_allows_chapter(collaborator, 2) is True
    assert collaboration_allows_chapter(collaborator, 4) is True
    assert collaboration_allows_chapter(collaborator, 1) is False
    assert collaboration_allows_chapter(collaborator, 5) is False


def test_normalizers_clean_email_and_reject_unknown_role():
    assert normalize_collaboration_email(" Editor@Example.COM ") == "editor@example.com"
    assert normalize_collaboration_role("beta_reader") == "beta_reader"

    with pytest.raises(HTTPException):
        normalize_collaboration_role("owner")
