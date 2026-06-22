"""Repair polluted character-bible data for an existing book.

Dry-run by default:
    python scripts/repair_character_bible_book.py --book-id <uuid>

Apply only after explicit confirmation:
    python scripts/repair_character_bible_book.py --book-id <uuid> --apply --confirm-apply REPAIR_CHARACTER_BIBLE --allow-merge-safe-pairs
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.engine.character.extractor import verify_character_candidate_personhood
from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterMention,
    CharacterRelationshipCandidate,
)
from app.utils.characters.candidates import (
    decide_character_candidate_disposition,
    decide_relationship_candidate_disposition,
)
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_REJECTED,
    CHARACTER_APPROVAL_SOURCE_BACKFILL_REVIEW,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_CANDIDATE_SUPPRESSED,
    CHARACTER_DUPLICATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED,
    CHARACTER_TRUST_TIER_REPAIRED_NOISE,
    CHARACTER_VISIBILITY_NOISE,
)
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.characters.governance import infer_character_trust_tier, is_cast_visible_character
from app.utils.characters.identity import normalize_character_name
from app.utils.characters.manual import find_earliest_character_mention_chapters
from app.utils.characters.merging import merge_characters
from app.utils.characters.review import record_character_candidate, set_character_review_state
from app.utils.characters.review_serialization import (
    build_character_review_payload,
)
from app.utils.logging import get_logger
from scripts.audit_character_bible_noise import _has_meaningful_profile, _is_obvious_noise_character

log = get_logger("lorevia.repair.character_bible")
CONFIRM_TOKEN = "REPAIR_CHARACTER_BIBLE"


@dataclass(frozen=True)
class RepairPlan:
    book_id: str
    dry_run: bool
    allow_merge_safe_pairs: bool
    allow_demote_obvious_noise: bool
    planned_merges: list[tuple[str, str]]
    planned_demotions: list[str]
    skipped_protected_merge_pairs: list[tuple[str, str]]
    skipped_protected_demotions: list[str]
    updated_first_chapters: dict[str, int]
    updated_last_seen_chapters: dict[str, int]
    character_labels: dict[str, str]
    pending_duplicate_suggestions: int
    pending_relationship_candidates: int
    pending_character_candidates_suppressed: int
    pending_character_candidates_kept: int
    pending_relationship_candidates_suppressed: int
    pending_relationship_candidates_kept: int
    protected_manual_records_skipped: int
    unresolved_relationship_deltas: dict[str, int]


@asynccontextmanager
async def _repair_session(db: AsyncSession | None = None):
    if db is not None:
        yield db
        return

    async with AsyncSessionLocal() as session:
        yield session


def _candidate_names(character: Character) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in [character.name, *(character.aliases or [])]:
        candidate = " ".join(str(value or "").split()).strip()
        if not candidate:
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def _character_label_map(characters: list[Character]) -> dict[str, str]:
    return {
        str(character.id): character.name
        for character in characters
        if character.id is not None and str(character.name or "").strip()
    }


def _has_manual_edit_markers(character: Character) -> bool:
    trait_state = dict(character.trait_state or {})
    manual_description = trait_state.get("manual_description")
    manual_entry = trait_state.get("manual_entry")
    return bool(
        getattr(character, "is_manual", False)
        or (
            isinstance(manual_description, dict)
            and str(manual_description.get("value") or "").strip()
        )
        or (isinstance(manual_entry, dict) and str(manual_entry.get("value") or "").strip())
    )


def _is_protected_character(character: Character) -> bool:
    metadata = dict(character.analysis_metadata or {})
    return bool(
        _has_manual_edit_markers(character)
        or _has_meaningful_profile(character)
        or int(character.mention_count or 0) >= 6
        or len(character.states or []) > 0
        or getattr(character, "voice_profile", None) is not None
        or bool(metadata.get("user_reviewed"))
        or bool(metadata.get("user_curated"))
        or bool(metadata.get("protected_from_repair"))
    )


def _auto_mergeable(
    suggestion, *, primary: Character | None = None, secondary: Character | None = None
) -> bool:
    reasons = {str(reason).strip().lower() for reason in (suggestion.reasons or [])}
    if primary is not None and _is_protected_character(primary):
        return False
    if secondary is not None and _is_protected_character(secondary):
        return False
    return bool(
        suggestion.status == CHARACTER_DUPLICATE_PENDING
        and (
            int(suggestion.confidence or 0) >= 90
            or "exact name match" in reasons
            or "primary name appears in alias list" in reasons
        )
    )


async def _load_characters(db, book_id: uuid.UUID) -> list[Character]:
    return (
        (
            await db.execute(
                select(Character)
                .options(
                    selectinload(Character.states),
                    selectinload(Character.relationships_as_a),
                    selectinload(Character.relationships_as_b),
                    selectinload(Character.voice_profile),
                )
                .where(Character.book_id == book_id)
                .order_by(Character.first_chapter.asc(), Character.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def _load_chapter_rows(db, book_id: uuid.UUID) -> list[tuple[int, str]]:
    chapters = (
        await db.execute(
            select(Chapter.number, Chapter.s3_key)
            .where(Chapter.book_id == book_id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    rows: list[tuple[int, str]] = []
    from app.core.storage import download_book
    from app.utils.reader_utils import deserialize_manuscript_content

    for chapter_number, s3_key in chapters:
        if not s3_key:
            continue
        try:
            raw = await asyncio.to_thread(download_book, s3_key)
            payload = deserialize_manuscript_content(raw)
        except Exception:
            continue
        text = str(payload.get("text") or "").strip() if isinstance(payload, dict) else ""
        if text:
            rows.append((int(chapter_number or 0), text))
    return rows


def _chapter_mentions(chapter_rows: list[tuple[int, str]], names: list[str]) -> list[int]:
    from app.utils.characters.manual import _find_name_occurrences

    hits: list[int] = []
    for chapter_number, text in chapter_rows:
        if any(_find_name_occurrences(text, candidate) > 0 for candidate in names):
            hits.append(chapter_number)
    return hits


async def _load_pending_relationship_candidates(
    db, book_id: uuid.UUID
) -> list[CharacterRelationshipCandidate]:
    return (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book_id,
                    CharacterRelationshipCandidate.status
                    == CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
                )
            )
        )
        .scalars()
        .all()
    )


async def _load_pending_character_candidates(db, book_id: uuid.UUID) -> list[CharacterCandidate]:
    return (
        (
            await db.execute(
                select(CharacterCandidate).where(
                    CharacterCandidate.book_id == book_id,
                    CharacterCandidate.status == CHARACTER_CANDIDATE_PENDING,
                )
            )
        )
        .scalars()
        .all()
    )


def _candidate_cleanup_disposition(candidate: CharacterCandidate):
    return decide_character_candidate_disposition(
        name=candidate.proposed_name or candidate.raw_name,
        aliases=candidate.aliases or [],
        confidence=candidate.confidence,
        reason_codes=candidate.reason_codes or [],
        evidence=candidate.evidence or {},
        matched_character_id=candidate.matched_character_id,
    )


def _relationship_cleanup_disposition(candidate: CharacterRelationshipCandidate):
    return decide_relationship_candidate_disposition(
        raw_character_a=candidate.raw_character_a,
        raw_character_b=candidate.raw_character_b,
        left_resolved=candidate.matched_character_a_id is not None,
        right_resolved=candidate.matched_character_b_id is not None,
        reason_codes=candidate.reason_codes or [],
        evidence=candidate.evidence or {},
    )


async def _load_character_mentions(
    db, book_id: uuid.UUID
) -> dict[uuid.UUID, list[CharacterMention]]:
    rows = (
        (
            await db.execute(
                select(CharacterMention)
                .where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.matched_character_id.is_not(None),
                )
                .order_by(CharacterMention.chapter_number.asc(), CharacterMention.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[uuid.UUID, list[CharacterMention]] = {}
    for row in rows:
        if row.matched_character_id is None:
            continue
        grouped.setdefault(row.matched_character_id, []).append(row)
    return grouped


def _chapter_excerpt(text: str, names: list[str]) -> str | None:
    from app.utils.characters.manual import _find_name_occurrences

    for candidate in names:
        occurrences = _find_name_occurrences(text, candidate)
        if occurrences <= 0:
            continue
        index = text.casefold().find(candidate.casefold())
        if index < 0:
            index = 0
        excerpt = " ".join(text[max(0, index - 90) : min(len(text), index + 180)].split()).strip()
        if excerpt:
            return excerpt
    return None


async def _repair_verification(
    character: Character,
    *,
    mention_rows: list[CharacterMention],
    chapter_rows: list[tuple[int, str]],
) -> dict[str, Any]:
    names = _candidate_names(character)
    snippets: list[tuple[int, str, CharacterMention | None]] = []
    for row in mention_rows:
        text = " ".join(str(row.mention_text or "").split()).strip()
        if text:
            snippets.append((int(row.chapter_number or 0), text, row))
    if not snippets:
        for chapter_number, text in chapter_rows:
            excerpt = _chapter_excerpt(text, names)
            if excerpt:
                snippets.append((int(chapter_number or 0), excerpt, None))
            if len(snippets) >= 6:
                break

    accepted_chapters: list[int] = []
    review_chapters: list[int] = []
    rejected_chapters: list[int] = []
    row_results: list[dict[str, Any]] = []
    for chapter_number, snippet, row in snippets[:8]:
        verifier = await verify_character_candidate_personhood(
            snippet,
            character.name,
            aliases=list(character.aliases or []),
            entity_type="person",
        )
        final = verifier.get("final") if isinstance(verifier, dict) else {}
        band = str(final.get("confidence_band") or "").strip() if isinstance(final, dict) else ""
        row_results.append(
            {
                "chapter_number": chapter_number,
                "snippet": snippet,
                "band": band,
                "verifier": verifier,
                "row": row,
            }
        )
        if band == "accept":
            accepted_chapters.append(chapter_number)
        elif band == "review":
            review_chapters.append(chapter_number)
        else:
            rejected_chapters.append(chapter_number)

    if accepted_chapters and not rejected_chapters:
        overall_band = "accept"
    elif accepted_chapters or review_chapters:
        overall_band = "review"
    else:
        overall_band = "reject" if row_results else "review"

    return {
        "overall_band": overall_band,
        "accepted_chapters": sorted({chapter for chapter in accepted_chapters if chapter > 0}),
        "review_chapters": sorted({chapter for chapter in review_chapters if chapter > 0}),
        "rejected_chapters": sorted({chapter for chapter in rejected_chapters if chapter > 0}),
        "rows": row_results,
    }


async def build_repair_plan(
    book_id: uuid.UUID,
    *,
    allow_merge_safe_pairs: bool,
    allow_demote_obvious_noise: bool,
    db: AsyncSession | None = None,
) -> RepairPlan:
    async with _repair_session(db) as session:
        book = await session.get(Book, book_id)
        if book is None:
            raise SystemExit(f"Book not found: {book_id}")

        characters = await _load_characters(session, book_id)
        initial_character_labels = _character_label_map(characters)
        character_map = {
            character.id: character for character in characters if character.id is not None
        }
        suggestions = await refresh_character_duplicate_suggestions(
            session, book_id=book_id, characters=characters
        )
        character_candidates = await _load_pending_character_candidates(session, book_id)
        relationship_candidates = await _load_pending_relationship_candidates(session, book_id)
        pending_character_candidates_suppressed = sum(
            1
            for candidate in character_candidates
            if _candidate_cleanup_disposition(candidate).status == CHARACTER_CANDIDATE_SUPPRESSED
        )
        pending_relationship_candidates_suppressed = sum(
            1
            for candidate in relationship_candidates
            if _relationship_cleanup_disposition(candidate).status
            == CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED
        )
        planned_merges: list[tuple[str, str]] = []
        skipped_protected_merge_pairs: list[tuple[str, str]] = []
        for item in suggestions:
            primary = character_map.get(item.primary_character_id)
            secondary = character_map.get(item.secondary_character_id)
            if _auto_mergeable(item, primary=primary, secondary=secondary):
                if allow_merge_safe_pairs:
                    planned_merges.append(
                        (str(item.primary_character_id), str(item.secondary_character_id))
                    )
            elif (
                primary is not None
                and secondary is not None
                and (_is_protected_character(primary) or _is_protected_character(secondary))
            ):
                skipped_protected_merge_pairs.append(
                    (str(item.primary_character_id), str(item.secondary_character_id))
                )

        planned_demotions: list[str] = []
        skipped_protected_demotions: list[str] = []
        mention_rows_by_character = await _load_character_mentions(session, book_id)
        chapter_rows = await _load_chapter_rows(session, book_id)
        for character in characters:
            verification = await _repair_verification(
                character,
                mention_rows=mention_rows_by_character.get(character.id, []),
                chapter_rows=chapter_rows,
            )
            is_noise, _reasons = _is_obvious_noise_character(character)
            trust_tier, _trust_reasons = infer_character_trust_tier(character)
            if (
                verification["overall_band"] != "reject"
                and not is_noise
                and trust_tier == "visible"
            ):
                continue
            if _is_protected_character(character):
                skipped_protected_demotions.append(str(character.id))
                continue
            if allow_demote_obvious_noise:
                planned_demotions.append(str(character.id))

        candidates_by_key = {
            character.id: _candidate_names(character)
            for character in characters
            if character.id is not None
        }
        first_chapters = await find_earliest_character_mention_chapters(
            session,
            book_id=book_id,
            candidates_by_key=candidates_by_key,
            upto_chapter=int(book.total_chapters or 0) or None,
        )
        first_chapter_updates: dict[str, int] = {
            str(key): int(value) for key, value in first_chapters.items()
        }
        last_seen_updates: dict[str, int] = {}
        for character in characters:
            verification = await _repair_verification(
                character,
                mention_rows=mention_rows_by_character.get(character.id, []),
                chapter_rows=chapter_rows,
            )
            verified_hits = verification["accepted_chapters"] or verification["review_chapters"]
            if verified_hits:
                first_chapter_updates[str(character.id)] = verified_hits[0]
                last_seen_updates[str(character.id)] = verified_hits[-1]
                continue
            chapter_hits = _chapter_mentions(chapter_rows, _candidate_names(character))
            if chapter_hits:
                last_seen_updates[str(character.id)] = chapter_hits[-1]

        return RepairPlan(
            book_id=str(book_id),
            dry_run=True,
            allow_merge_safe_pairs=allow_merge_safe_pairs,
            allow_demote_obvious_noise=allow_demote_obvious_noise,
            planned_merges=planned_merges,
            planned_demotions=planned_demotions,
            skipped_protected_merge_pairs=skipped_protected_merge_pairs,
            skipped_protected_demotions=skipped_protected_demotions,
            updated_first_chapters=first_chapter_updates,
            updated_last_seen_chapters=last_seen_updates,
            character_labels=initial_character_labels,
            pending_duplicate_suggestions=sum(
                1 for item in suggestions if item.status == CHARACTER_DUPLICATE_PENDING
            ),
            pending_relationship_candidates=len(relationship_candidates),
            pending_character_candidates_suppressed=pending_character_candidates_suppressed,
            pending_character_candidates_kept=len(character_candidates)
            - pending_character_candidates_suppressed,
            pending_relationship_candidates_suppressed=pending_relationship_candidates_suppressed,
            pending_relationship_candidates_kept=len(relationship_candidates)
            - pending_relationship_candidates_suppressed,
            protected_manual_records_skipped=len(skipped_protected_demotions)
            + len(skipped_protected_merge_pairs),
            unresolved_relationship_deltas={
                "before": len(relationship_candidates),
                "after_if_apply": len(relationship_candidates)
                - pending_relationship_candidates_suppressed,
            },
        )


async def apply_repair_plan(
    book_id: uuid.UUID,
    *,
    allow_merge_safe_pairs: bool,
    allow_demote_obvious_noise: bool,
    db: AsyncSession | None = None,
) -> dict[str, object]:
    async with _repair_session(db) as session:
        book = await session.get(Book, book_id)
        if book is None:
            raise SystemExit(f"Book not found: {book_id}")

        if not allow_merge_safe_pairs and not allow_demote_obvious_noise:
            raise SystemExit(
                "No repair actions enabled. Pass --allow-merge-safe-pairs and/or --allow-demote-obvious-noise."
            )

        characters = await _load_characters(session, book_id)
        initial_character_labels = _character_label_map(characters)
        character_map = {
            character.id: character for character in characters if character.id is not None
        }
        suggestions = await refresh_character_duplicate_suggestions(
            session, book_id=book_id, characters=characters
        )
        character_candidates_before = await _load_pending_character_candidates(session, book_id)
        relationship_candidates_before = await _load_pending_relationship_candidates(
            session, book_id
        )
        suppressed_character_candidate_ids: list[str] = []
        kept_character_candidate_ids: list[str] = []
        for candidate in character_candidates_before:
            disposition = _candidate_cleanup_disposition(candidate)
            if disposition.status == CHARACTER_CANDIDATE_SUPPRESSED:
                candidate.status = CHARACTER_CANDIDATE_SUPPRESSED
                candidate.reason_codes = list(disposition.reason_codes)
                candidate.evidence = disposition.evidence
                suppressed_character_candidate_ids.append(str(candidate.id))
            else:
                kept_character_candidate_ids.append(str(candidate.id))

        suppressed_relationship_candidate_ids: list[str] = []
        kept_relationship_candidate_ids: list[str] = []
        for candidate in relationship_candidates_before:
            disposition = _relationship_cleanup_disposition(candidate)
            if disposition.status == CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED:
                candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED
                candidate.reason_codes = list(disposition.reason_codes)
                candidate.evidence = disposition.evidence
                suppressed_relationship_candidate_ids.append(str(candidate.id))
            else:
                kept_relationship_candidate_ids.append(str(candidate.id))

        merged_pairs: list[tuple[str, str]] = []
        skipped_protected_merge_pairs: list[tuple[str, str]] = []
        for suggestion in suggestions:
            primary = character_map.get(suggestion.primary_character_id)
            secondary = character_map.get(suggestion.secondary_character_id)
            if not _auto_mergeable(suggestion, primary=primary, secondary=secondary):
                if (
                    primary is not None
                    and secondary is not None
                    and (_is_protected_character(primary) or _is_protected_character(secondary))
                ):
                    skipped_protected_merge_pairs.append(
                        (
                            str(suggestion.primary_character_id),
                            str(suggestion.secondary_character_id),
                        )
                    )
                continue
            if not allow_merge_safe_pairs or not primary or not secondary:
                continue
            await merge_characters(session, primary.id, secondary.id, book_id)
            merged_pairs.append((str(primary.id), str(secondary.id)))
        await session.flush()

        characters = await _load_characters(session, book_id)
        mention_rows_by_character = await _load_character_mentions(session, book_id)
        chapter_rows = await _load_chapter_rows(session, book_id)
        demoted_character_ids: list[str] = []
        skipped_protected_demotions: list[str] = []
        for character in characters:
            verification = await _repair_verification(
                character,
                mention_rows=mention_rows_by_character.get(character.id, []),
                chapter_rows=chapter_rows,
            )
            is_noise, reasons = _is_obvious_noise_character(character)
            trust_tier, trust_reasons = infer_character_trust_tier(character)
            if (
                verification["overall_band"] != "reject"
                and not is_noise
                and trust_tier == "visible"
            ):
                continue
            if _is_protected_character(character):
                skipped_protected_demotions.append(str(character.id))
                continue
            if not allow_demote_obvious_noise:
                continue
            set_character_review_state(
                character,
                visibility_state=CHARACTER_VISIBILITY_NOISE,
                approval_state=CHARACTER_APPROVAL_REJECTED,
                approval_source=CHARACTER_APPROVAL_SOURCE_BACKFILL_REVIEW,
                reason_codes=["repair_demoted_noise", *list(reasons), *list(trust_reasons)],
                action="character_backfill_suppressed",
                details={"repair_verifier_band": verification["overall_band"]},
            )
            await record_character_candidate(
                session,
                book_id=book_id,
                chapter_number=int(character.first_chapter or 1),
                raw_name=character.name,
                proposed_name=character.name,
                aliases=character.aliases or [],
                matched_character_id=character.id,
                status=CHARACTER_CANDIDATE_SUPPRESSED,
                confidence=0,
                reason_codes=["repair_demoted_noise", *list(reasons), *list(trust_reasons)],
                evidence={
                    "verifier": {
                        "final": {
                            "confidence_band": verification["overall_band"],
                            "accepted_chapters": verification["accepted_chapters"],
                            "review_chapters": verification["review_chapters"],
                            "rejected_chapters": verification["rejected_chapters"],
                        }
                    },
                    "repair_source": {
                        "character_id": str(character.id),
                        "mention_count": int(character.mention_count or 0),
                        "first_chapter": int(character.first_chapter or 0),
                        "last_seen_chapter": int(character.last_seen_chapter or 0)
                        if character.last_seen_chapter
                        else None,
                        "trust_tier": CHARACTER_TRUST_TIER_REPAIRED_NOISE,
                        "trust_reasons": trust_reasons,
                    },
                },
                source_batch_key=f"repair:{book_id}:{character.id}",
            )
            demoted_character_ids.append(str(character.id))
        await session.flush()

        characters = await _load_characters(session, book_id)
        mention_rows_by_character = await _load_character_mentions(session, book_id)
        candidates_by_key = {
            character.id: _candidate_names(character)
            for character in characters
            if character.id is not None
        }
        first_chapters = await find_earliest_character_mention_chapters(
            session,
            book_id=book_id,
            candidates_by_key=candidates_by_key,
            upto_chapter=int(book.total_chapters or 0) or None,
        )
        first_chapter_recomputes: dict[str, int] = {}
        last_seen_recomputes: dict[str, int] = {}
        for character in characters:
            verification = await _repair_verification(
                character,
                mention_rows=mention_rows_by_character.get(character.id, []),
                chapter_rows=chapter_rows,
            )
            verified_hits = verification["accepted_chapters"] or verification["review_chapters"]
            first = verified_hits[0] if verified_hits else first_chapters.get(character.id)
            if first and first < int(character.first_chapter or first):
                character.first_chapter = int(first)
                first_chapter_recomputes[str(character.id)] = int(first)
            hits = verified_hits or _chapter_mentions(chapter_rows, _candidate_names(character))
            if hits:
                character.last_seen_chapter = hits[-1]
                last_seen_recomputes[str(character.id)] = hits[-1]
                if character.first_chapter > character.last_seen_chapter:
                    character.first_chapter = character.last_seen_chapter
            elif character.last_seen_chapter is None:
                character.last_seen_chapter = int(character.first_chapter or 1)
            metadata = dict(character.analysis_metadata or {})
            trust_tier, trust_reasons = infer_character_trust_tier(character)
            metadata["repair_status"] = "recomputed"
            metadata["normalized_name"] = normalize_character_name(character.name)
            metadata["trust_tier"] = (
                trust_tier
                if is_cast_visible_character(character)
                else CHARACTER_TRUST_TIER_REPAIRED_NOISE
            )
            metadata["trust_reasons"] = trust_reasons
            metadata["repair_verifier"] = {
                "confidence_band": verification["overall_band"],
                "accepted_chapters": verification["accepted_chapters"],
                "review_chapters": verification["review_chapters"],
                "rejected_chapters": verification["rejected_chapters"],
            }
            character.analysis_metadata = metadata

            for item in verification["rows"]:
                row = item.get("row")
                if row is None:
                    continue
                merged_evidence = dict(row.evidence or {})
                merged_evidence["repair_verifier"] = item.get("verifier")
                row.evidence = merged_evidence

        refreshed = await refresh_character_duplicate_suggestions(
            session, book_id=book_id, characters=characters
        )
        relationship_candidates_after = await _load_pending_relationship_candidates(
            session, book_id
        )
        candidates = (
            (
                await session.execute(
                    select(CharacterCandidate).where(CharacterCandidate.book_id == book_id)
                )
            )
            .scalars()
            .all()
        )
        await session.commit()
        return {
            "book_id": str(book_id),
            "merged_pairs": merged_pairs,
            "demoted_character_ids": demoted_character_ids,
            "skipped_protected_merge_pairs": skipped_protected_merge_pairs,
            "skipped_protected_demotions": skipped_protected_demotions,
            "pending_character_candidates_suppressed": len(suppressed_character_candidate_ids),
            "pending_character_candidates_kept": len(kept_character_candidate_ids),
            "pending_relationship_candidates_suppressed": len(
                suppressed_relationship_candidate_ids
            ),
            "pending_relationship_candidates_kept": len(kept_relationship_candidate_ids),
            "suppressed_character_candidate_ids": suppressed_character_candidate_ids,
            "suppressed_relationship_candidate_ids": suppressed_relationship_candidate_ids,
            "first_chapter_recomputes": first_chapter_recomputes,
            "last_seen_chapter_recomputes": last_seen_recomputes,
            "character_labels": initial_character_labels,
            "duplicate_suggestion_delta": {
                "pending_after": sum(
                    1 for item in refreshed if item.status == CHARACTER_DUPLICATE_PENDING
                ),
            },
            "unresolved_relationship_deltas": {
                "before": len(relationship_candidates_before),
                "after": len(relationship_candidates_after),
            },
            "review": build_character_review_payload(
                candidates, refreshed, relationship_candidates_after
            ),
        }


def _write_output_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair duplicate/noisy character-bible data for a book."
    )
    parser.add_argument("--book-id", type=uuid.UUID, required=True, help="Target book ID.")
    parser.add_argument(
        "--apply", action="store_true", help="Apply the repair plan instead of printing a dry run."
    )
    parser.add_argument(
        "--confirm-apply",
        type=str,
        default="",
        help=f"Required confirmation token for apply mode: {CONFIRM_TOKEN}",
    )
    parser.add_argument(
        "--allow-merge-safe-pairs",
        action="store_true",
        help="Allow high-confidence duplicate merges.",
    )
    parser.add_argument(
        "--allow-demote-obvious-noise",
        action="store_true",
        help="Allow demotion of obvious noise characters into review candidates.",
    )
    parser.add_argument(
        "--output-json", type=str, default=None, help="Optional path to write the report JSON."
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    if args.apply:
        if args.confirm_apply != CONFIRM_TOKEN:
            raise SystemExit(f"Apply mode requires --confirm-apply {CONFIRM_TOKEN}")
        result = await apply_repair_plan(
            args.book_id,
            allow_merge_safe_pairs=bool(args.allow_merge_safe_pairs),
            allow_demote_obvious_noise=bool(args.allow_demote_obvious_noise),
        )
        _write_output_json(args.output_json, result)
        log.info("character_bible_repair_applied %s", json.dumps(result, default=str))
        return
    plan = await build_repair_plan(
        args.book_id,
        allow_merge_safe_pairs=bool(args.allow_merge_safe_pairs),
        allow_demote_obvious_noise=bool(args.allow_demote_obvious_noise),
    )
    payload = asdict(plan)
    _write_output_json(args.output_json, payload)
    log.info("character_bible_repair_plan %s", json.dumps(payload, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
