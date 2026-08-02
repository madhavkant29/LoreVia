from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.character import Character
from app.models.intelligence import BookChunk, ChapterSummary
from app.models.moderation import CreatorStrike
from app.models.user import AdminAuditEvent, AdminPrincipal, User
from app.schemas.admin import CreatorStrikeOut, PendingPublicShareOut
from app.utils.auth_utils import next_token_version
from app.utils.client_identity import trusted_client_ip
from app.utils.public.moderation import (
    active_serious_strike_count,
    add_moderation_action,
)
from app.utils.public_utils import (
    PUBLIC_SHARE_STATUS_PENDING,
    USER_PUBLIC_SHARE_SOURCE_KIND,
)

ADMIN_SCOPE_MODERATION = "moderation_admin"
ADMIN_SCOPE_BILLING = "billing_admin"
ADMIN_SCOPE_SUPER = "super_admin"
ADMIN_SCOPES = {ADMIN_SCOPE_MODERATION, ADMIN_SCOPE_BILLING, ADMIN_SCOPE_SUPER}
ADMIN_STATUS_ACTIVE = "active"
ADMIN_STATUS_REVOKED = "revoked"


def normalize_admin_scopes(scopes: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    normalized = sorted(
        {str(scope).strip().lower() for scope in (scopes or []) if str(scope).strip()}
    )
    invalid = [scope for scope in normalized if scope not in ADMIN_SCOPES]
    if invalid:
        raise ValueError(f"Invalid admin scopes: {', '.join(invalid)}")
    return normalized


def principal_scope_snapshot(principal: AdminPrincipal | None) -> list[str]:
    if principal is None or principal.status != ADMIN_STATUS_ACTIVE:
        return []
    return normalize_admin_scopes(principal.scopes)


def principal_has_scope(principal: AdminPrincipal | None, required_scope: str) -> bool:
    if principal is None or principal.status != ADMIN_STATUS_ACTIVE:
        return False
    if principal.is_owner:
        return True
    return required_scope in principal_scope_snapshot(principal)


async def get_active_admin_principal(db: AsyncSession, user_id: uuid.UUID) -> AdminPrincipal | None:
    return (
        (
            await db.execute(
                select(AdminPrincipal).where(
                    AdminPrincipal.user_id == user_id,
                    AdminPrincipal.status == ADMIN_STATUS_ACTIVE,
                )
            )
        )
        .scalars()
        .first()
    )


async def list_admin_principals(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminPrincipal]:
    return list(
        (
            await db.execute(
                select(AdminPrincipal)
                .order_by(AdminPrincipal.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def grant_admin_principal(
    db: AsyncSession,
    *,
    target_user: User,
    granted_by_user_id: uuid.UUID,
    scopes: list[str],
    is_owner: bool,
    reason: str,
) -> AdminPrincipal:
    resolved_scopes = normalize_admin_scopes(scopes)
    principal = (
        (await db.execute(select(AdminPrincipal).where(AdminPrincipal.user_id == target_user.id)))
        .scalars()
        .first()
    )
    if principal is None:
        principal = AdminPrincipal(
            user_id=target_user.id,
            status=ADMIN_STATUS_ACTIVE,
            is_owner=is_owner,
            scopes=resolved_scopes,
            grant_reason=reason.strip(),
            granted_by_user_id=granted_by_user_id,
        )
        db.add(principal)
        return principal

    principal.status = ADMIN_STATUS_ACTIVE
    principal.is_owner = is_owner
    principal.scopes = resolved_scopes
    principal.grant_reason = reason.strip()
    principal.revoke_reason = None
    principal.revoked_by_user_id = None
    principal.revoked_at = None
    principal.granted_by_user_id = granted_by_user_id
    principal.updated_at = datetime.now(UTC)
    return principal


async def revoke_admin_principal(
    db: AsyncSession,
    *,
    principal: AdminPrincipal,
    revoked_by_user_id: uuid.UUID,
    reason: str,
) -> None:
    principal.status = ADMIN_STATUS_REVOKED
    principal.revoke_reason = reason.strip()
    principal.revoked_by_user_id = revoked_by_user_id
    principal.revoked_at = datetime.now(UTC)
    principal.updated_at = datetime.now(UTC)
    user = await db.get(User, principal.user_id)
    if user is not None:
        user.token_version = next_token_version(user)


async def record_admin_audit_event(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action_type: str,
    result: str,
    reason: str | None = None,
    request: Request | None = None,
    scopes_snapshot: list[str] | None = None,
    target_user_id: uuid.UUID | None = None,
    target_book_id: uuid.UUID | None = None,
    target_report_id: uuid.UUID | None = None,
    target_refund_review_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdminAuditEvent:
    ip_address = trusted_client_ip(request)
    event = AdminAuditEvent(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        target_book_id=target_book_id,
        target_report_id=target_report_id,
        target_refund_review_id=target_refund_review_id,
        action_type=action_type,
        reason=reason,
        result=result,
        request_id=request.headers.get("x-request-id") if request is not None else None,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent") if request is not None else None,
        scopes_snapshot=scopes_snapshot or [],
        metadata_json=metadata or {},
    )
    db.add(event)
    return event


async def record_admin_read(
    db: AsyncSession,
    *,
    request: Request,
    admin_user: User,
    action_type: str,
    reason: str,
    metadata: dict[str, object] | None = None,
) -> None:
    scopes_snapshot = principal_scope_snapshot(getattr(request.state, "admin_principal", None))
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        action_type=action_type,
        result="allowed",
        reason=reason,
        request=request,
        scopes_snapshot=scopes_snapshot,
        metadata=metadata,
    )
    await db.commit()


async def serialize_pending_public_shares(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[PendingPublicShareOut]:
    rows = (
        await db.execute(
            select(Book, User.username)
            .join(User, User.id == Book.user_id)
            .where(
                Book.source_kind == USER_PUBLIC_SHARE_SOURCE_KIND,
                Book.public_share_status == PUBLIC_SHARE_STATUS_PENDING,
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
            )
            .order_by(Book.public_share_requested_at.asc(), Book.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return [
        PendingPublicShareOut(
            book_id=str(book.id),
            user_id=str(book.user_id),
            author_username=username,
            title=book.title,
            author=book.author,
            genre=book.genre,
            isbn=book.isbn,
            copyright_warning=bool(book.copyright_warning),
            public_description=book.public_description,
            requested_at=book.public_share_requested_at,
            created_at=book.created_at,
        )
        for book, username in rows
    ]


async def get_platform_metrics(db: AsyncSession) -> dict:
    import app.core.redis

    users = (await db.execute(select(func.count()).select_from(User))).scalar()
    books = (await db.execute(select(func.count()).select_from(Book))).scalar()
    chars = (await db.execute(select(func.count()).select_from(Character))).scalar()
    chunks = (await db.execute(select(func.count()).select_from(BookChunk))).scalar()
    summaries = (await db.execute(select(func.count()).select_from(ChapterSummary))).scalar()
    redis_diagnostics = await app.core.redis.get_redis_diagnostics()
    return {
        "users": users,
        "books": books,
        "characters": chars,
        "chunks_indexed": chunks,
        "summaries_cached": summaries,
        "redis_memory_mb": redis_diagnostics["memory_mb"],
        "redis_key_count": redis_diagnostics["key_count"],
        "redis_connected_clients": redis_diagnostics["connected_clients"],
        "redis_key_prefix_counts": redis_diagnostics["key_prefix_counts"],
        "redis_key_prefix_samples": redis_diagnostics["key_prefix_samples"],
        "redis_key_scan_truncated": redis_diagnostics["key_scan_truncated"],
    }


async def apply_creator_strike(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID | None,
    report_id: uuid.UUID | None,
    strike_type: str,
    severity: str,
    reason: str,
    admin_user_id: uuid.UUID,
    request: Request,
) -> CreatorStrikeOut:
    scopes_snapshot = principal_scope_snapshot(getattr(request.state, "admin_principal", None))
    strike = CreatorStrike(
        user_id=user_id,
        book_id=book_id,
        report_id=report_id,
        strike_type=strike_type,
        severity=severity,
        reason=reason,
        created_by_user_id=admin_user_id,
        is_active=True,
    )
    db.add(strike)
    await db.flush()
    serious_count = await active_serious_strike_count(db, user_id=user_id)
    await add_moderation_action(
        db,
        action_type="strike_added",
        actor_user_id=admin_user_id,
        target_user_id=user_id,
        book_id=strike.book_id,
        report_id=strike.report_id,
        previous_status=None,
        new_status=f"serious_strikes:{serious_count}",
        reason=reason,
        metadata={"severity": severity, "strike_type": strike_type},
    )
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user_id,
        target_user_id=user_id,
        target_book_id=strike.book_id,
        target_report_id=strike.report_id,
        action_type="strike_added",
        result="allowed",
        reason=reason,
        request=request,
        scopes_snapshot=scopes_snapshot,
        metadata={"severity": severity, "strike_type": strike_type},
    )
    await db.commit()
    return CreatorStrikeOut(
        id=str(strike.id),
        user_id=str(strike.user_id),
        book_id=str(strike.book_id) if strike.book_id else None,
        report_id=str(strike.report_id) if strike.report_id else None,
        strike_type=strike.strike_type,
        severity=strike.severity,
        reason=strike.reason,
        is_active=bool(strike.is_active),
        created_at=strike.created_at,
    )
