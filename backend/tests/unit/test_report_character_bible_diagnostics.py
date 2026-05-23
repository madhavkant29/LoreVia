import json

import pytest

from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterRelationshipCandidate,
)
from app.models.user import User
from scripts.report_character_bible_diagnostics import build_report


@pytest.mark.asyncio
async def test_build_report_summarizes_character_and_media_diagnostics(db, tmp_path):
    user = User(email="report-diagnostics@lorevia.app", username="reportdiagnostics", password_hash="hash")
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

    db.add(Chapter(book_id=book.id, number=1, title="Ashfall", s3_key="chapters/diagnostics/1.txt"))
    curated_character = Character(
        book_id=book.id,
        name="Nora Vale",
        first_chapter=1,
        mention_count=7,
        analysis_metadata={"user_curated": True},
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
            evidence={},
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

    report = await build_report(book.id, compare_after_repair_json=str(compare_path))

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
    assert report["compare_after_repair"] == {
        "merged_pairs": 1,
        "demoted_character_ids": 1,
        "pending_duplicate_suggestions_after": 2,
        "unresolved_relationship_after": 0,
    }
