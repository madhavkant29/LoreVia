from __future__ import annotations

import asyncio
import math
import re
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book, upload_text
from app.models.book import Book, Chapter
from app.models.user import User
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
    serialize_manuscript_content,
)
from app.utils.books.processing import (
    normalize_processing_timestamp,
)
from app.utils.books.writer_workspace import (
    normalize_writer_workspace,
)
from app.utils.logging.errors import redact_sensitive_text
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS

MEDIA_MARKER_RE = re.compile(r"\[\[IMAGE:[^\]]+\]\]")
READING_CHAPTER_TARGET_WORDS = 7000
READING_CHAPTER_MIN_WORDS = 1200
READING_CHAPTER_MIN_TAIL_WORDS = 2000
ANALYSIS_INFLIGHT_TTL_SECONDS = 20 * 60  # Must exceed analysis time_limit (15 min) by >= 5 min
EXTRACTION_INFLIGHT_TTL_SECONDS = 30 * 60  # Must exceed extraction time_limit (25 min) by >= 5 min
CHAPTER_RECOVERY_INFLIGHT_TTL_SECONDS = 15 * 60
LLM_USAGE_LIMIT_RETRY_SECONDS = 30 * 60
LLM_USAGE_LIMIT_MAX_RETRIES = 10


@dataclass(frozen=True)
class ChapterDispatch:
    chapter_number: int
    countdown: int


def build_chapter_storage_key(book_id: uuid.UUID, chapter_number: int) -> str:
    return f"chapters/{book_id}/{chapter_number}.txt"


