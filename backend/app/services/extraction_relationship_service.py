from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.models.character import Character
from app.models.intelligence import CharacterRelationship
from app.services.extraction_character_cache_service import _find_character_ids_in_cache
from app.utils.characters.candidates import decide_relationship_candidate_disposition
from app.utils.characters.constants import CHARACTER_RELATIONSHIP_CANDIDATE_PENDING
from app.utils.characters.extraction import resolve_character_reference_from_roster
from app.utils.characters.governance import is_cast_visible_character
from app.utils.characters.identity import family_role_reference
from app.utils.characters.review import record_relationship_candidate
from app.utils.relationship_utils import (
    canonical_relationship_pair_key,
    relationship_state_signature,
    upsert_relationship_timeline_state,
)

RelationshipSignature = tuple[
    str, str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...], float | None, str, int
]


def _relationship_signature(
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
    rel_type: str,
    sentiment: float | None,
    from_chapter: int,
    description: str | None,
    shared_labels: object | None = None,
    character_a_to_b_labels: object | None = None,
    character_b_to_a_labels: object | None = None,
) -> RelationshipSignature:
    left_id, right_id = canonical_relationship_pair_key(character_a_id, character_b_id)
    (
        normalized_type,
        normalized_shared,
        normalized_a_to_b,
        normalized_b_to_a,
        normalized_sentiment,
        normalized_description,
    ) = relationship_state_signature(
        rel_type=rel_type or "neutral",
        sentiment=sentiment,
        description=description,
        shared_labels=shared_labels,
        character_a_to_b_labels=character_a_to_b_labels,
        character_b_to_a_labels=character_b_to_a_labels,
    )
    return (
        left_id,
        right_id,
        normalized_type,
        normalized_shared,
        normalized_a_to_b,
        normalized_b_to_a,
        normalized_sentiment,
        normalized_description,
        int(from_chapter or 0),
    )


async def load_persisted_relationship_signatures(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
) -> set[RelationshipSignature]:
    existing_relationship_rows = (
        await db.execute(
            select(
                CharacterRelationship.character_a_id,
                CharacterRelationship.character_b_id,
                CharacterRelationship.rel_type,
                CharacterRelationship.sentiment,
                CharacterRelationship.from_chapter,
                CharacterRelationship.description,
                CharacterRelationship.shared_labels,
                CharacterRelationship.character_a_to_b_labels,
                CharacterRelationship.character_b_to_a_labels,
            ).where(
                CharacterRelationship.book_id == book_id,
                CharacterRelationship.from_chapter == chapter_number,
            )
        )
    ).all()
    return {
        _relationship_signature(
            row.character_a_id,
            row.character_b_id,
            row.rel_type,
            row.sentiment,
            row.from_chapter,
            row.description,
            row.shared_labels,
            row.character_a_to_b_labels,
            row.character_b_to_a_labels,
        )
        for row in existing_relationship_rows
    }


def _relationship_resolution_candidates(
    chars: list[Character],
    name: str | None,
    *,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
    context_text: str | None = None,
) -> list[uuid.UUID]:
    candidate = " ".join(str(name or "").split()).strip()
    if not candidate:
        return []
    visible_characters = [char for char in chars if is_cast_visible_character(char)]
    if not family_role_reference(candidate)[1]:
        matched = _find_character_ids_in_cache(
            visible_characters, candidate, [], key_cache=key_cache
        )
        if matched:
            return matched
    resolved = resolve_character_reference_from_roster(
        visible_characters, candidate, context_text=context_text
    )
    return [resolved.id] if resolved is not None else []


