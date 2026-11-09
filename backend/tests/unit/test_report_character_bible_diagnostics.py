import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterVoiceProfile,
)
from app.models.intelligence import AdvisorSuggestionJob
from app.models.user import User
from scripts import report_character_bible_diagnostics
from scripts.report_character_bible_diagnostics import build_report, verify_chapter_source_hash


def test_diagnostics_script_can_be_invoked_by_path_from_backend_workdir():
    backend_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/report_character_bible_diagnostics.py", "--help"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--verify-source" in result.stdout
    assert "--include-candidates" in result.stdout


@pytest.mark.asyncio
async def test_diagnostics_cli_disables_sql_echo_before_querying(monkeypatch, capsys):
    fake_engine = SimpleNamespace(echo=True)
    book_id = "book-1"

    async def fake_report(_book_id, **_kwargs):
        assert fake_engine.echo is False
        return {"book_id": book_id, "character_count": 7}

    monkeypatch.setattr(report_character_bible_diagnostics, "engine", fake_engine)
    monkeypatch.setattr(
        report_character_bible_diagnostics,
        "_parse_args",
        lambda: SimpleNamespace(
            book_id=book_id,
            compare_after_repair_json=None,
            verify_source=True,
            include_candidates=False,
        ),
    )
    monkeypatch.setattr(report_character_bible_diagnostics, "build_report", fake_report)

    await report_character_bible_diagnostics._main()

    assert json.loads(capsys.readouterr().out) == {"book_id": book_id, "character_count": 7}


