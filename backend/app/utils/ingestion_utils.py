from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.storage import upload_text
from app.utils.book_utils import serialize_manuscript_content


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
) -> list[dict[str, Any]]:
    normalized = [dict(chapter) for chapter in chapters]
    if not normalized:
        return []

    if not preserve_chapter_numbers:
        return _renumber_sequentially(normalized)

    source_numbers: list[int] = []
    for chapter in normalized:
        source_number = chapter.get("source_number")
        if not isinstance(source_number, int) or source_number < 1:
            return _renumber_sequentially(normalized)
        source_numbers.append(source_number)

    expected_numbers = list(range(1, len(source_numbers) + 1))
    if source_numbers != expected_numbers:
        return _renumber_sequentially(normalized)

    for chapter, source_number in zip(normalized, source_numbers):
        chapter["number"] = source_number
    return normalized


def _renumber_sequentially(chapters: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters, start=1):
        next_chapter = dict(chapter)
        next_chapter["number"] = index
        normalized.append(next_chapter)
    return normalized
