import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.redis
from app.api.deps.auth import (
    admin_step_up_active,
    mark_admin_step_up,
    require_admin_csrf,
    require_admin_principal,
    require_admin_step_up,
    require_billing_admin,
    require_moderation_admin,
    require_owner_admin,
    require_super_admin,
)
from app.core.database import get_db
from app.core.redis import cache_del, key_public_book_detail, key_public_books
from app.core.security import verify_password
from app.models.book import Book
from app.models.moderation import ContentReport
from app.models.operations import SupportIncident
from app.models.user import AdminAuditEvent, AdminPrincipal, User, UserRateLimitOverride
from app.schemas.admin import (
    AdminAuditEventOut,
    AdminBookModerationBody,
    AdminPrincipalGrantBody,
    AdminPrincipalOut,
    AdminPrincipalRevokeBody,
    AdminRestoreBookBody,
    AdminSessionOut,
    AdminStepUpBody,
    AdminTaskActionBody,
    ContentReportAdminOut,
    CreatorStrikeCreateBody,
    CreatorStrikeOut,
    PendingPublicShareOut,
    PublicShareApprovalBody,
    RateLimitOverrideBody,
    RefundReviewCreateBody,
    RefundReviewDecisionBody,
    RefundReviewOut,
    SubscriptionMetricsOut,
    SupportIncidentCreateBody,
    SupportIncidentResolveBody,
    UpdateUserTierBody,
)
from app.schemas.billing import BillingStatusOut
from app.schemas.public import (
    PublicBookCreateOut,
    PublicBookManualIn,
    PublicChapterAppendOut,
    PublicChapterIn,
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
    serialize_pending_public_shares,
)
from app.services.operations_admin_service import (
    contribution_margin,
    dismiss_terminal_execution,
    list_task_executions,
    operations_metrics,
    quality_metrics,
    retry_terminal_execution,
)
from app.services.refund_service import (
    approve_refund_review,
    create_refund_review_request,
    deny_refund_review,
    list_refund_reviews,
)
from app.utils.admin_security import set_admin_csrf_cookie
from app.utils.billing_utils import (
    VALID_USER_TIERS,
    billing_configuration_status,
    build_subscription_metrics_summary,
    normalize_tier,
)
from app.utils.public.content import (
    append_public_demo_book_chapter,
    create_public_demo_book,
)
from app.utils.public.moderation import (
    add_moderation_action,
)
from app.utils.public.serialization import (
    get_public_share_status,
)
from app.utils.public_utils import (
    MODERATION_STATUS_CLEAN,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_PUBLISHED,
    PUBLIC_STATUS_REMOVED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
)
from app.utils.rate_limit_utils import invalidate_rate_limit_override_cache
from app.utils.redis_utils import maybe_await

router = APIRouter()


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
    try:
        valid = verify_password(body.password, admin_user.password_hash)
    except Exception:
        valid = False
    if not valid:
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


@router.get("/billing/status", response_model=BillingStatusOut)
async def get_admin_billing_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_billing_admin),
):
    payload = BillingStatusOut(**billing_configuration_status())
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="billing_status_viewed",
        reason="Viewed billing configuration status.",
    )
    return payload


@router.get("/public-shares/pending", response_model=list[PendingPublicShareOut])
async def list_pending_public_shares(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_moderation_admin),
):
    payload = await serialize_pending_public_shares(db, limit=limit, offset=offset)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="public_share_queue_viewed",
        reason="Viewed pending public-share queue.",
        metadata={"limit": limit, "offset": offset},
    )
    return payload


@router.post("/public-books/manual", response_model=PublicBookCreateOut)
async def create_admin_public_demo_book(
    request: Request,
    body: PublicBookManualIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    book, payload = await create_public_demo_book(db, admin_user=admin_user, body=body)
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        target_book_id=book.id,
        action_type="public_demo_book_created",
        result="allowed",
        reason="Created public demo book.",
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"chapter_count": len(body.chapters), "public_slug": book.public_slug},
    )
    await db.commit()
    return payload


