import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_admin
from app.core.database import get_db
from app.core.redis import cache_del, key_public_book_detail, key_public_books
import app.core.redis
from app.models.book import Book
from app.models.moderation import ContentReport, CreatorStrike
from app.models.character import Character
from app.models.intelligence import BookChunk, ChapterSummary
from app.models.user import User, UserRateLimitOverride
from app.schemas.admin import (
    AdminBookModerationBody,
    AdminRestoreBookBody,
    ContentReportAdminOut,
    CreatorStrikeCreateBody,
    CreatorStrikeOut,
    PendingPublicShareOut,
    PublicShareApprovalBody,
    RateLimitOverrideBody,
    SubscriptionMetricsOut,
    UpdateUserTierBody,
)
from app.utils.billing_utils import (
    VALID_USER_TIERS,
    build_subscription_metrics_summary,
    normalize_tier,
)
from app.utils.public_utils import (
    MODERATION_STATUS_CLEAN,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_PUBLISHED,
    PUBLIC_STATUS_REMOVED,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    USER_PUBLIC_SHARE_SOURCE_KIND,
    add_moderation_action,
    active_serious_strike_count,
    get_public_share_status,
)
from app.utils.redis_utils import maybe_await

router = APIRouter()


@router.get("/public-shares/pending", response_model=list[PendingPublicShareOut])
async def list_pending_public_shares(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
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


@router.put("/public-shares/{book_id}")
async def review_public_share(
    book_id: uuid.UUID,
    body: PublicShareApprovalBody,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    if book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(409, "This manuscript is not available for public sharing.")

    current_status = get_public_share_status(book)
    if str(book.source_kind or "").strip().lower() != USER_PUBLIC_SHARE_SOURCE_KIND and current_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED:
        raise HTTPException(409, "This manuscript is not in the author public-share workflow.")
    if body.approved:
        if current_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED:
            raise HTTPException(409, "This manuscript does not have a pending public-share request.")
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
async def metrics(db: AsyncSession = Depends(get_db), _=Depends(get_admin)):
    users = (await db.execute(select(func.count()).select_from(User))).scalar()
    books = (await db.execute(select(func.count()).select_from(Book))).scalar()
    chars = (await db.execute(select(func.count()).select_from(Character))).scalar()
    chunks = (await db.execute(select(func.count()).select_from(BookChunk))).scalar()
    summaries = (await db.execute(select(func.count()).select_from(ChapterSummary))).scalar()
    r = await app.core.redis.get_redis()
    mem = await r.info("memory")
    return {
        "users": users, "books": books, "characters": chars,
        "chunks_indexed": chunks, "summaries_cached": summaries,
        "redis_memory_mb": round(mem.get("used_memory", 0) / 1024 / 1024, 2),
    }


@router.get("/subscription-metrics", response_model=SubscriptionMetricsOut)
async def subscription_metrics(
    start_date: date | None = None,
    end_date: date | None = None,
    reactivation_window_days: int = 30,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
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
    return SubscriptionMetricsOut(**summary.__dict__)


@router.get("/queue-depth")
async def queue_depth(_=Depends(get_admin)):
    r = await app.core.redis.get_redis()
    return {
        "extraction": await maybe_await(r.llen("extraction")),
        "analysis": await maybe_await(r.llen("analysis")),
        "embedding": await maybe_await(r.llen("embedding")),
        "intelligence": await maybe_await(r.llen("intelligence")),
    }


@router.get("/rate-limits/{user_id}")
async def get_rate_limit_override(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    override = (
        await db.execute(
            select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
        )
    ).scalars().first()
    return {
        "user_id": str(user_id),
        "email": user.email,
        "override": {
            "search_per_hour": override.search_per_hour if override else None,
            "summary_per_hour": override.summary_per_hour if override else None,
            "chat_per_day": override.chat_per_day if override else None,
            "api_per_minute": override.api_per_minute if override else None,
        },
    }


@router.put("/rate-limits/{user_id}")
async def upsert_rate_limit_override(
    user_id: uuid.UUID,
    body: RateLimitOverrideBody,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    override = (
        await db.execute(
            select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
        )
    ).scalars().first()
    if not override:
        override = UserRateLimitOverride(user_id=user_id)
        db.add(override)

    override.search_per_hour = body.search_per_hour
    override.summary_per_hour = body.summary_per_hour
    override.chat_per_day = body.chat_per_day
    override.api_per_minute = body.api_per_minute
    await db.commit()
    return {"ok": True, "user_id": str(user_id)}


@router.put("/users/{user_id}/tier")
async def update_user_tier(
    user_id: uuid.UUID,
    body: UpdateUserTierBody,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    tier = normalize_tier(body.tier)
    if tier not in VALID_USER_TIERS:
        raise HTTPException(400, f"Invalid tier. Must be one of: {', '.join(sorted(VALID_USER_TIERS))}")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.tier = tier
    await db.commit()
    return {"ok": True, "user_id": str(user_id), "tier": tier}


@router.get("/reports", response_model=list[ContentReportAdminOut])
async def list_content_reports(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    reports = (
        await db.execute(
            select(ContentReport).order_by(ContentReport.created_at.desc())
        )
    ).scalars().all()
    return [
        ContentReportAdminOut(
            id=str(report.id),
            reported_book_id=str(report.reported_book_id),
            reported_author_user_id=str(report.reported_author_user_id) if report.reported_author_user_id else None,
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


@router.post("/books/{book_id}/hide")
async def hide_public_book(
    book_id: uuid.UUID,
    body: AdminBookModerationBody,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin),
):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    previous_status = str(getattr(book, "moderation_status", "") or "") or None
    book.moderation_status = MODERATION_STATUS_HIDDEN
    book.public_status = PUBLIC_STATUS_HIDDEN
    book.is_public = False
    book.takedown_reason = body.reason
    book.takedown_at = datetime.now(UTC)
    book.takedown_by_user_id = admin_user.id
    await add_moderation_action(
        db,
        action_type="book_hidden",
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.moderation_status,
        reason=body.reason,
    )
    await db.commit()
    return {"ok": True, "book_id": str(book.id), "moderation_status": book.moderation_status}


@router.post("/books/{book_id}/remove")
async def remove_public_book(
    book_id: uuid.UUID,
    body: AdminBookModerationBody,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin),
):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    previous_status = str(getattr(book, "moderation_status", "") or "") or None
    book.moderation_status = MODERATION_STATUS_REMOVED
    book.public_status = PUBLIC_STATUS_REMOVED
    book.is_public = False
    book.takedown_reason = body.reason
    book.takedown_at = datetime.now(UTC)
    book.takedown_by_user_id = admin_user.id
    await add_moderation_action(
        db,
        action_type="book_removed",
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.moderation_status,
        reason=body.reason,
    )
    await db.commit()
    return {"ok": True, "book_id": str(book.id), "moderation_status": book.moderation_status}


@router.post("/books/{book_id}/restore")
async def restore_public_book(
    book_id: uuid.UUID,
    body: AdminRestoreBookBody,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin),
):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    previous_status = str(getattr(book, "moderation_status", "") or "") or None
    book.moderation_status = MODERATION_STATUS_CLEAN
    book.public_status = PUBLIC_STATUS_PUBLISHED
    book.is_public = True
    book.takedown_reason = None
    book.takedown_at = None
    book.takedown_by_user_id = None
    await add_moderation_action(
        db,
        action_type="book_restored",
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.moderation_status,
        reason=body.reason,
    )
    await db.commit()
    return {"ok": True, "book_id": str(book.id), "moderation_status": book.moderation_status}


@router.post("/users/{user_id}/strikes", response_model=CreatorStrikeOut)
async def add_creator_strike(
    user_id: uuid.UUID,
    body: CreatorStrikeCreateBody,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    strike = CreatorStrike(
        user_id=user_id,
        book_id=uuid.UUID(body.book_id) if body.book_id else None,
        report_id=uuid.UUID(body.report_id) if body.report_id else None,
        strike_type=body.strike_type,
        severity=body.severity,
        reason=body.reason,
        created_by_user_id=admin_user.id,
        is_active=True,
    )
    db.add(strike)
    await db.flush()
    serious_count = await active_serious_strike_count(db, user_id=user_id)
    await add_moderation_action(
        db,
        action_type="strike_added",
        actor_user_id=admin_user.id,
        target_user_id=user_id,
        book_id=strike.book_id,
        report_id=strike.report_id,
        previous_status=None,
        new_status=f"serious_strikes:{serious_count}",
        reason=body.reason,
        metadata={"severity": body.severity, "strike_type": body.strike_type},
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
