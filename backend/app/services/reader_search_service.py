"""Bounded, persisted search workflows for reader-facing endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.search.semantic import build_search_result, summarize_search_text
from app.models.book import Chapter
from app.models.intelligence import BookChunk, ChapterSummary

THEMATIC_SEARCH_LIMIT = 20


def _normalized_search_query(query: str) -> str:
    return " ".join((query or "").split()).strip()


def _search_terms(query: str) -> list[str]:
    return [term for term in _normalized_search_query(query).lower().split() if len(term) >= 3]


def _visible_chapter_numbers(chapters: Iterable[int]) -> list[int]:
    numbers: set[int] = set()
    for chapter in chapters:
        try:
            number = int(chapter)
        except (TypeError, ValueError):
            continue
        if number > 0:
            numbers.add(number)
    return sorted(numbers)


def _chunk_search_vector() -> Any:
    return func.to_tsvector("simple", BookChunk.text)


async def lexical_reader_chunk_search(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    query: str,
    max_chapter: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return bounded lexical chunk matches using the persisted GIN text index."""
    search_query = _normalized_search_query(query)
    if not search_query:
        return []

    bounded_limit = max(1, int(limit))
    vector = _chunk_search_vector()
    tsquery = func.websearch_to_tsquery("simple", search_query)
    rank = func.ts_rank_cd(vector, tsquery)
    rows = (
        await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title, rank)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(
                BookChunk.book_id == book_id,
                Chapter.number <= max_chapter,
                vector.op("@@")(tsquery),
            )
            .order_by(rank.desc(), Chapter.number.asc(), BookChunk.chunk_index.asc())
            .limit(bounded_limit)
        )
    ).all()
    if not rows:
        rows = await _broaden_chunk_search(
            db,
            book_id=book_id,
            max_chapter=max_chapter,
            search_terms=_search_terms(search_query),
            limit=bounded_limit,
        )
    return [
        build_search_result(
            text=row[0],
            chunk_index=row[1],
            chapter_num=row[2],
            chapter_title=row[3],
            relevance=float(row[4] or 0.0),
        )
        for row in rows
    ]


async def thematic_reader_search(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    visible_chapters: Iterable[int],
    query: str,
    limit: int = THEMATIC_SEARCH_LIMIT,
) -> dict[str, Any]:
    """Search persisted summaries, then indexed chunks, without object-storage fallback."""
    chapter_numbers = _visible_chapter_numbers(visible_chapters)
    search_query = _normalized_search_query(query)
    if not chapter_numbers or not search_query:
        return {"results": [], "index_status": "building"}

    bounded_limit = max(1, min(int(limit), THEMATIC_SEARCH_LIMIT))
    terms = _search_terms(search_query)
    summary_rows = (
        await db.execute(
            select(
                Chapter.number,
                Chapter.title,
                ChapterSummary.content,
                ChapterSummary.key_events,
                ChapterSummary.clues,
            )
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                Chapter.number.in_(chapter_numbers),
                ChapterSummary.mode.in_(["short", "detailed"]),
            )
            .order_by(Chapter.number)
        )
    ).all()
    results = _thematic_summary_matches(summary_rows, search_query=search_query, terms=terms)
    indexed_chapter_count = int(
        await db.scalar(
            select(func.count(func.distinct(BookChunk.chapter_id)))
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(BookChunk.book_id == book_id, Chapter.number.in_(chapter_numbers))
        )
        or 0
    )
    has_indexed_chunks = indexed_chapter_count > 0
    index_ready = indexed_chapter_count >= len(chapter_numbers)
    if not results and has_indexed_chunks:
        results = await _thematic_chunk_matches(
            db,
            book_id=book_id,
            chapter_numbers=chapter_numbers,
            search_query=search_query,
            terms=terms,
            limit=bounded_limit,
        )
    results.sort(key=lambda item: (-float(item["score"]), int(item["chapter_number"])))
    return {
        "results": results[:bounded_limit],
        "index_status": "ready" if index_ready else "building",
    }


async def _broaden_chunk_search(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    max_chapter: int,
    search_terms: list[str],
    limit: int,
) -> list[Any]:
    if not search_terms:
        return []
    vector = _chunk_search_vector()
    term_queries = [func.plainto_tsquery("simple", term) for term in search_terms]
    rank = func.greatest(*[func.ts_rank_cd(vector, term_query) for term_query in term_queries])
    return (
        await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title, rank)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(
                BookChunk.book_id == book_id,
                Chapter.number <= max_chapter,
                or_(*[vector.op("@@")(term_query) for term_query in term_queries]),
            )
            .order_by(rank.desc(), Chapter.number.asc(), BookChunk.chunk_index.asc())
            .limit(limit)
        )
    ).all()


def _thematic_summary_matches(
    rows: Iterable[tuple[Any, ...]],
    *,
    search_query: str,
    terms: list[str],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    normalized_query = search_query.lower()
    for chapter_number, chapter_title, content, key_events, clues in rows:
        haystacks = [str(content or "")]
        haystacks.extend(
            str(event.get("event") or "") for event in (key_events or []) if isinstance(event, dict)
        )
        haystacks.extend(
            str(clue.get("clue") or "") for clue in (clues or []) if isinstance(clue, dict)
        )
        haystack = " ".join(haystacks).lower()
        score = sum(1 for term in terms if term in haystack)
        if not score and normalized_query in haystack:
            score = 1
        if score:
            matches.append(
                {
                    "chapter_number": int(chapter_number),
                    "chapter_title": chapter_title,
                    "score": score,
                    "summary": content,
                }
            )
    return matches


async def _thematic_chunk_matches(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_numbers: list[int],
    search_query: str,
    terms: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    vector = _chunk_search_vector()
    tsquery = func.websearch_to_tsquery("simple", search_query)
    rank = func.ts_rank_cd(vector, tsquery)
    rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, BookChunk.text, rank)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(
                BookChunk.book_id == book_id,
                Chapter.number.in_(chapter_numbers),
                vector.op("@@")(tsquery),
            )
            .order_by(rank.desc(), Chapter.number.asc(), BookChunk.chunk_index.asc())
            .limit(limit)
        )
    ).all()
    if not rows and terms:
        term_queries = [func.plainto_tsquery("simple", term) for term in terms]
        fallback_rank = func.greatest(
            *[func.ts_rank_cd(vector, term_query) for term_query in term_queries]
        )
        rows = (
            await db.execute(
                select(Chapter.number, Chapter.title, BookChunk.text, fallback_rank)
                .join(Chapter, Chapter.id == BookChunk.chapter_id)
                .where(
                    BookChunk.book_id == book_id,
                    Chapter.number.in_(chapter_numbers),
                    or_(*[vector.op("@@")(term_query) for term_query in term_queries]),
                )
                .order_by(fallback_rank.desc(), Chapter.number.asc(), BookChunk.chunk_index.asc())
                .limit(limit)
            )
        ).all()
    matches_by_chapter: dict[int, dict[str, Any]] = {}
    for chapter_number, chapter_title, text, score in rows:
        numeric_chapter = int(chapter_number)
        numeric_score = float(score or 0.0)
        current = matches_by_chapter.get(numeric_chapter)
        if current is None or numeric_score > float(current["score"]):
            matches_by_chapter[numeric_chapter] = {
                "chapter_number": numeric_chapter,
                "chapter_title": chapter_title,
                "score": numeric_score,
                "summary": summarize_search_text(str(text or ""), max_length=320),
            }
    return list(matches_by_chapter.values())
