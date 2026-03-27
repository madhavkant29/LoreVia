from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.engine.embeddings.embedder import embed_character
import uuid


async def embed_for_dedup(name: str, traits: dict) -> list[float]:
    return await embed_character(name, traits)


async def find_similar(
    db: AsyncSession, book_id: uuid.UUID, embedding: list[float], threshold: float = 0.88
) -> uuid.UUID | None:
    result = await db.execute(
        text("""
            SELECT id, 1 - (embedding <=> :emb::vector) AS sim
            FROM characters
            WHERE book_id = :bid
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> :emb::vector) > :thr
            ORDER BY sim DESC LIMIT 1
        """),
        {"emb": str(embedding), "bid": str(book_id), "thr": threshold},
    )
    row = result.fetchone()
    return uuid.UUID(str(row[0])) if row else None


async def merge_alias(db: AsyncSession, character_id: uuid.UUID, alias: str) -> None:
    await db.execute(
        text("""
            UPDATE characters
            SET aliases = array_append(COALESCE(aliases, ARRAY[]::text[]), :alias)
            WHERE id = :cid
              AND NOT (:alias = ANY(COALESCE(aliases, ARRAY[]::text[])))
              AND name != :alias
        """),
        {"cid": str(character_id), "alias": alias},
    )
    await db.commit()
