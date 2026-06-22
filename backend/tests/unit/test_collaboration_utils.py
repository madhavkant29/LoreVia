import pytest
from fastapi import HTTPException

from app.schemas.books import CollaborationScope
from app.utils.books.collaboration import (
    build_book_access_context,
    normalize_collaboration_email,
    normalize_collaboration_permissions,
    normalize_collaboration_role,
    normalize_collaboration_scope,
)
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_can_comment,
    collaboration_can_copy_manuscript,
    collaboration_can_edit,
    collaboration_can_export,
    collaboration_has_resource,
)


class _Collaborator:
    def __init__(self, scope, role="viewer", permissions=None, **attrs):
        self.scope = scope
        self.role = role
        self.permissions = permissions
        for key, value in attrs.items():
            setattr(self, key, value)


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


def test_collaboration_permissions_follow_role_defaults():
    permissions = normalize_collaboration_permissions(
        None,
        role="co_writer",
        scope={"chapter_start": None, "chapter_end": None},
    )

    assert permissions["can_edit_manuscript"] is True
    assert permissions["can_export"] is True
    assert permissions["can_comment"] is True

    beta_reader_permissions = normalize_collaboration_permissions(
        None,
        role="beta_reader",
        scope={"chapter_start": None, "chapter_end": None},
    )
    assert beta_reader_permissions["can_view_story_bible"] is False
    assert beta_reader_permissions["can_run_ai_scans"] is False
    assert beta_reader_permissions["can_comment"] is True


def test_collaboration_permissions_honor_selected_chapter_override():
    collaborator = _Collaborator(
        {"chapter_start": 2, "chapter_end": 4},
        role="editor",
        permissions={"can_view_selected_chapters_only": False},
    )

    assert collaboration_allows_chapter(collaborator, 1) is True
    assert collaboration_allows_chapter(collaborator, 5) is True


def test_collaboration_permission_helpers_gate_edit_comment_export_and_resources():
    collaborator = _Collaborator(
        {
            "chapter_start": 1,
            "chapter_end": 3,
            "character_bible": True,
            "continuity_report": True,
            "reader_confusion_report": False,
        },
        role="commenter",
        permissions={
            "can_comment": True,
            "can_view_story_bible": True,
            "can_run_ai_scans": False,
            "can_export": False,
        },
    )

    assert collaboration_can_comment(collaborator) is True
    assert collaboration_can_edit(collaborator) is False
    assert collaboration_can_export(collaborator) is False
    assert collaboration_has_resource(collaborator, "character_bible") is True
    assert collaboration_has_resource(collaborator, "continuity_report") is False


def test_collaboration_helpers_prefer_normalized_columns_when_present():
    collaborator = _Collaborator(
        {
            "chapter_start": 1,
            "chapter_end": 10,
            "character_bible": False,
            "continuity_report": False,
            "reader_confusion_report": False,
        },
        role="beta_reader",
        permissions={"can_comment": False, "can_view_selected_chapters_only": False},
        scope_chapter_start=3,
        scope_chapter_end=4,
        scope_character_bible=True,
        scope_continuity_report=True,
        scope_reader_confusion_report=False,
        permission_can_edit_manuscript=False,
        permission_can_view_story_bible=True,
        permission_can_run_ai_scans=True,
        permission_can_export=False,
        permission_can_comment=True,
        permission_can_view_selected_chapters_only=True,
    )

    assert collaboration_allows_chapter(collaborator, 2) is False
    assert collaboration_allows_chapter(collaborator, 3) is True
    assert collaboration_can_comment(collaborator) is True
    assert collaboration_has_resource(collaborator, "character_bible") is True
    assert collaboration_has_resource(collaborator, "continuity_report") is True


def test_collaboration_copy_permission_allows_public_or_editable_shares():
    private_book = type("BookStub", (), {"is_public": False})()
    public_book = type("BookStub", (), {"is_public": True})()

    read_only_collaborator = _Collaborator(
        {"chapter_start": 1, "chapter_end": 3},
        role="beta_reader",
        permissions={"can_edit_manuscript": False},
    )
    editor_collaborator = _Collaborator(
        {"chapter_start": None, "chapter_end": None},
        role="editor",
        permissions={"can_edit_manuscript": True},
    )

    assert collaboration_can_copy_manuscript(private_book, None) is True
    assert collaboration_can_copy_manuscript(private_book, read_only_collaborator) is False
    assert collaboration_can_copy_manuscript(public_book, read_only_collaborator) is True
    assert collaboration_can_copy_manuscript(private_book, editor_collaborator) is True


def test_normalizers_clean_email_and_reject_unknown_role():
    assert normalize_collaboration_email(" Editor@Example.COM ") == "editor@example.com"
    assert normalize_collaboration_role("beta_reader") == "beta_reader"
    assert normalize_collaboration_role("co_writer") == "co_writer"

    with pytest.raises(HTTPException):
        normalize_collaboration_role("owner")


def test_access_context_forces_reader_shell_for_reader_roles():
    owner_book = type("BookStub", (), {"mode": "author", "user_id": "owner"})()
    collaborator = _Collaborator(
        {
            "chapter_start": 2,
            "chapter_end": 4,
            "character_bible": False,
            "continuity_report": False,
            "reader_confusion_report": False,
        },
        role="beta_reader",
        permissions={"can_comment": True, "can_edit_manuscript": False},
    )

    owner_access = build_book_access_context(owner_book, user_id="owner", collaborator=None)
    collaborator_access = build_book_access_context(
        owner_book, user_id="reader", collaborator=collaborator
    )

    assert owner_access.workspace_shell == "author"
    assert owner_access.access_class == "owner"
    assert collaborator_access.workspace_shell == "reader"
    assert collaborator_access.access_class == "reader_collaborator"
    assert collaborator_access.can_switch_workspace_mode is False
