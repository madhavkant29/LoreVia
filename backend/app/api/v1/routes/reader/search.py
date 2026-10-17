import uuid
from typing import Any

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_search
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_search_results, mark_user_dashboard_cache_dirty
from app.engine.search.semantic import semantic_search
from app.models.book import Book
from app.models.intelligence import QuoteEntry
from app.schemas.reader import SaveQuoteBody
from app.services.reader_search_service import lexical_reader_chunk_search, thematic_reader_search
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.reader_utils import summary_visible_chapter_set

router = APIRouter()

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


@router.get("/{book_id}/search")
async def search(
    book_id: uuid.UUID,
    q: str = Query(...),
    chapter: int | None = Query(None, ge=1, description="Max chapter to search - spoiler gate"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    chapter_limit = chapter if chapter is not None else int(book.total_chapters or 0)
    if not collaboration_allows_chapter(collaborator, chapter_limit):
        raise HTTPException(403, "This share does not include that chapter.")
    if collaborator is None:
        require_author_access(current_user)

    cache_key = key_search_results(f"{current_user.id}:{book_id}", q, chapter_limit)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    results = await semantic_search(
        db,
        book_id,
        q,
        chapter_limit,
        limit=settings.READER_SEARCH_RETURN_CHUNKS,
        candidate_limit=settings.READER_SEARCH_CANDIDATE_CHUNKS,
        similarity_threshold=settings.READER_SEARCH_SIMILARITY_THRESHOLD,
        usage_user_id=current_user.id,
        usage_feature="reader_search",
    )
    if not results:
        results = await lexical_reader_chunk_search(
            db,
            book_id=book_id,
            query=q,
            max_chapter=chapter_limit,
            limit=settings.READER_SEARCH_RETURN_CHUNKS,
        )
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
        return {"results": [], "index_status": "building"}

    return await thematic_reader_search(
        db,
        book_id=book_id,
        visible_chapters=read_set,
        query=q,
    )


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
    await mark_user_dashboard_cache_dirty(str(current_user.id))
    return {"id": str(quote.id), "saved": True}
