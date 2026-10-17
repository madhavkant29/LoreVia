import logging
import re
import uuid
from collections.abc import Iterable

from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.embeddings.embedder import embed_character
from app.models.character import Character
from app.utils.characters.identity import (
    has_conflicting_title_identity,
    has_shared_surname,
)
from app.utils.characters.similarity import name_similarity

log = logging.getLogger(__name__)

ALIAS_STOPWORDS = {
    "after",
    "and",
    "are",
    "around",
    "association",
    "but",
    "considering",
    "creation",
    "faculty",
    "for",
    "from",
    "having",
    "his",
    "however",
    "just",
    "lady",
    "leaving",
    "let",
    "looking",
    "lord",
    "lords",
    "maybe",
    "miss",
    "now",
    "once",
    "regardless",
    "seeing",
    "she",
    "sure",
    "taking",
    "thanks",
    "that",
    "the",
    "they",
    "thinking",
    "this",
    "though",
    "unfortunately",
    "using",
    "very",
    "war",
    "well",
    "what",
    "when",
    "with",
    "yes",
    "you",
}
ALIAS_EXACT_BLOCKLIST = {
    "Clock Tower",
    "Far East",
    "Fourth Holy Grail",
    "Great Ritual",
    "Mage's Association",
    "Magic Circuits",
    "Magic Crest",
    "Modern Magecraft",
    "Mystic Codes",
    "Source Crest",
    "The Twin Towers",
    "United States",
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
HONORIFIC_SUFFIXES = ("san", "kun", "chan", "sama", "sensei", "senpai", "dono", "tan", "nee", "nii")
HONORIFIC_PREFIXES = ("mr", "mrs", "ms", "miss", "dr", "sir", "lady", "lord")


async def embed_for_dedup(
    name: str,
    traits: dict,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID | None = None,
) -> list[float]:
    return await embed_character(
        name,
        traits,
        user_id=user_id,
        book_id=book_id,
    )


def normalize_character_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _strip_honorific_suffixes(name: str | None) -> str:
    normalized = normalize_character_name(name)
    if not normalized:
        return ""
    for suffix in HONORIFIC_SUFFIXES:
        normalized = re.sub(rf"(?:\s|^)([a-z0-9]+)[-\s]{suffix}$", r"\1", normalized)
    return normalized.strip()


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
    return [
        token
        for token in _strip_honorific_suffixes(name).split()
        if token and token not in stopwords
    ]


def _honorific_prefix(name: str | None) -> str:
    normalized = normalize_character_name(name)
    tokens = normalized.split()
    if tokens and tokens[0] in HONORIFIC_PREFIXES:
        return tokens[0]
    return ""


def _has_titled_bare_surname_mismatch(
    left_name: str | None,
    right_name: str | None,
    *,
    left_meaningful: list[str],
    right_meaningful: list[str],
    left_honorific: str,
    right_honorific: str,
) -> bool:
    if not left_meaningful or not right_meaningful:
        return False
    if left_meaningful != right_meaningful:
        return False
    return bool(left_honorific) != bool(right_honorific)


def character_name_keys(name: str | None, aliases: Iterable[str] | None = None) -> set[str]:
    keys: set[str] = set()

    def _add(candidate: str | None) -> None:
        normalized = normalize_character_name(candidate)
        if not normalized:
            return
        keys.add(normalized)
        stripped = _strip_honorific_suffixes(candidate)
        if stripped:
            keys.add(stripped)
        tokens = normalized.split()
        stripped_tokens = stripped.split() if stripped else []
        if len(tokens) >= 2:
            keys.add(" ".join(tokens[:2]))
        if len(tokens) >= 2:
            keys.add(f"{tokens[0]} {tokens[-1]}")
        if len(tokens) >= 3:
            keys.add(" ".join(tokens[:3]))
        if len(stripped_tokens) == 1 and not _honorific_prefix(candidate):
            keys.add(stripped_tokens[0])

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
    if has_conflicting_title_identity(left_name, right_name):
        return False

    left_keys = character_name_keys(left_name, left_aliases)
    right_keys = character_name_keys(right_name, right_aliases)
    if left_keys & right_keys:
        return True

    left_norm = normalize_character_name(left_name)
    right_norm = normalize_character_name(right_name)
    left_base = _strip_honorific_suffixes(left_name)
    right_base = _strip_honorific_suffixes(right_name)
    if not left_norm or not right_norm:
        return False

    left_tokens = left_norm.split()
    right_tokens = right_norm.split()
    left_meaningful = _meaningful_tokens(left_name)
    right_meaningful = _meaningful_tokens(right_name)
    left_base_tokens = left_base.split() if left_base else []
    right_base_tokens = right_base.split() if right_base else []
    left_honorific = _honorific_prefix(left_name)
    right_honorific = _honorific_prefix(right_name)

    if len(left_tokens) == len(right_tokens) == 2:
        if left_tokens[0] == right_tokens[0] and left_tokens[1] != right_tokens[1]:
            return False
        if left_tokens[-1] == right_tokens[-1] and left_tokens[0] != right_tokens[0]:
            return False

    if left_meaningful and right_meaningful and len(left_meaningful) == len(right_meaningful) == 1:
        if left_meaningful[0] == right_meaningful[0]:
            if left_honorific != right_honorific:
                return False
            if bool(left_honorific) != bool(right_honorific):
                return False

    if _has_titled_bare_surname_mismatch(
        left_name,
        right_name,
        left_meaningful=left_meaningful,
        right_meaningful=right_meaningful,
        left_honorific=left_honorific,
        right_honorific=right_honorific,
    ):
        return False

    if name_similarity(left_name, right_name) >= 0.85:
        return True

    if has_shared_surname(left_name, right_name):
        left_given = left_tokens[0] if left_tokens else ""
        right_given = right_tokens[0] if right_tokens else ""
        if left_given and right_given and left_given != right_given:
            return False

    if left_base and right_base and left_base == right_base:
        if _has_titled_bare_surname_mismatch(
            left_name,
            right_name,
            left_meaningful=left_meaningful,
            right_meaningful=right_meaningful,
            left_honorific=left_honorific,
            right_honorific=right_honorific,
        ):
            return False
        return True

    if left_base_tokens and right_base_tokens:
        if len(left_base_tokens) == 1 and left_base_tokens[0] in set(right_base_tokens):
            if _has_titled_bare_surname_mismatch(
                left_name,
                right_name,
                left_meaningful=left_meaningful,
                right_meaningful=right_meaningful,
                left_honorific=left_honorific,
                right_honorific=right_honorific,
            ):
                return False
            return True
        if len(right_base_tokens) == 1 and right_base_tokens[0] in set(left_base_tokens):
            if _has_titled_bare_surname_mismatch(
                left_name,
                right_name,
                left_meaningful=left_meaningful,
                right_meaningful=right_meaningful,
                left_honorific=left_honorific,
                right_honorific=right_honorific,
            ):
                return False
            return True
        if len(left_base_tokens) == len(right_base_tokens) == 2 and left_base_tokens == list(
            reversed(right_base_tokens)
        ):
            return True

    if (left_norm.startswith(right_norm) or right_norm.startswith(left_norm)) and min(
        len(left_tokens), len(right_tokens)
    ) >= 2:
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

    if has_shared_surname(left_name, right_name) and name_similarity(left_name, right_name) >= 0.70:
        return True

    return False


def resolve_character_match_ids(
    name: str | None,
    aliases: Iterable[str] | None,
    roster: Iterable[tuple[uuid.UUID, str | None, Iterable[str] | None]],
    *,
    blocked_ids: Iterable[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    candidate_keys = character_name_keys(name, aliases)
    if not candidate_keys:
        return []

    blocked = set(blocked_ids or [])
    matches: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for char_id, char_name, char_aliases in roster:
        if char_id in blocked:
            continue
        if candidate_keys & character_name_keys(char_name, char_aliases or []):
            if char_id not in seen:
                seen.add(char_id)
                matches.append(char_id)
            continue
        if names_equivalent(name, aliases, char_name, char_aliases or []):
            if char_id not in seen:
                seen.add(char_id)
                matches.append(char_id)
    return matches


def resolve_character_match_id(
    name: str | None,
    aliases: Iterable[str] | None,
    roster: Iterable[tuple[uuid.UUID, str | None, Iterable[str] | None]],
    *,
    blocked_ids: Iterable[uuid.UUID] | None = None,
) -> uuid.UUID | None:
    matches = resolve_character_match_ids(
        name,
        aliases,
        roster,
        blocked_ids=blocked_ids,
    )
    return matches[0] if len(matches) == 1 else None


async def find_similar(
    db: AsyncSession,
    book_id: uuid.UUID,
    embedding: list[float],
    threshold: float = 0.88,
    excluded_ids: Iterable[uuid.UUID] | None = None,
) -> uuid.UUID | None:
    max_distance = max(0.0, 1 - threshold)
    try:
        result = await db.execute(
            text("""
                SELECT id, embedding <=> CAST(:emb AS vector) AS distance
                FROM characters
                WHERE book_id = :bid
                  AND embedding IS NOT NULL
                  AND embedding <=> CAST(:emb AS vector) < :max_distance
                ORDER BY embedding <=> CAST(:emb AS vector) ASC
                LIMIT 10
            """),
            {"emb": str(embedding), "bid": str(book_id), "max_distance": max_distance},
        )
    except ProgrammingError as exc:
        if 'type "vector" does not exist' in str(getattr(exc, "orig", exc)).lower():
            log.warning("find_similar_pgvector_unavailable book_id=%s", book_id)
            return None
        raise
    excluded = {str(item) for item in (excluded_ids or [])}
    for row in result.fetchall():
        if str(row[0]) not in excluded:
            return uuid.UUID(str(row[0]))
    return None


async def find_by_name_or_alias(
    db: AsyncSession,
    book_id: uuid.UUID,
    name: str,
    aliases: Iterable[str] | None = None,
) -> uuid.UUID | None:
    result = await db.execute(
        select(Character.id, Character.name, Character.aliases).where(Character.book_id == book_id)
    )
    return resolve_character_match_id(name, aliases, result.all())


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
