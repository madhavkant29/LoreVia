"""
Semantic search over book chunks using pgvector.
Spoiler-gated to user's current chapter.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.engine.embeddings.embedder import embed_text
from app.core.config import settings
import uuid


async def semantic_search(
    db: AsyncSession,
    book_id: uuid.UUID,
    query: str,
    max_chapter: int,
    limit: int = settings.SEARCH_MAX_CONTEXT_CHUNKS,
) -> list[dict]:
    """
    Embed query → cosine similarity search over book_chunks.
    Returns ranked results with chapter reference, spoiler-gated.
    """
    query_embedding = await embed_text(query)

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
        results.append({
            "text": row.text[:300] + ("..." if len(row.text) > 300 else ""),
            "chunk_index": row.chunk_index,
            "chapter_num": row.chapter_num,
            "chapter_title": row.chapter_title,
            "relevance": round(float(row.relevance), 3),
        })
    return results


async def find_context_for_tap(
    db: AsyncSession,
    book_id: uuid.UUID,
    query: str,
    max_chapter: int,
) -> list[dict]:
    """Used for Smart Tap — returns top 3 most relevant context snippets."""
    return await semantic_search(db, book_id, query, max_chapter, limit=settings.SEARCH_MAX_CONTEXT_CHUNKS)
