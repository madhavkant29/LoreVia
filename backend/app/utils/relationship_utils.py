from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from math import inf
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character, CharacterRelationshipCandidate
from app.models.intelligence import CharacterRelationship


def clean_relationship_text(value: object | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or None


def normalize_relationship_type_value(value: object | None) -> str:
    text = clean_relationship_text(value)
    if not text:
        return "connection"
    return text.lower().replace(" ", "_")


def normalize_relationship_sentiment_value(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def canonical_relationship_pair_ids(
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    if str(character_a_id) <= str(character_b_id):
        return character_a_id, character_b_id
    return character_b_id, character_a_id


def canonical_relationship_pair_key(
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
) -> tuple[str, str]:
    left, right = canonical_relationship_pair_ids(character_a_id, character_b_id)
    return str(left), str(right)


def relationship_pair_matches(
    relationship: CharacterRelationship,
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
) -> bool:
    pair = canonical_relationship_pair_ids(character_a_id, character_b_id)
    return canonical_relationship_pair_ids(
        getattr(relationship, "character_a_id"),
        getattr(relationship, "character_b_id"),
    ) == pair


def relationship_pair_key_for_row(relationship: CharacterRelationship) -> tuple[str, str]:
    return canonical_relationship_pair_key(
        getattr(relationship, "character_a_id"),
        getattr(relationship, "character_b_id"),
    )


def relationship_state_signature(
    *,
    rel_type: object | None,
    sentiment: object | None,
    description: object | None,
) -> tuple[str, float | None, str]:
    return (
        normalize_relationship_type_value(rel_type),
        normalize_relationship_sentiment_value(sentiment),
        clean_relationship_text(description) or "",
    )


def relationship_state_signature_for_row(relationship: CharacterRelationship) -> tuple[str, float | None, str]:
    return relationship_state_signature(
        rel_type=getattr(relationship, "rel_type", None),
        sentiment=getattr(relationship, "sentiment", None),
        description=getattr(relationship, "description", None),
    )


def relationship_effective_status(relationship: CharacterRelationship, chapter: int) -> str:
    to_chapter = getattr(relationship, "to_chapter", None)
    if to_chapter is not None and to_chapter < chapter:
        return "ended"
    return "ongoing"


def _relationship_sort_key(
    relationship: CharacterRelationship,
    *,
    preferred_relationship_id: uuid.UUID | None = None,
) -> tuple[int, int, float, str]:
    relationship_id = getattr(relationship, "id", None)
    to_chapter = getattr(relationship, "to_chapter", None)
    preferred_order = 1 if preferred_relationship_id and relationship_id == preferred_relationship_id else 0
    return (
        int(getattr(relationship, "from_chapter", 0) or 0),
        preferred_order,
        -(float(to_chapter) if to_chapter is not None else inf),
        str(relationship_id),
    )


def canonicalize_relationship_rows(
    relationships: Iterable[CharacterRelationship],
    *,
    preferred_relationship_id: uuid.UUID | None = None,
) -> tuple[list[CharacterRelationship], list[CharacterRelationship]]:
    rows = sorted(
        list(relationships),
        key=lambda relationship: _relationship_sort_key(
            relationship,
            preferred_relationship_id=preferred_relationship_id,
        ),
    )
    kept: list[CharacterRelationship] = []
    removed: list[CharacterRelationship] = []
    index = 0
    while index < len(rows):
        relationship = rows[index]
        if getattr(relationship, "from_chapter", None) is None:
            relationship.from_chapter = 1
        if not hasattr(relationship, "to_chapter"):
            relationship.to_chapter = None
        if not hasattr(relationship, "id"):
            relationship.id = None
        if not hasattr(relationship, "book_id"):
            relationship.book_id = None
        left_id, right_id = canonical_relationship_pair_ids(
            relationship.character_a_id,
            relationship.character_b_id,
        )
        relationship.character_a_id = left_id
        relationship.character_b_id = right_id
        relationship.rel_type = normalize_relationship_type_value(relationship.rel_type)
        relationship.description = clean_relationship_text(relationship.description)
        relationship.sentiment = normalize_relationship_sentiment_value(relationship.sentiment)

        if relationship.from_chapter < 1:
            relationship.from_chapter = 1
        if relationship.to_chapter is not None and relationship.to_chapter < relationship.from_chapter:
            relationship.to_chapter = relationship.from_chapter

        if not kept:
            kept.append(relationship)
            index += 1
            continue

        previous = kept[-1]
        previous_signature = relationship_state_signature_for_row(previous)
        current_signature = relationship_state_signature_for_row(relationship)
        previous_to = previous.to_chapter
        current_to = relationship.to_chapter

        if previous_signature == current_signature:
            previous_open_ended = previous_to is None
            current_open_ended = current_to is None
            previous_covers_current = previous_open_ended or (
                previous_to is not None and previous_to >= relationship.from_chapter - 1
            )
            if previous_covers_current:
                if previous_open_ended or current_open_ended:
                    previous.to_chapter = None
                elif current_to is not None:
                    previous.to_chapter = max(previous_to or current_to, current_to)
                removed.append(relationship)
                index += 1
                continue

        if relationship.from_chapter <= previous.from_chapter:
            original_previous_to = previous.to_chapter
            if (
                relationship.from_chapter == previous.from_chapter
                and current_to is not None
                and (original_previous_to is None or original_previous_to > current_to)
                and previous_signature != current_signature
            ):
                tail = CharacterRelationship(
                    book_id=previous.book_id,
                    character_a_id=previous.character_a_id,
                    character_b_id=previous.character_b_id,
                    rel_type=previous.rel_type,
                    sentiment=previous.sentiment,
                    description=previous.description,
                    from_chapter=current_to + 1,
                    to_chapter=original_previous_to,
                )
                insert_at = len(rows)
                tail_sort_key = _relationship_sort_key(
                    tail,
                    preferred_relationship_id=preferred_relationship_id,
                )
                for offset in range(index + 1, len(rows)):
                    if _relationship_sort_key(
                        rows[offset],
                        preferred_relationship_id=preferred_relationship_id,
                    ) > tail_sort_key:
                        insert_at = offset
                        break
                rows.insert(insert_at, tail)
            removed.append(previous)
            kept[-1] = relationship
            index += 1
            continue

        if previous.to_chapter is None or previous.to_chapter >= relationship.from_chapter:
            original_previous_to = previous.to_chapter
            if (
                current_to is not None
                and (original_previous_to is None or original_previous_to > current_to)
                and previous_signature != current_signature
            ):
                tail = CharacterRelationship(
                    book_id=previous.book_id,
                    character_a_id=previous.character_a_id,
                    character_b_id=previous.character_b_id,
                    rel_type=previous.rel_type,
                    sentiment=previous.sentiment,
                    description=previous.description,
                    from_chapter=current_to + 1,
                    to_chapter=original_previous_to,
                )
                insert_at = len(rows)
                tail_sort_key = _relationship_sort_key(
                    tail,
                    preferred_relationship_id=preferred_relationship_id,
                )
                for offset in range(index + 1, len(rows)):
                    if _relationship_sort_key(
                        rows[offset],
                        preferred_relationship_id=preferred_relationship_id,
                    ) > tail_sort_key:
                        insert_at = offset
                        break
                rows.insert(insert_at, tail)
            previous.to_chapter = relationship.from_chapter - 1
            if previous.to_chapter < previous.from_chapter:
                removed.append(previous)
                kept[-1] = relationship
                index += 1
                continue

        kept.append(relationship)
        index += 1

    return kept, removed


def canonicalize_relationship_book_rows(
    relationships: Iterable[CharacterRelationship],
) -> tuple[list[CharacterRelationship], list[CharacterRelationship]]:
    grouped: dict[tuple[str, str], list[CharacterRelationship]] = defaultdict(list)
    for relationship in relationships:
        grouped[relationship_pair_key_for_row(relationship)].append(relationship)

    kept: list[CharacterRelationship] = []
    removed: list[CharacterRelationship] = []
    for pair_rows in grouped.values():
        pair_kept, pair_removed = canonicalize_relationship_rows(pair_rows)
        kept.extend(pair_kept)
        removed.extend(pair_removed)
    kept.sort(key=lambda relationship: _relationship_sort_key(relationship))
    return kept, removed


async def normalize_relationship_pair_timeline(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
    preferred_relationship_id: uuid.UUID | None = None,
) -> tuple[list[CharacterRelationship], list[CharacterRelationship]]:
    left_id, right_id = canonical_relationship_pair_ids(character_a_id, character_b_id)
    rows = (
        await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == book_id,
                or_(
                    and_(
                        CharacterRelationship.character_a_id == left_id,
                        CharacterRelationship.character_b_id == right_id,
                    ),
                    and_(
                        CharacterRelationship.character_a_id == right_id,
                        CharacterRelationship.character_b_id == left_id,
                    ),
                ),
            )
        )
    ).scalars().all()
    kept, removed = canonicalize_relationship_rows(
        rows,
        preferred_relationship_id=preferred_relationship_id,
    )
    for relationship in kept:
        if relationship.id is None:
            db.add(relationship)
    for relationship in removed:
        if not getattr(relationship, "edited_by_author", False):
            await db.delete(relationship)
    await db.flush()
    return kept, removed


async def upsert_relationship_timeline_state(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
    rel_type: str,
    sentiment: float | None,
    description: str | None,
    from_chapter: int,
    to_chapter: int | None = None,
    relationship_id: uuid.UUID | None = None,
) -> tuple[CharacterRelationship, bool]:
    left_id, right_id = canonical_relationship_pair_ids(character_a_id, character_b_id)
    target_relationship: CharacterRelationship | None = None
    if relationship_id is not None:
        target_relationship = await db.get(CharacterRelationship, relationship_id)
        if target_relationship is None:
            raise ValueError("Relationship not found")
    if target_relationship is None:
        _existing_curated = await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == book_id,
                CharacterRelationship.character_a_id == left_id,
                CharacterRelationship.character_b_id == right_id,
                CharacterRelationship.edited_by_author == True,
            ).limit(1)
        )
        curated = _existing_curated.scalar_one_or_none()
        if curated is not None:
            return curated, False
        target_relationship = CharacterRelationship(
            book_id=book_id,
            character_a_id=left_id,
            character_b_id=right_id,
            rel_type=normalize_relationship_type_value(rel_type),
            sentiment=normalize_relationship_sentiment_value(sentiment),
            description=clean_relationship_text(description),
            from_chapter=from_chapter,
            to_chapter=to_chapter,
        )
        db.add(target_relationship)

    if getattr(target_relationship, "edited_by_author", False):
        return target_relationship, False

    target_relationship.book_id = book_id
    target_relationship.character_a_id = left_id
    target_relationship.character_b_id = right_id
    target_relationship.rel_type = normalize_relationship_type_value(rel_type)
    target_relationship.sentiment = normalize_relationship_sentiment_value(sentiment)
    target_relationship.description = clean_relationship_text(description)
    target_relationship.from_chapter = from_chapter
    target_relationship.to_chapter = to_chapter
    await db.flush()

    kept, removed = await normalize_relationship_pair_timeline(
        db,
        book_id=book_id,
        character_a_id=left_id,
        character_b_id=right_id,
        preferred_relationship_id=target_relationship.id,
    )
    removed_ids = {relationship.id for relationship in removed}
    created_new_state = target_relationship.id not in removed_ids
    if created_new_state:
        return target_relationship, True

    target_signature = relationship_state_signature_for_row(target_relationship)
    for relationship in kept:
        if relationship_state_signature_for_row(relationship) != target_signature:
            continue
        if relationship.from_chapter <= from_chapter and (
            relationship.to_chapter is None or relationship.to_chapter >= from_chapter
        ):
            return relationship, False
    return kept[-1], False