def _relationship_evidence_payload(
    rel: dict[str, Any],
    *,
    chapter_number: int,
    counterpart_name: str | None,
    counterpart_character_id: uuid.UUID | None,
    unresolved_side: str,
    resolution: str,
) -> dict[str, Any]:
    pair_key: list[str] | None = None
    if rel.get("matched_character_a_id") and rel.get("matched_character_b_id"):
        pair_key = list(
            canonical_relationship_pair_key(
                uuid.UUID(str(rel["matched_character_a_id"])),
                uuid.UUID(str(rel["matched_character_b_id"])),
            )
        )
    return {
        "relationship": {
            "character_a": " ".join(str(rel.get("character_a") or "").split()).strip(),
            "character_b": " ".join(str(rel.get("character_b") or "").split()).strip(),
            "type": " ".join(
                str(rel.get("primary_type") or rel.get("type") or "neutral").split()
            ).strip()
            or "neutral",
            "description": " ".join(str(rel.get("description") or "").split()).strip(),
            "chapter_number": int(chapter_number or 0),
            "source_batch_key": rel.get("source_batch_key"),
            "shared_labels": rel.get("shared_labels") or [],
            "character_a_to_b_labels": rel.get("character_a_to_b_labels") or [],
            "character_b_to_a_labels": rel.get("character_b_to_a_labels") or [],
            "label_evidence": rel.get("label_evidence") or rel.get("evidence") or {},
        },
        "review_kind": "relationship_resolution",
        "unresolved_side": unresolved_side,
        "resolution": resolution,
        "counterpart_name": counterpart_name,
        "counterpart_character_id": str(counterpart_character_id)
        if counterpart_character_id
        else None,
        "pair_key": pair_key,
        "character_a_matches": [str(item) for item in rel.get("character_a_matches", [])[:3]],
        "character_b_matches": [str(item) for item in rel.get("character_b_matches", [])[:3]],
    }


async def _record_relationship_review_candidates(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    rel: dict[str, Any],
    left_matches: list[uuid.UUID],
    right_matches: list[uuid.UUID],
) -> int:
    created = 0
    left_name = " ".join(str(rel.get("character_a") or "").split()).strip()
    right_name = " ".join(str(rel.get("character_b") or "").split()).strip()
    relationship_key = str(rel.get("source_batch_key") or f"{book_id}:{chapter_number}")
    left_resolution = (
        "resolved"
        if len(left_matches) == 1
        else ("ambiguous" if len(left_matches) > 1 else "missing")
    )
    right_resolution = (
        "resolved"
        if len(right_matches) == 1
        else ("ambiguous" if len(right_matches) > 1 else "missing")
    )

    if (
        left_name
        and right_name
        and (
            len(left_matches) != 1
            or len(right_matches) != 1
            or rel.get("source_quote_verified") is False
        )
    ):
        reason_codes = [
            "relationship_source_quote_unverified"
            if rel.get("source_quote_verified") is False
            else "relationship_unresolved",
            f"character_a_{left_resolution}",
            f"character_b_{right_resolution}",
        ]
        evidence = _relationship_evidence_payload(
            rel,
            chapter_number=chapter_number,
            counterpart_name=right_name or left_name or None,
            counterpart_character_id=right_matches[0]
            if len(right_matches) == 1
            else left_matches[0]
            if len(left_matches) == 1
            else None,
            unresolved_side=(
                "source_quote"
                if len(left_matches) == 1
                and len(right_matches) == 1
                and rel.get("source_quote_verified") is False
                else "both"
                if len(left_matches) != 1 and len(right_matches) != 1
                else "character_a"
                if len(left_matches) != 1
                else "character_b"
            ),
            resolution=f"{left_resolution}:{right_resolution}",
        )
        disposition = decide_relationship_candidate_disposition(
            raw_character_a=left_name,
            raw_character_b=right_name,
            left_resolved=len(left_matches) == 1,
            right_resolved=len(right_matches) == 1,
            reason_codes=reason_codes,
            evidence=evidence,
        )
        candidate = await record_relationship_candidate(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            raw_character_a=left_name,
            raw_character_b=right_name,
            matched_character_a_id=left_matches[0] if len(left_matches) == 1 else None,
            matched_character_b_id=right_matches[0] if len(right_matches) == 1 else None,
            rel_type=str(
                rel.get("rel_type")
                or rel.get("primary_type")
                or rel.get("type")
                or rel.get("relationship")
                or "connection"
            ).strip()
            or None,
            sentiment=rel.get("sentiment"),
            description=str(rel.get("description") or "").strip() or None,
            status=disposition.status,
            reason_codes=disposition.reason_codes,
            evidence=disposition.evidence,
            source_batch_key=f"{relationship_key}:relationship",
        )
        if candidate is not None and candidate.status == CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
            created += 1

    return created


