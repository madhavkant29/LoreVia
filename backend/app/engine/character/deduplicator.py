import re
import uuid
from collections.abc import Iterable

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.embeddings.embedder import embed_character
from app.models.character import Character


async def embed_for_dedup(name: str, traits: dict) -> list[float]:
    return await embed_character(name, traits)


def normalize_character_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def character_name_keys(name: str | None, aliases: Iterable[str] | None = None) -> set[str]:
    keys: set[str] = set()

    def _add(candidate: str | None) -> None:
        normalized = normalize_character_name(candidate)
        if not normalized:
            return
        keys.add(normalized)
        tokens = normalized.split()
        if len(tokens) >= 2:
            keys.add(" ".join(tokens[:2]))
        if len(tokens) >= 2:
            keys.add(f"{tokens[0]} {tokens[-1]}")
        if len(tokens) >= 3:
            keys.add(" ".join(tokens[:3]))

    _add(name)
    for alias in aliases or []:
        _add(alias)
    return keys


def names_equivalent(
    left_name: str | None,
    left_aliases: Iterable[str] | None,
    right_name: str | None,
    right_aliases: Iterable[str] | None,
) -> bool:
    left_keys = character_name_keys(left_name, left_aliases)
    right_keys = character_name_keys(right_name, right_aliases)
    if left_keys & right_keys:
        return True

    left_norm = normalize_character_name(left_name)
    right_norm = normalize_character_name(right_name)
    if not left_norm or not right_norm:
        return False

    left_tokens = left_norm.split()
    right_tokens = right_norm.split()

    if (left_norm.startswith(right_norm) or right_norm.startswith(left_norm)) and min(len(left_tokens), len(right_tokens)) >= 2:
        return True

    if left_tokens and right_tokens and left_tokens[0] == right_tokens[0]:
        if len(left_tokens) >= 2 and len(right_tokens) >= 2 and left_tokens[1] == right_tokens[1]:
            return True
        if left_tokens[-1] == right_tokens[-1]:
            return True

    return False


async def find_similar(
    db: AsyncSession, book_id: uuid.UUID, embedding: list[float], threshold: float = 0.88
) -> uuid.UUID | None:
    result = await db.execute(
        text("""
            SELECT id, 1 - (embedding <=> CAST(:emb AS vector)) AS sim
            FROM characters
            WHERE book_id = :bid
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> CAST(:emb AS vector)) > :thr
            ORDER BY sim DESC LIMIT 1
        """),
        {"emb": str(embedding), "bid": str(book_id), "thr": threshold},
    )
    row = result.fetchone()
    return uuid.UUID(str(row[0])) if row else None


async def find_by_name_or_alias(
    db: AsyncSession,
    book_id: uuid.UUID,
    name: str,
    aliases: Iterable[str] | None = None,
) -> uuid.UUID | None:
    candidate_keys = character_name_keys(name, aliases)
    if not candidate_keys:
        return None

    result = await db.execute(
        select(Character.id, Character.name, Character.aliases).where(Character.book_id == book_id)
    )

    for char_id, char_name, char_aliases in result.all():
        if candidate_keys & character_name_keys(char_name, char_aliases or []):
            return char_id
        if names_equivalent(name, aliases, char_name, char_aliases or []):
            return char_id
    return None


async def merge_alias(db: AsyncSession, character_id: uuid.UUID, alias: str) -> None:
    await db.execute(
        text("""
            UPDATE characters
            SET aliases = array_append(COALESCE(aliases, ARRAY[]::text[]), :alias)
            WHERE id = :cid
              AND NOT (:alias = ANY(COALESCE(aliases, ARRAY[]::text[])))
              AND lower(name) != lower(:alias)
        """),
        {"cid": str(character_id), "alias": alias},
    )
    await db.commit()
