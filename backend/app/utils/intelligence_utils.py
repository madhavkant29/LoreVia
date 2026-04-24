"""
Helper functions for grounded intelligence answers and citations.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.search.semantic import semantic_search
from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread


def build_grounded_citation(
    chapter_num: int,
    chapter_title: str | None,
    excerpt: str,
    source_type: str,
    relevance: float | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "excerpt": excerpt.strip(),
        "source_type": source_type,
    }
    if relevance is not None:
        payload["relevance"] = round(float(relevance), 3)
    return payload


async def build_grounded_qa_context(
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    question: str,
    current_chapter: int,
) -> tuple[list[str], list[dict[str, object]]]:
    summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.content)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book.id,
                Chapter.number <= current_chapter,
                ChapterSummary.mode == "short",
            )
            .order_by(Chapter.number.desc())
            .limit(4)
        )
    ).all()
    semantic_hits = await semantic_search(
        db,
        book.id,
        question,
        current_chapter,
        limit=4,
    )

    context_blocks: list[str] = []
    citations: list[dict[str, object]] = []

    for chapter_num, chapter_title, content in reversed(summary_rows):
        summary_text = (content or "").strip()
        if not summary_text:
            continue
        context_blocks.append(
            f"Chapter {chapter_num}: {chapter_title or 'Untitled'}\nSummary: {summary_text[:500]}"
        )
        citations.append(
            build_grounded_citation(
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                excerpt=summary_text[:240],
                source_type="summary",
            )
        )

    for hit in semantic_hits:
        chapter_num = int(hit["chapter_num"])
        chapter_title = hit.get("chapter_title")
        excerpt = str(hit.get("text") or "").strip()
        if not excerpt:
            continue
        context_blocks.append(
            f"Passage from Chapter {chapter_num}: {chapter_title or 'Untitled'}\n{excerpt[:420]}"
        )
        citations.append(
            build_grounded_citation(
                chapter_num=chapter_num,
                chapter_title=chapter_title if isinstance(chapter_title, str) else None,
                excerpt=excerpt[:240],
                source_type="passage",
                relevance=float(hit.get("relevance") or 0.0),
            )
        )

    series_context = await build_prior_series_context(db, book, user_id)
    if series_context:
        context_blocks = series_context + context_blocks

    deduped_citations: list[dict[str, object]] = []
    seen: set[tuple[int, str, str]] = set()
    for citation in sorted(
        citations,
        key=lambda item: (
            0 if item["source_type"] == "passage" else 1,
            -(float(item.get("relevance") or 0.0)),
            -int(item["chapter_num"]),
        ),
    ):
        key = (
            int(citation["chapter_num"]),
            str(citation["source_type"]),
            str(citation["excerpt"]),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped_citations.append(citation)
        if len(deduped_citations) >= 5:
            break

    return context_blocks, deduped_citations


async def build_prior_series_context(db: AsyncSession, book: Book, user_id: uuid.UUID) -> list[str]:
    if not book.primary_series_id:
        return []

    series_rows = (
        await db.execute(
            select(Book, SeriesBook.position)
            .join(SeriesBook, SeriesBook.book_id == Book.id)
            .where(
                SeriesBook.series_id == book.primary_series_id,
                Book.user_id == user_id,
            )
            .order_by(SeriesBook.position.is_(None), SeriesBook.position, Book.created_at)
        )
    ).all()
    if not series_rows:
        return []

    ordered_books = [row[0] for row in series_rows]
    try:
        current_index = next(index for index, item in enumerate(ordered_books) if item.id == book.id)
    except StopIteration:
        return []

    previous_books = ordered_books[:current_index]
    if not previous_books:
        return []

    context_blocks: list[str] = []
    for prior_book in previous_books[-3:]:
        snapshot = await book_series_snapshot(db, prior_book.id, prior_book.title)
        if snapshot:
            context_blocks.append(snapshot)
    return context_blocks


async def book_series_snapshot(db: AsyncSession, book_id: uuid.UUID, title: str) -> str | None:
    summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "short",
            )
            .order_by(Chapter.number.desc())
            .limit(3)
        )
    ).all()
    character_rows = (
        await db.execute(
            select(Character.name, Character.role, Character.arc_summary)
            .where(Character.book_id == book_id)
            .order_by(Character.first_chapter, Character.name)
            .limit(8)
        )
    ).all()
    relationship_rows = (
        await db.execute(
            select(CharacterRelationship.rel_type, CharacterRelationship.description)
            .where(CharacterRelationship.book_id == book_id)
            .order_by(CharacterRelationship.from_chapter.desc())
            .limit(6)
        )
    ).all()
    thread_rows = (
        await db.execute(
            select(PlotThread.title, PlotThread.description, PlotThread.status)
            .where(PlotThread.book_id == book_id)
            .order_by(PlotThread.importance.desc(), PlotThread.created_at.desc())
            .limit(5)
        )
    ).all()

    blocks: list[str] = [f"Previous volume context: {title}"]

    if summary_rows:
        summary_lines = []
        for chapter_num, chapter_title, content, key_events in reversed(summary_rows):
            summary_lines.append(
                f"Chapter {chapter_num} ({chapter_title or 'Untitled'}): {(content or '')[:320]}"
            )
            event_line = flatten_key_events(key_events)
            if event_line:
                summary_lines.append(f"Key events: {event_line}")
        blocks.append("Story so far:\n" + "\n".join(summary_lines[:6]))

    if character_rows:
        cast = [
            f"{name}{f' ({role})' if role else ''}: {(arc_summary or 'role in progress')[:140]}"
            for name, role, arc_summary in character_rows
            if name
        ]
        if cast:
            blocks.append("Core cast:\n" + "\n".join(cast[:6]))

    if relationship_rows:
        relationship_lines = []
        for rel_type, description in relationship_rows:
            fallback = (rel_type or "connection").replace("_", " ")
            text = (description or fallback).strip()
            if text:
                relationship_lines.append(text[:180])
        if relationship_lines:
            blocks.append("Known relationships:\n" + "\n".join(relationship_lines[:4]))

    if thread_rows:
        thread_lines = []
        for thread_title, description, status in thread_rows:
            thread_lines.append(
                f"{thread_title} [{status or 'unknown'}]: {(description or 'No detail yet.')[:180]}"
            )
        if thread_lines:
            blocks.append("Major plot threads:\n" + "\n".join(thread_lines[:4]))

    if len(blocks) == 1:
        return None
    return "\n\n".join(blocks)


def flatten_key_events(key_events: object) -> str:
    if isinstance(key_events, list):
        items = [str(item).strip() for item in key_events if str(item).strip()]
        return "; ".join(items[:4])
    if isinstance(key_events, dict):
        flattened: list[str] = []
        for value in key_events.values():
            if isinstance(value, list):
                flattened.extend(str(item).strip() for item in value if str(item).strip())
            elif value:
                flattened.append(str(value).strip())
        return "; ".join(flattened[:4])
    return ""
