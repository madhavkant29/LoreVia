from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AdminAuditEvent, AdminPrincipal, User
from app.utils.auth_utils import next_token_version


ADMIN_SCOPE_MODERATION = "moderation_admin"
ADMIN_SCOPE_BILLING = "billing_admin"
ADMIN_SCOPE_SUPER = "super_admin"
ADMIN_SCOPES = {ADMIN_SCOPE_MODERATION, ADMIN_SCOPE_BILLING, ADMIN_SCOPE_SUPER}
ADMIN_STATUS_ACTIVE = "active"
ADMIN_STATUS_REVOKED = "revoked"


def normalize_admin_scopes(scopes: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    normalized = sorted({str(scope).strip().lower() for scope in (scopes or []) if str(scope).strip()})
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
        await db.execute(
            select(AdminPrincipal).where(
                AdminPrincipal.user_id == user_id,
                AdminPrincipal.status == ADMIN_STATUS_ACTIVE,
            )
        )
    ).scalars().first()


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
        ).scalars().all()
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
        await db.execute(select(AdminPrincipal).where(AdminPrincipal.user_id == target_user.id))
    ).scalars().first()
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
    forwarded_for = request.headers.get("x-forwarded-for") if request is not None else None
    ip_address = (forwarded_for or "").split(",", 1)[0].strip() if forwarded_for else None
    if not ip_address and request is not None and request.client is not None:
        ip_address = request.client.host
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
