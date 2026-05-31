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
from app.models.intelligence import ChapterSummary, Notification
from app.models.intelligence import CharacterRelationship, PlotThread
from app.schemas.books import ChapterConsistencyReport
from app.utils.book_utils import build_revision_intelligence_payload, detect_chapter_continuity_flags


@dataclass(frozen=True)
class BookReadyStats:
    character_count: int
    relationship_count: int
    plot_thread_count: int
    continuity_issue_count: int
    chapter_count: int
    analyzed_chapter_count: int

    @property
    def analysis_complete(self) -> bool:
        return self.chapter_count > 0 and self.analyzed_chapter_count >= self.chapter_count


def _compose_book_ready_title(book: Book, stats: BookReadyStats) -> str:
    return f"{book.title} is ready" if stats.analysis_complete else f"{book.title} finished processing"


def _character_extraction_failures(book: Book) -> int:
    raw_workspace = getattr(book, "writer_workspace", None)
    workspace = raw_workspace if isinstance(raw_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    parser_diagnostics = processing.get("parser_diagnostics") if isinstance(processing, dict) else {}
    extraction = parser_diagnostics.get("character_extraction") if isinstance(parser_diagnostics, dict) else {}
    failed_batches = extraction.get("failed_batches") if isinstance(extraction, dict) else 0
    return int(failed_batches or 0)


def _analysis_pipeline_status(book: Book) -> str:
    raw_workspace = getattr(book, "writer_workspace", None)
    workspace = raw_workspace if isinstance(raw_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    pipeline = processing.get("pipeline") if isinstance(processing.get("pipeline"), dict) else {}
    analysis = pipeline.get("analysis") if isinstance(pipeline.get("analysis"), dict) else {}
    return " ".join(str(analysis.get("status") or "").split()).strip() or "pending"


def _book_ready_diagnostic_totals(book: Book) -> tuple[int, int]:
    raw_workspace = getattr(book, "writer_workspace", None)
    workspace = raw_workspace if isinstance(raw_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    parser_diagnostics = processing.get("parser_diagnostics") if isinstance(processing, dict) else {}
    extraction = parser_diagnostics.get("character_extraction") if isinstance(parser_diagnostics, dict) else {}
    totals = extraction.get("totals") if isinstance(extraction.get("totals"), dict) else {}
    return (
        int(totals.get("saved_characters") or 0),
        int(totals.get("relationships_persisted") or 0),
    )


def _compose_book_ready_body(book: Book, stats: BookReadyStats) -> str:
    extraction_failures = _character_extraction_failures(book)
    analysis_status = _analysis_pipeline_status(book)
    if stats.analysis_complete:
        if stats.character_count == 0 and extraction_failures > 0:
            return (
                "LoreVia finished the analysis pass, but character extraction hit an internal error and did not save "
                "reliable character results for this book yet."
            )
        total_findings = (
            stats.character_count
            + stats.relationship_count
            + stats.plot_thread_count
            + stats.continuity_issue_count
        )
        if total_findings == 0:
            return (
                "LoreVia finished the analysis pass, but it did not save any characters, relationships, "
                "plot threads, or continuity issues for this book yet."
            )
        return (
            f"We found {stats.character_count} characters, mapped {stats.relationship_count} relationships, "
            f"identified {stats.plot_thread_count} plot threads, and flagged {stats.continuity_issue_count} continuity issues."
        )

    if analysis_status == "failed":
        return (
            "LoreVia finished processing this book, but part of the analysis pipeline failed. "
            "Saved extraction results are available now, and the failed analysis chapters can be retried."
        )

    saved_findings: list[str] = []
    if stats.character_count > 0:
        saved_findings.append(f"{stats.character_count} character{'s' if stats.character_count != 1 else ''}")
    if stats.relationship_count > 0:
        saved_findings.append(
            f"{stats.relationship_count} relationship{'s' if stats.relationship_count != 1 else ''}"
        )

    if saved_findings:
        saved_summary = " and ".join(saved_findings[:2])
        return (
            f"LoreVia finished processing this book and has already saved {saved_summary}. "
            "Plot-thread and continuity analysis is still running, so deeper results will appear once that finishes."
        )

    if extraction_failures > 0:
        return (
            "LoreVia finished processing this book, but character extraction hit an internal issue before it could save "
            "reliable character results. LoreVia will keep showing the rest of the analysis once it is ready."
        )

    return (
        "LoreVia finished processing this book, but the story-intelligence pass is still running. "
        "Character, relationship, plot-thread, and continuity results will appear here once they are ready."
    )


def _build_book_ready_data(book: Book, stats: BookReadyStats) -> dict[str, Any]:
    analysis_status = _analysis_pipeline_status(book)
    data: dict[str, Any] = {
        "book_title": book.title,
        "analysis_complete": stats.analysis_complete,
        "analysis_status": analysis_status,
        "chapter_count": stats.chapter_count,
        "analyzed_chapter_count": stats.analyzed_chapter_count,
    }
    if stats.analysis_complete or stats.character_count > 0:
        data["character_count"] = stats.character_count
    if stats.analysis_complete or stats.relationship_count > 0:
        data["relationship_count"] = stats.relationship_count
    if stats.analysis_complete:
        data["plot_thread_count"] = stats.plot_thread_count
        data["continuity_issue_count"] = stats.continuity_issue_count
    elif analysis_status == "failed":
        data["retry_actions"] = ["retry_analysis"]
    return data


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
    chapter_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id)
            )
        ).scalar_one()
    )
    analyzed_chapter_count = int(
        (
            await db.execute(
                select(func.count(func.distinct(ChapterSummary.chapter_id)))
                .select_from(ChapterSummary)
                .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
                .where(
                    Chapter.book_id == book.id,
                    ChapterSummary.mode == "detailed",
                )
            )
        ).scalar_one()
    )
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
    diagnostic_character_count, diagnostic_relationship_count = _book_ready_diagnostic_totals(book)
    character_count = max(character_count, diagnostic_character_count)
    relationship_count = max(relationship_count, diagnostic_relationship_count)
    plot_thread_count = int(
        (
            await db.execute(
                select(func.count()).select_from(PlotThread).where(PlotThread.book_id == book.id)
            )
        ).scalar_one()
    )

    continuity_issue_count = 0
    if chapter_count > 0 and analyzed_chapter_count >= chapter_count:
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
        chapter_count=chapter_count,
        analyzed_chapter_count=analyzed_chapter_count,
    )


