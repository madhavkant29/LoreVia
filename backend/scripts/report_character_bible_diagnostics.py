"""Summarize character-bible extraction diagnostics for a single book."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, engine
from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterMention,
    CharacterRelationshipCandidate,
)
from app.models.intelligence import AdvisorSuggestionJob
from app.utils.ingestion_utils import load_processing_chapter_payload
from scripts.audit_character_bible_noise import _is_obvious_noise_character


def _parser_character_diagnostics(book: Book) -> dict[str, Any]:
    workspace = dict(book.writer_workspace or {})
    processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    parser = (
        processing.get("parser_diagnostics")
        if isinstance(processing.get("parser_diagnostics"), dict)
        else {}
    )
    return (
        parser.get("character_extraction")
        if isinstance(parser.get("character_extraction"), dict)
        else {}
    )


def verify_chapter_source_hash(text: str, coverage: object) -> dict[str, Any]:
    """Compare stored source against one complete, hash-tracked extraction chunk."""
    if not isinstance(coverage, dict):
        return {"status": "not_recorded", "source_characters": len(text)}
    chunks = coverage.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != 1 or not isinstance(chunks[0], dict):
        return {"status": "unverifiable_metadata", "source_characters": len(text)}
    recorded = chunks[0]
    expected_hash = recorded.get("sha256")
    expected_length = recorded.get("length")
    if not isinstance(expected_hash, str) or not isinstance(expected_length, int):
        return {"status": "unverifiable_metadata", "source_characters": len(text)}
    ranges = coverage.get("ranges")
    if not isinstance(ranges, list):
        return {"status": "unverifiable_metadata", "source_characters": len(text)}
    cursor = 0
    for span in sorted(
        ranges,
        key=lambda item: (
            item["start"] if isinstance(item, dict) and isinstance(item.get("start"), int) else -1
        ),
    ):
        if not isinstance(span, dict):
            return {"status": "unverifiable_metadata", "source_characters": len(text)}
        start, end = span.get("start"), span.get("end")
        if (
            span.get("chunk_index") != 0
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end > len(text)
            or end <= start
            or start > cursor
        ):
            return {"status": "mismatch", "source_characters": len(text)}
        cursor = max(cursor, end)
    matches = (
        coverage.get("source_characters") == len(text)
        and expected_length == len(text)
        and expected_hash == hashlib.sha256(text.encode("utf-8")).hexdigest()
        and cursor == len(text)
    )
    status = (
        "match"
        if matches and coverage.get("complete") is True
        else "source_match_extraction_incomplete"
        if matches
        else "mismatch"
    )
    return {"status": status, "source_characters": len(text)}


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


async def build_report(
    book_id: uuid.UUID,
    compare_after_repair_json: str | None = None,
    *,
    verify_source: bool = False,
    include_candidates: bool = False,
) -> dict[str, Any]:
    async with _diagnostics_session() as db:
        book = await db.get(Book, book_id)
        if book is None:
            raise SystemExit(f"Book not found: {book_id}")

        characters = (
            (
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
            )
            .scalars()
            .all()
        )
        candidates = (
            (
                await db.execute(
                    select(CharacterCandidate).where(CharacterCandidate.book_id == book_id)
                )
            )
            .scalars()
            .all()
        )
        duplicates = (
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
        relationship_candidates = (
            (
                await db.execute(
                    select(CharacterRelationshipCandidate).where(
                        CharacterRelationshipCandidate.book_id == book_id
                    )
                )
            )
            .scalars()
            .all()
        )
        mentions = (
            (await db.execute(select(CharacterMention).where(CharacterMention.book_id == book_id)))
            .scalars()
            .all()
        )
        advisor_job = (
            (
                await db.execute(
                    select(AdvisorSuggestionJob)
                    .where(AdvisorSuggestionJob.book_id == book_id)
                    .order_by(AdvisorSuggestionJob.updated_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        chapters = (
            (await db.execute(select(Chapter).where(Chapter.book_id == book_id))).scalars().all()
        )

        noisy_count = 0
        protected_count = 0
        for character in characters:
            metadata = dict(character.analysis_metadata or {})
            if (
                metadata.get("protected_from_repair")
                or metadata.get("user_curated")
                or metadata.get("user_reviewed")
                or character.is_manual
            ):
                protected_count += 1
            is_noise, _ = _is_obvious_noise_character(character)
            if is_noise:
                noisy_count += 1

        diagnostics = _parser_character_diagnostics(book)
        processing = (
            (book.writer_workspace or {}).get("processing")
            if isinstance(book.writer_workspace, dict)
            else None
        )
        processing = processing if isinstance(processing, dict) else {}
        candidate_statuses = Counter(str(item.status or "unknown") for item in candidates)
        candidate_adjudications = Counter(
            str(item.adjudication_status or "unknown") for item in candidates
        )
        candidate_rejection_reasons = Counter(
            str(item.rejection_reason) for item in candidates if item.rejection_reason
        )
        candidate_reasons_by_status: dict[str, Counter[str]] = {}
        for item in candidates:
            status = str(item.status or "unknown")
            candidate_reasons_by_status.setdefault(status, Counter()).update(
                str(reason).strip() for reason in (item.reason_codes or []) if str(reason).strip()
            )
        relationship_reasons_by_status: dict[str, Counter[str]] = {}
        for item in relationship_candidates:
            status = str(item.status or "unknown")
            relationship_reasons_by_status.setdefault(status, Counter()).update(
                str(reason).strip() for reason in (item.reason_codes or []) if str(reason).strip()
            )
        pending_candidates = [item for item in candidates if item.status == "pending"]
        pending_reason_codes = Counter(
            str(reason)
            for item in pending_candidates
            for reason in (item.reason_codes or [])
            if str(reason).strip()
        )
        pending_verifier_bands: Counter[str] = Counter()
        pending_mention_buckets: Counter[str] = Counter()
        for item in pending_candidates:
            evidence = item.evidence if isinstance(item.evidence, dict) else {}
            verifier = evidence.get("verifier")
            verifier = verifier if isinstance(verifier, dict) else {}
            final = verifier.get("final")
            final = final if isinstance(final, dict) else {}
            pending_verifier_bands[str(final.get("confidence_band") or "not_recorded")] += 1
            candidate_mentions = int(item.mention_count or 0)
            pending_mention_buckets[
                str(candidate_mentions) if candidate_mentions < 3 else "3_plus"
            ] += 1
        candidates_by_chapter = Counter(item.chapter_number for item in candidates)
        mentions_by_chapter = Counter(item.chapter_number for item in mentions)
        unresolved_mentions_by_chapter = Counter(
            item.chapter_number for item in mentions if item.matched_character_id is None
        )
        # All required rows are loaded. Release the read transaction before
        # potentially slow object-storage downloads in --verify-source mode.
        if verify_source:
            await db.commit()
        chapter_coverage = []
        for chapter in sorted(chapters, key=lambda item: item.number):
            state = chapter.analysis_state if isinstance(chapter.analysis_state, dict) else {}
            integrity = (
                state.get("source_integrity")
                if isinstance(state.get("source_integrity"), dict)
                else {}
            )
            coverage = (
                integrity.get("extraction_coverage")
                if isinstance(integrity.get("extraction_coverage"), dict)
                else None
            )
            attempt = (
                integrity.get("extraction_attempt")
                if isinstance(integrity.get("extraction_attempt"), dict)
                else None
            )
            recorded_coverage = coverage or attempt
            chapter_entry = {
                "chapter_number": chapter.number,
                "processed": bool(chapter.processed),
                "word_count": chapter.word_count,
                "analysis_status": state.get("status"),
                "coverage_complete": recorded_coverage.get("complete")
                if recorded_coverage
                else None,
                "source_characters": recorded_coverage.get("source_characters")
                if recorded_coverage
                else None,
                "source_ranges": len(recorded_coverage.get("ranges") or [])
                if recorded_coverage
                else None,
                "candidate_count": candidates_by_chapter[chapter.number],
                "mention_count": mentions_by_chapter[chapter.number],
                "unresolved_mentions": unresolved_mentions_by_chapter[chapter.number],
            }
            if recorded_coverage and isinstance(recorded_coverage.get("batch_outcomes"), list):
                chapter_entry["batch_outcomes"] = recorded_coverage["batch_outcomes"]
            profile_enrichment = (
                recorded_coverage.get("profile_enrichment") if recorded_coverage else None
            )
            if isinstance(profile_enrichment, dict):
                profile_summary = {
                    "status": profile_enrichment.get("status"),
                    "identity_clusters": profile_enrichment.get("identity_clusters"),
                    "evidence_passages": profile_enrichment.get("evidence_passages"),
                    "unanchored_references": profile_enrichment.get("unanchored_references"),
                }
                if "invalid_response_batches" in profile_enrichment:
                    profile_summary["invalid_response_batches"] = profile_enrichment[
                        "invalid_response_batches"
                    ]
                chapter_entry["profile_enrichment"] = profile_summary
            if attempt:
                chapter_entry["failure_stage"] = attempt.get("failure_stage")
                profile_stage = attempt.get("profile_enrichment")
                if isinstance(profile_stage, dict) and profile_stage.get("status") == "failed":
                    chapter_entry["profile_failure_type"] = profile_stage.get("error_type")
            if verify_source:
                try:
                    payload = await load_processing_chapter_payload(
                        book_id,
                        chapter.number,
                        chapter_s3_key=chapter.s3_key,
                        chapter_title=chapter.title,
                    )
                    source_verification = (
                        verify_chapter_source_hash(payload["text"], recorded_coverage)
                        if payload is not None
                        else {"status": "unavailable", "error_type": "missing_source"}
                    )
                except Exception as exc:
                    source_verification = {
                        "status": "unavailable",
                        "error_type": type(exc).__name__,
                    }
                chapter_entry["source_verification"] = source_verification
            chapter_coverage.append(chapter_entry)
        voice_profiles = [
            character.voice_profile for character in characters if character.voice_profile
        ]
        advisor_result = (
            advisor_job.result_json
            if advisor_job and isinstance(advisor_job.result_json, dict)
            else {}
        )
        advisor_meta = advisor_result.get("meta")
        advisor_meta = advisor_meta if isinstance(advisor_meta, dict) else {}
        cast_summary = []
        for character in sorted(characters, key=lambda item: item.name.casefold()):
            metadata = (
                character.analysis_metadata if isinstance(character.analysis_metadata, dict) else {}
            )
            claim_records = metadata.get("profile_claims")
            cast_summary.append(
                {
                    "name": character.name,
                    "first_chapter": character.first_chapter,
                    "last_seen_chapter": character.last_seen_chapter,
                    "mention_count": character.mention_count,
                    "profile_claim_count": len(claim_records)
                    if isinstance(claim_records, list)
                    else 0,
                    "voice_baseline_samples": character.voice_profile.sample_dialogue_count
                    if character.voice_profile
                    else 0,
                }
            )
        summary = {
            "book_id": str(book_id),
            "processing_run_id": processing.get("processing_run_id"),
            "book_status": book.status,
            "character_count": len(characters),
            "candidate_status_counts": dict(candidate_statuses),
            "unanchored_candidate_count": sum(
                "unanchored_character_reference" in (item.reason_codes or []) for item in candidates
            ),
            "candidate_adjudication_counts": dict(candidate_adjudications),
            "candidate_rejection_reasons": dict(candidate_rejection_reasons),
            "candidate_reason_codes_by_status": {
                status: dict(reasons)
                for status, reasons in sorted(candidate_reasons_by_status.items())
            },
            "relationship_reason_codes_by_status": {
                status: dict(reasons)
                for status, reasons in sorted(relationship_reasons_by_status.items())
            },
            "pending_candidate_reason_codes": dict(pending_reason_codes),
            "pending_candidate_verifier_bands": dict(pending_verifier_bands),
            "pending_candidate_mention_buckets": dict(pending_mention_buckets),
            "chapter_extraction_coverage": chapter_coverage,
            "voice_profile_count": len(voice_profiles),
            "voice_baseline_samples": sum(
                item.sample_dialogue_count or 0 for item in voice_profiles
            ),
            "voice_baseline_words": sum(item.sample_word_count or 0 for item in voice_profiles),
            "cast": cast_summary,
            "latest_advisor_scan": {
                "status": advisor_job.status,
                "error_code": advisor_job.error_code,
                "suggestion_count": len(advisor_result.get("suggestions") or []),
                "audit_failure_category": advisor_meta.get("audit_failure_category"),
                "audit_groups_total": advisor_meta.get("audit_groups_total"),
                "audit_groups_completed": advisor_meta.get("audit_groups_completed"),
            }
            if advisor_job
            else None,
            "pending_character_candidates": sum(
                1 for item in candidates if item.status == "pending"
            ),
            "suppressed_character_candidates": sum(
                1 for item in candidates if item.status == "suppressed"
            ),
            "pending_duplicate_suggestions": sum(
                1 for item in duplicates if item.status == "pending"
            ),
            "pending_relationship_candidates": sum(
                1 for item in relationship_candidates if item.status == "pending"
            ),
            "suppressed_relationship_candidates": sum(
                1 for item in relationship_candidates if item.status == "suppressed"
            ),
            "unresolved_relationship_count": sum(
                1 for item in relationship_candidates if item.status == "pending"
            ),
            "saved_characters": int(diagnostics.get("saved_characters") or 0),
            "quarantined_candidates": int(diagnostics.get("quarantined_candidates") or 0),
            "rejected_entities": int(diagnostics.get("rejected_entities") or 0),
            "relationships_persisted": int(diagnostics.get("relationships_persisted") or 0),
            "duplicate_suggestions": int(diagnostics.get("duplicate_suggestions") or 0),
            "chapter_media_count": int(diagnostics.get("chapter_media_count") or 0),
            "media_marker_count": int(diagnostics.get("media_marker_count") or 0),
            "media_anomaly": int(diagnostics.get("chapter_media_count") or 0)
            != int(diagnostics.get("media_marker_count") or 0),
            "cover_available": bool(diagnostics.get("cover_available")),
            "protected_character_count": protected_count,
            "likely_noisy_character_count": noisy_count,
            "chapter_count": len(chapters),
        }
        if include_candidates:
            # Names may originate in manuscript text, so this audit is opt-in.
            # Evidence snippets and free-form verifier explanations are excluded.
            # The candidate list is intentionally not truncated.
            summary["candidate_audit"] = []
            for item in sorted(
                candidates,
                key=lambda candidate: (
                    candidate.chapter_number or 0,
                    (candidate.proposed_name or "").casefold(),
                    str(candidate.id),
                ),
            ):
                evidence = item.evidence if isinstance(item.evidence, dict) else {}
                verifier = evidence.get("verifier")
                verifier = verifier if isinstance(verifier, dict) else {}
                final = verifier.get("final")
                final = final if isinstance(final, dict) else {}
                summary["candidate_audit"].append(
                    {
                        "id": str(item.id),
                        "name": item.proposed_name,
                        "raw_name": item.raw_name,
                        "chapter_number": item.chapter_number,
                        "status": item.status,
                        "adjudication_status": item.adjudication_status,
                        "entity_type": item.entity_type,
                        "mention_count": item.mention_count,
                        "chapter_count": item.chapter_count,
                        "reason_codes": list(item.reason_codes or []),
                        "rejection_reason": item.rejection_reason,
                        "matched_character_id": (
                            str(item.matched_character_id) if item.matched_character_id else None
                        ),
                        "source_batch_key": item.source_batch_key,
                        "verifier_is_person": final.get("is_person")
                        if isinstance(final.get("is_person"), bool)
                        else None,
                        "verifier_confidence_band": final.get("confidence_band"),
                    }
                )
        if compare_after_repair_json:
            compare_payload = json.loads(open(compare_after_repair_json, encoding="utf-8").read())
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
    parser.add_argument(
        "--verify-source",
        action="store_true",
        help="Read stored chapter objects and compare hashes without printing manuscript text.",
    )
    parser.add_argument(
        "--include-candidates",
        action="store_true",
        help="Include source-derived candidate names and dispositions; review before sharing.",
    )
    parser.add_argument(
        "--compare-after-repair-json",
        type=str,
        default=None,
        help="Optional JSON output from the repair script to compare against.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    # Diagnostic output is meant to contain counts and hashes, not SQL/parameters.
    engine.echo = False
    report = await build_report(
        args.book_id,
        compare_after_repair_json=args.compare_after_repair_json,
        verify_source=args.verify_source,
        include_candidates=args.include_candidates,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