@pytest.mark.asyncio
async def test_build_report_summarizes_character_and_media_diagnostics(db, tmp_path, monkeypatch):
    stored_source = "X" * 250

    committed_before_storage = False

    def download_source(_key):
        assert committed_before_storage, "source verification must not hold the read transaction"
        return stored_source.encode("utf-8")

    monkeypatch.setattr("app.utils.ingestion_utils.download_book", download_source)
    user = User(
        email="report-diagnostics@lorevia.app", username="reportdiagnostics", password_hash="hash"
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Diagnostics",
        format="pdf",
        s3_key="books/diagnostics.pdf",
        status="ready",
        writer_workspace={
            "processing": {
                "parser_diagnostics": {
                    "character_extraction": {
                        "saved_characters": 4,
                        "quarantined_candidates": 2,
                        "rejected_entities": 3,
                        "relationships_persisted": 1,
                        "duplicate_suggestions": 5,
                        "chapter_media_count": 1,
                        "media_marker_count": 2,
                        "cover_available": True,
                    }
                }
            }
        },
    )
    db.add(book)
    await db.flush()

    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title="Ashfall",
            s3_key="chapters/diagnostics/1.txt",
            word_count=42,
            processed=True,
            analysis_state={
                "status": "succeeded",
                "source_integrity": {
                    "extraction_coverage": {
                        "complete": True,
                        "source_characters": 250,
                        "profile_enrichment": {
                            "status": "partial",
                            "identity_clusters": 2,
                            "evidence_passages": 3,
                            "unanchored_references": 1,
                        },
                        "ranges": [{"chunk_index": 0, "start": 0, "end": 250}],
                        "chunks": [
                            {
                                "chunk_index": 0,
                                "length": 250,
                                "sha256": hashlib.sha256(stored_source.encode()).hexdigest(),
                            }
                        ],
                    }
                },
            },
        )
    )
    curated_character = Character(
        book_id=book.id,
        name="Nora Vale",
        first_chapter=1,
        mention_count=7,
        analysis_metadata={
            "user_curated": True,
            "profile_claims": [
                {"field": "goal", "value": "protect the gate", "quote": "I will protect the gate."}
            ],
        },
    )
    noisy_character = Character(
        book_id=book.id,
        name="Please",
        first_chapter=1,
        mention_count=1,
        analysis_metadata={},
    )
    db.add(curated_character)
    db.add(noisy_character)
    await db.flush()
    db.add(
        CharacterVoiceProfile(
            book_id=book.id,
            character_id=curated_character.id,
            sample_dialogue_count=2,
            sample_word_count=37,
        )
    )
    db.add(
        CharacterCandidate(
            book_id=book.id,
            chapter_number=1,
            raw_name="Gregor's sister",
            proposed_name="Gregor's sister",
            normalized_name="gregor sister",
            aliases=[],
            status="pending",
            confidence=61,
            reason_codes=["needs_review"],
            mention_count=1,
            evidence={
                "verifier": {
                    "final": {
                        "is_person": True,
                        "confidence_band": "review",
                        "reason": "private source passage must not appear in diagnostics",
                    }
                }
            },
        )
    )
    db.add_all(
        [
            CharacterMention(
                book_id=book.id,
                chapter_number=1,
                raw_name="Nora Vale",
                normalized_name="nora vale",
                matched_character_id=curated_character.id,
            ),
            CharacterMention(
                book_id=book.id,
                chapter_number=1,
                raw_name="Unknown visitor",
                normalized_name="unknown visitor",
            ),
        ]
    )
    db.add(
        AdvisorSuggestionJob(
            user_id=user.id,
            book_id=book.id,
            status="complete",
            result_json={
                "suggestions": [{"title": "Check the gate"}],
                "meta": {
                    "audit_failure_category": "capacity",
                    "audit_groups_total": 3,
                    "audit_groups_completed": 1,
                },
            },
        )
    )
    db.add(
        CharacterDuplicateSuggestion(
            book_id=book.id,
            primary_character_id=curated_character.id,
            secondary_character_id=noisy_character.id,
            confidence=91,
            reasons=["Exact overlap"],
            shared_evidence={},
            status="pending",
        )
    )
    db.add(
        CharacterRelationshipCandidate(
            book_id=book.id,
            chapter_number=2,
            raw_character_a="Grete",
            raw_character_b="Gregor's father",
            rel_type="family",
            status="pending",
            reason_codes=["relationship_unresolved"],
            evidence={},
        )
    )
    await db.commit()

    original_commit = AsyncSession.commit

    async def record_commit(session):
        nonlocal committed_before_storage
        await original_commit(session)
        committed_before_storage = True

    monkeypatch.setattr(AsyncSession, "commit", record_commit)

    compare_path = tmp_path / "repair-report.json"
    compare_path.write_text(
        json.dumps(
            {
                "merged_pairs": [["char-1", "char-2"]],
                "demoted_character_ids": ["char-3"],
                "duplicate_suggestion_delta": {"pending_after": 2},
                "unresolved_relationship_deltas": {"after": 0},
            }
        ),
        encoding="utf-8",
    )

    report = await build_report(
        book.id, compare_after_repair_json=str(compare_path), verify_source=True
    )

    assert report["character_count"] == 2
    assert report["pending_character_candidates"] == 1
    assert report["pending_duplicate_suggestions"] == 1
    assert report["pending_relationship_candidates"] == 1
    assert report["unresolved_relationship_count"] == 1
    assert report["saved_characters"] == 4
    assert report["quarantined_candidates"] == 2
    assert report["rejected_entities"] == 3
    assert report["relationships_persisted"] == 1
    assert report["duplicate_suggestions"] == 5
    assert report["chapter_media_count"] == 1
    assert report["media_marker_count"] == 2
    assert report["media_anomaly"] is True
    assert report["cover_available"] is True
    assert report["protected_character_count"] == 1
    assert report["likely_noisy_character_count"] == 1
    assert report["chapter_count"] == 1
    assert report["book_status"] == "ready"
    assert report["candidate_status_counts"] == {"pending": 1}
    assert report["unanchored_candidate_count"] == 0
    assert report["candidate_adjudication_counts"] == {"unknown": 1}
    assert report["candidate_reason_codes_by_status"] == {"pending": {"needs_review": 1}}
    assert report["relationship_reason_codes_by_status"] == {
        "pending": {"relationship_unresolved": 1}
    }
    assert report["pending_candidate_reason_codes"] == {"needs_review": 1}
    assert report["pending_candidate_verifier_bands"] == {"review": 1}
    assert report["pending_candidate_mention_buckets"] == {"1": 1}
    assert report["chapter_extraction_coverage"] == [
        {
            "chapter_number": 1,
            "processed": True,
            "word_count": 42,
            "analysis_status": "succeeded",
            "coverage_complete": True,
            "source_characters": 250,
            "source_ranges": 1,
            "profile_enrichment": {
                "status": "partial",
                "identity_clusters": 2,
                "evidence_passages": 3,
                "unanchored_references": 1,
            },
            "candidate_count": 1,
            "mention_count": 2,
            "unresolved_mentions": 1,
            "source_verification": {"status": "match", "source_characters": 250},
        }
    ]
    assert report["cast"][0]["name"] == "Nora Vale"
    assert report["cast"][0]["profile_claim_count"] == 1
    assert report["cast"][0]["voice_baseline_samples"] == 2
    assert report["latest_advisor_scan"] == {
        "status": "complete",
        "error_code": None,
        "suggestion_count": 1,
        "audit_failure_category": "capacity",
        "audit_groups_total": 3,
        "audit_groups_completed": 1,
    }
    assert "I will protect the gate." not in json.dumps(report)
    assert "candidate_audit" not in report
    assert report["voice_profile_count"] == 1
    assert report["voice_baseline_samples"] == 2
    assert report["voice_baseline_words"] == 37
    assert report["compare_after_repair"] == {
        "merged_pairs": 1,
        "demoted_character_ids": 1,
        "pending_duplicate_suggestions_after": 2,
        "unresolved_relationship_after": 0,
    }

    audit_report = await build_report(book.id, include_candidates=True)
    assert len(audit_report["candidate_audit"]) == 1
    audit_candidate = audit_report["candidate_audit"][0]
    assert str(uuid.UUID(audit_candidate["id"])) == audit_candidate["id"]
    assert {key: value for key, value in audit_candidate.items() if key != "id"} == {
        "name": "Gregor's sister",
        "raw_name": "Gregor's sister",
        "chapter_number": 1,
        "status": "pending",
        "adjudication_status": None,
        "entity_type": None,
        "mention_count": 1,
        "chapter_count": None,
        "reason_codes": ["needs_review"],
        "rejection_reason": None,
        "matched_character_id": None,
        "source_batch_key": None,
        "verifier_is_person": True,
        "verifier_confidence_band": "review",
    }
    assert "private source passage" not in json.dumps(audit_report)


