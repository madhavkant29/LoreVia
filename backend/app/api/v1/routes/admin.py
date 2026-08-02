import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import (
    admin_step_up_active,
    mark_admin_step_up,
    require_admin_csrf,
    require_admin_principal,
    require_admin_step_up,
    require_moderation_admin,
    require_owner_admin,
    require_super_admin,
)
from app.api.v1.routes import admin_billing, admin_operations, admin_public
from app.core.database import get_db
from app.models.book import Book
from app.models.moderation import ContentReport
from app.models.user import AdminAuditEvent, AdminPrincipal, User
from app.schemas.admin import (
    AdminAuditEventOut,
    AdminBookModerationBody,
    AdminPrincipalGrantBody,
    AdminPrincipalOut,
    AdminPrincipalRevokeBody,
    AdminRestoreBookBody,
    AdminSessionOut,
    AdminStepUpBody,
    ContentReportAdminOut,
    CreatorStrikeCreateBody,
    CreatorStrikeOut,
)
from app.services.admin_service import (
    apply_creator_strike,
    get_platform_metrics,
    grant_admin_principal,
    list_admin_principals,
    principal_scope_snapshot,
    record_admin_audit_event,
    record_admin_read,
    revoke_admin_principal,
)
from app.utils.admin_security import set_admin_csrf_cookie
from app.utils.auth_utils import verify_password_safely
from app.utils.public.moderation import (
    add_moderation_action,
)
from app.utils.public_utils import (
    MODERATION_STATUS_CLEAN,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_PUBLISHED,
    PUBLIC_STATUS_REMOVED,
)

router = APIRouter()
router.include_router(admin_billing.router)
router.include_router(admin_operations.router)
router.include_router(admin_public.router)


def _admin_scopes_from_request(request: Request) -> list[str]:
    return principal_scope_snapshot(getattr(request.state, "admin_principal", None))


async def _apply_book_moderation_action(
    db: AsyncSession,
    book_id: uuid.UUID,
    action: str,
    reason: str,
    admin_user_id: uuid.UUID,
    request: Request,
) -> dict:
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    previous_status = str(getattr(book, "moderation_status", "") or "") or None

    if action == "hide":
        book.moderation_status = MODERATION_STATUS_HIDDEN
        book.public_status = PUBLIC_STATUS_HIDDEN
        book.is_public = False
        book.takedown_reason = reason
        book.takedown_at = datetime.now(UTC)
        book.takedown_by_user_id = admin_user_id
        audit_action = "book_hidden"
        moderation_action = "book_hidden"
    elif action == "remove":
        book.moderation_status = MODERATION_STATUS_REMOVED
        book.public_status = PUBLIC_STATUS_REMOVED
        book.is_public = False
        book.takedown_reason = reason
        book.takedown_at = datetime.now(UTC)
        book.takedown_by_user_id = admin_user_id
        audit_action = "book_removed"
        moderation_action = "book_removed"
    elif action == "restore":
        book.moderation_status = MODERATION_STATUS_CLEAN
        book.public_status = PUBLIC_STATUS_PUBLISHED
        book.is_public = True
        book.takedown_reason = None
        book.takedown_at = None
        book.takedown_by_user_id = None
        audit_action = "book_restored"
        moderation_action = "book_restored"
    else:
        raise HTTPException(400, f"Unknown moderation action: {action}")

    await add_moderation_action(
        db,
        action_type=moderation_action,
        actor_user_id=admin_user_id,
        target_user_id=book.user_id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.moderation_status,
        reason=reason,
    )
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user_id,
        target_user_id=book.user_id,
        target_book_id=book.id,
        action_type=audit_action,
        result="allowed",
        reason=reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
    )
    await db.commit()
    return {"ok": True, "book_id": str(book.id), "moderation_status": book.moderation_status}


@router.get("/session", response_model=AdminSessionOut)
async def admin_session(
    request: Request,
    response: Response,
    admin_user: User = Depends(require_admin_principal),
):
    principal = getattr(request.state, "admin_principal", None)
    set_admin_csrf_cookie(response)
    return AdminSessionOut(
        is_admin=True,
        scopes=_admin_scopes_from_request(request),
        is_owner=bool(getattr(principal, "is_owner", False)),
        requires_step_up=not await admin_step_up_active(request, admin_user.id),
        session_expires_at=None,
    )


@router.post("/step-up")
async def admin_step_up(
    request: Request,
    body: AdminStepUpBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    admin_user: User = Depends(require_admin_principal),
):
    if not verify_password_safely(body.password, admin_user.password_hash):
        await record_admin_audit_event(
            db,
            actor_user_id=admin_user.id,
            action_type="admin_step_up",
            result="denied",
            reason="Invalid password.",
            request=request,
            scopes_snapshot=_admin_scopes_from_request(request),
        )
        await db.commit()
        raise HTTPException(403, "Invalid admin verification.")
    await mark_admin_step_up(request, admin_user.id)
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        action_type="admin_step_up",
        result="allowed",
        reason="Recent admin verification completed.",
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
    )
    await db.commit()
    return {"ok": True}


