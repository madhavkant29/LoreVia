"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from app.models.book import (
    Book,
    BookCollaborator,
)
from app.schemas.books import (
    BookCollaboratorOut,
    CollaborationPermissions,
    CollaborationScope,
)

if TYPE_CHECKING:
    pass


COLLABORATION_ROLES = {
    "viewer",
    "commenter",
    "editor",
    "beta_reader",
    "developmental_editor",
    "coauthor",
    "reader_only",
    "co_writer",
}
COLLABORATION_DEFAULT_SCOPE = {
    "chapter_start": None,
    "chapter_end": None,
    "character_bible": False,
    "continuity_report": False,
    "reader_confusion_report": False,
}
COLLABORATION_DEFAULT_PERMISSIONS = {
    "can_edit_manuscript": False,
    "can_view_story_bible": False,
    "can_run_ai_scans": False,
    "can_export": False,
    "can_comment": False,
    "can_view_selected_chapters_only": True,
}
COLLABORATION_ROLE_DEFAULT_PERMISSIONS = {
    "viewer": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_view_selected_chapters_only": True,
    },
    "reader_only": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_view_selected_chapters_only": True,
    },
    "commenter": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_comment": True,
        "can_view_selected_chapters_only": True,
    },
    "beta_reader": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_comment": True,
        "can_view_selected_chapters_only": True,
    },
    "editor": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
    "developmental_editor": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
    "coauthor": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
    "co_writer": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
}
COLLABORATION_READER_SHELL_ROLES = {"viewer", "reader_only", "commenter", "beta_reader"}
COLLABORATION_AUTHOR_SHELL_ROLES = {"editor", "developmental_editor", "coauthor", "co_writer"}
READER_VISIBLE_FEATURES = (
    "overview",
    "read",
    "chapters",
    "recaps",
    "search",
    "timeline",
    "feedback",
)


@dataclass(slots=True)
class BookAccessContext:
    access_class: str
    workspace_shell: str
    can_switch_workspace_mode: bool
    can_edit_manuscript: bool
    can_comment: bool
    can_export: bool
    can_view_story_bible: bool
    can_run_ai_scans: bool
    visible_reader_features: tuple[str, ...]
    collaboration_role: str | None
    collaboration_scope: dict | None
    collaboration_permissions: dict | None


def normalize_collaboration_email(email: str) -> str:
    cleaned = str(email or "").strip().lower()
    if not cleaned or "@" not in cleaned or len(cleaned) > 320:
        raise HTTPException(400, "Valid collaborator email is required")
    return cleaned


def normalize_collaboration_role(role: str) -> str:
    cleaned = str(role or "").strip().lower()
    if cleaned not in COLLABORATION_ROLES:
        raise HTTPException(400, "Invalid collaborator role")
    return cleaned


def collaboration_role_workspace_shell(role: str) -> str:
    normalized_role = normalize_collaboration_role(role)
    if normalized_role in COLLABORATION_READER_SHELL_ROLES:
        return "reader"
    return "author"