async def _persist_relationship_records(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    existing_characters: list[Character],
    relationships: list[dict[str, Any]],
    key_cache: dict[uuid.UUID, set[str]],
    persisted_signatures: set[RelationshipSignature],
) -> tuple[int, list[dict[str, Any]], int]:
    persisted = 0
    unresolved: list[dict[str, Any]] = []
    review_candidate_count = 0

    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        left_name = " ".join(str(rel.get("character_a") or "").split()).strip()
        right_name = " ".join(str(rel.get("character_b") or "").split()).strip()
        if not left_name or not right_name:
            continue

        context_text = " ".join(str(rel.get("description") or "").split()).strip()
        left_matches = _relationship_resolution_candidates(
            existing_characters, left_name, key_cache=key_cache, context_text=context_text
        )
        right_matches = _relationship_resolution_candidates(
            existing_characters, right_name, key_cache=key_cache, context_text=context_text
        )
        quote_verified = rel.get("source_quote_verified") is True
        if (
            quote_verified
            and isinstance(rel.get("label_evidence"), dict)
            and rel["label_evidence"].get("quote")
            and len(left_matches) == 1
            and len(right_matches) == 1
            and left_matches[0] != right_matches[0]
        ):
            signature = _relationship_signature(
                left_matches[0],
                right_matches[0],
                str(rel.get("primary_type") or rel.get("type") or "neutral"),
                rel.get("sentiment"),
                chapter_number,
                str(rel.get("description") or ""),
                rel.get("shared_labels"),
                rel.get("character_a_to_b_labels"),
                rel.get("character_b_to_a_labels"),
            )
            relationship, created = await upsert_relationship_timeline_state(
                db,
                book_id=book_id,
                character_a_id=left_matches[0],
                character_b_id=right_matches[0],
                rel_type=str(rel.get("primary_type") or rel.get("type") or "neutral"),
                sentiment=rel.get("sentiment"),
                description=str(rel.get("description") or ""),
                from_chapter=chapter_number,
                shared_labels=rel.get("shared_labels"),
                character_a_to_b_labels=rel.get("character_a_to_b_labels"),
                character_b_to_a_labels=rel.get("character_b_to_a_labels"),
                label_evidence=rel.get("label_evidence")
                if isinstance(rel.get("label_evidence"), dict)
                else rel.get("evidence")
                if isinstance(rel.get("evidence"), dict)
                else None,
            )
            if created:
                persisted_signatures.add(signature)
                persisted += 1
            continue

        unresolved_entry = {
            "character_a": left_name,
            "character_b": right_name,
            "type": str(rel.get("primary_type") or rel.get("type") or "neutral"),
            "description": " ".join(str(rel.get("description") or "").split()).strip(),
            "shared_labels": rel.get("shared_labels") or [],
            "character_a_to_b_labels": rel.get("character_a_to_b_labels") or [],
            "character_b_to_a_labels": rel.get("character_b_to_a_labels") or [],
            "label_evidence": rel.get("label_evidence")
            if isinstance(rel.get("label_evidence"), dict)
            else rel.get("evidence")
            if isinstance(rel.get("evidence"), dict)
            else {},
            "source_batch_key": rel.get("source_batch_key"),
            "source_quote_verified": quote_verified,
            "chapter_number": chapter_number,
            "character_a_matches": [str(item) for item in left_matches[:3]],
            "character_b_matches": [str(item) for item in right_matches[:3]],
            "matched_character_a_id": str(left_matches[0]) if len(left_matches) == 1 else None,
            "matched_character_b_id": str(right_matches[0]) if len(right_matches) == 1 else None,
        }
        unresolved.append(unresolved_entry)
        review_candidate_count += await _record_relationship_review_candidates(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            rel=unresolved_entry,
            left_matches=left_matches,
            right_matches=right_matches,
        )

    return persisted, unresolved, review_candidate_count
