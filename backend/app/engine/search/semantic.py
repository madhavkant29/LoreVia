"""
Semantic search over book chunks using pgvector.
Spoiler-gated to user's current chapter.
"""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.engine.embeddings.embedder import embed_text

log = logging.getLogger(__name__)


def _pgvector_extension_missing(exc: ProgrammingError) -> bool:
    return 'type "vector" does not exist' in str(getattr(exc, "orig", exc)).lower()


def summarize_search_text(text: str, max_length: int = 180) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    sentences = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
    candidate = sentences[0] if sentences else cleaned
    if len(candidate) <= max_length:
        return candidate
    shortened = candidate[:max_length].rsplit(" ", 1)[0].strip()
    return f"{shortened}..."


def build_search_result(
    text: str,
    chunk_index: int,
    chapter_num: int,
    chapter_title: str | None,
    relevance: float,
) -> dict:
    excerpt = text[:300] + ("..." if len(text) > 300 else "")
    return {
        "text": excerpt,
        "summary": summarize_search_text(text),
        "chunk_index": chunk_index,
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "relevance": round(float(relevance), 3),
    }


async def semantic_search(
    db: AsyncSession,
    book_id: uuid.UUID,
    query: str,
    max_chapter: int,
    limit: int = settings.SEARCH_MAX_CONTEXT_CHUNKS,
    *,
    candidate_limit: int | None = None,
    similarity_threshold: float | None = None,
    usage_user_id: uuid.UUID,
    usage_feature: str = "semantic_search_query",
) -> list[dict]:
    """
    Embed query → cosine similarity search over book_chunks.
    Returns ranked results with chapter reference, spoiler-gated.
    """
    query_embedding = await embed_text(
        query,
        db=db,
        user_id=usage_user_id,
        book_id=book_id,
        feature=usage_feature,
    )

    final_limit = max(1, int(limit))
    retrieval_limit = max(final_limit, int(candidate_limit or final_limit))
    threshold = float(
        settings.SEARCH_SIMILARITY_THRESHOLD
        if similarity_threshold is None
        else similarity_threshold
    )

    try:
        rows = await db.execute(
            text("""
                WITH nearest AS MATERIALIZED (
                    SELECT
                        bc.text,
                        bc.chunk_index,
                        ch.number AS chapter_num,
                        ch.title AS chapter_title,
                        bc.embedding <=> CAST(:emb AS vector) AS distance
                    FROM book_chunks bc
                    JOIN chapters ch ON ch.id = bc.chapter_id
                    WHERE bc.book_id = :bid
                      AND ch.number <= :max_ch
                      AND bc.embedding IS NOT NULL
                    ORDER BY bc.embedding <=> CAST(:emb AS vector) ASC
                    LIMIT :lim
                )
                SELECT
                    text,
                    chunk_index,
                    chapter_num,
                    chapter_title,
                    1 - distance AS relevance
                FROM nearest
                WHERE 1 - distance > :thr
                ORDER BY distance ASC
            """),
            {
                "emb": str(query_embedding),
                "bid": str(book_id),
                "max_ch": max_chapter,
                "thr": threshold,
                "lim": retrieval_limit,
            },
        )
    except ProgrammingError as exc:
        if _pgvector_extension_missing(exc):
            log.warning(
                "semantic_search_pgvector_unavailable book_id=%s max_chapter=%s",
                book_id,
                max_chapter,
            )
            return []
        raise

    results = []
    for row in rows.fetchall():
        results.append(
            build_search_result(
                text=row.text,
                chunk_index=row.chunk_index,
                chapter_num=row.chapter_num,
                chapter_title=row.chapter_title,
                relevance=row.relevance,
            )
        )
    return results[:final_limit]


