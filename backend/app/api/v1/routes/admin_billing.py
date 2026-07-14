from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import (
    require_admin_csrf,
    require_admin_step_up,
    require_billing_admin,
    require_super_admin,
)
from app.api.v1.routes.admin_common import admin_scopes_from_request
from app.core.database import get_db
from app.models.user import User, UserRateLimitOverride
from app.schemas.admin import (
    RateLimitOverrideBody,
    RefundReviewCreateBody,
    RefundReviewDecisionBody,
    RefundReviewOut,
    SubscriptionMetricsOut,
    UpdateUserTierBody,
)
from app.schemas.billing import BillingStatusOut
from app.services.admin_service import record_admin_audit_event, record_admin_read
from app.services.refund_service import (
    approve_refund_review,
    create_refund_review_request,
    deny_refund_review,
    list_refund_reviews,
)
from app.utils.billing_utils import (
    VALID_USER_TIERS,
    billing_configuration_status,
    build_subscription_metrics_summary,
    normalize_tier,
)
from app.utils.rate_limit_utils import invalidate_rate_limit_override_cache

router = APIRouter()


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
        scopes_snapshot=admin_scopes_from_request(request),
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
        scopes_snapshot=admin_scopes_from_request(request),
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
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"status": review.status},
    )
    await db.commit()
    return review


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
    __: None = Depends(require_admin_step_up),
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
    if override is None:
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
        scopes_snapshot=admin_scopes_from_request(request),
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
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"tier": tier},
    )
    await db.commit()
    return {"ok": True, "user_id": str(user_id), "tier": tier}