def build_book_ready_notification(book: Book, stats: BookReadyStats) -> Notification:
    return Notification(
        user_id=book.user_id,
        book_id=book.id,
        kind="book_ready",
        title=_compose_book_ready_title(book, stats),
        body=_compose_book_ready_body(book, stats),
        data=_build_book_ready_data(book, stats),
    )


async def upsert_book_ready_notification(
    db: AsyncSession,
    book: Book,
    stats: BookReadyStats | None = None,
) -> tuple[Notification, bool]:
    next_stats = stats or await collect_book_ready_stats(db, book)
    payload = build_book_ready_notification(book, next_stats)
    existing = (
        await db.execute(
            select(Notification).where(
                Notification.book_id == book.id,
                Notification.user_id == book.user_id,
                Notification.kind == "book_ready",
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(payload)
        return payload, True

    existing.title = payload.title
    existing.body = payload.body
    existing.data = payload.data
    return existing, False


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
    stale_notifications: list[Notification] = []
    for notification in existing:
        key = str(notification.book_id) if notification.book_id else ""
        if not key:
            continue
        if key not in latest_by_book_id:
            latest_by_book_id[key] = notification
            continue
        stale_notifications.append(notification)

    now = datetime.now(UTC)
    changed = False
    for notification in stale_notifications:
        await db.delete(notification)
        changed = True

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
        if latest is None:
            db.add(next_notification)
            changed = True
            continue
        latest.title = next_notification.title
        latest.body = next_notification.body
        latest.data = next_notification.data
        latest.read_at = None
        changed = True

    if changed:
        await db.commit()