@router.post("/public-books/{book_id}/chapters", response_model=PublicChapterAppendOut)
async def append_admin_public_demo_book_chapter(
    request: Request,
    book_id: uuid.UUID,
    body: PublicChapterIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    book, payload = await append_public_demo_book_chapter(db, book_id=book_id, body=body)
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        target_book_id=book.id,
        action_type="public_demo_book_chapter_appended",
        result="allowed",
        reason="Appended chapter to public demo book.",
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"chapter_number": payload.chapter_number},
    )
    await db.commit()
    return payload


@router.put("/public-shares/{book_id}")
async def review_public_share(
    request: Request,
    book_id: uuid.UUID,
    body: PublicShareApprovalBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    admin_user: User = Depends(require_moderation_admin),
):
    if not body.approved and not (body.reason or "").strip():
        raise HTTPException(400, "A reason is required when rejecting public sharing.")
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    if book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(409, "This manuscript is not available for public sharing.")

    current_status = get_public_share_status(book)
    if (
        str(book.source_kind or "").strip().lower() != USER_PUBLIC_SHARE_SOURCE_KIND
        and current_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED
    ):
        raise HTTPException(409, "This manuscript is not in the author public-share workflow.")
    if body.approved:
        if current_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED:
            raise HTTPException(
                409, "This manuscript does not have a pending public-share request."
            )
        book.public_share_status = PUBLIC_SHARE_STATUS_APPROVED
        book.public_share_approved_at = datetime.now(UTC)
        book.public_share_approved_by_user_id = admin_user.id
        book.is_public = True
        book.public_status = PUBLIC_STATUS_PUBLISHED
        book.public_visibility = "public"
        book.moderation_status = MODERATION_STATUS_CLEAN
        visibility = "public"
    else:
        book.is_public = False
        book.public_status = PUBLIC_STATUS_HIDDEN
        book.public_visibility = "private"
        if current_status == PUBLIC_SHARE_STATUS_PENDING:
            book.public_share_status = PUBLIC_SHARE_STATUS_NOT_REQUESTED
            book.public_share_requested_at = None
        else:
            book.public_share_status = PUBLIC_SHARE_STATUS_NOT_REQUESTED
        book.public_share_approved_at = None
        book.public_share_approved_by_user_id = None
        book.source_kind = USER_PUBLIC_SHARE_SOURCE_KIND
        visibility = "private"

    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        target_book_id=book.id,
        action_type="public_share_reviewed",
        result="allowed",
        reason=(body.reason or "Public share approved.").strip(),
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"approved": body.approved},
    )
    await db.commit()
    await cache_del(key_public_books())
    await cache_del(key_public_book_detail(str(book.id)))
    return {
        "book_id": str(book.id),
        "approval_status": get_public_share_status(book),
        "visibility": visibility,
        "approved": bool(body.approved),
    }


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


@router.get("/subscription-metrics", response_model=SubscriptionMetricsOut)
async def subscription_metrics(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    reactivation_window_days: int = 30,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_billing_admin),
):
    today = datetime.now(UTC).date()
    resolved_end_date = end_date or today
    resolved_start_date = start_date or (resolved_end_date - timedelta(days=29))
    summary = await build_subscription_metrics_summary(
        db,
        cohort_start=resolved_start_date,
        cohort_end=resolved_end_date,
        reactivation_window_days=reactivation_window_days,
    )
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="subscription_metrics_viewed",
        reason="Viewed subscription metrics.",
        metadata={
            "start_date": resolved_start_date.isoformat(),
            "end_date": resolved_end_date.isoformat(),
            "reactivation_window_days": reactivation_window_days,
        },
    )
    return SubscriptionMetricsOut(**summary.__dict__)


@router.get("/refunds/reviews", response_model=list[RefundReviewOut])
async def get_refund_reviews(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_billing_admin),
):
    reviews = await list_refund_reviews(db, status=status, limit=limit, offset=offset)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="refund_review_list_viewed",
        reason="Viewed refund review list.",
        metadata={"status": status, "limit": limit, "offset": offset},
    )
    return reviews


@router.post("/refunds/reviews", response_model=RefundReviewOut)
async def create_refund_review(
    request: Request,
    body: RefundReviewCreateBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_billing_admin),
):
    review = await create_refund_review_request(
        db,
        transaction_id=body.transaction_id,
        request_reason=body.reason,
        request_source=body.request_source,
        support_reference=body.support_reference,
        requested_by_admin_user_id=admin_user.id,
    )
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=review.user_id,
        target_refund_review_id=review.id,
        action_type="refund_review_created",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"status": review.status, "transaction_id": review.paddle_transaction_id},
    )
    await db.commit()
    return review


