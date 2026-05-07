from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user import PointLedgerEntry, Referral, TrialEmailEvent, User
from app.utils.monetization_utils import (
    FIRST_PROCESSED_BOOK_POINTS,
    POINT_ENTRY_EXPIRE,
    POINT_ENTRY_GRANT,
    POINT_SOURCE_FIRST_BOOK,
    POINT_SOURCE_REFERRAL,
    REFERRED_REWARD_POINTS,
    REFERRAL_REWARD_POINTS,
    build_trial_email_schedule,
    generate_referral_code,
    normalize_referral_code,
    points_expire_at,
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
