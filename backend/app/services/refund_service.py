from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.intelligence import WorldBuildingDocument
from app.models.progress import ReadingSession
from app.models.user import LlmUsageEvent, RefundReview, Subscription, User, UserWritingActivity
from app.services.paddle_service import (
    PaddleTransactionSummary,
    cancel_subscription_immediately,
    create_refund_adjustment,
    get_transaction_summary,
)
from app.utils.logging import redact_sensitive_text

REFUND_STATUS_PENDING_EVALUATION = "pending_evaluation"
REFUND_STATUS_MANUAL_REVIEW_REQUIRED = "manual_review_required"
REFUND_STATUS_APPROVED_PENDING_PROVIDER = "approved_pending_provider"
REFUND_STATUS_APPROVED = "approved"
REFUND_STATUS_DENIED = "denied"
REFUND_STATUS_PROVIDER_REJECTED = "provider_rejected"
REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED = "provider_followup_required"
REFUND_STATUS_DUPLICATE_REQUEST = "duplicate_request"

ACTIVE_REFUND_REVIEW_STATUSES = {
    REFUND_STATUS_PENDING_EVALUATION,
    REFUND_STATUS_MANUAL_REVIEW_REQUIRED,
    REFUND_STATUS_APPROVED_PENDING_PROVIDER,
    REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
}
SERVICE_CANCELABLE_STATUSES = {"active", "trialing"}
REJECTED_ADJUSTMENT_STATUSES = {"rejected", "denied"}
APPROVED_ADJUSTMENT_STATUSES = {"approved"}
AUTO_REFUND_WINDOW = timedelta(hours=24)
AUTO_REFUND_MAX_APPROVED_HISTORY = 2
AUTO_REFUND_MIN_ACCOUNT_AGE = timedelta(days=7)
ADJUSTMENT_CREATE_ERROR_MESSAGE = (
    "Provider refund creation failed. Manual provider follow-up is required."
)
CANCEL_SUBSCRIPTION_ERROR_MESSAGE = "Refund was created, but provider subscription cancellation failed. Manual provider follow-up is required."
AUTO_REFUND_SUBSCRIPTION_LINKAGE_ERROR_MESSAGE = "This monthly charge requires manual review because the active local subscription could not be safely linked for immediate cancellation."
PADDLE_PROVIDER_EXCEPTIONS = (httpx.HTTPError, KeyError, TypeError, ValueError)


@dataclass(frozen=True)
class RefundEligibilityResult:
    auto_approve: bool
    decision_reason: str
    eligibility_snapshot: dict[str, Any]
    usage_snapshot: dict[str, Any]


async def list_refund_reviews(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RefundReview]:
    statement = select(RefundReview).order_by(RefundReview.created_at.desc())
    if status:
        statement = statement.where(RefundReview.status == status.strip().lower())
    statement = statement.offset(offset).limit(limit)
    return list((await db.execute(statement)).scalars().all())


