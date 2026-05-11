from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book
from app.models.user import PointLedgerEntry, Referral, RewardedAdSession, TrialEmailEvent, User
from app.services.email_service import send_trial_email
from app.utils.billing_utils import (
    FREE_TIER,
    free_search_limit_per_day,
    normalize_tier,
    prediction_limit_per_day,
    protected_authoring_limit_per_day,
)
from app.utils.monetization_utils import (
    FIRST_PROCESSED_BOOK_POINTS,
    POINT_ACTION_HIGH_COST,
    POINT_ACTION_PREDICTION,
    POINT_ACTION_SEARCH,
    POINT_ENTRY_SPEND,
    POINT_ENTRY_EXPIRE,
    POINT_ENTRY_GRANT,
    POINT_SOURCE_FIRST_BOOK,
    POINT_SOURCE_REFERRAL,
    POINT_SOURCE_REWARDED_AD,
    POINT_SPEND_OFFERS,
    REFERRED_REWARD_POINTS,
    REWARDED_AD_PROVIDER_GPT,
    REWARDED_AD_STATUS_DISMISSED,
    REWARDED_AD_STATUS_ERROR,
    REWARDED_AD_STATUS_EXPIRED,
    REWARDED_AD_STATUS_PENDING,
    REWARDED_AD_STATUS_REWARDED,
    REWARDED_AD_STATUS_UNSUPPORTED,
    REFERRAL_REWARD_POINTS,
    build_trial_email_schedule,
    generate_referral_code,
    normalize_referral_code,
    normalize_rewarded_ad_outcome,
    point_spend_offer_by_code,
    point_spend_offer_for_action,
    points_expire_at,
    utc_day_bounds,
    utc_now,
)


async def ensure_referral_code(db: AsyncSession, user: User) -> str:
    if user.referral_code:
        return user.referral_code

    for _ in range(5):
        candidate = generate_referral_code(user)
        exists = (
            await db.execute(select(User.id).where(User.referral_code == candidate).limit(1))
        ).first()
        if not exists:
            user.referral_code = candidate
            return candidate

    fallback = f"LORE{uuid.uuid4().hex[:12].upper()}"
    user.referral_code = fallback
    return fallback


async def create_referral_if_valid(db: AsyncSession, referred_user: User, referral_code: str | None) -> Referral | None:
    code = normalize_referral_code(referral_code)
    if not code:
        return None

    referrer = (
        await db.execute(select(User).where(User.referral_code == code).limit(1))
    ).scalar()
    if not referrer or referrer.id == referred_user.id:
        return None

    existing = (
        await db.execute(
            select(Referral).where(Referral.referred_user_id == referred_user.id).limit(1)
        )
    ).scalar()
    if existing:
        return existing

    referral = Referral(
        referrer_user_id=referrer.id,
        referred_user_id=referred_user.id,
        referral_code=code,
        status="pending",
    )
    db.add(referral)
    return referral


async def schedule_trial_email_events(db: AsyncSession, user: User) -> None:
    schedule = build_trial_email_schedule(user.created_at)
    existing_types = {
        row[0]
        for row in (
            await db.execute(
                select(TrialEmailEvent.email_type).where(TrialEmailEvent.user_id == user.id)
            )
        ).all()
    }
    for email_type, scheduled_for in schedule.items():
        if email_type in existing_types:
            continue
        db.add(
            TrialEmailEvent(
                user_id=user.id,
                email_type=email_type,
                scheduled_for=scheduled_for,
                status="pending",
            )
        )


async def grant_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    points: int,
    source_type: str,
    source_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PointLedgerEntry | None:
    if points <= 0:
        return None
    if source_id:
        existing = (
            await db.execute(
                select(PointLedgerEntry).where(
                    PointLedgerEntry.user_id == user_id,
                    PointLedgerEntry.entry_type == POINT_ENTRY_GRANT,
                    PointLedgerEntry.source_type == source_type,
                    PointLedgerEntry.source_id == source_id,
                )
            )
        ).scalar()
        if existing:
            return existing

    entry = PointLedgerEntry(
        user_id=user_id,
        entry_type=POINT_ENTRY_GRANT,
        source_type=source_type,
        source_id=source_id,
        points_delta=points,
        expires_at=points_expire_at(),
        metadata_json=metadata or {},
    )
    db.add(entry)
    return entry


