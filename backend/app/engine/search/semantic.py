"""
Semantic search over book chunks using pgvector.
Spoiler-gated to user's current chapter.
"""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.engine.embeddings.embedder import embed_text


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
    usage_user_id: uuid.UUID | None = None,
    usage_feature: str = "semantic_search_query",
) -> list[dict]:
    """
    Embed query → cosine similarity search over book_chunks.
    Returns ranked results with chapter reference, spoiler-gated.
    """
    query_embedding = await embed_text(
        query,
        user_id=usage_user_id,
        book_id=book_id,
        feature=usage_feature,
    )

    rows = await db.execute(
        text("""
            SELECT
                bc.text,
                bc.chunk_index,
                ch.number  AS chapter_num,
                ch.title   AS chapter_title,
                1 - (bc.embedding <=> CAST(:emb AS vector)) AS relevance
            FROM book_chunks bc
            JOIN chapters ch ON ch.id = bc.chapter_id
            WHERE bc.book_id = :bid
              AND ch.number <= :max_ch
              AND bc.embedding IS NOT NULL
              AND 1 - (bc.embedding <=> CAST(:emb AS vector)) > :thr
            ORDER BY relevance DESC
            LIMIT :lim
        """),
        {
            "emb": str(query_embedding),
            "bid": str(book_id),
            "max_ch": max_chapter,
            "thr": settings.SEARCH_SIMILARITY_THRESHOLD,
            "lim": limit,
        },
    )

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
    return results


async def find_context_for_tap(
    db: AsyncSession,
    book_id: uuid.UUID,
    query: str,
    max_chapter: int,
) -> list[dict]:
    """Used for Smart Tap — returns top 3 most relevant context snippets."""
    return await semantic_search(db, book_id, query, max_chapter, limit=settings.SEARCH_MAX_CONTEXT_CHUNKS)
