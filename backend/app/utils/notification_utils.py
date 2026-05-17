"""
Notification utility helpers for building and storing in-app notifications.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import Notification
from app.models.intelligence import CharacterRelationship, PlotThread
from app.schemas.books import ChapterConsistencyReport
from app.utils.book_utils import build_revision_intelligence_payload, detect_chapter_continuity_flags


@dataclass(frozen=True)
class BookReadyStats:
    character_count: int
    relationship_count: int
    plot_thread_count: int
    continuity_issue_count: int


def make_notification_idempotency_key(*parts: Any) -> str:
    segments = [str(part).strip() for part in parts if str(part).strip()]
    if not segments:
        raise ValueError("Notification idempotency keys require at least one non-empty segment.")
    return ":".join(segments)


async def create_notification_once(
    db: AsyncSession,
    *,
    user_id,
    kind: str,
    title: str,
    body: str,
    idempotency_key: str,
    book_id=None,
    data: dict[str, Any] | None = None,
) -> tuple[Notification, bool]:
    existing = (
        await db.execute(
            select(Notification).where(Notification.idempotency_key == idempotency_key)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    notification = Notification(
        user_id=user_id,
        book_id=book_id,
        kind=kind,
        idempotency_key=idempotency_key,
        title=title,
        body=body,
        data=data,
    )

    try:
        async with db.begin_nested():
            db.add(notification)
            await db.flush()
    except IntegrityError:
        existing = (
            await db.execute(
                select(Notification).where(Notification.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False
        raise

    return notification, True


def _revision_digest_signature(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    active = int(summary.get("active_item_count") or 0)
    high = int(summary.get("high_severity_count") or 0)
    recent_edit_label = str(summary.get("recent_edit_label") or "").strip()
    top_ids = [str(item.get("id") or "") for item in (payload.get("change_impacts") or [])[:3] if isinstance(item, dict)]
    return f"{active}:{high}:{recent_edit_label}:{'|'.join(top_ids)}"


def build_revision_digest_notification(book: Book, payload: dict[str, Any]) -> Notification | None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    active = int(summary.get("active_item_count") or 0)
    high = int(summary.get("high_severity_count") or 0)
    if active <= 0:
        return None
    recent_edit_label = str(summary.get("recent_edit_label") or "").strip() or None
    top_item = next((item for item in (payload.get("change_impacts") or []) if isinstance(item, dict)), None)
    top_title = str(top_item.get("title") or "").strip() if isinstance(top_item, dict) else ""
    title = (
        f"{high} revision risk{'s' if high != 1 else ''} surfaced in {book.title}"
        if high > 0
        else f"{active} revision item{'s' if active != 1 else ''} surfaced in {book.title}"
    )
    body = str(summary.get("hero_message") or "LoreVia surfaced new downstream revision risks.")
    if recent_edit_label:
        body = f"{recent_edit_label} {body}".strip()
    if top_title:
        body = f"{body} Top issue: {top_title}."
    return Notification(
        user_id=book.user_id,
        book_id=book.id,
        kind="revision_digest",
        title=title,
        body=body,
        data={
            "tagline": payload.get("tagline"),
            "hero_message": summary.get("hero_message"),
            "active_item_count": active,
            "high_severity_count": high,
            "task_ready_count": int(summary.get("task_ready_count") or 0),
            "recent_edit_label": recent_edit_label,
            "top_item_title": top_title or None,
            "signature": _revision_digest_signature(payload),
        },
    )


def build_chapter_report_notification(
    book: Book,
    report: ChapterConsistencyReport,
) -> Notification | None:
    noteworthy_count = (
        len(report.new_characters)
        + len(report.relationship_changes)
        + len(report.plot_threads_opened)
        + len(report.continuity_flags)
    )
    if noteworthy_count == 0:
        return None

    if report.new_characters:
        names = ", ".join(character.name for character in report.new_characters[:4])
        extra = len(report.new_characters) - 4
        if extra > 0:
            names = f"{names}, and {extra} more"
        title = f"{len(report.new_characters)} new character{'s' if len(report.new_characters) != 1 else ''} detected in Chapter {report.chapter_number}"
        body = f"{names}. Review their extracted profiles and the latest chapter report."
    else:
        title = f"Chapter {report.chapter_number} consistency report ready"
        body = report.summary

    return Notification(
        user_id=book.user_id,
        book_id=book.id,
        kind="chapter_report",
        title=title,
        body=body,
        data={
            "chapter_number": report.chapter_number,
            "chapter_title": report.chapter_title,
            "book_title": book.title,
            "summary": report.summary,
            "new_characters": [character.model_dump() for character in report.new_characters],
            "relationship_changes": report.relationship_changes,
            "plot_threads_opened": report.plot_threads_opened,
            "plot_threads_resolved": report.plot_threads_resolved,
            "continuity_flags": report.continuity_flags,
        },
    )


def build_continuity_risk_notifications(
    book: Book,
    report: ChapterConsistencyReport,
) -> list[Notification]:
    notifications: list[Notification] = []
    for flag in report.continuity_flags[:2]:
        notifications.append(
            Notification(
                user_id=book.user_id,
                book_id=book.id,
                kind="continuity_risk",
                title="Readers might notice an inconsistency",
                body=flag,
                data={
                    "chapter_number": report.chapter_number,
                    "chapter_title": report.chapter_title,
                    "book_title": book.title,
                    "summary": report.summary,
                },
            )
        )
    return notifications


def build_upload_processing_notification(
    book: Book,
    mode: str,
    file_size_bytes: int,
) -> Notification:
    """Build a notification to inform users about upload processing time."""
    # Estimate processing time based on file size
    size_mb = file_size_bytes / (1024 * 1024)
    if size_mb < 5:
        estimated_minutes = 5
    elif size_mb < 20:
        estimated_minutes = 7
    else:
        estimated_minutes = "10-15"

    if mode == "author":
        title = "Your novel is being processed"
        body = f"This will take approximately {estimated_minutes} minute{'s' if isinstance(estimated_minutes, int) and estimated_minutes != 1 else ''}. Sit back and relax!"
    else:
        title = "Your book is being processed"
        body = f"This will take approximately {estimated_minutes} minute{'s' if isinstance(estimated_minutes, int) and estimated_minutes != 1 else ''}. Sit back and relax!"

    return Notification(
        user_id=book.user_id,
        book_id=book.id,
        kind="upload_processing",
        title=title,
        body=body,
        data={
            "book_title": book.title,
            "mode": mode,
            "estimated_minutes": estimated_minutes,
            "file_size_mb": round(size_mb, 2),
        },
    )


async def collect_book_ready_stats(db: AsyncSession, book: Book) -> BookReadyStats:
    character_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Character).where(Character.book_id == book.id)
            )
        ).scalar_one()
    )
    relationship_count = int(
        (
            await db.execute(
                select(func.count()).select_from(CharacterRelationship).where(CharacterRelationship.book_id == book.id)
            )
        ).scalar_one()
    )
    plot_thread_count = int(
        (
            await db.execute(
                select(func.count()).select_from(PlotThread).where(PlotThread.book_id == book.id)
            )
        ).scalar_one()
    )

    continuity_issue_count = 0
    chapter_rows = (
        await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )
    ).all()
    for (chapter_number,) in chapter_rows:
        continuity_issue_count += len(await detect_chapter_continuity_flags(db, book.id, chapter_number))

    return BookReadyStats(
        character_count=character_count,
        relationship_count=relationship_count,
        plot_thread_count=plot_thread_count,
        continuity_issue_count=continuity_issue_count,
    )


def build_book_ready_notification(book: Book, stats: BookReadyStats) -> Notification:
    return Notification(
        user_id=book.user_id,
        book_id=book.id,
        kind="book_ready",
        title=f"{book.title} is ready",
        body=(
            f"We found {stats.character_count} characters, mapped {stats.relationship_count} relationships, "
            f"identified {stats.plot_thread_count} plot threads, and flagged {stats.continuity_issue_count} continuity issues."
        ),
        data={
            "book_title": book.title,
            "character_count": stats.character_count,
            "relationship_count": stats.relationship_count,
            "plot_thread_count": stats.plot_thread_count,
            "continuity_issue_count": stats.continuity_issue_count,
        },
    )


async def sync_revision_digest_notifications(db: AsyncSession, user_id, *, limit: int = 6) -> None:
    books = (
        await db.execute(
            select(Book)
            .where(Book.user_id == user_id, Book.mode == "author", Book.status == "ready")
            .order_by(Book.created_at.desc())
            .limit(max(1, min(limit, 10)))
        )
    ).scalars().all()
    if not books:
        return

    existing = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id, Notification.kind == "revision_digest")
            .order_by(Notification.created_at.desc())
        )
    ).scalars().all()
    latest_by_book_id: dict[str, Notification] = {}
    for notification in existing:
        key = str(notification.book_id) if notification.book_id else ""
        if key and key not in latest_by_book_id:
            latest_by_book_id[key] = notification

    now = datetime.now(UTC)
    changed = False
    for book in books:
        payload = await build_revision_intelligence_payload(db, book)
        latest = latest_by_book_id.get(str(book.id))
        next_notification = build_revision_digest_notification(book, payload)
        if next_notification is None:
            if latest is not None and latest.read_at is None:
                latest.read_at = now
                changed = True
            continue
        next_signature = str((next_notification.data or {}).get("signature") or "")
        current_signature = str((latest.data or {}).get("signature") or "") if latest is not None and isinstance(latest.data, dict) else ""
        if latest is not None and current_signature == next_signature:
            continue
        if latest is not None and latest.read_at is None:
            latest.read_at = now
        db.add(next_notification)
        changed = True

    if changed:
        await db.commit()
