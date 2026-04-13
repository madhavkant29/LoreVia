import re
import uuid
from collections.abc import Iterable

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.embeddings.embedder import embed_character
from app.models.character import Character

ALIAS_STOPWORDS = {
    "after", "and", "are", "around", "association", "but", "considering", "creation",
    "faculty", "for", "from", "having", "his", "however", "just", "lady", "leaving",
    "let", "looking", "lord", "lords", "maybe", "miss", "now", "once", "regardless",
    "seeing", "she", "sure", "taking", "thanks", "that", "the", "they", "thinking",
    "this", "though", "unfortunately", "using", "very", "war", "well", "what", "when",
    "with", "yes", "you",
}
ALIAS_EXACT_BLOCKLIST = {
    "Clock Tower", "Far East", "Fourth Holy Grail", "Great Ritual", "Mage's Association",
    "Magic Circuits", "Magic Crest", "Modern Magecraft", "Mystic Codes", "Source Crest",
    "The Twin Towers", "United States",
}
ALIAS_SUFFIX_BLOCKLIST = (
    " Association",
    " Crest",
    " Energy",
    " Fundamentals",
    " Magecraft",
    " Ritual",
    " Towers",
)


async def embed_for_dedup(name: str, traits: dict) -> list[float]:
    return await embed_character(name, traits)


def normalize_character_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def is_valid_alias(alias: str | None) -> bool:
    candidate = re.sub(r"\s+", " ", (alias or "").strip())
    if not candidate:
        return False
    if candidate in ALIAS_EXACT_BLOCKLIST:
        return False
    if any(candidate.endswith(suffix) for suffix in ALIAS_SUFFIX_BLOCKLIST):
        return False

    normalized = normalize_character_name(candidate)
    if not normalized or normalized in ALIAS_STOPWORDS:
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", candidate)
    if not words:
        return False
    if len(words) == 1 and (len(words[0]) <= 3 or normalized in ALIAS_STOPWORDS):
        return False
    if len(words) == 1 and candidate[0].islower():
        return False
    return True


def _meaningful_tokens(name: str | None) -> list[str]:
    stopwords = {"mr", "mrs", "ms", "miss", "dr", "sir", "lady", "lord", "the"}
    return [token for token in normalize_character_name(name).split() if token and token not in stopwords]


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
    left_meaningful = _meaningful_tokens(left_name)
    right_meaningful = _meaningful_tokens(right_name)

    if (left_norm.startswith(right_norm) or right_norm.startswith(left_norm)) and min(len(left_tokens), len(right_tokens)) >= 2:
        return True

    if left_tokens and right_tokens and left_tokens[0] == right_tokens[0]:
        if len(left_tokens) >= 2 and len(right_tokens) >= 2 and left_tokens[1] == right_tokens[1]:
            return True
        if left_tokens[-1] == right_tokens[-1]:
            return True

    if left_meaningful and right_meaningful:
        left_set = set(left_meaningful)
        right_set = set(right_meaningful)
        overlap = left_set & right_set
        if overlap and (left_set <= right_set or right_set <= left_set):
            return True
        if len(overlap) >= 2:
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
    if not is_valid_alias(alias):
        return
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