async def point_balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = (
        await db.execute(
            select(func.coalesce(func.sum(PointLedgerEntry.points_delta), 0)).where(
                PointLedgerEntry.user_id == user_id
            )
        )
    ).scalar_one()
    return max(int(balance or 0), 0)


def rewarded_ads_are_enabled() -> bool:
    return bool(settings.REWARDED_ADS_ENABLED and settings.REWARDED_AD_GPT_UNIT_PATH)


def rewarded_ad_disabled_reason() -> str | None:
    if not settings.REWARDED_ADS_ENABLED:
        return "Rewarded ads are not enabled in this environment."
    if not settings.REWARDED_AD_GPT_UNIT_PATH:
        return "Rewarded ad unit path is not configured yet."
    if settings.REWARDED_AD_REWARD_POINTS <= 0:
        return "Rewarded ad reward points are set to zero."
    if settings.REWARDED_AD_DAILY_CAP <= 0:
        return "Rewarded ad daily cap is set to zero."
    return None


async def expire_stale_rewarded_ad_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> int:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    sessions = (
        await db.execute(
            select(RewardedAdSession)
            .where(
                RewardedAdSession.user_id == user_id,
                RewardedAdSession.status == REWARDED_AD_STATUS_PENDING,
                RewardedAdSession.expires_at <= current,
            )
        )
    ).scalars().all()

    for session in sessions:
        session.status = REWARDED_AD_STATUS_EXPIRED
        session.finalized_at = current
        session.metadata_json = {
            **(session.metadata_json or {}),
            "expired_at": current.isoformat(),
        }
    return len(sessions)


