"""Focused character duplicates workflows."""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import (
    Character,
    CharacterDuplicateSuggestion,
    CharacterMention,
)
from app.services.character_identity.constraints import (
    has_blocking_identity_constraint,
)
from app.services.character_identity.merge import add_character_alias
from app.services.character_identity.normalization import (
    assign_unique_active_normalized_names,
    first_name_token,
)
from app.services.character_identity.suppression import suppress_candidate
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_REJECTED,
    CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
    CHARACTER_DUPLICATE_ACCEPTED,
    CHARACTER_DUPLICATE_DISMISSED,
    CHARACTER_DUPLICATE_PENDING,
    CHARACTER_VISIBILITY_NOISE,
)
from app.utils.characters.governance import (
    character_governance,
)
from app.utils.characters.identity import (
    family_role_reference,
    has_conflicting_title_identity,
    normalize_character_name,
)
from app.utils.characters.merging import (
    merge_characters,
)
from app.utils.characters.review import (
    set_character_review_state,
)
from app.utils.characters.serialization import is_protected_character
from app.utils.characters.similarity import (
    name_similarity,
)
from app.utils.characters.text import _clean_reason_codes, clean_optional_text


def _normalize_merge_score_value(value: float) -> int:
    return max(0, min(96, int(round(value * 100))))


def _cosine_similarity(left: Sequence[float] | None, right: Sequence[float] | None) -> float:
    if left is None or right is None:
        return 0.0
    if len(left) == 0 or len(right) == 0 or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _chapter_window_overlap(left: Character, right: Character) -> bool:
    left_first = int(left.first_chapter or 0)
    left_last = int(left.last_seen_chapter or left.first_chapter or 0)
    right_first = int(right.first_chapter or 0)
    right_last = int(right.last_seen_chapter or right.first_chapter or 0)
    return max(left_first, right_first) <= min(left_last, right_last)