async def repair_relationship_timelines(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[str, int]:
    rows = (
        await db.execute(
            select(CharacterRelationship).where(CharacterRelationship.book_id == book_id)
        )
    ).scalars().all()
    removed_total = 0
    repaired_pairs = 0
    normalized_rows = 0
    grouped: dict[tuple[str, str], list[CharacterRelationship]] = defaultdict(list)
    for relationship in rows:
        grouped[relationship_pair_key_for_row(relationship)].append(relationship)
    for pair_rows in grouped.values():
        original_state = [
            (
                relationship.character_a_id,
                relationship.character_b_id,
                relationship.rel_type,
                relationship.sentiment,
                relationship.description,
                relationship.from_chapter,
                relationship.to_chapter,
            )
            for relationship in pair_rows
        ]
        kept, removed = canonicalize_relationship_rows(pair_rows)
        for relationship in kept:
            if relationship.id is None:
                db.add(relationship)
        removed_total += len(removed)
        normalized_rows += len(kept)
        if removed:
            repaired_pairs += 1
        else:
            current_state = [
                (
                    relationship.character_a_id,
                    relationship.character_b_id,
                    relationship.rel_type,
                    relationship.sentiment,
                    relationship.description,
                    relationship.from_chapter,
                    relationship.to_chapter,
                )
                for relationship in kept
            ]
            if current_state != original_state:
                repaired_pairs += 1
        for relationship in removed:
            if not getattr(relationship, "edited_by_author", False):
                await db.delete(relationship)

    candidate_rows = (
        await db.execute(
            select(CharacterRelationshipCandidate).where(
                CharacterRelationshipCandidate.book_id == book_id
            )
        )
    ).scalars().all()
    updated_candidates = 0
    for candidate in candidate_rows:
        evidence = dict(candidate.evidence or {})
        changed = False
        if candidate.matched_character_a_id and candidate.matched_character_b_id:
            left_id, right_id = canonical_relationship_pair_ids(
                candidate.matched_character_a_id,
                candidate.matched_character_b_id,
            )
            if candidate.matched_character_a_id != left_id:
                candidate.matched_character_a_id = left_id
                changed = True
            if candidate.matched_character_b_id != right_id:
                candidate.matched_character_b_id = right_id
                changed = True
            pair_key = [str(left_id), str(right_id)]
            if evidence.get("pair_key") != pair_key:
                evidence["pair_key"] = pair_key
                changed = True
        if changed:
            candidate.evidence = evidence
            updated_candidates += 1

    await db.flush()
    return {
        "pairs_repaired": repaired_pairs,
        "relationships_deleted": removed_total,
        "relationships_remaining": normalized_rows,
        "relationship_candidates_updated": updated_candidates,
    }


async def reconcile_extracted_relationships(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[str, int]:
    from app.engine.character.deduplicator import resolve_character_match_ids
    from app.utils.character_utils import (
        filter_character_identity_aliases,
        family_role_reference,
        is_cast_visible_character,
        is_protected_character,
        resolve_character_reference_from_roster,
    )

    characters = (
        await db.execute(select(Character).where(Character.book_id == book_id))
    ).scalars().all()
    sanitized_aliases = 0
    for character in characters:
        if is_protected_character(character):
            continue
        aliases = filter_character_identity_aliases(character.name, character.aliases or [])
        if aliases != list(character.aliases or []):
            character.aliases = aliases
            sanitized_aliases += 1

    visible_characters = [character for character in characters if is_cast_visible_character(character)]
    visible_ids = {character.id for character in visible_characters}
    roster = [(character.id, character.name, character.aliases or []) for character in visible_characters]

    removed_hidden_relationships = 0
    relationship_rows = (
        await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    ).scalars().all()
    for relationship in relationship_rows:
        if getattr(relationship, "edited_by_author", False):
            continue
        if relationship.character_a_id in visible_ids and relationship.character_b_id in visible_ids:
            continue
        await db.delete(relationship)
        removed_hidden_relationships += 1

    def _resolve(raw_name: str, description: str | None) -> list[uuid.UUID]:
        candidate = clean_relationship_text(raw_name)
        if not candidate:
            return []
        if not family_role_reference(candidate)[1]:
            matches = resolve_character_match_ids(candidate, [], roster)
            if matches:
                return matches
        context_text = clean_relationship_text(description)
        resolved = resolve_character_reference_from_roster(
            visible_characters,
            candidate,
            context_text=context_text,
        )
        return [resolved.id] if resolved is not None else []

    candidates = (
        await db.execute(
            select(CharacterRelationshipCandidate).where(
                CharacterRelationshipCandidate.book_id == book_id,
                CharacterRelationshipCandidate.status.in_(("pending", "suppressed", "accepted")),
            )
        )
    ).scalars().all()
    reconciled_candidates = 0
    demoted_candidates = 0
    for candidate in candidates:
        was_auto_reconciled = (
            candidate.status == "accepted"
            and "relationship_auto_reconciled" in set(candidate.reason_codes or [])
        )
        if candidate.status == "accepted" and not was_auto_reconciled:
            continue
        left_matches = _resolve(candidate.raw_character_a, candidate.description)
        right_matches = _resolve(candidate.raw_character_b, candidate.description)
        if len(left_matches) != 1 or len(right_matches) != 1 or left_matches[0] == right_matches[0]:
            if was_auto_reconciled:
                candidate.matched_character_a_id = None
                candidate.matched_character_b_id = None
                candidate.status = "suppressed"
                candidate.reason_codes = ["relationship_unresolved"]
                evidence = dict(candidate.evidence or {})
                evidence["resolution"] = "unresolved_after_reconcile"
                evidence["relationship_auto_reconciled"] = False
                candidate.evidence = evidence
                demoted_candidates += 1
            continue
        relationship, _created = await upsert_relationship_timeline_state(
            db,
            book_id=book_id,
            character_a_id=left_matches[0],
            character_b_id=right_matches[0],
            rel_type=candidate.rel_type or "connection",
            sentiment=candidate.sentiment,
            description=candidate.description,
            from_chapter=int(candidate.chapter_number or 1),
        )
        candidate.matched_character_a_id = relationship.character_a_id
        candidate.matched_character_b_id = relationship.character_b_id
        candidate.status = "accepted"
        candidate.reason_codes = ["relationship_auto_reconciled"]
        evidence = dict(candidate.evidence or {})
        evidence["pair_key"] = [str(relationship.character_a_id), str(relationship.character_b_id)]
        evidence["resolution"] = "resolved:resolved"
        evidence["relationship_auto_reconciled"] = True
        candidate.evidence = evidence
        reconciled_candidates += 1

    timeline_result = await repair_relationship_timelines(db, book_id=book_id)
    return {
        "aliases_sanitized": sanitized_aliases,
        "hidden_relationships_removed": removed_hidden_relationships,
        "relationship_candidates_reconciled": reconciled_candidates,
        "relationship_candidates_demoted": demoted_candidates,
        "timeline_pairs_repaired": int(timeline_result.get("pairs_repaired") or 0),
    }