async def rewarded_ad_claims_today(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> int:
    start, end = utc_day_bounds(now)
    count = (
        await db.execute(
            select(func.count(RewardedAdSession.id)).where(
                RewardedAdSession.user_id == user_id,
                RewardedAdSession.status == REWARDED_AD_STATUS_REWARDED,
                RewardedAdSession.reward_granted_at.is_not(None),
                RewardedAdSession.reward_granted_at >= start,
                RewardedAdSession.reward_granted_at < end,
            )
        )
    ).scalar_one()
    return int(count or 0)


async def rewarded_ad_status_for_user(
    db: AsyncSession,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    await expire_stale_rewarded_ad_sessions(db, user.id, now=now)
    claims_used = await rewarded_ad_claims_today(db, user.id, now=now)
    daily_cap = min(max(int(settings.REWARDED_AD_DAILY_CAP), 0), 3)
    reward_points = max(int(settings.REWARDED_AD_REWARD_POINTS), 0)
    enabled = rewarded_ads_are_enabled() and daily_cap > 0 and reward_points > 0
    claims_remaining = max(daily_cap - claims_used, 0) if enabled else 0
    return {
        "enabled": enabled,
        "provider": REWARDED_AD_PROVIDER_GPT,
        "reward_points": reward_points,
        "daily_cap": daily_cap,
        "claims_used_today": claims_used,
        "claims_remaining_today": claims_remaining,
        "session_ttl_seconds": max(int(settings.REWARDED_AD_SESSION_TTL_SECONDS), 60),
        "min_grant_seconds": max(int(settings.REWARDED_AD_MIN_GRANT_SECONDS), 0),
        "reason": None if enabled else rewarded_ad_disabled_reason(),
    }


async def _active_rewarded_ad_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> RewardedAdSession | None:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    return (
        await db.execute(
            select(RewardedAdSession)
            .where(
                RewardedAdSession.user_id == user_id,
                RewardedAdSession.status == REWARDED_AD_STATUS_PENDING,
                RewardedAdSession.expires_at > current,
            )
            .order_by(RewardedAdSession.created_at.desc())
            .limit(1)
        )
    ).scalar()


def _rewarded_ad_session_payload(session: RewardedAdSession, claims_remaining_today: int) -> dict[str, Any]:
    return {
        "session_token": session.claim_token,
        "provider": session.provider,
        "reward_points": session.reward_points,
        "ad_unit_path": session.ad_unit_path,
        "expires_at": session.expires_at,
        "claims_remaining_today": claims_remaining_today,
    }


async def start_rewarded_ad_session(
    db: AsyncSession,
    user: User,
    placement: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    status = await rewarded_ad_status_for_user(db, user, now=now)
    if not status["enabled"]:
        raise ValueError(status["reason"] or "Rewarded ads are unavailable right now.")
    if status["claims_remaining_today"] <= 0:
        raise ValueError("You already used today's rewarded ad.")

    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    active_session = await _active_rewarded_ad_session(db, user.id, now=current)
    if active_session is not None:
        return _rewarded_ad_session_payload(
            active_session,
            claims_remaining_today=status["claims_remaining_today"],
        )

    ttl_seconds = max(int(settings.REWARDED_AD_SESSION_TTL_SECONDS), 60)
    session = RewardedAdSession(
        user_id=user.id,
        provider=REWARDED_AD_PROVIDER_GPT,
        claim_token=uuid.uuid4().hex,
        ad_unit_path=settings.REWARDED_AD_GPT_UNIT_PATH or "",
        placement=placement.strip().lower()[:64],
        status=REWARDED_AD_STATUS_PENDING,
        reward_points=max(int(settings.REWARDED_AD_REWARD_POINTS), 0),
        expires_at=current + timedelta(seconds=ttl_seconds),
        metadata_json={"placement": placement.strip().lower()[:64]},
    )
    db.add(session)
    await db.flush()
    return _rewarded_ad_session_payload(
        session,
        claims_remaining_today=status["claims_remaining_today"],
    )


async def resolve_rewarded_ad_session(
    db: AsyncSession,
    user: User,
    *,
    session_token: str,
    outcome: str,
    reward_type: str | None = None,
    reward_amount: int | None = None,
    error_message: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    normalized_outcome = normalize_rewarded_ad_outcome(outcome)
    await expire_stale_rewarded_ad_sessions(db, user.id, now=current)

    session = (
        await db.execute(
            select(RewardedAdSession)
            .where(
                RewardedAdSession.user_id == user.id,
                RewardedAdSession.claim_token == session_token,
            )
            .limit(1)
        )
    ).scalar()
    if session is None:
        raise ValueError("Rewarded ad session was not found.")

    claims_used = await rewarded_ad_claims_today(db, user.id, now=current)
    daily_cap = min(max(int(settings.REWARDED_AD_DAILY_CAP), 0), 3)
    if session.status == REWARDED_AD_STATUS_REWARDED:
        return {
            "status": session.status,
            "balance": await point_balance(db, user.id),
            "reward_points_granted": session.reward_points,
            "claims_remaining_today": max(daily_cap - claims_used, 0),
            "confirmation_message": f"You already earned {session.reward_points} points from this ad.",
        }
    if session.status != REWARDED_AD_STATUS_PENDING:
        raise ValueError("This rewarded ad session is no longer active.")
    if session.expires_at <= current:
        session.status = REWARDED_AD_STATUS_EXPIRED
        session.finalized_at = current
        session.metadata_json = {
            **(session.metadata_json or {}),
            "expired_at": current.isoformat(),
        }
        raise ValueError("This rewarded ad session expired. Please start a new one.")

    metadata = {
        **(session.metadata_json or {}),
        "client_outcome": normalized_outcome,
        "reward_type": reward_type,
        "reward_amount": reward_amount,
        "error_message": error_message,
        "resolved_at": current.isoformat(),
    }

    if normalized_outcome == REWARDED_AD_STATUS_REWARDED:
        minimum_seconds = max(int(settings.REWARDED_AD_MIN_GRANT_SECONDS), 0)
        if (current - session.created_at).total_seconds() < minimum_seconds:
            raise ValueError("Reward confirmation arrived too quickly. Please try again.")
        if daily_cap <= claims_used:
            raise ValueError("You already used today's rewarded ad.")
        await grant_points(
            db,
            user.id,
            session.reward_points,
            POINT_SOURCE_REWARDED_AD,
            source_id=str(session.id),
            metadata={
                "provider": session.provider,
                "placement": session.placement,
                "reward_type": reward_type,
                "reward_amount": reward_amount,
            },
        )
        session.status = REWARDED_AD_STATUS_REWARDED
        session.reward_granted_at = current
        session.finalized_at = current
        session.metadata_json = metadata
        await db.flush()
        return {
            "status": session.status,
            "balance": await point_balance(db, user.id),
            "reward_points_granted": session.reward_points,
            "claims_remaining_today": max(daily_cap - claims_used - 1, 0),
            "confirmation_message": f"You earned {session.reward_points} LoreVia points.",
        }

    if normalized_outcome == REWARDED_AD_STATUS_DISMISSED:
        session.status = REWARDED_AD_STATUS_DISMISSED
        confirmation_message = "No reward was granted because the ad was closed early."
    elif normalized_outcome == REWARDED_AD_STATUS_UNSUPPORTED:
        session.status = REWARDED_AD_STATUS_UNSUPPORTED
        confirmation_message = "Rewarded ads are not supported on this device or page."
    else:
        session.status = REWARDED_AD_STATUS_ERROR
        confirmation_message = "Rewarded ad playback failed before a reward was granted."

    session.finalized_at = current
    session.metadata_json = metadata
    return {
        "status": session.status,
        "balance": await point_balance(db, user.id),
        "reward_points_granted": 0,
        "claims_remaining_today": max(daily_cap - claims_used, 0),
        "confirmation_message": confirmation_message,
    }


def _offer_is_useful_for_user(user: User, action: str) -> bool:
    if action == POINT_ACTION_SEARCH:
        return free_search_limit_per_day(user) is not None
    if action == POINT_ACTION_PREDICTION:
        limit = prediction_limit_per_day(user)
        return 0 < limit < 999999
    if action == POINT_ACTION_HIGH_COST:
        limit = protected_authoring_limit_per_day(user)
        return 0 < limit < 999999
    return False


def point_spend_offers_for_user(user: User) -> list[dict[str, Any]]:
    offers: list[dict[str, Any]] = []
    for offer in POINT_SPEND_OFFERS:
        eligible = _offer_is_useful_for_user(user, offer.action)
        reason = None
        if not eligible:
            if offer.action == POINT_ACTION_SEARCH:
                reason = "Your current plan does not use a daily semantic-search cap."
            elif offer.action == POINT_ACTION_PREDICTION:
                reason = "Your current plan does not need extra prediction overflow."
            elif offer.action == POINT_ACTION_HIGH_COST:
                reason = "This overflow only works for plans that already include author tools."
        offers.append(
            {
                "code": offer.code,
                "action": offer.action,
                "title": offer.title,
                "description": offer.description,
                "points_cost": offer.points_cost,
                "units": offer.units,
                "eligible": eligible,
                "reason": reason,
            }
        )
    return offers


async def purchased_overflow_units_for_action(
    db: AsyncSession,
    user_id: object,
    action: str,
    *,
    now: datetime | None = None,
) -> int:
    offer = point_spend_offer_for_action(action)
    if offer is None:
        return 0
    start, end = utc_day_bounds(now)
    purchase_count = (
        await db.execute(
            select(func.count(PointLedgerEntry.id)).where(
                PointLedgerEntry.user_id == user_id,
                PointLedgerEntry.entry_type == POINT_ENTRY_SPEND,
                PointLedgerEntry.source_type == offer.source_type,
                PointLedgerEntry.created_at >= start,
                PointLedgerEntry.created_at < end,
            )
        )
    ).scalar_one()
    return int(purchase_count or 0) * offer.units


async def purchased_overflow_units_for_action_via_session(
    user_id: object,
    action: str,
    *,
    now: datetime | None = None,
) -> int:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await purchased_overflow_units_for_action(db, user_id, action, now=now)


async def spend_points_on_offer(
    db: AsyncSession,
    user: User,
    offer_code: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    offer = point_spend_offer_by_code(offer_code)
    if offer is None:
        raise ValueError("Unknown point offer.")

    if not _offer_is_useful_for_user(user, offer.action):
        raise ValueError("That point offer is not available on your current plan.")

    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    await expire_due_points_for_user(db, user.id, now=now)

    balance = await point_balance(db, user.id)
    if balance < offer.points_cost:
        raise ValueError("Not enough points for this overflow purchase.")

    db.add(
        PointLedgerEntry(
            user_id=user.id,
            entry_type=POINT_ENTRY_SPEND,
            source_type=offer.source_type,
            source_id=uuid.uuid4().hex,
            points_delta=-offer.points_cost,
            metadata_json={
                "offer_code": offer.code,
                "action": offer.action,
                "units": offer.units,
                "title": offer.title,
            },
        )
    )
    await db.flush()

    new_balance = await point_balance(db, user.id)
    purchased_units_today = await purchased_overflow_units_for_action(db, user.id, offer.action, now=now)
    return {
        "balance": new_balance,
        "purchased_units_today": purchased_units_today,
        "offer": {
            "code": offer.code,
            "action": offer.action,
            "title": offer.title,
            "description": offer.description,
            "points_cost": offer.points_cost,
            "units": offer.units,
            "eligible": True,
            "reason": None,
        },
        "confirmation_message": f"Spent {offer.points_cost} points. Your {offer.title.lower()} is ready for today.",
    }


async def send_due_trial_emails(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    due_rows = (
        await db.execute(
            select(TrialEmailEvent, User)
            .join(User, User.id == TrialEmailEvent.user_id)
            .where(
                TrialEmailEvent.status == "pending",
                TrialEmailEvent.scheduled_for <= current,
                User.email_verified_at.is_not(None),
            )
            .order_by(TrialEmailEvent.scheduled_for.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()

    sent_count = 0
    latest_due_by_user: dict[str, tuple[TrialEmailEvent, User]] = {}
    for event, user in due_rows:
        user_key = str(user.id)
        older = latest_due_by_user.get(user_key)
        if older is not None:
            older[0].status = "skipped"
            older[0].last_error = "Superseded by a later due trial email."
        latest_due_by_user[user_key] = (event, user)

    for event, user in latest_due_by_user.values():
        if normalize_tier(user.tier) != FREE_TIER:
            event.status = "skipped"
            event.last_error = "User upgraded before trial email was due."
            continue
        delivered = await send_trial_email(user.email, event.email_type)
        if delivered:
            event.status = "sent"
            event.sent_at = current
            event.last_error = None
            sent_count += 1
        else:
            event.status = "failed"
            event.last_error = "Resend delivery failed."

    return {"sent": sent_count, "checked": len(due_rows)}


async def qualify_referral_if_ready(
    db: AsyncSession,
    referred_user: User,
    *,
    source_book_id: uuid.UUID | None = None,
) -> Referral | None:
    if not referred_user.email_verified_at:
        return None

    referral = (
        await db.execute(
            select(Referral).where(
                Referral.referred_user_id == referred_user.id,
                Referral.status == "pending",
            )
        )
    ).scalar()
    if not referral:
        return None

    now = utc_now()
    referral.status = "rewarded"
    referral.qualified_at = now
    referral.rewarded_at = now
    referral.metadata_json = {
        **(referral.metadata_json or {}),
        "source_book_id": str(source_book_id) if source_book_id else None,
    }
    await grant_points(
        db,
        referral.referrer_user_id,
        REFERRAL_REWARD_POINTS,
        POINT_SOURCE_REFERRAL,
        source_id=str(referral.id),
        metadata={"role": "referrer", "referred_user_id": str(referred_user.id)},
    )
    await grant_points(
        db,
        referred_user.id,
        REFERRED_REWARD_POINTS,
        POINT_SOURCE_REFERRAL,
        source_id=str(referral.id),
        metadata={"role": "referred", "referrer_user_id": str(referral.referrer_user_id)},
    )
    return referral


async def reward_first_processed_book(db: AsyncSession, user: User, book: Book) -> PointLedgerEntry | None:
    existing = (
        await db.execute(
            select(PointLedgerEntry).where(
                PointLedgerEntry.user_id == user.id,
                PointLedgerEntry.entry_type == POINT_ENTRY_GRANT,
                PointLedgerEntry.source_type == POINT_SOURCE_FIRST_BOOK,
            )
        )
    ).scalar()
    if existing:
        return existing
    return await grant_points(
        db,
        user.id,
        FIRST_PROCESSED_BOOK_POINTS,
        POINT_SOURCE_FIRST_BOOK,
        source_id=str(book.id),
        metadata={"book_title": book.title},
    )


async def expire_due_points(db: AsyncSession, now: datetime | None = None, limit: int = 250) -> int:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    grants = (
        await db.execute(
            select(PointLedgerEntry)
            .where(
                PointLedgerEntry.entry_type == POINT_ENTRY_GRANT,
                PointLedgerEntry.points_delta > 0,
                PointLedgerEntry.expires_at.is_not(None),
                PointLedgerEntry.expires_at <= current,
            )
            .order_by(PointLedgerEntry.expires_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    expired = 0
    for grant in grants:
        source_id = str(grant.id)
        exists = (
            await db.execute(
                select(PointLedgerEntry.id).where(
                    PointLedgerEntry.user_id == grant.user_id,
                    PointLedgerEntry.entry_type == POINT_ENTRY_EXPIRE,
                    PointLedgerEntry.source_type == grant.source_type,
                    PointLedgerEntry.source_id == source_id,
                )
            )
        ).first()
        if exists:
            continue
        db.add(
            PointLedgerEntry(
                user_id=grant.user_id,
                entry_type=POINT_ENTRY_EXPIRE,
                source_type=grant.source_type,
                source_id=source_id,
                points_delta=-grant.points_delta,
                metadata_json={"expired_grant_id": source_id},
            )
        )
        expired += 1
    return expired


async def expire_due_points_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    grants = (
        await db.execute(
            select(PointLedgerEntry)
            .where(
                PointLedgerEntry.user_id == user_id,
                PointLedgerEntry.entry_type == POINT_ENTRY_GRANT,
                PointLedgerEntry.points_delta > 0,
                PointLedgerEntry.expires_at.is_not(None),
                PointLedgerEntry.expires_at <= current,
            )
            .order_by(PointLedgerEntry.expires_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    expired = 0
    for grant in grants:
        source_id = str(grant.id)
        exists = (
            await db.execute(
                select(PointLedgerEntry.id).where(
                    PointLedgerEntry.user_id == user_id,
                    PointLedgerEntry.entry_type == POINT_ENTRY_EXPIRE,
                    PointLedgerEntry.source_type == grant.source_type,
                    PointLedgerEntry.source_id == source_id,
                )
            )
        ).first()
        if exists:
            continue
        db.add(
            PointLedgerEntry(
                user_id=user_id,
                entry_type=POINT_ENTRY_EXPIRE,
                source_type=grant.source_type,
                source_id=source_id,
                points_delta=-grant.points_delta,
                metadata_json={"expired_grant_id": source_id},
            )
        )
        expired += 1
    return expired