async def _load_character_mention_evidence_map(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[uuid.UUID, dict[str, Any]]:
    rows = (
        (
            await db.execute(
                select(CharacterMention).where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.matched_character_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]] = {}
    for row in rows:
        if row.matched_character_id is None:
            continue
        bucket = evidence_by_character_id.setdefault(
            row.matched_character_id,
            {"cluster_keys": set(), "chapter_numbers": set(), "snippets": [], "mention_count": 0},
        )
        if row.cluster_key:
            cast(set[str], bucket["cluster_keys"]).add(row.cluster_key)
        cast(set[int], bucket["chapter_numbers"]).add(int(row.chapter_number or 0))
        bucket["mention_count"] = int(bucket.get("mention_count") or 0) + int(
            (row.evidence or {}).get("mention_count") or 1
        )
        snippet = clean_optional_text(row.mention_text)
        if snippet and snippet not in bucket["snippets"]:
            cast(list[str], bucket["snippets"]).append(snippet)
    return evidence_by_character_id


def score_duplicate_characters(
    left: Character,
    right: Character,
    *,
    left_evidence: dict[str, Any] | None = None,
    right_evidence: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if getattr(left, "is_manual", False) and getattr(right, "is_manual", False):
        return None
    left_name = normalize_character_name(left.name)
    right_name = normalize_character_name(right.name)
    if not left_name or not right_name:
        return None
    if has_conflicting_title_identity(left.name, right.name):
        return None

    left_aliases = [
        normalize_character_name(alias)
        for alias in (left.aliases or [])
        if normalize_character_name(alias)
    ]
    right_aliases = [
        normalize_character_name(alias)
        for alias in (right.aliases or [])
        if normalize_character_name(alias)
    ]

    reasons: list[str] = []
    shared_tokens: list[str] = []
    score = 0.0

    if left_name == right_name:
        reasons.append("Exact name match")
        score += 0.95
    if left_name in right_aliases or right_name in left_aliases:
        reasons.append("Primary name appears in alias list")
        score += 0.30

    shared_aliases = [alias for alias in left_aliases if alias in right_aliases]
    if shared_aliases:
        reasons.append("Shared aliases detected")
        score += min(0.22, len(shared_aliases) * 0.08)

    left_tokens = {token for token in left_name.split() if token}
    right_tokens = {token for token in right_name.split() if token}
    shared_tokens = sorted(token for token in left_tokens & right_tokens if len(token) > 3)
    if shared_tokens:
        reasons.append("Overlapping name tokens")
        score += min(0.16, len(shared_tokens) * 0.06)

    if (
        int(left.first_chapter or 0) == int(right.first_chapter or -1)
        and int(left.first_chapter or 0) > 0
    ):
        reasons.append("First seen in the same chapter")
        score += 0.06

    if name_similarity(left.name, right.name) >= 0.88:
        reasons.append("High name similarity")
        score += 0.10

    shared_cluster_keys = sorted(
        set(cast(set[str], (left_evidence or {}).get("cluster_keys") or set()))
        & set(cast(set[str], (right_evidence or {}).get("cluster_keys") or set()))
    )
    if shared_cluster_keys:
        reasons.append("Shared mention clusters")
        score += min(0.24, len(shared_cluster_keys) * 0.10)
        if bool(family_role_reference(left.name)[1]) ^ bool(family_role_reference(right.name)[1]):
            reasons.append("Role reference shares grounded cluster with canonical name")
            score += 0.12

    if _chapter_window_overlap(left, right):
        reasons.append("Overlapping chapter windows")
        score += 0.05

    left_chapters = set(cast(set[int], (left_evidence or {}).get("chapter_numbers") or set()))
    right_chapters = set(cast(set[int], (right_evidence or {}).get("chapter_numbers") or set()))
    shared_chapters = sorted(left_chapters & right_chapters)
    if shared_chapters:
        reasons.append("Shared grounded chapters")
        score += min(0.10, len(shared_chapters) * 0.02)

    embedding_similarity = _cosine_similarity(left.embedding, right.embedding)
    if embedding_similarity >= 0.92:
        reasons.append("High embedding similarity")
        score += 0.12
    elif embedding_similarity >= 0.84:
        reasons.append("Related embedding similarity")
        score += 0.06

    if score < 0.75:
        return None

    primary = left if int(left.mention_count or 0) >= int(right.mention_count or 0) else right
    secondary = right if primary.id == left.id else left
    return {
        "primary": primary,
        "secondary": secondary,
        "confidence": _normalize_merge_score_value(min(0.96, score)),
        "reasons": reasons,
        "shared_evidence": {
            "shared_aliases": shared_aliases[:6],
            "shared_tokens": shared_tokens[:6],
            "shared_cluster_keys": shared_cluster_keys[:6],
            "shared_chapters": shared_chapters[:8],
            "embedding_similarity": round(embedding_similarity, 4)
            if embedding_similarity > 0
            else None,
            "first_chapter_pair": [int(left.first_chapter or 0), int(right.first_chapter or 0)],
            "manual_anchor_present": bool(
                getattr(left, "is_manual", False) or getattr(right, "is_manual", False)
            ),
        },
    }


async def refresh_character_duplicate_suggestions(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    characters: Sequence[Character] | None = None,
) -> list[CharacterDuplicateSuggestion]:
    if characters is None:
        characters = (
            (
                await db.execute(
                    select(Character)
                    .where(Character.book_id == book_id)
                    .order_by(Character.first_chapter, Character.name)
                )
            )
            .scalars()
            .all()
        )
    characters = [
        character
        for character in characters
        if getattr(character, "merged_into_character_id", None) is None
        and character_governance(character)[0] != CHARACTER_VISIBILITY_NOISE
        and character_governance(character)[1] != CHARACTER_APPROVAL_REJECTED
    ]

    exact_groups: dict[str, list[Character]] = defaultdict(list)
    for character in characters:
        normalized = normalize_character_name(character.name)
        if normalized:
            exact_groups[normalized].append(character)

    merged_any = False
    for exact_matches in exact_groups.values():
        if len(exact_matches) < 2:
            continue
        ordered = sorted(
            exact_matches,
            key=lambda item: (int(item.mention_count or 0), -int(item.first_chapter or 0)),
            reverse=True,
        )
        primary = ordered[0]
        for secondary in ordered[1:]:
            if is_protected_character(secondary):
                continue
            if await has_blocking_identity_constraint(
                db,
                book_id=book_id,
                left_character_id=primary.id,
                right_character_id=secondary.id,
            ):
                continue
            await merge_characters(db, primary.id, secondary.id, book_id)
            merged_any = True

    if merged_any:
        characters = (
            (
                await db.execute(
                    select(Character)
                    .where(Character.book_id == book_id)
                    .order_by(Character.first_chapter, Character.name)
                )
            )
            .scalars()
            .all()
        )
        characters = [
            character
            for character in characters
            if getattr(character, "merged_into_character_id", None) is None
            and character_governance(character)[0] != CHARACTER_VISIBILITY_NOISE
            and character_governance(character)[1] != CHARACTER_APPROVAL_REJECTED
        ]
    assign_unique_active_normalized_names(characters)

    full_name_by_first: dict[str, list[Character]] = defaultdict(list)
    single_token_characters: list[Character] = []
    for character in characters:
        tokens = normalize_character_name(character.name).split()
        if len(tokens) == 1:
            single_token_characters.append(character)
        elif len(tokens) >= 2:
            full_name_by_first[tokens[0]].append(character)

    for alias_character in single_token_characters:
        token = first_name_token(alias_character.name)
        full_matches = full_name_by_first.get(token) or []
        if not full_matches or is_protected_character(alias_character):
            continue
        target = sorted(full_matches, key=lambda item: int(item.mention_count or 0), reverse=True)[
            0
        ]
        if int(target.mention_count or 0) < int(alias_character.mention_count or 0):
            continue
        if await has_blocking_identity_constraint(
            db,
            book_id=book_id,
            left_character_id=alias_character.id,
            right_character_id=target.id,
        ):
            continue
        await add_character_alias(
            db,
            character=target,
            alias_text=alias_character.name,
            alias_kind="first_name",
            source="duplicate_refresh",
            confidence=0.9,
        )
        alias_character.merged_into_character_id = target.id
        alias_character.is_auto_suppressed = True
        alias_character.suppression_reason = "single_token_first_name_alias"
        set_character_review_state(
            alias_character,
            visibility_state=CHARACTER_VISIBILITY_NOISE,
            approval_state=CHARACTER_APPROVAL_REJECTED,
            approval_source=CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
            reason_codes=["single_token_first_name_alias"],
            action="character_auto_alias_suppressed",
            details={"target_character_id": str(target.id)},
        )
        mention_rows = (
            (
                await db.execute(
                    select(CharacterMention).where(
                        CharacterMention.book_id == book_id,
                        CharacterMention.matched_character_id == alias_character.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for mention in mention_rows:
            mention.matched_character_id = target.id
        await suppress_candidate(
            db,
            book_id=book_id,
            character_id=alias_character.id,
            surface_text=alias_character.name,
            candidate_kind="alias",
            reason="single_token_first_name_alias",
            confidence=0.9,
        )

    characters = [
        character
        for character in characters
        if getattr(character, "merged_into_character_id", None) is None
        and character_governance(character)[0] != CHARACTER_VISIBILITY_NOISE
        and character_governance(character)[1] != CHARACTER_APPROVAL_REJECTED
    ]

    existing_suggestions = (
        (
            await db.execute(
                select(CharacterDuplicateSuggestion).where(
                    CharacterDuplicateSuggestion.book_id == book_id
                )
            )
        )
        .scalars()
        .all()
    )
    existing_by_pair = {
        (str(item.primary_character_id), str(item.secondary_character_id)): item
        for item in existing_suggestions
    }
    active_pairs: set[tuple[str, str]] = set()
    mention_evidence_by_character_id = await _load_character_mention_evidence_map(
        db, book_id=book_id
    )

    for index, left in enumerate(characters):
        for right in characters[index + 1 :]:
            suggestion = score_duplicate_characters(
                left,
                right,
                left_evidence=mention_evidence_by_character_id.get(left.id),
                right_evidence=mention_evidence_by_character_id.get(right.id),
            )
            if suggestion is None:
                continue
            primary = cast(Character, suggestion["primary"])
            secondary = cast(Character, suggestion["secondary"])
            if await has_blocking_identity_constraint(
                db,
                book_id=book_id,
                left_character_id=primary.id,
                right_character_id=secondary.id,
            ):
                continue
            pair_key = (str(primary.id), str(secondary.id))
            active_pairs.add(pair_key)
            existing = existing_by_pair.get(pair_key)
            if existing is None:
                existing = CharacterDuplicateSuggestion(
                    book_id=book_id,
                    primary_character_id=primary.id,
                    secondary_character_id=secondary.id,
                )
                db.add(existing)
            if existing.status != CHARACTER_DUPLICATE_ACCEPTED:
                existing.status = CHARACTER_DUPLICATE_PENDING
            existing.confidence = int(suggestion["confidence"])
            existing.reasons = _clean_reason_codes(cast(Sequence[object], suggestion["reasons"]))
            existing.shared_evidence = dict(cast(dict[str, Any], suggestion["shared_evidence"]))

    for pair_key, existing in existing_by_pair.items():
        if pair_key in active_pairs or existing.status == CHARACTER_DUPLICATE_ACCEPTED:
            continue
        existing.status = CHARACTER_DUPLICATE_DISMISSED
        existing.auto_dismissed = True
        existing.dismissal_reason = existing.dismissal_reason or "duplicate_score_below_threshold"

    await db.flush()
    return (
        (
            await db.execute(
                select(CharacterDuplicateSuggestion)
                .where(CharacterDuplicateSuggestion.book_id == book_id)
                .order_by(
                    CharacterDuplicateSuggestion.confidence.desc(),
                    CharacterDuplicateSuggestion.created_at,
                )
            )
        )
        .scalars()
        .all()
    )