@pytest.mark.asyncio
async def test_diagnostics_groups_suppression_reasons_without_disclosing_candidate_names(db):
    user = User(
        email="report-suppressions@lorevia.app",
        username="reportsuppressions",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Suppression Audit",
        format="pdf",
        s3_key="books/suppression-audit.pdf",
    )
    db.add(book)
    await db.flush()
    db.add_all(
        [
            CharacterCandidate(
                book_id=book.id,
                chapter_number=1,
                raw_name="private manuscript candidate",
                proposed_name="private manuscript candidate",
                normalized_name="private manuscript candidate",
                aliases=[],
                status="suppressed",
                reason_codes=["not_a_person", "low_support"],
            ),
            CharacterCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_name="another private candidate",
                proposed_name="another private candidate",
                normalized_name="another private candidate",
                aliases=[],
                status="pending",
                reason_codes=["low_support"],
            ),
            CharacterRelationshipCandidate(
                book_id=book.id,
                chapter_number=1,
                raw_character_a="private source name one",
                raw_character_b="private source name two",
                rel_type="family",
                status="suppressed",
                reason_codes=["missing_source_quote", "unresolved_identity"],
                evidence={},
            ),
            CharacterRelationshipCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_character_a="private source name three",
                raw_character_b="private source name four",
                rel_type="family",
                status="suppressed",
                reason_codes=["missing_source_quote"],
                evidence={},
            ),
        ]
    )
    await db.commit()

    report = await build_report(book.id)

    assert report["candidate_reason_codes_by_status"] == {
        "pending": {"low_support": 1},
        "suppressed": {"not_a_person": 1, "low_support": 1},
    }
    assert report["relationship_reason_codes_by_status"] == {
        "suppressed": {"missing_source_quote": 2, "unresolved_identity": 1}
    }
    assert "private manuscript candidate" not in json.dumps(report)
    assert "private source name" not in json.dumps(report)