def build_book_access_context(
    book: Book,
    *,
    user_id: uuid.UUID,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    if collaborator is None:
        workspace_shell = (
            "author" if (getattr(book, "mode", None) or "reader") == "author" else "reader"
        )
        return BookAccessContext(
            access_class="owner",
            workspace_shell=workspace_shell,
            can_switch_workspace_mode=True,
            can_edit_manuscript=True,
            can_comment=True,
            can_export=True,
            can_view_story_bible=True,
            can_run_ai_scans=True,
            visible_reader_features=READER_VISIBLE_FEATURES,
            collaboration_role=None,
            collaboration_scope=None,
            collaboration_permissions=None,
        )

    scope = collaboration_scope_payload(collaborator)
    permissions = collaboration_permissions_payload(
        collaborator, role=collaborator.role, scope=scope
    )
    workspace_shell = collaboration_role_workspace_shell(collaborator.role)
    return BookAccessContext(
        access_class="reader_collaborator"
        if workspace_shell == "reader"
        else "author_collaborator",
        workspace_shell=workspace_shell,
        can_switch_workspace_mode=False,
        can_edit_manuscript=permissions["can_edit_manuscript"],
        can_comment=permissions["can_comment"],
        can_export=permissions["can_export"],
        can_view_story_bible=permissions["can_view_story_bible"],
        can_run_ai_scans=permissions["can_run_ai_scans"],
        visible_reader_features=READER_VISIBLE_FEATURES,
        collaboration_role=collaborator.role,
        collaboration_scope=scope,
        collaboration_permissions=permissions,
    )


def _collaboration_permissions_for_role(collaborator: BookCollaborator) -> dict:
    scope = collaboration_scope_payload(collaborator)
    return collaboration_permissions_payload(collaborator, role=collaborator.role, scope=scope)


def collaboration_scope_payload(raw_scope: Any) -> dict:
    source = raw_scope
    if hasattr(raw_scope, "scope") and not isinstance(raw_scope, (dict, CollaborationScope)):
        source = getattr(raw_scope, "scope")
    scope = normalize_collaboration_scope(source)
    if hasattr(raw_scope, "scope_chapter_start"):
        scope["chapter_start"] = getattr(raw_scope, "scope_chapter_start")
    if hasattr(raw_scope, "scope_chapter_end"):
        scope["chapter_end"] = getattr(raw_scope, "scope_chapter_end")
    if hasattr(raw_scope, "scope_character_bible"):
        scope["character_bible"] = bool(getattr(raw_scope, "scope_character_bible"))
    if hasattr(raw_scope, "scope_continuity_report"):
        scope["continuity_report"] = bool(getattr(raw_scope, "scope_continuity_report"))
    if hasattr(raw_scope, "scope_reader_confusion_report"):
        scope["reader_confusion_report"] = bool(getattr(raw_scope, "scope_reader_confusion_report"))
    return normalize_collaboration_scope(scope)


def normalize_collaboration_scope(raw_scope: dict | CollaborationScope | None) -> dict:
    source = (
        raw_scope.model_dump()
        if isinstance(raw_scope, CollaborationScope)
        else dict(raw_scope or {})
    )
    scope = dict(COLLABORATION_DEFAULT_SCOPE)
    scope.update({key: source.get(key) for key in scope if key in source})

    chapter_start = scope.get("chapter_start")
    chapter_end = scope.get("chapter_end")
    if chapter_start is not None:
        chapter_start = int(chapter_start)
        if chapter_start < 1:
            raise HTTPException(400, "chapter_start must be at least 1")
    if chapter_end is not None:
        chapter_end = int(chapter_end)
        if chapter_end < 1:
            raise HTTPException(400, "chapter_end must be at least 1")
    if chapter_start is not None and chapter_end is not None and chapter_end < chapter_start:
        raise HTTPException(400, "chapter_end cannot be earlier than chapter_start")

    scope["chapter_start"] = chapter_start
    scope["chapter_end"] = chapter_end
    scope["character_bible"] = bool(scope.get("character_bible"))
    scope["continuity_report"] = bool(scope.get("continuity_report"))
    scope["reader_confusion_report"] = bool(scope.get("reader_confusion_report"))
    return scope


def collaboration_scope_model(scope: dict | None) -> CollaborationScope:
    return CollaborationScope(**collaboration_scope_payload(scope))


def normalize_collaboration_permissions(
    raw_permissions: dict | CollaborationPermissions | None,
    *,
    role: str,
    scope: dict | CollaborationScope | None = None,
) -> dict:
    normalized_role = normalize_collaboration_role(role)
    source = (
        raw_permissions.model_dump()
        if isinstance(raw_permissions, CollaborationPermissions)
        else dict(raw_permissions or {})
    )
    permissions = dict(COLLABORATION_ROLE_DEFAULT_PERMISSIONS[normalized_role])
    permissions.update({key: source.get(key) for key in permissions if key in source})
    normalized_scope = normalize_collaboration_scope(scope)
    if "can_view_selected_chapters_only" not in source and (
        normalized_scope.get("chapter_start") is not None
        or normalized_scope.get("chapter_end") is not None
    ):
        permissions["can_view_selected_chapters_only"] = True
    for key in permissions:
        permissions[key] = bool(permissions.get(key))
    return permissions


def collaboration_permissions_payload(
    raw_permissions: Any,
    *,
    role: str,
    scope: Any = None,
) -> dict:
    source = raw_permissions
    if hasattr(raw_permissions, "permissions") and not isinstance(
        raw_permissions, (dict, CollaborationPermissions)
    ):
        source = getattr(raw_permissions, "permissions")
    normalized_scope = collaboration_scope_payload(scope)
    permissions = normalize_collaboration_permissions(source, role=role, scope=normalized_scope)
    if hasattr(raw_permissions, "permission_can_edit_manuscript"):
        permissions["can_edit_manuscript"] = bool(
            getattr(raw_permissions, "permission_can_edit_manuscript")
        )
    if hasattr(raw_permissions, "permission_can_view_story_bible"):
        permissions["can_view_story_bible"] = bool(
            getattr(raw_permissions, "permission_can_view_story_bible")
        )
    if hasattr(raw_permissions, "permission_can_run_ai_scans"):
        permissions["can_run_ai_scans"] = bool(
            getattr(raw_permissions, "permission_can_run_ai_scans")
        )
    if hasattr(raw_permissions, "permission_can_export"):
        permissions["can_export"] = bool(getattr(raw_permissions, "permission_can_export"))
    if hasattr(raw_permissions, "permission_can_comment"):
        permissions["can_comment"] = bool(getattr(raw_permissions, "permission_can_comment"))
    if hasattr(raw_permissions, "permission_can_view_selected_chapters_only"):
        permissions["can_view_selected_chapters_only"] = bool(
            getattr(raw_permissions, "permission_can_view_selected_chapters_only")
        )
    return normalize_collaboration_permissions(permissions, role=role, scope=normalized_scope)


def collaboration_permissions_model(
    permissions: dict | None,
    *,
    role: str,
    scope: dict | None,
) -> CollaborationPermissions:
    return CollaborationPermissions(
        **collaboration_permissions_payload(permissions, role=role, scope=scope)
    )


def apply_collaboration_scope(collaborator: BookCollaborator, scope: dict) -> None:
    normalized_scope = normalize_collaboration_scope(scope)
    collaborator.scope = normalized_scope
    collaborator.scope_chapter_start = normalized_scope["chapter_start"]
    collaborator.scope_chapter_end = normalized_scope["chapter_end"]
    collaborator.scope_character_bible = normalized_scope["character_bible"]
    collaborator.scope_continuity_report = normalized_scope["continuity_report"]
    collaborator.scope_reader_confusion_report = normalized_scope["reader_confusion_report"]


def apply_collaboration_permissions(
    collaborator: BookCollaborator,
    permissions: dict,
    *,
    role: str,
    scope: dict,
) -> None:
    normalized_permissions = normalize_collaboration_permissions(
        permissions, role=role, scope=scope
    )
    collaborator.permissions = normalized_permissions
    collaborator.permission_can_edit_manuscript = normalized_permissions["can_edit_manuscript"]
    collaborator.permission_can_view_story_bible = normalized_permissions["can_view_story_bible"]
    collaborator.permission_can_run_ai_scans = normalized_permissions["can_run_ai_scans"]
    collaborator.permission_can_export = normalized_permissions["can_export"]
    collaborator.permission_can_comment = normalized_permissions["can_comment"]
    collaborator.permission_can_view_selected_chapters_only = normalized_permissions[
        "can_view_selected_chapters_only"
    ]


def serialize_book_collaborator(collaborator: BookCollaborator) -> BookCollaboratorOut:
    scope = collaboration_scope_payload(collaborator)
    return BookCollaboratorOut(
        id=str(collaborator.id),
        book_id=str(collaborator.book_id),
        email=collaborator.email,
        display_name=collaborator.display_name,
        role=collaborator.role,
        scope=collaboration_scope_model(scope),
        permissions=collaboration_permissions_model(
            collaborator,
            role=collaborator.role,
            scope=scope,
        ),
        invite_status=collaborator.invite_status,
        invited_at=collaborator.invited_at,
        updated_at=collaborator.updated_at,
    )