async def create_refund_review_request(
    db: AsyncSession,
    *,
    transaction_id: str,
    request_reason: str,
    request_source: str,
    support_reference: str | None,
    requested_by_admin_user_id: uuid.UUID,
    now: datetime | None = None,
) -> RefundReview:
    normalized_transaction_id = transaction_id.strip()
    if not normalized_transaction_id:
        raise HTTPException(400, "Transaction ID is required.")

    summary = await get_transaction_summary(normalized_transaction_id)
    user, subscription = await _resolve_local_transaction_context(
        db,
        transaction_id=normalized_transaction_id,
        summary=summary,
    )

    existing_active = await _find_active_review_for_transaction(db, normalized_transaction_id)
    if existing_active is not None:
        return existing_active

    latest_review = await _find_latest_review_for_transaction(db, normalized_transaction_id)
    if latest_review is not None:
        duplicate = RefundReview(
            user_id=user.id,
            subscription_id=subscription.id if subscription is not None else None,
            paddle_transaction_id=normalized_transaction_id,
            paddle_adjustment_id=latest_review.paddle_adjustment_id,
            charge_at=summary.charge_at,
            plan_code=summary.plan
            or (subscription.plan if subscription is not None else "unknown"),
            billing_interval=summary.billing_interval or "unknown",
            request_source=request_source.strip(),
            support_reference=(support_reference or None),
            request_reason=request_reason.strip(),
            status=REFUND_STATUS_DUPLICATE_REQUEST,
            auto_decision=False,
            decision_reason="A refund review already exists for this transaction.",
            eligibility_snapshot_json={"duplicate_of_review_id": str(latest_review.id)},
            usage_snapshot_json={},
            provider_response_json={},
            requested_by_admin_user_id=requested_by_admin_user_id,
            resolved_by_admin_user_id=requested_by_admin_user_id,
            resolved_at=now or datetime.now(UTC),
        )
        db.add(duplicate)
        await db.commit()
        await db.refresh(duplicate)
        return duplicate

    review = RefundReview(
        user_id=user.id,
        subscription_id=subscription.id if subscription is not None else None,
        paddle_transaction_id=normalized_transaction_id,
        charge_at=summary.charge_at,
        plan_code=summary.plan or (subscription.plan if subscription is not None else "unknown"),
        billing_interval=summary.billing_interval or "unknown",
        request_source=request_source.strip(),
        support_reference=(support_reference or None),
        request_reason=request_reason.strip(),
        status=REFUND_STATUS_PENDING_EVALUATION,
        requested_by_admin_user_id=requested_by_admin_user_id,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
    )
    try:
        db.add(review)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing_active = await _find_active_review_for_transaction(db, normalized_transaction_id)
        if existing_active is not None:
            return existing_active
        raise

    evaluation = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id=normalized_transaction_id,
        billing_interval=summary.billing_interval,
        charge_at=summary.charge_at,
        transaction_status=summary.status,
        now=now,
    )
    review.auto_decision = evaluation.auto_approve
    review.decision_reason = evaluation.decision_reason
    review.eligibility_snapshot_json = evaluation.eligibility_snapshot
    review.usage_snapshot_json = evaluation.usage_snapshot

    if not evaluation.auto_approve:
        review.status = REFUND_STATUS_MANUAL_REVIEW_REQUIRED
        await db.commit()
        await db.refresh(review)
        return review

    if not _can_auto_refund_with_subscription_linkage(review, subscription):
        review.auto_decision = False
        review.decision_reason = AUTO_REFUND_SUBSCRIPTION_LINKAGE_ERROR_MESSAGE
        review.status = REFUND_STATUS_MANUAL_REVIEW_REQUIRED
        eligibility_snapshot = dict(review.eligibility_snapshot_json or {})
        eligibility_snapshot["has_required_subscription_linkage"] = False
        review.eligibility_snapshot_json = eligibility_snapshot
        await db.commit()
        await db.refresh(review)
        return review

    try:
        await _submit_refund_review_to_provider(
            review=review,
            subscription=subscription,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing_active = await _find_active_review_for_transaction(db, normalized_transaction_id)
        if existing_active is not None:
            return existing_active
        raise
    await db.refresh(review)
    return review


async def approve_refund_review(
    db: AsyncSession,
    *,
    review_id: uuid.UUID,
    resolved_by_admin_user_id: uuid.UUID,
    reason: str,
    provider_followup_only: bool = False,
) -> RefundReview:
    review = await db.get(RefundReview, review_id)
    if review is None:
        raise HTTPException(404, "Refund review not found.")
    if review.status not in {
        REFUND_STATUS_MANUAL_REVIEW_REQUIRED,
        REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
    }:
        raise HTTPException(409, "This refund review cannot be manually approved.")

    subscription = (
        await db.get(Subscription, review.subscription_id) if review.subscription_id else None
    )
    if not _can_auto_refund_with_subscription_linkage(review, subscription):
        if not provider_followup_only:
            raise HTTPException(
                409,
                "This monthly refund lacks safe local subscription linkage. Mark it provider-follow-up-only instead of approving it directly.",
            )
        review.auto_decision = False
        review.decision_reason = reason.strip()
        review.status = REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED
        review.resolved_by_admin_user_id = resolved_by_admin_user_id
        review.resolved_at = None
        provider_response = dict(review.provider_response_json or {})
        provider_response["provider_followup_only"] = True
        review.provider_response_json = provider_response
        await db.commit()
        await db.refresh(review)
        return review

    review.auto_decision = False
    review.decision_reason = reason.strip()
    review.resolved_by_admin_user_id = resolved_by_admin_user_id
    review.resolved_at = None

    await _submit_refund_review_to_provider(
        review=review,
        subscription=subscription,
        provider_reason=review.decision_reason,
    )
    await db.commit()
    await db.refresh(review)
    return review


async def deny_refund_review(
    db: AsyncSession,
    *,
    review_id: uuid.UUID,
    resolved_by_admin_user_id: uuid.UUID,
    reason: str,
) -> RefundReview:
    review = await db.get(RefundReview, review_id)
    if review is None:
        raise HTTPException(404, "Refund review not found.")
    if review.status in {REFUND_STATUS_APPROVED, REFUND_STATUS_DENIED}:
        raise HTTPException(409, "This refund review is already closed.")
    if review.status == REFUND_STATUS_APPROVED_PENDING_PROVIDER:
        raise HTTPException(
            409,
            "This refund review has already been submitted to the provider and cannot be denied locally.",
        )
    if review.status == REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED and review.paddle_adjustment_id:
        raise HTTPException(
            409,
            "This refund review already has a provider refund in flight and cannot be denied locally.",
        )

    review.status = REFUND_STATUS_DENIED
    review.auto_decision = False if review.auto_decision is None else review.auto_decision
    review.decision_reason = reason.strip()
    review.resolved_by_admin_user_id = resolved_by_admin_user_id
    review.resolved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(review)
    return review


async def evaluate_refund_eligibility(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    transaction_id: str,
    billing_interval: str,
    charge_at: datetime | None,
    transaction_status: str,
    now: datetime | None = None,
) -> RefundEligibilityResult:
    current_time = now or datetime.now(UTC)
    normalized_status = (transaction_status or "").strip().lower()
    normalized_interval = (billing_interval or "").strip().lower()
    approved_refund_count = await _count_refunds_counted_toward_auto_limit(db, user_id)
    user = await db.get(User, user_id)
    usage_snapshot = await _build_usage_snapshot(db, user_id=user_id, charge_at=charge_at)

    charge_age_hours: float | None = None
    account_age_hours: float | None = None
    within_window = False
    meets_account_age_requirement = False
    if charge_at is not None:
        charge_age = current_time - _ensure_utc(charge_at)
        charge_age_hours = round(charge_age.total_seconds() / 3600, 2)
        within_window = timedelta(0) <= charge_age <= AUTO_REFUND_WINDOW
    if user is not None and user.created_at is not None:
        account_age = current_time - _ensure_utc(user.created_at)
        account_age_hours = round(account_age.total_seconds() / 3600, 2)
        meets_account_age_requirement = account_age >= AUTO_REFUND_MIN_ACCOUNT_AGE

    eligibility_snapshot = {
        "transaction_id": transaction_id,
        "transaction_status": normalized_status,
        "billing_interval": normalized_interval,
        "charge_at": charge_at.isoformat() if charge_at is not None else None,
        "charge_age_hours": charge_age_hours,
        "within_auto_refund_window": within_window,
        "auto_refund_window_hours": int(AUTO_REFUND_WINDOW.total_seconds() // 3600),
        "account_age_hours": account_age_hours,
        "meets_account_age_requirement": meets_account_age_requirement,
        "min_account_age_hours": int(AUTO_REFUND_MIN_ACCOUNT_AGE.total_seconds() // 3600),
        "approved_refund_count": approved_refund_count,
        "approved_refund_limit": AUTO_REFUND_MAX_APPROVED_HISTORY,
    }

    if normalized_status != "completed":
        return RefundEligibilityResult(
            auto_approve=False,
            decision_reason="Only completed monthly charges are eligible for automated review.",
            eligibility_snapshot=eligibility_snapshot,
            usage_snapshot=usage_snapshot,
        )

    if normalized_interval != "monthly":
        return RefundEligibilityResult(
            auto_approve=False,
            decision_reason="Annual charges always require manual review.",
            eligibility_snapshot=eligibility_snapshot,
            usage_snapshot=usage_snapshot,
        )

    if charge_at is None or not within_window:
        return RefundEligibilityResult(
            auto_approve=False,
            decision_reason="This charge is outside the 24-hour automated refund window.",
            eligibility_snapshot=eligibility_snapshot,
            usage_snapshot=usage_snapshot,
        )

    if not meets_account_age_requirement:
        return RefundEligibilityResult(
            auto_approve=False,
            decision_reason="This account is too new for automated refunds and requires manual review.",
            eligibility_snapshot=eligibility_snapshot,
            usage_snapshot=usage_snapshot,
        )

    if approved_refund_count >= AUTO_REFUND_MAX_APPROVED_HISTORY:
        return RefundEligibilityResult(
            auto_approve=False,
            decision_reason="This account has reached the automated refund limit and now requires manual review.",
            eligibility_snapshot=eligibility_snapshot,
            usage_snapshot=usage_snapshot,
        )

    if usage_snapshot["has_meaningful_usage"]:
        return RefundEligibilityResult(
            auto_approve=False,
            decision_reason="Post-charge usage was detected, so this refund requires manual review.",
            eligibility_snapshot=eligibility_snapshot,
            usage_snapshot=usage_snapshot,
        )

    return RefundEligibilityResult(
        auto_approve=True,
        decision_reason="This monthly charge is within 24 hours and has no meaningful post-charge usage.",
        eligibility_snapshot=eligibility_snapshot,
        usage_snapshot=usage_snapshot,
    )


async def apply_adjustment_webhook(
    db: AsyncSession,
    *,
    event_type: str,
    data: dict[str, Any],
) -> None:
    action = _normalized_text(data.get("action"))
    if action != "refund":
        return

    adjustment_id = _normalized_text(data.get("id"))
    transaction = data.get("transaction") or {}
    transaction_id = _normalized_text(data.get("transaction_id")) or _normalized_text(
        transaction.get("id")
    )

    review = None
    if adjustment_id:
        review = (
            (
                await db.execute(
                    select(RefundReview)
                    .where(RefundReview.paddle_adjustment_id == adjustment_id)
                    .order_by(RefundReview.created_at.desc())
                )
            )
            .scalars()
            .first()
        )

    if review is None and transaction_id:
        review = await _find_latest_review_for_transaction(db, transaction_id)

    if review is None:
        return

    provider_response = dict(review.provider_response_json or {})
    provider_response[event_type.replace(".", "_")] = data
    review.provider_response_json = provider_response
    if adjustment_id:
        review.paddle_adjustment_id = adjustment_id

    provider_status = _normalized_text(data.get("status"))
    if event_type == "adjustment.created":
        if review.status not in {
            REFUND_STATUS_DENIED,
            REFUND_STATUS_APPROVED,
            REFUND_STATUS_PROVIDER_REJECTED,
            REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
        }:
            review.status = REFUND_STATUS_APPROVED_PENDING_PROVIDER
        return

    if event_type != "adjustment.updated":
        return

    if provider_status in APPROVED_ADJUSTMENT_STATUSES:
        if review.status != REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED:
            review.status = REFUND_STATUS_APPROVED
        review.resolved_at = review.resolved_at or datetime.now(UTC)
        if adjustment_id and transaction_id:
            from app.services.revenue_ledger_service import record_refund_revenue

            await record_refund_revenue(
                db,
                source_event_id=f"refund:{adjustment_id}",
                user_id=review.user_id,
                transaction_id=transaction_id,
            )
        return

    if provider_status in REJECTED_ADJUSTMENT_STATUSES:
        review.status = REFUND_STATUS_PROVIDER_REJECTED
        review.resolved_at = datetime.now(UTC)


async def _submit_refund_review_to_provider(
    *,
    review: RefundReview,
    subscription: Subscription | None,
    provider_reason: str | None = None,
) -> None:
    provider_response = dict(review.provider_response_json or {})
    adjustment_status = ""
    refund_reason = (provider_reason or review.request_reason).strip()

    if not review.paddle_adjustment_id:
        try:
            adjustment = await create_refund_adjustment(
                review.paddle_transaction_id,
                refund_reason,
            )
        except PADDLE_PROVIDER_EXCEPTIONS as exc:
            provider_response["adjustment_create_error"] = ADJUSTMENT_CREATE_ERROR_MESSAGE
            provider_response["adjustment_create_error_redacted"] = redact_sensitive_text(str(exc))
            review.provider_response_json = provider_response
            review.status = REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED
            review.decision_reason = "Refund approval requires manual provider follow-up."
            return

        provider_response["adjustment_create"] = adjustment
        review.provider_response_json = provider_response
        review.paddle_adjustment_id = _normalized_text(adjustment.get("id"))
        adjustment_status = _normalized_text(adjustment.get("status"))

        if adjustment_status in REJECTED_ADJUSTMENT_STATUSES:
            review.status = REFUND_STATUS_PROVIDER_REJECTED
            review.resolved_at = datetime.now(UTC)
            return

    review.status = REFUND_STATUS_APPROVED_PENDING_PROVIDER
    if not _should_cancel_subscription(review, subscription, provider_response):
        return

    try:
        cancellation = await cancel_subscription_immediately(subscription.paddle_sub_id)
    except PADDLE_PROVIDER_EXCEPTIONS as exc:
        provider_response["cancel_subscription_error"] = CANCEL_SUBSCRIPTION_ERROR_MESSAGE
        provider_response["cancel_subscription_error_redacted"] = redact_sensitive_text(str(exc))
        review.provider_response_json = provider_response
        review.status = REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED
        review.decision_reason = "Refund was created in Paddle, but immediate subscription cancellation requires manual follow-up."
        return

    provider_response["cancel_subscription"] = cancellation
    review.provider_response_json = provider_response


async def _resolve_local_transaction_context(
    db: AsyncSession,
    *,
    transaction_id: str,
    summary: PaddleTransactionSummary,
) -> tuple[User, Subscription | None]:
    subscription = None
    user = None

    if summary.subscription_id:
        subscription = (
            (
                await db.execute(
                    select(Subscription)
                    .where(Subscription.paddle_sub_id == summary.subscription_id)
                    .order_by(Subscription.created_at.desc())
                )
            )
            .scalars()
            .first()
        )

    if subscription is None:
        subscription = (
            (
                await db.execute(
                    select(Subscription)
                    .where(Subscription.paddle_transaction_id == transaction_id)
                    .order_by(Subscription.created_at.desc())
                )
            )
            .scalars()
            .first()
        )

    if subscription is not None:
        user = await db.get(User, subscription.user_id)

    if user is None and summary.customer_email:
        user = (
            (
                await db.execute(
                    select(User).where(
                        func.lower(User.email) == summary.customer_email.strip().lower()
                    )
                )
            )
            .scalars()
            .first()
        )

    if user is None:
        raise HTTPException(409, "Unable to link this Paddle transaction to a LoreVia user.")

    return user, subscription


async def _find_active_review_for_transaction(
    db: AsyncSession, transaction_id: str
) -> RefundReview | None:
    return (
        (
            await db.execute(
                select(RefundReview)
                .where(
                    RefundReview.paddle_transaction_id == transaction_id,
                    RefundReview.status.in_(ACTIVE_REFUND_REVIEW_STATUSES),
                )
                .order_by(RefundReview.created_at.desc())
            )
        )
        .scalars()
        .first()
    )


async def _find_latest_review_for_transaction(
    db: AsyncSession, transaction_id: str
) -> RefundReview | None:
    return (
        (
            await db.execute(
                select(RefundReview)
                .where(RefundReview.paddle_transaction_id == transaction_id)
                .order_by(RefundReview.created_at.desc())
            )
        )
        .scalars()
        .first()
    )


async def _count_refunds_counted_toward_auto_limit(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        (
            await db.execute(
                select(func.count(RefundReview.id)).where(
                    RefundReview.user_id == user_id,
                    (RefundReview.status == REFUND_STATUS_APPROVED)
                    | (RefundReview.status == REFUND_STATUS_APPROVED_PENDING_PROVIDER)
                    | (
                        (RefundReview.status == REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED)
                        & RefundReview.paddle_adjustment_id.is_not(None)
                    ),
                )
            )
        ).scalar()
        or 0
    )


async def _build_usage_snapshot(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    charge_at: datetime | None,
) -> dict[str, Any]:
    if charge_at is None:
        return {
            "charge_at": None,
            "has_meaningful_usage": True,
            "reason": "missing_charge_timestamp",
        }

    normalized_charge_at = _ensure_utc(charge_at)
    llm_usage_count = await _count_since(
        db,
        select(func.count(LlmUsageEvent.id)).where(
            LlmUsageEvent.user_id == user_id,
            LlmUsageEvent.created_at >= normalized_charge_at,
        ),
    )
    book_count = await _count_since(
        db,
        select(func.count(Book.id)).where(
            Book.user_id == user_id,
            Book.created_at >= normalized_charge_at,
        ),
    )
    writing_activity_count = await _count_since(
        db,
        select(func.count(UserWritingActivity.id)).where(
            UserWritingActivity.user_id == user_id,
            UserWritingActivity.created_at >= normalized_charge_at,
        ),
    )
    reading_session_count = await _count_since(
        db,
        select(func.count(ReadingSession.id)).where(
            ReadingSession.user_id == user_id,
            ReadingSession.started_at >= normalized_charge_at,
        ),
    )
    worldbuilding_document_count = await _count_since(
        db,
        select(func.count(WorldBuildingDocument.id))
        .join(Book, Book.id == WorldBuildingDocument.book_id)
        .where(
            Book.user_id == user_id,
            WorldBuildingDocument.created_at >= normalized_charge_at,
        ),
    )

    has_meaningful_usage = any(
        count > 0
        for count in (
            llm_usage_count,
            book_count,
            writing_activity_count,
            reading_session_count,
            worldbuilding_document_count,
        )
    )
    return {
        "charge_at": normalized_charge_at.isoformat(),
        "llm_usage_event_count": llm_usage_count,
        "book_count": book_count,
        "writing_activity_count": writing_activity_count,
        "reading_session_count": reading_session_count,
        "worldbuilding_document_count": worldbuilding_document_count,
        "has_meaningful_usage": has_meaningful_usage,
    }


async def _count_since(db: AsyncSession, statement) -> int:
    return int((await db.execute(statement)).scalar() or 0)


def _should_cancel_subscription(
    review: RefundReview,
    subscription: Subscription | None,
    provider_response: dict[str, Any],
) -> bool:
    if review.billing_interval != "monthly":
        return False
    if subscription is None or not subscription.paddle_sub_id:
        return False
    if _normalized_text(subscription.status) not in SERVICE_CANCELABLE_STATUSES:
        return False
    return "cancel_subscription" not in provider_response


def _can_auto_refund_with_subscription_linkage(
    review: RefundReview,
    subscription: Subscription | None,
) -> bool:
    if review.billing_interval != "monthly":
        return True
    if subscription is None or not subscription.paddle_sub_id:
        return False
    return _normalized_text(subscription.status) in SERVICE_CANCELABLE_STATUSES


def _normalized_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