async def hybrid_story_search(
    db: AsyncSession,
    book_id: uuid.UUID,
    query: str,
    max_chapter: int,
    limit: int = settings.SEARCH_MAX_CONTEXT_CHUNKS,
    *,
    candidate_limit: int | None = None,
    similarity_threshold: float | None = None,
    usage_user_id: uuid.UUID,
    usage_feature: str = "hybrid_story_search",
) -> list[dict]:
    """Combine lexical and vector candidates, then rerank with chapter chronology."""
    final_limit = max(1, int(limit))
    retrieval_limit = max(final_limit * 3, int(candidate_limit or 0))
    semantic_hits = await semantic_search(
        db,
        book_id,
        query,
        max_chapter,
        limit=retrieval_limit,
        candidate_limit=retrieval_limit,
        similarity_threshold=similarity_threshold,
        usage_user_id=usage_user_id,
        usage_feature=usage_feature,
    )
    lexical_rows = await db.execute(
        text(
            """
            SELECT
                bc.text,
                bc.chunk_index,
                ch.number AS chapter_num,
                ch.title AS chapter_title,
                ts_rank_cd(
                    to_tsvector('simple', bc.text),
                    plainto_tsquery('simple', :query)
                ) AS relevance
            FROM book_chunks bc
            JOIN chapters ch ON ch.id = bc.chapter_id
            WHERE bc.book_id = :bid
              AND ch.number <= :max_ch
              AND to_tsvector('simple', bc.text) @@ plainto_tsquery('simple', :query)
            ORDER BY relevance DESC, ch.number ASC
            LIMIT :lim
            """
        ),
        {
            "query": query[:1600],
            "bid": str(book_id),
            "max_ch": max_chapter,
            "lim": retrieval_limit,
        },
    )
    combined: dict[tuple[int, int], dict] = {}
    for hit in semantic_hits:
        key = (int(hit["chapter_num"]), int(hit["chunk_index"]))
        combined[key] = {
            **hit,
            "vector_relevance": float(hit.get("relevance") or 0),
            "lexical_relevance": 0.0,
        }
    for row in lexical_rows.fetchall():
        key = (int(row.chapter_num), int(row.chunk_index))
        current = combined.get(key)
        lexical_relevance = min(1.0, max(0.0, float(row.relevance or 0)))
        if current is None:
            current = build_search_result(
                text=row.text,
                chunk_index=row.chunk_index,
                chapter_num=row.chapter_num,
                chapter_title=row.chapter_title,
                relevance=lexical_relevance,
            )
            current["vector_relevance"] = 0.0
            combined[key] = current
        current["lexical_relevance"] = lexical_relevance

    candidates = []
    for hit in combined.values():
        chronology = 1 / (1 + abs(max_chapter - int(hit["chapter_num"])))
        score = (
            float(hit.get("vector_relevance") or 0) * 0.65
            + float(hit.get("lexical_relevance") or 0) * 0.3
            + chronology * 0.05
        )
        candidates.append({**hit, "score": round(score, 4), "relevance": round(score, 4)})

    selected: list[dict] = []
    remaining = list(candidates)
    seen_chapters: set[int] = set()
    while remaining and len(selected) < final_limit:
        remaining.sort(
            key=lambda item: (
                -(
                    float(item["score"])
                    + (0.04 if int(item["chapter_num"]) not in seen_chapters else 0)
                ),
                int(item["chapter_num"]),
            )
        )
        chosen = remaining.pop(0)
        selected.append(chosen)
        seen_chapters.add(int(chosen["chapter_num"]))
    return selected


async def find_context_for_tap(
    db: AsyncSession,
    book_id: uuid.UUID,
    query: str,
    max_chapter: int,
    *,
    usage_user_id: uuid.UUID,
) -> list[dict]:
    """Used for Smart Tap — returns top 3 most relevant context snippets."""
    return await semantic_search(
        db,
        book_id,
        query,
        max_chapter,
        limit=settings.SEARCH_MAX_CONTEXT_CHUNKS,
        usage_user_id=usage_user_id,
        usage_feature="reader_smart_tap",
    )
