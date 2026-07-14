from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.character import (
    Character,
    CharacterAlias,
    CharacterCandidate,
    CharacterIdentityAction,
    CharacterSuppression,
)
from app.services.character_identity.constraints import add_identity_constraint
from app.services.character_identity.merge import record_identity_action
from app.services.character_identity.normalization import normalize_name
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
)
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.characters.review import set_character_review_state
from app.utils.characters.review_serialization import list_character_review_data
from app.utils.characters.text import clean_string_list


async def get_book_character_review_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    include_quarantined: bool,
    include_places: bool,
    include_rejected: bool,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character review is only available in author mode")
    return await list_character_review_data(
        db,
        book_id=book.id,
        include_quarantined=include_quarantined,
        include_places=include_places,
        include_rejected=include_rejected,
    )


async def get_character_identity_diagnostics_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suppressions = (
        (
            await db.execute(
                select(CharacterSuppression).where(CharacterSuppression.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    actions = (
        (
            await db.execute(
                select(CharacterIdentityAction)
                .where(CharacterIdentityAction.book_id == book.id)
                .order_by(CharacterIdentityAction.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    hidden_candidates = (
        (
            await db.execute(
                select(CharacterCandidate).where(
                    CharacterCandidate.book_id == book.id,
                    CharacterCandidate.status == "suppressed",
                )
            )
        )
        .scalars()
        .all()
    )
    action_counts = Counter(action.action_type for action in actions)
    return {
        "suppressed_count": len(suppressions),
        "auto_merged_count": action_counts.get("auto_merge", 0),
        "auto_alias_count": action_counts.get("auto_alias", 0),
        "blocked_duplicate_count": action_counts.get("auto_block_duplicate", 0),
        "hidden_candidate_count": len(hidden_candidates),
        "suppression_reasons": dict(Counter(item.reason for item in suppressions)),
        "recent_identity_actions": [
            {
                "id": str(action.id),
                "action_type": action.action_type,
                "source_character_id": str(action.source_character_id)
                if action.source_character_id
                else None,
                "target_character_id": str(action.target_character_id)
                if action.target_character_id
                else None,
                "surface_text": action.surface_text,
                "confidence": action.confidence,
                "reason": action.reason,
                "reversible": action.reversible,
                "created_at": action.created_at,
            }
            for action in actions
        ],
    }


async def undo_character_identity_action_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    action_id: uuid.UUID,
) -> dict[str, str | None]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    action = await db.get(CharacterIdentityAction, action_id)
    if not action or action.book_id != book.id:
        raise HTTPException(404, "Identity action not found")
    if not action.reversible:
        raise HTTPException(400, "Identity action cannot be undone")

    reversible_data = dict(action.reversible_data or {})
    restored_character_id: uuid.UUID | None = None
    if action.action_type == "auto_merge":
        restored_character_id = await _undo_auto_merge(
            db,
            book=book,
            action=action,
            reversible_data=reversible_data,
            actor_user_id=current_user.id,
        )
    elif action.action_type == "auto_alias":
        restored_character_id = await _undo_auto_alias(
            db,
            book=book,
            action=action,
            actor_user_id=current_user.id,
        )
    else:
        raise HTTPException(400, "Unsupported undo action type")

    action.reversible = False
    await record_identity_action(
        db,
        book_id=book.id,
        action_type="undo_merge" if action.action_type == "auto_merge" else "manual_override",
        source_character_id=action.source_character_id,
        target_character_id=action.target_character_id,
        surface_text=action.surface_text,
        confidence=1.0,
        reason=f"undo:{action.action_type}",
        reversible=False,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {
        "undone": str(action.id),
        "restored_character_id": str(restored_character_id) if restored_character_id else None,
    }


async def _undo_auto_merge(
    db: AsyncSession,
    *,
    book: Any,
    action: CharacterIdentityAction,
    reversible_data: dict[str, Any],
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
    secondary = (
        await db.get(Character, action.source_character_id) if action.source_character_id else None
    )
    if secondary is None or secondary.book_id != book.id:
        raise HTTPException(404, "Merged character record not found")
    secondary.merged_into_character_id = None
    secondary.normalized_name = None
    secondary.is_auto_suppressed = False
    secondary.suppression_reason = None
    set_character_review_state(
        secondary,
        visibility_state=str(reversible_data.get("secondary_visibility_state") or "quarantined"),
        approval_state=str(
            reversible_data.get("secondary_approval_state") or CHARACTER_APPROVAL_PENDING_REVIEW
        ),
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        reason_codes=["identity_action_undone"],
        action="identity_auto_merge_undone",
        details={
            "identity_action_id": str(action.id),
            "target_character_id": str(action.target_character_id)
            if action.target_character_id
            else None,
        },
        actor_user_id=actor_user_id,
    )
    if action.target_character_id is not None:
        primary = await db.get(Character, action.target_character_id)
        if primary is not None and primary.book_id == book.id:
            await add_identity_constraint(
                db,
                book_id=book.id,
                left_character_id=primary.id,
                right_character_id=secondary.id,
                left_text=primary.name,
                right_text=secondary.name,
                constraint_type="not_same_character",
                reason="identity_action_undo",
                source="manual",
                confidence=1.0,
            )
    return secondary.id


async def _undo_auto_alias(
    db: AsyncSession,
    *,
    book: Any,
    action: CharacterIdentityAction,
    actor_user_id: uuid.UUID,
) -> uuid.UUID | None:
    target = (
        await db.get(Character, action.target_character_id) if action.target_character_id else None
    )
    source = (
        await db.get(Character, action.source_character_id) if action.source_character_id else None
    )
    normalized_alias = normalize_name(action.surface_text)
    if target is not None and target.book_id == book.id and normalized_alias:
        target.aliases = [
            alias
            for alias in clean_string_list(target.aliases or [])
            if normalize_name(alias) != normalized_alias
        ]
        alias_rows = (
            (
                await db.execute(
                    select(CharacterAlias).where(
                        CharacterAlias.book_id == book.id,
                        CharacterAlias.character_id == target.id,
                        CharacterAlias.normalized_alias == normalized_alias,
                    )
                )
            )
            .scalars()
            .all()
        )
        for alias in alias_rows:
            await db.delete(alias)
    if source is None or source.book_id != book.id:
        return None

    source.merged_into_character_id = None
    source.normalized_name = None
    source.is_auto_suppressed = False
    source.suppression_reason = None
    set_character_review_state(
        source,
        visibility_state="quarantined",
        approval_state=CHARACTER_APPROVAL_PENDING_REVIEW,
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        reason_codes=["identity_action_undone"],
        action="identity_auto_alias_undone",
        details={
            "identity_action_id": str(action.id),
            "target_character_id": str(action.target_character_id)
            if action.target_character_id
            else None,
        },
        actor_user_id=actor_user_id,
    )
    if target is not None and target.book_id == book.id:
        await add_identity_constraint(
            db,
            book_id=book.id,
            left_character_id=source.id,
            right_character_id=target.id,
            left_text=source.name,
            right_text=target.name,
            constraint_type="not_same_character",
            reason="identity_action_undo",
            source="manual",
            confidence=1.0,
        )
    return source.id
