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

from app.models.book import Book
from app.core.storage import upload_text
from app.utils.book_utils import normalize_writer_workspace, serialize_manuscript_content
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

MEDIA_MARKER_RE = re.compile(r"\[\[IMAGE:[^\]]+\]\]")
READING_CHAPTER_TARGET_WORDS = 7000
READING_CHAPTER_MIN_WORDS = 1200
READING_CHAPTER_MIN_TAIL_WORDS = 2000


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


def build_writer_workspace_with_processing(book: Book, processing_state: dict[str, Any] | None) -> dict:
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    workspace["processing"] = processing_state
    return normalize_writer_workspace(workspace)


def _current_processing_progress(book: Book) -> tuple[int, int | None]:
    workspace = normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)
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
    workspace = normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)
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
) -> dict:
    processing_started_at = started_at or get_processing_started_at(book) or datetime.now(UTC)
    effective_parser_diagnostics = parser_diagnostics if parser_diagnostics is not None else current_parser_diagnostics(book)
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
    return build_writer_workspace_with_processing(book, processing_state)


async def is_book_hidden(db: AsyncSession, book_id: uuid.UUID) -> bool:
    hidden_at = await db.scalar(select(Book.hidden_at).where(Book.id == book_id))
    return hidden_at is not None


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

    if all(re.fullmatch(r"(chapter|part|section|scene|act|book|episode|volume)\s+([0-9]+|[ivxlcdm]+|[a-z])", title) for title in normalized_titles):
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
    normalized = [dict(chapter) for chapter in chapters if _chapter_word_count(chapter) > 0 or chapter.get("images")]
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
    text_parts = [str(chapter.get("text") or "").strip() for chapter in group if str(chapter.get("text") or "").strip()]
    html_parts = [str(chapter.get("html") or "").strip() for chapter in group if str(chapter.get("html") or "").strip()]
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


def _estimate_ingestion_eta_seconds(completed_chapters: int, total_chapters: int | None, elapsed_seconds: float) -> int | None:
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
    status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(exc, "status_code", None)
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