def build_chapter_dispatch_plan(
    chapter_numbers: Sequence[int],
    *,
    eager_limit: int,
    dispatch_window: int,
    dispatch_delay_seconds: int,
) -> list[ChapterDispatch]:
    if not chapter_numbers:
        return []

    normalized_eager_limit = max(0, eager_limit)
    normalized_window = max(1, dispatch_window)
    normalized_delay = max(0, dispatch_delay_seconds)

    plan: list[ChapterDispatch] = []
    for index, chapter_number in enumerate(chapter_numbers):
        if index < normalized_eager_limit:
            countdown = 0
        else:
            window_index = ((index - normalized_eager_limit) // normalized_window) + 1
            countdown = window_index * normalized_delay
        plan.append(ChapterDispatch(chapter_number=chapter_number, countdown=countdown))
    return plan


async def persist_chapter_payloads(
    book_id: uuid.UUID,
    chapters: Sequence[Mapping[str, Any]],
    *,
    concurrency: int,
) -> dict[int, str]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _store(chapter: Mapping[str, Any]) -> tuple[int, str]:
        chapter_number = int(chapter["number"])
        storage_key = build_chapter_storage_key(book_id, chapter_number)
        payload = serialize_manuscript_content(
            str(chapter.get("text") or ""),
            chapter.get("html"),
        )
        async with semaphore:
            stored_key = await asyncio.to_thread(upload_text, storage_key, payload)
        return chapter_number, stored_key

    stored_pairs = await asyncio.gather(*(_store(chapter) for chapter in chapters))
    return dict(stored_pairs)


async def load_staged_chapter_payload(
    book_id: uuid.UUID,
    chapter_number: int,
    *,
    chapter_s3_key: str | None = None,
) -> dict[str, str | None] | None:
    candidate_keys: list[str] = []
    normalized_key = " ".join(str(chapter_s3_key or "").split()).strip()
    if normalized_key:
        candidate_keys.append(normalized_key)

    fallback_key = build_chapter_storage_key(book_id, chapter_number)
    if fallback_key not in candidate_keys:
        candidate_keys.append(fallback_key)

    for storage_key in candidate_keys:
        try:
            raw = await asyncio.to_thread(download_book, storage_key)
        except STORAGE_IO_EXCEPTIONS:
            continue
        return deserialize_manuscript_content(raw)

    return None


async def load_processing_chapter_payload(
    book_id: uuid.UUID,
    chapter_number: int,
    *,
    chapter_s3_key: str | None = None,
    chapter_title: str | None = None,
) -> dict[str, Any] | None:
    """Load chapter processing input from chapter storage only."""
    stored_payload = await load_staged_chapter_payload(
        book_id,
        chapter_number,
        chapter_s3_key=chapter_s3_key,
    )
    if not stored_payload:
        return None

    chapter_text = str(stored_payload.get("text") or "").strip()
    if not chapter_text:
        return None

    return {
        "number": chapter_number,
        "title": " ".join(str(chapter_title or "").split()).strip() or None,
        "text": chapter_text,
        "html": stored_payload.get("html"),
    }


async def load_analysis_chapter_payload(
    db: AsyncSession,
    chapter_id: str,
    *,
    book_id: str | None = None,
) -> dict[str, Any] | None:
    """Load stored chapter text/title for analysis task execution."""
    chapter = await db.get(Chapter, uuid.UUID(str(chapter_id)))
    if chapter is None:
        return None
    if book_id and str(chapter.book_id) != str(book_id):
        return None

    payload = await load_processing_chapter_payload(
        chapter.book_id,
        chapter.number,
        chapter_s3_key=chapter.s3_key,
        chapter_title=chapter.title,
    )
    if payload is None:
        return None
    return {
        "chapter_id": str(chapter.id),
        "text": payload["text"],
        "title": payload.get("title") or "",
    }


def build_ingestion_progress_state(
    *,
    status: str,
    stage: str,
    total_chapters: int | None,
    completed_chapters: int,
    started_at: datetime,
    queue_wait_ms: int | None = None,
    chapter_number: int | None = None,
    chapter_title: str | None = None,
    last_error: str | None = None,
    parser_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    completed = max(0, completed_chapters)
    total = total_chapters if isinstance(total_chapters, int) and total_chapters > 0 else None
    progress_pct = round((completed / total) * 100, 1) if total else None
    elapsed_seconds = max((now - started_at).total_seconds(), 0.0)
    eta_seconds = _estimate_ingestion_eta_seconds(completed, total, elapsed_seconds)

    payload: dict[str, Any] = {
        "status": " ".join(str(status or "").split()).strip() or "processing",
        "stage": " ".join(str(stage or "").split()).strip() or "processing",
        "chapters_completed": completed,
        "started_at": started_at.isoformat(),
        "updated_at": now.isoformat(),
    }
    if total is not None:
        payload["chapters_total"] = total
    if progress_pct is not None:
        payload["progress_pct"] = progress_pct
    if eta_seconds is not None:
        payload["eta_seconds"] = eta_seconds
    if queue_wait_ms is not None and queue_wait_ms >= 0:
        payload["queue_wait_ms"] = int(queue_wait_ms)
    if chapter_number is not None and chapter_number > 0:
        payload["last_chapter_number"] = int(chapter_number)
    if chapter_title:
        payload["last_chapter_title"] = " ".join(str(chapter_title).split()).strip()
    if last_error:
        payload["last_error"] = " ".join(str(last_error).split()).strip()
    if parser_diagnostics:
        payload["parser_diagnostics"] = parser_diagnostics
    return payload


def _clean_pipeline_stage(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    source = raw if isinstance(raw, dict) else {}
    payload: dict[str, Any] = {}
    status = " ".join(str(source.get("status") or "").split()).strip()
    if status:
        payload["status"] = status
    completed = source.get("completed_chapters")
    if isinstance(completed, (int, float)) and int(completed) >= 0:
        payload["completed_chapters"] = int(completed)
    total = source.get("total_chapters")
    if isinstance(total, (int, float)) and int(total) >= 0:
        payload["total_chapters"] = int(total)
    updated_at = source.get("updated_at")
    if updated_at:
        normalized_updated_at = normalize_processing_timestamp(updated_at)
        if normalized_updated_at:
            payload["updated_at"] = normalized_updated_at
    eta_seconds = source.get("eta_seconds")
    if isinstance(eta_seconds, (int, float)) and int(eta_seconds) >= 0:
        payload["eta_seconds"] = int(eta_seconds)
    last_error = " ".join(str(source.get("last_error") or "").split()).strip()
    if last_error:
        payload["last_error"] = last_error
    failed_chapters = source.get("failed_chapters")
    if isinstance(failed_chapters, Sequence) and not isinstance(failed_chapters, (str, bytes)):
        payload["failed_chapters"] = [
            int(item)
            for item in failed_chapters
            if isinstance(item, (int, float)) and int(item) > 0
        ]
    return payload or None


def _derive_retry_actions(pipeline: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    extraction = pipeline.get("extraction") if isinstance(pipeline.get("extraction"), dict) else {}
    analysis = pipeline.get("analysis") if isinstance(pipeline.get("analysis"), dict) else {}
    if extraction.get("status") == "failed":
        actions.append("retry_extraction")
    if analysis.get("status") == "failed":
        actions.append("retry_analysis")
    if analysis.get("status") in {"pending", "running", "queued"}:
        actions.append("wait_for_analysis")
    return actions


def merge_processing_pipeline(
    processing_state: dict[str, Any],
    *,
    extraction: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_processing = dict(processing_state)
    current_pipeline = (
        next_processing.get("pipeline") if isinstance(next_processing.get("pipeline"), dict) else {}
    )
    pipeline: dict[str, Any] = {}

    current_extraction = _clean_pipeline_stage(current_pipeline.get("extraction"))
    current_analysis = _clean_pipeline_stage(current_pipeline.get("analysis"))
    next_extraction = (
        _clean_pipeline_stage(extraction) if extraction is not None else current_extraction
    )
    next_analysis = _clean_pipeline_stage(analysis) if analysis is not None else current_analysis

    if next_extraction:
        pipeline["extraction"] = next_extraction
    if next_analysis:
        pipeline["analysis"] = next_analysis

    extraction_status = ((next_extraction or {}).get("status") or "").strip().lower()
    analysis_status = ((next_analysis or {}).get("status") or "").strip().lower()
    next_processing["pipeline"] = pipeline or None
    next_processing["is_fully_ready"] = (
        extraction_status == "succeeded" and analysis_status == "succeeded"
    )
    next_processing["retry_actions"] = _derive_retry_actions(pipeline)
    return next_processing


def build_analysis_chapter_state(
    existing: dict[str, Any] | None,
    *,
    status: str,
    generated_modes: Sequence[str] | None = None,
    last_error: str | None = None,
    increment_attempt: bool = False,
    source_integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = dict(existing) if isinstance(existing, dict) else {}
    attempts = int(current.get("attempt_count") or 0)
    current_modes = [
        str(mode).strip() for mode in (current.get("generated_modes") or []) if str(mode).strip()
    ]
    next_modes = list(
        dict.fromkeys(
            [
                *current_modes,
                *[str(mode).strip() for mode in (generated_modes or []) if str(mode).strip()],
            ]
        )
    )
    payload: dict[str, Any] = {
        "status": " ".join(str(status or "").split()).strip() or "pending",
        "generated_modes": next_modes,
        "attempt_count": attempts + (1 if increment_attempt else 0),
        "last_error": " ".join((redact_sensitive_text(str(last_error or "")) or "").split()).strip()
        or None,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    next_source_integrity = (
        source_integrity if isinstance(source_integrity, dict) else current.get("source_integrity")
    )
    if isinstance(next_source_integrity, dict):
        payload["source_integrity"] = next_source_integrity
    return payload


def build_source_integrity_state(
    *,
    text_present: bool,
    media_marker_count: int,
    stored_media_count: int,
    recovery_status: str,
    last_recovery_error: str | None = None,
) -> dict[str, Any]:
    payload = {
        "text_present": bool(text_present),
        "media_marker_count": max(0, int(media_marker_count or 0)),
        "stored_media_count": max(0, int(stored_media_count or 0)),
        "recovery_status": " ".join(str(recovery_status or "").split()).strip() or "ok",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if last_recovery_error:
        payload["last_recovery_error"] = " ".join(str(last_recovery_error).split()).strip()
    return payload


def build_writer_workspace_with_processing(
    book: Book, processing_state: dict[str, Any] | None
) -> dict:
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    workspace["processing"] = processing_state
    return normalize_writer_workspace(workspace)


def processing_state_for_completed_extraction(*, analysis_complete: bool) -> tuple[str, str]:
    if analysis_complete:
        return "ready", "complete"
    return "processing", "analysis"


def _current_processing_progress(book: Book) -> tuple[int, int | None]:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = workspace.get("processing") if isinstance(workspace, dict) else None
    completed_chapters = 0
    total_chapters = book.total_chapters

    if isinstance(processing, dict):
        completed_value = processing.get("chapters_completed")
        if isinstance(completed_value, (int, float)) and int(completed_value) >= 0:
            completed_chapters = int(completed_value)

        total_value = processing.get("chapters_total")
        if isinstance(total_value, (int, float)) and int(total_value) > 0:
            total_chapters = int(total_value)

    return completed_chapters, total_chapters


def current_parser_diagnostics(book: Book) -> dict[str, Any] | None:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = workspace.get("processing") if isinstance(workspace, dict) else None
    if not isinstance(processing, dict):
        return None
    diagnostics = processing.get("parser_diagnostics")
    return diagnostics if isinstance(diagnostics, dict) else None


def update_book_processing_state(
    book: Book,
    *,
    status: str,
    stage: str,
    total_chapters: int | None,
    completed_chapters: int,
    started_at: datetime | None = None,
    queue_wait_ms: int | None = None,
    chapter_number: int | None = None,
    chapter_title: str | None = None,
    last_error: str | None = None,
    parser_diagnostics: dict[str, Any] | None = None,
    progress_pct: float | None = None,
) -> dict:
    processing_started_at = started_at or get_processing_started_at(book) or datetime.now(UTC)
    effective_parser_diagnostics = (
        parser_diagnostics if parser_diagnostics is not None else current_parser_diagnostics(book)
    )
    processing_state = build_ingestion_progress_state(
        status=status,
        stage=stage,
        total_chapters=total_chapters,
        completed_chapters=completed_chapters,
        started_at=processing_started_at,
        queue_wait_ms=queue_wait_ms,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        last_error=last_error,
        parser_diagnostics=effective_parser_diagnostics,
    )
    if isinstance(progress_pct, (int, float)) and math.isfinite(float(progress_pct)):
        processing_state["progress_pct"] = round(max(0.0, min(100.0, float(progress_pct))), 1)
    workspace = book.writer_workspace if isinstance(book.writer_workspace, dict) else {}
    current_processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    active_rebuild_run_id = (
        current_processing.get("rebuild_run_id") if isinstance(current_processing, dict) else None
    )
    if active_rebuild_run_id:
        processing_state["rebuild_run_id"] = str(active_rebuild_run_id)
    extraction_status = "running"
    if status == "ready" or stage == "analysis":
        extraction_status = "succeeded"
    elif status in {"failed", "error"}:
        extraction_status = "failed"
    elif stage == "queued":
        extraction_status = "queued"
    processing_state = merge_processing_pipeline(
        processing_state,
        extraction={
            "status": extraction_status,
            "completed_chapters": completed_chapters,
            "total_chapters": total_chapters,
            "updated_at": processing_state.get("updated_at"),
            "eta_seconds": processing_state.get("eta_seconds"),
            "last_error": processing_state.get("last_error"),
        },
    )
    return build_writer_workspace_with_processing(book, processing_state)


async def is_book_hidden(db: AsyncSession, book_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(Book.hidden_at, User.deletion_status, User.deleted_at)
            .join(User, User.id == Book.user_id)
            .where(Book.id == book_id)
        )
    ).first()
    if not row:
        return True
    hidden_at, deletion_status, deleted_at = row
    return (
        hidden_at is not None or (deletion_status or "active") != "active" or deleted_at is not None
    )


async def mark_book_processing_cancelled(
    db: AsyncSession,
    book: Book,
    *,
    stage: str,
    rollback: bool = False,
    queue_wait_ms: int | None = None,
    chapter_number: int | None = None,
    chapter_title: str | None = None,
    last_error: str | None = None,
) -> None:
    if rollback:
        await db.rollback()
    completed_chapters, total_chapters = _current_processing_progress(book)
    book.status = "failed"
    book.writer_workspace = update_book_processing_state(
        book,
        status="failed",
        stage="cancelled",
        total_chapters=total_chapters,
        completed_chapters=completed_chapters,
        started_at=get_processing_started_at(book),
        queue_wait_ms=queue_wait_ms,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        last_error=last_error or f"Book was removed while processing at {stage} stage.",
        parser_diagnostics=current_parser_diagnostics(book),
    )
    from app.services.editor_project_service import fail_rebuild_if_active

    await fail_rebuild_if_active(
        db, book, error=last_error or f"Book was removed while processing at {stage} stage."
    )
    await db.commit()


def get_processing_started_at(book: Book) -> datetime | None:
    workspace = book.writer_workspace if isinstance(book.writer_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace, dict) else None
    if not isinstance(processing, dict):
        return None

    started_at = processing.get("started_at")
    if isinstance(started_at, datetime):
        return started_at
    if isinstance(started_at, str) and started_at.strip():
        try:
            parsed = datetime.fromisoformat(started_at.strip())
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def elapsed_ms(start: float, end: float | None = None) -> int:
    stop = time.perf_counter() if end is None else end
    return int((stop - start) * 1000)


def extract_queue_wait_ms(headers: Mapping[str, Any] | None) -> int | None:
    if not headers:
        return None

    enqueued_at = headers.get("enqueued_at")
    if enqueued_at in (None, ""):
        return None

    try:
        enqueued_at_float = float(enqueued_at)
    except (TypeError, ValueError):
        return None

    wait_ms = int(max(0.0, (time.time() - enqueued_at_float) * 1000))
    return wait_ms


def chunked(items: Iterable[str], batch_size: int) -> list[list[str]]:
    normalized_batch_size = max(1, batch_size)
    batches: list[list[str]] = []
    current_batch: list[str] = []

    for item in items:
        current_batch.append(item)
        if len(current_batch) >= normalized_batch_size:
            batches.append(current_batch)
            current_batch = []

    if current_batch:
        batches.append(current_batch)

    return batches


def apply_chapter_number_strategy(
    chapters: Sequence[Mapping[str, Any]],
    *,
    preserve_chapter_numbers: bool,
    generic_titles: bool = False,
) -> list[dict[str, Any]]:
    normalized = [dict(chapter) for chapter in chapters]
    if not normalized:
        return []

    if not preserve_chapter_numbers:
        if generic_titles and _should_regroup_before_renumbering(normalized):
            normalized = regroup_prose_chapters_for_reading(normalized)
        return _renumber_sequentially(normalized, generic_titles=generic_titles)

    source_numbers: list[int] = []
    for chapter in normalized:
        source_number = chapter.get("source_number")
        if not isinstance(source_number, int) or source_number < 1:
            return _renumber_sequentially(normalized, generic_titles=generic_titles)
        source_numbers.append(source_number)

    expected_numbers = list(range(1, len(source_numbers) + 1))
    if source_numbers != expected_numbers:
        return _renumber_sequentially(normalized, generic_titles=generic_titles)

    for chapter, source_number in zip(normalized, source_numbers):
        chapter["number"] = source_number
    return normalized


def _should_regroup_before_renumbering(chapters: Sequence[Mapping[str, Any]]) -> bool:
    normalized_titles = [
        " ".join(str(chapter.get("title") or "").split()).strip().lower()
        for chapter in chapters
        if " ".join(str(chapter.get("title") or "").split()).strip()
    ]
    if len(normalized_titles) < 2:
        return False

    if all(
        re.fullmatch(
            r"(chapter|part|section|scene|act|book|episode|volume)\s+([0-9]+|[ivxlcdm]+|[a-z])",
            title,
        )
        for title in normalized_titles
    ):
        return True

    repeated_bases: dict[str, int] = {}
    for title in normalized_titles:
        match = re.fullmatch(r"(?P<base>.+?)\s+([0-9]+|[ivxlcdm]+|[a-z])", title)
        if not match:
            continue
        base = match.group("base").strip()
        if not base:
            continue
        repeated_bases[base] = repeated_bases.get(base, 0) + 1

    return any(count >= 2 for count in repeated_bases.values())


def _renumber_sequentially(
    chapters: Sequence[Mapping[str, Any]],
    *,
    generic_titles: bool,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters, start=1):
        next_chapter = dict(chapter)
        next_chapter["number"] = index
        if generic_titles:
            next_chapter["title"] = f"Chapter {index}"
        normalized.append(next_chapter)
    return normalized


def regroup_prose_chapters_for_reading(
    chapters: Sequence[Mapping[str, Any]],
    *,
    target_words: int = READING_CHAPTER_TARGET_WORDS,
    min_chapter_words: int = READING_CHAPTER_MIN_WORDS,
    min_tail_words: int = READING_CHAPTER_MIN_TAIL_WORDS,
) -> list[dict[str, Any]]:
    normalized = [
        dict(chapter)
        for chapter in chapters
        if _chapter_word_count(chapter) > 0 or chapter.get("images")
    ]
    if not normalized:
        return []

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_words = 0

    for chapter in normalized:
        chapter_words = _chapter_word_count(chapter)
        should_close_group = (
            current_group
            and current_words >= max(1, min_chapter_words)
            and current_words + chapter_words > max(1, target_words)
            and _chapter_ends_naturally(current_group[-1])
        )
        if should_close_group:
            groups.append(current_group)
            current_group = []
            current_words = 0

        current_group.append(chapter)
        current_words += chapter_words

    if current_group:
        groups.append(current_group)

    if len(groups) >= 2 and _group_word_count(groups[-1]) < max(1, min_tail_words):
        groups[-2].extend(groups.pop())

    return [_merge_chapter_group(group) for group in groups]


def _merge_chapter_group(group: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    merged = dict(group[0])
    text_parts = [
        str(chapter.get("text") or "").strip()
        for chapter in group
        if str(chapter.get("text") or "").strip()
    ]
    html_parts = [
        str(chapter.get("html") or "").strip()
        for chapter in group
        if str(chapter.get("html") or "").strip()
    ]
    image_parts: list[Any] = []
    for chapter in group:
        image_parts.extend(list(chapter.get("images") or []))

    merged["text"] = "\n\n".join(text_parts)
    if html_parts:
        merged["html"] = "\n\n".join(html_parts)
    elif "html" in merged:
        merged["html"] = None
    merged["images"] = image_parts
    merged["source_number"] = None
    return merged


def _group_word_count(group: Sequence[Mapping[str, Any]]) -> int:
    return sum(_chapter_word_count(chapter) for chapter in group)


def _chapter_word_count(chapter: Mapping[str, Any]) -> int:
    text = MEDIA_MARKER_RE.sub(" ", str(chapter.get("text") or ""))
    return len(re.findall(r"\b[\w']+\b", text))


def _chapter_ends_naturally(chapter: Mapping[str, Any]) -> bool:
    text = str(chapter.get("text") or "")
    cleaned = MEDIA_MARKER_RE.sub(" ", text).strip()
    if not cleaned:
        return False
    return bool(re.search(r"[.!?][\"')\]]*\s*$", cleaned))


def _estimate_ingestion_eta_seconds(
    completed_chapters: int, total_chapters: int | None, elapsed_seconds: float
) -> int | None:
    if not total_chapters or total_chapters <= 0:
        return None

    remaining = max(total_chapters - completed_chapters, 0)
    if remaining == 0:
        return 0
    if completed_chapters <= 0 or elapsed_seconds <= 0:
        return None

    average_seconds = elapsed_seconds / completed_chapters
    return max(0, int(math.ceil(average_seconds * remaining)))


def is_retryable_processing_error(exc: BaseException) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(
        exc, "status_code", None
    )
    if isinstance(status_code, int) and status_code in {408, 425, 429, 500, 502, 503, 504}:
        return True

    message = str(exc).lower()
    retryable_markers = (
        "timeout",
        "timed out",
        "rate limit",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "broken pipe",
        "service unavailable",
        "gateway timeout",
    )
    return any(marker in message for marker in retryable_markers)


def is_llm_usage_limit_error(exc: BaseException) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(
        exc, "status_code", None
    )
    if status_code != 429:
        return False

    detail = getattr(exc, "detail", None)
    message = " ".join(str(detail if detail is not None else exc).lower().split())
    return "token limit exceeded" in message and "window" in message


def is_llm_coordination_retry_error(exc: BaseException) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(
        exc, "status_code", None
    )
    if status_code not in {429, 503}:
        return False
    detail = getattr(exc, "detail", None)
    message = " ".join(str(detail if detail is not None else exc).lower().split())
    return "llm capacity" in message or "llm coordination" in message