@router.get("/access", response_model=list[AdminPrincipalOut])
async def get_admin_access(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_owner_admin),
):
    principals = await list_admin_principals(db, limit=limit, offset=offset)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="admin_access_list_viewed",
        reason="Viewed admin principal list.",
        metadata={"limit": limit, "offset": offset},
    )
    return principals


@router.post("/access", response_model=AdminPrincipalOut)
async def grant_admin_access(
    request: Request,
    body: AdminPrincipalGrantBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    owner_user: User = Depends(require_owner_admin),
):
    target_user = await db.get(User, body.user_id)
    if target_user is None:
        raise HTTPException(404, "User not found")
    try:
        principal = await grant_admin_principal(
            db,
            target_user=target_user,
            granted_by_user_id=owner_user.id,
            scopes=body.scopes,
            is_owner=body.is_owner,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await record_admin_audit_event(
        db,
        actor_user_id=owner_user.id,
        target_user_id=target_user.id,
        action_type="admin_access_granted",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"granted_scopes": principal.scopes, "is_owner": principal.is_owner},
    )
    await db.commit()
    await db.refresh(principal)
    return principal


@router.post("/access/{principal_id}/revoke", response_model=AdminPrincipalOut)
async def revoke_admin_access(
    request: Request,
    principal_id: uuid.UUID,
    body: AdminPrincipalRevokeBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    owner_user: User = Depends(require_owner_admin),
):
    principal = await db.get(AdminPrincipal, principal_id)
    if principal is None:
        raise HTTPException(404, "Admin principal not found")
    if principal.user_id == owner_user.id and principal.is_owner:
        raise HTTPException(409, "Owners cannot revoke their own owner access.")
    await revoke_admin_principal(
        db,
        principal=principal,
        revoked_by_user_id=owner_user.id,
        reason=body.reason,
    )
    await record_admin_audit_event(
        db,
        actor_user_id=owner_user.id,
        target_user_id=principal.user_id,
        action_type="admin_access_revoked",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
    )
    await db.commit()
    await db.refresh(principal)
    return principal


@router.get("/audit", response_model=list[AdminAuditEventOut])
async def list_admin_audit_events(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_owner_admin),
):
    events = list(
        (
            await db.execute(
                select(AdminAuditEvent)
                .order_by(AdminAuditEvent.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="admin_audit_viewed",
        reason="Viewed admin audit history.",
        metadata={"limit": limit, "offset": offset},
    )
    return events


@router.get("/metrics")
async def metrics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await get_platform_metrics(db)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="admin_metrics_viewed",
        reason="Viewed admin metrics.",
    )
    return payload


# Thin endpoint — Redis queue checks are lightweight standalone calls.
@router.get("/reports", response_model=list[ContentReportAdminOut])
async def list_content_reports(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_moderation_admin),
):
    reports = (
        (
            await db.execute(
                select(ContentReport)
                .order_by(ContentReport.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    payload = [
        ContentReportAdminOut(
            id=str(report.id),
            reported_book_id=str(report.reported_book_id),
            reported_author_user_id=str(report.reported_author_user_id)
            if report.reported_author_user_id
            else None,
            reporter_user_id=str(report.reporter_user_id) if report.reporter_user_id else None,
            reporter_email=report.reporter_email,
            report_type=report.report_type,
            status=report.status,
            reason=report.reason,
            details=report.details,
            created_at=report.created_at,
        )
        for report in reports
    ]
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="content_reports_viewed",
        reason="Viewed content report list.",
        metadata={"limit": limit, "offset": offset},
    )
    return payload


@router.post("/books/{book_id}/hide")
async def hide_public_book(
    request: Request,
    book_id: uuid.UUID,
    body: AdminBookModerationBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    return await _apply_book_moderation_action(
        db=db,
        book_id=book_id,
        action="hide",
        reason=body.reason,
        admin_user_id=admin_user.id,
        request=request,
    )


@router.post("/books/{book_id}/remove")
async def remove_public_book(
    request: Request,
    book_id: uuid.UUID,
    body: AdminBookModerationBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    return await _apply_book_moderation_action(
        db=db,
        book_id=book_id,
        action="remove",
        reason=body.reason,
        admin_user_id=admin_user.id,
        request=request,
    )


@router.post("/books/{book_id}/restore")
async def restore_public_book(
    request: Request,
    book_id: uuid.UUID,
    body: AdminRestoreBookBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    return await _apply_book_moderation_action(
        db=db,
        book_id=book_id,
        action="restore",
        reason=body.reason,
        admin_user_id=admin_user.id,
        request=request,
    )


@router.post("/users/{user_id}/strikes", response_model=CreatorStrikeOut)
async def add_creator_strike(
    request: Request,
    user_id: uuid.UUID,
    body: CreatorStrikeCreateBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return await apply_creator_strike(
        db,
        user_id=user_id,
        book_id=uuid.UUID(body.book_id) if body.book_id else None,
        report_id=uuid.UUID(body.report_id) if body.report_id else None,
        strike_type=body.strike_type,
        severity=body.severity,
        reason=body.reason,
        admin_user_id=admin_user.id,
        request=request,
    )
