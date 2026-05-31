"""Summarize character-bible extraction diagnostics for a single book."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterCandidate, CharacterDuplicateSuggestion, CharacterRelationshipCandidate
from scripts.audit_character_bible_noise import _is_obvious_noise_character


def _parser_character_diagnostics(book: Book) -> dict[str, Any]:
    workspace = dict(book.writer_workspace or {})
    processing = workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    parser = processing.get("parser_diagnostics") if isinstance(processing.get("parser_diagnostics"), dict) else {}
    return parser.get("character_extraction") if isinstance(parser.get("character_extraction"), dict) else {}


def _async_database_url(raw_url: str) -> str:
    url = make_url(raw_url.replace("postgresql://", "postgresql+psycopg://", 1))
    return url.render_as_string(hide_password=False)


@asynccontextmanager
async def _diagnostics_session() -> AsyncIterator[AsyncSession]:
    test_database_url = os.getenv("TEST_DATABASE_URL")
    if not test_database_url:
        async with AsyncSessionLocal() as db:
            yield db
        return

    engine = create_async_engine(_async_database_url(test_database_url), echo=False)
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_local() as db:
            yield db
    finally:
        await engine.dispose()


async def build_report(book_id: uuid.UUID, compare_after_repair_json: str | None = None) -> dict[str, Any]:
    async with _diagnostics_session() as db:
        book = await db.get(Book, book_id)
        if book is None:
            raise SystemExit(f"Book not found: {book_id}")

        characters = (
            await db.execute(
                select(Character)
                .where(Character.book_id == book_id)
                .options(
                    selectinload(Character.states),
                    selectinload(Character.relationships_as_a),
                    selectinload(Character.relationships_as_b),
                    selectinload(Character.voice_profile),
                )
            )
        ).scalars().all()
        candidates = (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book_id))).scalars().all()
        duplicates = (await db.execute(select(CharacterDuplicateSuggestion).where(CharacterDuplicateSuggestion.book_id == book_id))).scalars().all()
        relationship_candidates = (
            await db.execute(select(CharacterRelationshipCandidate).where(CharacterRelationshipCandidate.book_id == book_id))
        ).scalars().all()
        chapters = (await db.execute(select(Chapter).where(Chapter.book_id == book_id))).scalars().all()

        noisy_count = 0
        protected_count = 0
        for character in characters:
            metadata = dict(character.analysis_metadata or {})
            if metadata.get("protected_from_repair") or metadata.get("user_curated") or metadata.get("user_reviewed") or character.is_manual:
                protected_count += 1
            is_noise, _ = _is_obvious_noise_character(character)
            if is_noise:
                noisy_count += 1

        diagnostics = _parser_character_diagnostics(book)
        summary = {
            "book_id": str(book_id),
            "character_count": len(characters),
            "pending_character_candidates": sum(1 for item in candidates if item.status == "pending"),
            "pending_duplicate_suggestions": sum(1 for item in duplicates if item.status == "pending"),
            "pending_relationship_candidates": sum(1 for item in relationship_candidates if item.status == "pending"),
            "unresolved_relationship_count": sum(1 for item in relationship_candidates if item.status == "pending"),
            "saved_characters": int(diagnostics.get("saved_characters") or 0),
            "quarantined_candidates": int(diagnostics.get("quarantined_candidates") or 0),
            "rejected_entities": int(diagnostics.get("rejected_entities") or 0),
            "relationships_persisted": int(diagnostics.get("relationships_persisted") or 0),
            "duplicate_suggestions": int(diagnostics.get("duplicate_suggestions") or 0),
            "chapter_media_count": int(diagnostics.get("chapter_media_count") or 0),
            "media_marker_count": int(diagnostics.get("media_marker_count") or 0),
            "media_anomaly": int(diagnostics.get("chapter_media_count") or 0) != int(diagnostics.get("media_marker_count") or 0),
            "cover_available": bool(diagnostics.get("cover_available")),
            "protected_character_count": protected_count,
            "likely_noisy_character_count": noisy_count,
            "chapter_count": len(chapters),
        }
        if compare_after_repair_json:
            compare_payload = json.loads(open(compare_after_repair_json, "r", encoding="utf-8").read())
            summary["compare_after_repair"] = {
                "merged_pairs": len(compare_payload.get("merged_pairs") or []),
                "demoted_character_ids": len(compare_payload.get("demoted_character_ids") or []),
                "pending_duplicate_suggestions_after": (
                    (compare_payload.get("duplicate_suggestion_delta") or {}).get("pending_after")
                ),
                "unresolved_relationship_after": (
                    (compare_payload.get("unresolved_relationship_deltas") or {}).get("after")
                ),
            }
        return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report character-bible diagnostics for a book.")
    parser.add_argument("--book-id", type=uuid.UUID, required=True, help="Target book ID.")
    parser.add_argument("--compare-after-repair-json", type=str, default=None, help="Optional JSON output from the repair script to compare against.")
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    report = await build_report(args.book_id, compare_after_repair_json=args.compare_after_repair_json)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
