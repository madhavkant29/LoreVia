import uuid
from typing import Any

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_search
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_search_results
from app.core.storage import download_book
from app.engine.search.semantic import build_search_result, semantic_search
from app.models.book import Book, Chapter
from app.models.intelligence import BookChunk, ChapterSummary, QuoteEntry
from app.schemas.reader import SaveQuoteBody
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.reader_utils import summary_visible_chapter_set
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS

router = APIRouter()

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


@router.get("/{book_id}/search")
async def search(
    book_id: uuid.UUID,
    q: str = Query(...),
    chapter: int = Query(..., description="Max chapter to search — spoiler gate"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter):
        raise HTTPException(403, "This share does not include that chapter.")
    if collaborator is None:
        require_author_access(current_user)

    cache_key = key_search_results(f"{current_user.id}:{book_id}", q, chapter)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    results = await semantic_search(
        db,
        book_id,
        q,
        chapter,
        limit=settings.READER_SEARCH_RETURN_CHUNKS,
        candidate_limit=settings.READER_SEARCH_CANDIDATE_CHUNKS,
        similarity_threshold=settings.READER_SEARCH_SIMILARITY_THRESHOLD,
        usage_user_id=current_user.id,
        usage_feature="reader_search",
    )
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (
            await db.execute(
                select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
                .join(Chapter, Chapter.id == BookChunk.chapter_id)
                .where(
                    BookChunk.book_id == book_id,
                    Chapter.number <= chapter,
                    BookChunk.text.ilike(f"%{lowered}%"),
                )
                .limit(settings.READER_SEARCH_RETURN_CHUNKS)
            )
        ).all()
        results = [
            build_search_result(
                text=row[0],
                chunk_index=row[1],
                chapter_num=row[2],
                chapter_title=row[3],
                relevance=0.5,
            )
            for row in lexical_rows
        ]
    if not results:
        terms = [term for term in q.strip().split() if len(term) >= 3]
        if terms:
            token_filters = [BookChunk.text.ilike(f"%{term}%") for term in terms]
            token_rows = (
                await db.execute(
                    select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
                    .join(Chapter, Chapter.id == BookChunk.chapter_id)
                    .where(
                        BookChunk.book_id == book_id, Chapter.number <= chapter, or_(*token_filters)
                    )
                    .limit(settings.READER_SEARCH_RETURN_CHUNKS)
                )
            ).all()
            results = [
                build_search_result(
                    text=row[0],
                    chunk_index=row[1],
                    chapter_num=row[2],
                    chapter_title=row[3],
                    relevance=0.35,
                )
                for row in token_rows
            ]
    await cache_set(cache_key, results, settings.REDIS_TTL_SEARCH)
    return results


@router.get("/{book_id}/thematic-search")
async def thematic_search(
    book_id: uuid.UUID,
    q: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is None:
        require_author_access(current_user)

    read_set = await summary_visible_chapter_set(db, book, current_user, collaborator)
    if collaborator is not None:
        read_set = {
            chapter for chapter in read_set if collaboration_allows_chapter(collaborator, chapter)
        }
    if not read_set:
        return {"results": []}

    normalized_query = q.strip().lower()
    terms = [term for term in normalized_query.split() if len(term) >= 3]
    if not terms and normalized_query:
        terms = [normalized_query]
    rows = (
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
                Chapter.number.in_(sorted(read_set)),
                ChapterSummary.mode.in_(["short", "detailed"]),
            )
            .order_by(Chapter.number)
        )
    ).all()

    results = []
    for chapter_num, chapter_title, content, key_events, clues in rows:
        haystacks = [content or ""]
        haystacks.extend(
            event.get("event", "") for event in (key_events or []) if isinstance(event, dict)
        )
        haystacks.extend(clue.get("clue", "") for clue in (clues or []) if isinstance(clue, dict))
        haystack_text = " ".join(haystacks).lower()
        score = sum(1 for term in terms if term in haystack_text)
        if not score and normalized_query and normalized_query in haystack_text:
            score = 1
        if score:
            results.append(
                {
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title,
                    "score": score,
                    "summary": content,
                }
            )
    if not results:
        chapter_rows = (
            await db.execute(
                select(Chapter.number, Chapter.title, Chapter.s3_key)
                .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)))
                .order_by(Chapter.number)
            )
        ).all()
        for chapter_num, chapter_title, s3_key in chapter_rows:
            if not s3_key:
                continue
            try:
                chapter_text = download_book(s3_key).decode("utf-8", errors="ignore")
            except STORAGE_IO_EXCEPTIONS:
                continue
            normalized_text = chapter_text.lower()
            score = sum(1 for term in terms if term in normalized_text)
            if not score and normalized_query and normalized_query in normalized_text:
                score = 1
            if not score:
                continue
            results.append(
                {
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title,
                    "score": score,
                    "summary": chapter_text[:320] + ("..." if len(chapter_text) > 320 else ""),
                }
            )
    results.sort(key=lambda item: (-item["score"], item["chapter_number"]))
    return {"results": results[:20]}


@router.post("/{book_id}/quotes")
async def save_quote(
    book_id: uuid.UUID,
    body: SaveQuoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)
    quote_text = _clean_text(body.quote_text)
    if not quote_text:
        raise HTTPException(400, "Quote text is required")
    character_name = _clean_text(body.character_name) or None
    note_text = _clean_text(body.note) or None

    quote = QuoteEntry(
        user_id=current_user.id,
        book_id=book_id,
        chapter_number=body.chapter_number,
        character_name=character_name,
        quote_text=quote_text,
        note=note_text,
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return {"id": str(quote.id), "saved": True}
