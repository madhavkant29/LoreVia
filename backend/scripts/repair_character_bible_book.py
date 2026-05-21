"""Repair polluted character-bible data for an existing book.

Dry-run by default:
    python scripts/repair_character_bible_book.py --book-id <uuid>

Apply changes after reviewing the plan:
    python scripts/repair_character_bible_book.py --book-id <uuid> --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterCandidate
from app.utils.character_utils import (
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_DUPLICATE_PENDING,
    build_character_review_payload,
    find_earliest_character_mention_chapters,
    merge_characters,
    normalize_character_name,
    record_character_candidate,
    refresh_character_duplicate_suggestions,
)
from app.utils.logging import get_logger

from scripts.audit_character_bible_noise import _is_obvious_noise_character

log = get_logger("lorevia.repair.character_bible")


@dataclass(frozen=True)
class RepairPlan:
    auto_merge_pairs: list[tuple[str, str]]
    demote_character_ids: list[str]
    updated_first_chapters: dict[str, int]
    updated_last_seen_chapters: dict[str, int]
    pending_duplicate_suggestions: int


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


def _auto_mergeable(suggestion) -> bool:
    reasons = {str(reason).strip().lower() for reason in (suggestion.reasons or [])}
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
    ).scalars().all()


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
    from app.utils.character_utils import _find_name_occurrences

    hits: list[int] = []
    for chapter_number, text in chapter_rows:
        if any(_find_name_occurrences(text, candidate) > 0 for candidate in names):
            hits.append(chapter_number)
    return hits


async def build_repair_plan(book_id: uuid.UUID) -> RepairPlan:
    async with AsyncSessionLocal() as db:
        book = await db.get(Book, book_id)
        if book is None:
            raise SystemExit(f"Book not found: {book_id}")

        characters = await _load_characters(db, book_id)
        suggestions = await refresh_character_duplicate_suggestions(db, book_id=book_id, characters=characters)
        auto_merge_pairs = [
            (str(item.primary_character_id), str(item.secondary_character_id))
            for item in suggestions
            if _auto_mergeable(item)
        ]
        demote_character_ids = [
            str(character.id)
            for character in characters
            if _is_obvious_noise_character(character)[0]
        ]

        chapter_rows = await _load_chapter_rows(db, book_id)
        candidates_by_key = {
            character.id: _candidate_names(character)
            for character in characters
            if character.id is not None
        }
        first_chapters = await find_earliest_character_mention_chapters(
            db,
            book_id=book_id,
            candidates_by_key=candidates_by_key,
            upto_chapter=int(book.total_chapters or 0) or None,
        )
        last_seen_updates: dict[str, int] = {}
        for character in characters:
            chapter_hits = _chapter_mentions(chapter_rows, _candidate_names(character))
            if chapter_hits:
                last_seen_updates[str(character.id)] = chapter_hits[-1]

        return RepairPlan(
            auto_merge_pairs=auto_merge_pairs,
            demote_character_ids=demote_character_ids,
            updated_first_chapters={str(key): int(value) for key, value in first_chapters.items()},
            updated_last_seen_chapters=last_seen_updates,
            pending_duplicate_suggestions=sum(1 for item in suggestions if item.status == CHARACTER_DUPLICATE_PENDING),
        )


async def apply_repair_plan(book_id: uuid.UUID) -> dict[str, object]:
    async with AsyncSessionLocal() as db:
        book = await db.get(Book, book_id)
        if book is None:
            raise SystemExit(f"Book not found: {book_id}")

        characters = await _load_characters(db, book_id)
        suggestions = await refresh_character_duplicate_suggestions(db, book_id=book_id, characters=characters)
        merged_pairs: list[tuple[str, str]] = []
        for suggestion in suggestions:
            if not _auto_mergeable(suggestion):
                continue
            primary = await db.get(Character, suggestion.primary_character_id)
            secondary = await db.get(Character, suggestion.secondary_character_id)
            if not primary or not secondary:
                continue
            await merge_characters(db, primary.id, secondary.id, book_id)
            merged_pairs.append((str(primary.id), str(secondary.id)))
        await db.flush()

        characters = await _load_characters(db, book_id)
        demoted_character_ids: list[str] = []
        for character in characters:
            is_noise, reasons = _is_obvious_noise_character(character)
            if not is_noise:
                continue
            await record_character_candidate(
                db,
                book_id=book_id,
                chapter_number=int(character.first_chapter or 1),
                raw_name=character.name,
                proposed_name=character.name,
                aliases=character.aliases or [],
                matched_character_id=None,
                status=CHARACTER_CANDIDATE_PENDING,
                confidence=0,
                reason_codes=["repair_demoted_noise", *list(reasons)],
                evidence={
                    "repair_source": {
                        "character_id": str(character.id),
                        "mention_count": int(character.mention_count or 0),
                        "first_chapter": int(character.first_chapter or 0),
                        "last_seen_chapter": int(character.last_seen_chapter or 0) if character.last_seen_chapter else None,
                    }
                },
                source_batch_key=f"repair:{book_id}:{character.id}",
            )
            await db.delete(character)
            demoted_character_ids.append(str(character.id))
        await db.flush()

        characters = await _load_characters(db, book_id)
        candidates_by_key = {
            character.id: _candidate_names(character)
            for character in characters
            if character.id is not None
        }
        first_chapters = await find_earliest_character_mention_chapters(
            db,
            book_id=book_id,
            candidates_by_key=candidates_by_key,
            upto_chapter=int(book.total_chapters or 0) or None,
        )
        chapter_rows = await _load_chapter_rows(db, book_id)
        for character in characters:
            first = first_chapters.get(character.id)
            if first and first < int(character.first_chapter or first):
                character.first_chapter = int(first)
            hits = _chapter_mentions(chapter_rows, _candidate_names(character))
            if hits:
                character.last_seen_chapter = hits[-1]
                if character.first_chapter > character.last_seen_chapter:
                    character.first_chapter = character.last_seen_chapter
            elif character.last_seen_chapter is None:
                character.last_seen_chapter = int(character.first_chapter or 1)
            metadata = dict(character.analysis_metadata or {})
            metadata["repair_status"] = "recomputed"
            metadata["normalized_name"] = normalize_character_name(character.name)
            character.analysis_metadata = metadata

        refreshed = await refresh_character_duplicate_suggestions(db, book_id=book_id, characters=characters)
        candidates = (
            await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book_id))
        ).scalars().all()
        await db.commit()
        return {
            "book_id": str(book_id),
            "merged_pairs": merged_pairs,
            "demoted_character_ids": demoted_character_ids,
            "review": build_character_review_payload(candidates, refreshed),
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair duplicate/noisy character-bible data for a book.")
    parser.add_argument("--book-id", type=uuid.UUID, required=True, help="Target book ID.")
    parser.add_argument("--apply", action="store_true", help="Apply the repair plan instead of printing a dry run.")
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    if args.apply:
        result = await apply_repair_plan(args.book_id)
        log.info("character_bible_repair_applied %s", json.dumps(result, default=str))
        return
    plan = await build_repair_plan(args.book_id)
    log.info("character_bible_repair_plan %s", json.dumps(asdict(plan), default=str))


if __name__ == "__main__":
    asyncio.run(_main())