@router.post("/refunds/reviews/{review_id}/approve", response_model=RefundReviewOut)
async def approve_refund_review_request(
    request: Request,
    review_id: uuid.UUID,
    body: RefundReviewDecisionBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_billing_admin),
):
    review = await approve_refund_review(
        db,
        review_id=review_id,
        resolved_by_admin_user_id=admin_user.id,
        reason=body.reason,
        provider_followup_only=body.provider_followup_only,
    )
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=review.user_id,
        target_refund_review_id=review.id,
        action_type="refund_review_approved",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"status": review.status},
    )
    await db.commit()
    return review


@router.post("/refunds/reviews/{review_id}/deny", response_model=RefundReviewOut)
async def deny_refund_review_request(
    request: Request,
    review_id: uuid.UUID,
    body: RefundReviewDecisionBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_billing_admin),
):
    review = await deny_refund_review(
        db,
        review_id=review_id,
        resolved_by_admin_user_id=admin_user.id,
        reason=body.reason,
    )
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=review.user_id,
        target_refund_review_id=review.id,
        action_type="refund_review_denied",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"status": review.status},
    )
    await db.commit()
    return review


# Thin endpoint — Redis queue checks are lightweight standalone calls.
@router.get("/queue-depth")
async def queue_depth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    r = await app.core.redis.get_redis()
    payload = {
        "extraction": await maybe_await(r.llen("extraction")),
        "analysis": await maybe_await(r.llen("analysis")),
        "embedding": await maybe_await(r.llen("embedding")),
        "intelligence": await maybe_await(r.llen("intelligence")),
    }
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="queue_depth_viewed",
        reason="Viewed worker queue depths.",
    )
    return payload