@pytest.mark.asyncio
async def test_build_report_marks_pre_coverage_chapters_unknown_instead_of_incomplete(db):
    user = User(email="old-report@lorevia.app", username="oldreport", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Older Book",
        format="pdf",
        s3_key="books/older-book.pdf",
        status="ready",
        writer_workspace={},
    )
    db.add(book)
    await db.flush()
    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title="Old Chapter",
            s3_key="chapters/older-book/1.txt",
            processed=True,
            analysis_state={"status": "succeeded"},
        )
    )
    await db.commit()

    report = await build_report(book.id)

    assert report["chapter_extraction_coverage"] == [
        {
            "chapter_number": 1,
            "processed": True,
            "word_count": None,
            "analysis_status": "succeeded",
            "coverage_complete": None,
            "source_characters": None,
            "source_ranges": None,
            "candidate_count": 0,
            "mention_count": 0,
            "unresolved_mentions": 0,
        }
    ]
    assert report["latest_advisor_scan"] is None
    assert (await build_report(book.id, include_candidates=True))["candidate_audit"] == []


@pytest.mark.asyncio
async def test_build_report_exposes_failed_batch_without_manuscript_text(db, monkeypatch):
    source = "Mara waited near the gate."
    recorded_key = "chapters/stale/1.txt"
    requested_keys: list[str] = []

    def download_source(storage_key: str) -> bytes:
        requested_keys.append(storage_key)
        if storage_key != f"chapters/{book.id}/1.txt":
            raise FileNotFoundError(storage_key)
        return source.encode()

    monkeypatch.setattr("app.utils.ingestion_utils.download_book", download_source)
    user = User(
        email="failed-batch-report@lorevia.app",
        username="failedbatchreport",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Failed Batch",
        format="txt",
        s3_key="books/failed-batch.txt",
        status="failed",
        writer_workspace={},
    )
    db.add(book)
    await db.flush()
    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title="Gate",
            s3_key=recorded_key,
            processed=False,
            analysis_state={
                "status": "pending",
                "source_integrity": {
                    "extraction_attempt": {
                        "complete": False,
                        "failure_stage": "character_discovery",
                        "source_characters": len(source),
                        "chunks": [
                            {
                                "chunk_index": 0,
                                "length": len(source),
                                "sha256": hashlib.sha256(source.encode()).hexdigest(),
                            }
                        ],
                        "ranges": [
                            {"chunk_index": 0, "start": 0, "end": len(source), "batch_index": 1}
                        ],
                        "batch_outcomes": [
                            {
                                "batch_index": 1,
                                "status": "failed",
                                "error_type": "TimeoutError",
                            }
                        ],
                    }
                },
            },
        )
    )
    await db.commit()

    report = await build_report(book.id, verify_source=True)
    chapter = report["chapter_extraction_coverage"][0]

    assert chapter["processed"] is False
    assert chapter["coverage_complete"] is False
    assert chapter["failure_stage"] == "character_discovery"
    assert chapter["batch_outcomes"] == [
        {"batch_index": 1, "status": "failed", "error_type": "TimeoutError"}
    ]
    assert chapter["source_verification"]["status"] == "source_match_extraction_incomplete"
    assert requested_keys == [recorded_key, f"chapters/{book.id}/1.txt"]
    assert source not in json.dumps(report)


def test_source_hash_verification_distinguishes_absent_mismatched_and_valid_metadata():
    source = "An original chapter passage."
    coverage = {
        "complete": True,
        "source_characters": len(source),
        "chunks": [{"length": len(source), "sha256": hashlib.sha256(source.encode()).hexdigest()}],
        "ranges": [{"chunk_index": 0, "start": 0, "end": len(source)}],
    }
    assert verify_chapter_source_hash(source, None)["status"] == "not_recorded"
    assert verify_chapter_source_hash(source, {"chunks": []})["status"] == "unverifiable_metadata"
    assert verify_chapter_source_hash(source, coverage)["status"] == "match"
    assert (
        verify_chapter_source_hash(source, {**coverage, "complete": False})["status"]
        == "source_match_extraction_incomplete"
    )
    assert verify_chapter_source_hash(source + " changed", coverage)["status"] == "mismatch"
    assert (
        verify_chapter_source_hash(
            source, {**coverage, "ranges": [{"chunk_index": 0, "start": 1, "end": len(source)}]}
        )["status"]
        == "mismatch"
    )
