from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.engine.embeddings.embedder import embed_text
from app.models.book import Book
from app.utils.advisor_prompt_templates import (
    WORLD_ADVISOR_QUERY_TERMS,
    WORLD_GAP_QUERY_TERMS,
    WORLD_INTEGRATION_QUERY_TERMS,
)
from app.utils.world_building_utils import build_world_logic_response, classify_world_intent

log = logging.getLogger(__name__)


def detect_advisor_world_mode(message: str, intent: str | None = None) -> str | None:
    """Return the world-analysis mode when an advisor question is lore-focused."""
    text_value = (message or "").strip().lower()
    if not text_value:
        return None
    has_world_signal = any(term in text_value for term in WORLD_ADVISOR_QUERY_TERMS)
    if not has_world_signal:
        return None
    if intent in {"plothole", "consistency"} or any(
        term in text_value for term in WORLD_GAP_QUERY_TERMS
    ):
        return "gap_detection"
    if any(term in text_value for term in WORLD_INTEGRATION_QUERY_TERMS):
        return "story_integration"
    return classify_world_intent(message)


def advisor_retrieval_settings(
    intent: str | None, world_mode: str | None = None
) -> tuple[int, float]:
    if intent in {"consistency", "plothole"} or world_mode:
        return (
            settings.ADVISOR_CONTINUITY_SEARCH_CHUNKS,
            settings.ADVISOR_CONTINUITY_SEARCH_SIMILARITY_THRESHOLD,
        )
    return (
        settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
        settings.ADVISOR_GENERAL_SEARCH_SIMILARITY_THRESHOLD,
    )


async def retrieve_series_continuity_passages(
    *,
    db: AsyncSession,
    prior_book_ids: list[uuid.UUID],
    query: str,
    similarity_threshold: float | None = None,
    candidate_limit: int | None = None,
    return_limit: int | None = None,
    user_id: uuid.UUID,
    book_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    if not prior_book_ids:
        return []

    query_emb = await embed_text(
        query,
        db=db,
        user_id=user_id,
        book_id=book_id,
        feature="series_continuity_query_embedding",
    )
    threshold = (
        settings.SERIES_CONTINUITY_SEARCH_SIMILARITY_THRESHOLD
        if similarity_threshold is None
        else float(similarity_threshold)
    )
    retrieval_limit = (
        settings.SERIES_CONTINUITY_SEARCH_CANDIDATE_CHUNKS
        if candidate_limit is None
        else int(candidate_limit)
    )
    final_limit = (
        settings.SERIES_CONTINUITY_SEARCH_RETURN_CHUNKS
        if return_limit is None
        else int(return_limit)
    )
    retrieval_statement = text("""
        SELECT bc.text, ch.number AS chapter_num, ch.title AS chapter_title,
               b.title AS book_title,
               1 - (bc.embedding <=> CAST(:emb AS vector)) AS relevance
        FROM book_chunks bc
        JOIN chapters ch ON ch.id = bc.chapter_id
        JOIN books b ON b.id = bc.book_id
        WHERE bc.book_id IN :prior_book_ids
          AND bc.embedding IS NOT NULL
          AND 1 - (bc.embedding <=> CAST(:emb AS vector)) > :threshold
        ORDER BY relevance DESC
        LIMIT :lim
    """).bindparams(bindparam("prior_book_ids", expanding=True))
    try:
        rows = await db.execute(
            retrieval_statement,
            {
                "emb": str(query_emb),
                "prior_book_ids": prior_book_ids,
                "threshold": threshold,
                "lim": retrieval_limit,
            },
        )
    except ProgrammingError as exc:
        if 'type "vector" does not exist' in str(getattr(exc, "orig", exc)).lower():
            log.warning(
                "series_continuity_pgvector_unavailable book_id=%s prior_books=%s",
                book_id,
                [str(item) for item in prior_book_ids],
            )
            return []
        raise
    return [
        {
            "text": row.text,
            "chapter_num": row.chapter_num,
            "chapter_title": row.chapter_title,
            "book_title": row.book_title,
            "relevance": round(float(row.relevance), 3),
        }
        for row in rows.fetchall()[:final_limit]
    ]


async def build_advisor_world_analysis(
    db: AsyncSession,
    book: Book,
    query: str,
    mode: str,
) -> dict[str, Any]:
    """Run the world-building analyzer for advisor chat questions."""
    return await build_world_logic_response(db, book, query, mode)