@router.get("/task-executions")
async def admin_task_executions(
    request: Request,
    status: str | None = Query(default="failed_terminal"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await list_task_executions(db, status=status, limit=limit, offset=offset)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="task_execution_list_viewed",
        reason="Viewed durable task executions.",
    )
    return payload


@router.post("/task-executions/{execution_id}/retry")
async def admin_retry_task_execution(
    request: Request,
    execution_id: uuid.UUID,
    body: AdminTaskActionBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    try:
        execution = await retry_terminal_execution(db, execution_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=execution.user_id,
        target_book_id=execution.book_id,
        action_type="task_execution_retried",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"execution_id": str(execution.id)},
    )
    await db.commit()
    return {"id": str(execution.id), "status": execution.status}


@router.post("/task-executions/{execution_id}/dismiss")
async def admin_dismiss_task_execution(
    request: Request,
    execution_id: uuid.UUID,
    body: AdminTaskActionBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    try:
        execution = await dismiss_terminal_execution(
            db, execution_id, admin_user_id=admin_user.id, reason=body.reason
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=execution.user_id,
        target_book_id=execution.book_id,
        action_type="task_execution_dismissed",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"execution_id": str(execution.id)},
    )
    await db.commit()
    return {"id": str(execution.id), "status": execution.status}


@router.get("/operations-metrics")
async def admin_operations_metrics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await operations_metrics(db)
    await record_admin_read(
        db=db, request=request, admin_user=admin_user,
        action_type="operations_metrics_viewed", reason="Viewed processing operations metrics."
    )
    return payload


@router.get("/ai-quality")
async def admin_ai_quality(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await quality_metrics(db)
    await record_admin_read(
        db=db, request=request, admin_user=admin_user,
        action_type="ai_quality_viewed", reason="Viewed AI quality metrics."
    )
    return payload


@router.get("/contribution-margin")
async def admin_contribution_margin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await contribution_margin(db)
    await record_admin_read(
        db=db, request=request, admin_user=admin_user,
        action_type="contribution_margin_viewed", reason="Viewed contribution-margin estimates."
    )
    return payload


@router.get("/support-incidents")
async def admin_support_incidents(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    rows = (
        await db.execute(select(SupportIncident).order_by(SupportIncident.created_at.desc()).limit(200))
    ).scalars().all()
    return [
        {
            "id": str(row.id), "user_id": str(row.user_id) if row.user_id else None,
            "book_id": str(row.book_id) if row.book_id else None, "category": row.category,
            "feature": row.feature, "severity": row.severity, "status": row.status,
            "summary": row.summary, "resolution": row.resolution, "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/support-incidents")
async def admin_create_support_incident(
    request: Request,
    body: SupportIncidentCreateBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    incident = SupportIncident(
        user_id=body.user_id, book_id=body.book_id, task_execution_id=body.task_execution_id,
        category=body.category, feature=body.feature, severity=body.severity,
        summary=body.summary, created_by_user_id=admin_user.id,
    )
    db.add(incident)
    await db.flush()
    await record_admin_audit_event(
        db, actor_user_id=admin_user.id, target_user_id=body.user_id,
        target_book_id=body.book_id, action_type="support_incident_created", result="allowed",
        reason=body.summary, request=request, scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"incident_id": str(incident.id), "category": body.category},
    )
    await db.commit()
    return {"id": str(incident.id), "status": incident.status}


@router.post("/support-incidents/{incident_id}/resolve")
async def admin_resolve_support_incident(
    request: Request,
    incident_id: uuid.UUID,
    body: SupportIncidentResolveBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    incident = await db.get(SupportIncident, incident_id)
    if incident is None:
        raise HTTPException(404, "Support incident not found")
    incident.status = "resolved"
    incident.resolution = body.resolution
    incident.resolved_at = datetime.now(UTC)
    await record_admin_audit_event(
        db, actor_user_id=admin_user.id, target_user_id=incident.user_id,
        target_book_id=incident.book_id, action_type="support_incident_resolved", result="allowed",
        reason=body.resolution, request=request, scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"incident_id": str(incident.id)},
    )
    await db.commit()
    return {"id": str(incident.id), "status": incident.status}


@router.get("/rate-limits/{user_id}")
async def get_rate_limit_override(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    override = (
        (
            await db.execute(
                select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
            )
        )
        .scalars()
        .first()
    )
    payload = {
        "user_id": str(user_id),
        "email": user.email,
        "override": {
            "search_per_hour": override.search_per_hour if override else None,
            "summary_per_hour": override.summary_per_hour if override else None,
            "chat_per_day": override.chat_per_day if override else None,
            "api_per_minute": override.api_per_minute if override else None,
        },
    }
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="rate_limit_override_viewed",
        reason="Viewed user rate limit override.",
        metadata={"target_user_id": str(user_id)},
    )
    return payload


@router.put("/rate-limits/{user_id}")
async def upsert_rate_limit_override(
    request: Request,
    user_id: uuid.UUID,
    body: RateLimitOverrideBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    admin_user: User = Depends(require_super_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    override = (
        (
            await db.execute(
                select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
            )
        )
        .scalars()
        .first()
    )
    if not override:
        override = UserRateLimitOverride(user_id=user_id)
        db.add(override)

    override.search_per_hour = body.search_per_hour
    override.summary_per_hour = body.summary_per_hour
    override.chat_per_day = body.chat_per_day
    override.api_per_minute = body.api_per_minute
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=user_id,
        action_type="rate_limit_override_updated",
        result="allowed",
        reason="Admin rate limit override updated.",
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
    )
    await db.commit()
    await invalidate_rate_limit_override_cache(user_id)
    return {"ok": True, "user_id": str(user_id)}


@router.put("/users/{user_id}/tier")
async def update_user_tier(
    request: Request,
    user_id: uuid.UUID,
    body: UpdateUserTierBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    tier = normalize_tier(body.tier)
    if tier == "admin":
        raise HTTPException(
            400, "Admin access is managed through admin principals, not user tiers."
        )
    if tier not in VALID_USER_TIERS:
        raise HTTPException(
            400, f"Invalid tier. Must be one of: {', '.join(sorted(VALID_USER_TIERS))}"
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.tier = tier
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=user.id,
        action_type="user_tier_updated",
        result="allowed",
        reason=f"Changed product tier to {tier}.",
        request=request,
        scopes_snapshot=_admin_scopes_from_request(request),
        metadata={"tier": tier},
    )
    await db.commit()
    return {"ok": True, "user_id": str(user_id), "tier": tier}


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
