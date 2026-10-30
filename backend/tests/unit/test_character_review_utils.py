import uuid

import numpy as np
import pytest
from sqlalchemy import select

from app.models.book import Book
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDecisionEvent,
    CharacterDuplicateSuggestion,
    CharacterMention,
    CharacterRelationshipCandidate,
)
from app.models.operations import AiQualityEvent
from app.models.user import User
from app.utils.characters.candidates import (
    can_auto_persist_character_candidate,
    decide_character_candidate_disposition,
    decide_relationship_candidate_disposition,
)
from app.utils.characters.constants import (
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_CANDIDATE_SUPPRESSED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED,
)
from app.utils.characters.duplicates import score_duplicate_characters
from app.utils.characters.extraction import record_character_mention
from app.utils.characters.review import (
    record_character_candidate,
    record_relationship_candidate,
)
from app.utils.characters.review_serialization import build_character_review_payload
from app.utils.characters.serialization import build_character_roster_snapshot


def test_disposition_gate_suppresses_weak_verifier_review_candidate():
    disposition = decide_character_candidate_disposition(
        name="Chapitre",
        reason_codes=["mention_verifier_review"],
        evidence={
            "mention_count": 1,
            "verifier": {
                "final": {
                    "confidence_band": "review",
                    "is_person_like": False,
                    "reasons": ["sentence_start_capitalization_only"],
                }
            },
        },
    )

    assert disposition.status == CHARACTER_CANDIDATE_SUPPRESSED
    assert disposition.action == "suppress"
    assert "mention_verifier_review_suppressed" in disposition.reason_codes


def test_disposition_gate_allows_llm_confirmed_person_into_review():
    disposition = decide_character_candidate_disposition(
        name="Mira",
        confidence=0.52,
        reason_codes=["candidate_dossier_needs_review"],
        evidence={
            "mention_count": 1,
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "verifier": {
                "llm": {"used": True, "is_person_like": True, "confidence": 0.83},
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": ["llm_confirmed_person"],
                },
            },
        },
    )

    assert disposition.status == CHARACTER_CANDIDATE_PENDING
    assert disposition.visible_review_allowed is True


def test_disposition_suppresses_unanchored_reference_despite_model_confidence():
    disposition = decide_character_candidate_disposition(
        name="Imaginary Person",
        confidence=0.99,
        reason_codes=["unanchored_character_reference"],
        evidence={
            "mention_count": 3,
            "strong_mention_count": 2,
            "has_dialogue_or_action": True,
            "verifier": {
                "llm": {"is_person_like": True},
                "final": {"confidence_band": "accept", "is_person_like": True},
            },
        },
    )

    assert disposition.status == CHARACTER_CANDIDATE_SUPPRESSED
    assert disposition.action == "suppress"
    assert "unanchored_character_reference" in disposition.reason_codes


def test_auto_persist_gate_allows_grounded_first_pass_full_name():
    assert (
        can_auto_persist_character_candidate(
            name="Anna Sergeyevna",
            aliases=[],
            evidence={
                "mention_count": 3,
                "strong_mention_count": 2,
                "has_dialogue_or_action": True,
                "has_physical_description": True,
                "verifier": {
                    "local": {
                        "person_ner_mentions": 1,
                        "mid_sentence_mentions": 1,
                    },
                    "final": {
                        "confidence_band": "accept",
                        "is_person_like": True,
                        "reasons": [],
                    },
                },
            },
        )
        is True
    )


def test_auto_persist_gate_keeps_unnamed_role_in_review_despite_strong_evidence():
    assert (
        can_auto_persist_character_candidate(
            name="examining magistrate",
            evidence={
                "mention_count": 5,
                "strong_mention_count": 4,
                "source_mention_count_verified": True,
                "has_attributed_speech": True,
                "has_physical_description": True,
                "verifier": {
                    "local": {"person_ner_mentions": 1, "mid_sentence_mentions": 3},
                    "final": {"confidence_band": "accept", "is_person_like": True},
                },
            },
        )
        is False
    )


def test_auto_persist_gate_allows_grounded_full_name_with_soft_multi_token_ambiguity():
    assert (
        can_auto_persist_character_candidate(
            name="Gregor Samsa",
            aliases=[],
            evidence={
                "mention_count": 77,
                "strong_mention_count": 38,
                "has_dialogue_or_action": True,
                "has_physical_description": True,
                "verifier": {
                    "local": {
                        "person_ner_mentions": 1,
                        "non_person_ner_mentions": 0,
                        "mid_sentence_mentions": 48,
                    },
                    "final": {
                        "confidence_band": "accept",
                        "is_person_like": True,
                        "reasons": ["llm_confirmed_person", "ambiguous_multi_token_mention"],
                    },
                },
            },
        )
        is True
    )


def test_auto_persist_gate_allows_obvious_fallback_name_with_shared_identity_support():
    assert (
        can_auto_persist_character_candidate(
            name="Gregor Samsa",
            aliases=["Gregor"],
            evidence={
                "mention_count": 3,
                "strong_mention_count": 2,
                "has_dialogue_or_action": True,
                "has_physical_description": True,
                "deterministic_fallback": True,
                "cluster_names": ["Gregor Samsa", "Gregor"],
                "entity": {"canonical_name": "Gregor"},
                "verifier": {
                    "local": {
                        "person_ner_mentions": 1,
                        "mid_sentence_mentions": 1,
                    },
                    "final": {
                        "confidence_band": "accept",
                        "is_person_like": True,
                        "reasons": [],
                    },
                },
            },
        )
        is True
    )


def test_disposition_gate_suppresses_rejected_verifier_candidate():
    disposition = decide_character_candidate_disposition(
        name="Mais",
        reason_codes=["mention_verifier_rejected"],
        evidence={
            "mention_count": 1,
            "verifier": {
                "final": {
                    "confidence_band": "reject",
                    "is_person_like": False,
                    "reasons": ["interjection_like_usage"],
                }
            },
        },
    )

    assert disposition.status == CHARACTER_CANDIDATE_SUPPRESSED
    assert disposition.action == "reject"
    assert "mention_verifier_rejected" in disposition.reason_codes


def test_relationship_disposition_suppresses_noise_endpoint():
    disposition = decide_relationship_candidate_disposition(
        raw_character_a="Gregor",
        raw_character_b="Texte",
        left_resolved=True,
        right_resolved=False,
        reason_codes=["relationship_unresolved", "character_b_missing"],
        evidence={"relationship": {"description": "Texte appears as a heading."}},
    )

    assert disposition.status == CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED
    assert "character_b_suppressed" in disposition.reason_codes


def test_build_character_roster_snapshot_marks_manual_anchors():
    character = Character(
        id=None,
        book_id=None,
        name="Hitagi Senjogahara",
        aliases=["Hitagi", "Senjogahara"],
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=4,
        personality_tags=["sharp"],
        motivations=["protect Araragi"],
        arc_summary="Guarded but emotionally precise.",
        is_manual=True,
    )

    snapshot = build_character_roster_snapshot([character])

    assert snapshot[0]["name"] == "Hitagi Senjogahara"
    assert snapshot[0]["aliases"] == ["Hitagi", "Senjogahara"]
    assert snapshot[0]["is_manual"] is True


def test_score_duplicate_characters_hides_first_name_alias_pair_below_review_threshold():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Tsubasa Hanekawa",
        aliases=["Hanekawa"],
        role="sc",
        first_chapter=1,
        mention_count=5,
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Tsubasa",
        aliases=["Hanekawa", "Tsubasa Hanekawa"],
        role="sc",
        first_chapter=1,
        mention_count=2,
    )

    suggestion = score_duplicate_characters(primary, secondary)

    assert suggestion is None


def test_score_duplicate_characters_hides_descriptor_pair_below_review_threshold():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Grete",
        aliases=[],
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=5,
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000012"),
        book_id=primary.book_id,
        name="Gregor's sister",
        aliases=[],
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=2,
    )

    suggestion = score_duplicate_characters(
        primary,
        secondary,
        left_evidence={"cluster_keys": {"grete"}, "chapter_numbers": {1, 2}},
        right_evidence={"cluster_keys": {"grete"}, "chapter_numbers": {1, 2}},
    )

    assert suggestion is None


def test_score_duplicate_characters_uses_embedding_similarity_signal():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000021"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Anna Sergeyevna",
        aliases=["Anna"],
        role="sc",
        first_chapter=2,
        mention_count=4,
        embedding=[0.8, 0.1, 0.2],
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000022"),
        book_id=primary.book_id,
        name="Anna Sergeyevna",
        aliases=["Anna Sergeyevna"],
        role="sc",
        first_chapter=2,
        mention_count=2,
        embedding=[0.79, 0.11, 0.19],
    )

    suggestion = score_duplicate_characters(primary, secondary)

    assert suggestion is not None
    assert any(
        reason in suggestion["reasons"]
        for reason in ["High embedding similarity", "Related embedding similarity"]
    )
    assert suggestion["shared_evidence"]["embedding_similarity"] is not None


def test_score_duplicate_characters_accepts_numpy_embeddings():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000031"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Anna Sergeyevna",
        aliases=["Anna"],
        role="sc",
        first_chapter=2,
        mention_count=4,
        embedding=np.array([0.8, 0.1, 0.2]),
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000032"),
        book_id=primary.book_id,
        name="Anna Sergeyevna",
        aliases=["Anna Sergeyevna"],
        role="sc",
        first_chapter=2,
        mention_count=2,
        embedding=np.array([0.79, 0.11, 0.19]),
    )

    suggestion = score_duplicate_characters(primary, secondary)

    assert suggestion is not None
    assert suggestion["shared_evidence"]["embedding_similarity"] is not None


@pytest.mark.asyncio
async def test_record_character_candidate_upserts_by_source_key(db):
    user = User(
        email="candidate-review@lorevia.app", username="candidate-review", password_hash="hash"
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Candidate Review",
        format="pdf",
        s3_key="books/candidate-review.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    await record_character_candidate(
        db,
        book_id=book.id,
        chapter_number=3,
        raw_name="Hitagi",
        proposed_name="Hitagi",
        aliases=["Senjogahara"],
        status=CHARACTER_CANDIDATE_PENDING,
        confidence=0.62,
        reason_codes=["ambiguous_roster_match"],
        evidence={"mention_count": 1},
        source_batch_key="book:3:1",
    )
    await record_character_candidate(
        db,
        book_id=book.id,
        chapter_number=3,
        raw_name="Hitagi",
        proposed_name="Hitagi",
        aliases=["Senjogahara"],
        status=CHARACTER_CANDIDATE_PENDING,
        confidence=0.68,
        reason_codes=["ambiguous_roster_match", "single_token_needs_stronger_support"],
        evidence={"strong_mention_count": 1},
        source_batch_key="book:3:1",
    )
    await db.commit()

    rows = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id)))
        .scalars()
        .all()
    )

    assert len(rows) == 1
    assert rows[0].confidence == 68
    assert rows[0].reason_codes == ["ambiguous_roster_match", "single_token_needs_stronger_support"]
    assert rows[0].evidence["mention_count"] == 1
    assert rows[0].evidence["strong_mention_count"] == 1


@pytest.mark.asyncio
async def test_extraction_candidate_upserts_preserve_decided_character_and_relationship_rows(db):
    user = User(
        email="decided-candidate@lorevia.app", username="decided-candidate", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Preserve decisions",
        format="pdf",
        s3_key="books/preserve-decisions.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    names = ("Mara Vale", "Mara Voss", "Mara Reed")
    for index, (name, status) in enumerate(
        zip(names, ("accepted", "promoted", "rejected"), strict=True), start=1
    ):
        candidate = CharacterCandidate(
            book_id=book.id,
            chapter_number=2,
            raw_name=name,
            proposed_name=name,
            normalized_name=name.casefold(),
            status=status,
            confidence=91,
            evidence={"review_note": "Keep this decision."},
            source_batch_key=f"book:2:{index}",
        )
        db.add(candidate)
        await db.flush()
        db.add(
            AiQualityEvent(
                book_id=book.id,
                user_id=user.id,
                actor_user_id=user.id,
                entity_type="character_candidate",
                entity_id=str(candidate.id),
                outcome=status,
            )
        )
    for index, status in enumerate(("accepted", "resolved", "rejected"), start=1):
        db.add(
            CharacterRelationshipCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_character_a="Mara",
                raw_character_b=f"Sol {index}",
                status=status,
                evidence={"review_note": "Keep this relationship decision."},
                source_batch_key=f"book:2:{index}",
            )
        )
    await db.flush()

    for index, name in enumerate(names, start=1):
        await record_character_candidate(
            db,
            book_id=book.id,
            chapter_number=2,
            raw_name=name,
            proposed_name=name,
            status="pending",
            confidence=0.1,
            evidence={"review_note": "Overwrite attempt"},
            source_batch_key=f"book:2:{index}",
        )
        await record_relationship_candidate(
            db,
            book_id=book.id,
            chapter_number=2,
            raw_character_a="Mara",
            raw_character_b=f"Sol {index}",
            status="pending",
            evidence={"review_note": "Overwrite attempt"},
            source_batch_key=f"book:2:{index}",
        )
    await db.flush()

    characters = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id)))
        .scalars()
        .all()
    )
    relationships = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {row.status for row in characters} == {"accepted", "promoted", "rejected"}
    assert {row.status for row in relationships} == {"accepted", "resolved", "rejected"}
    assert all(row.evidence["review_note"] == "Keep this decision." for row in characters)
    assert all(
        row.evidence["review_note"] == "Keep this relationship decision." for row in relationships
    )
    old_relationship = next(row for row in relationships if row.raw_character_b == "Sol 1")
    new_pair_batch = await record_relationship_candidate(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_character_a="Mara",
        raw_character_b="Sol 1",
        status="pending",
        source_batch_key="book:2:new-pair-batch",
    )
    assert new_pair_batch.id == old_relationship.id

    old_reviewed = next(row for row in characters if row.proposed_name == "Mara Vale")
    new_batch_result = await record_character_candidate(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_name="Mara Vale",
        proposed_name="Mara Vale",
        status="pending",
        confidence=0.1,
        source_batch_key="book:2:new-batch",
    )
    assert new_batch_result.id == old_reviewed.id
    assert (
        await db.scalar(
            select(CharacterCandidate).where(
                CharacterCandidate.book_id == book.id,
                CharacterCandidate.normalized_name == "mara vale",
            )
        )
    ) is old_reviewed

    auto_candidate = CharacterCandidate(
        book_id=book.id,
        chapter_number=2,
        raw_name="Iris Bell",
        proposed_name="Iris Bell",
        normalized_name="iris bell",
        status="accepted",
        confidence=91,
        evidence={"review_note": "Old automatic evidence"},
        source_batch_key="book:2:auto",
    )
    db.add(auto_candidate)
    await db.flush()
    updated = await record_character_candidate(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_name="Iris Bell",
        proposed_name="Iris Bell",
        status="pending",
        confidence=0.6,
        evidence={"review_note": "New automatic evidence"},
        source_batch_key="book:2:auto",
    )
    assert updated.id == auto_candidate.id
    assert updated.status == "pending"
    assert updated.evidence["review_note"] == "New automatic evidence"

    attached_endpoint = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=2,
        raw_character_a="Iris",
        raw_character_b="Sol",
        status="pending",
        reason_codes=["author_attached_endpoint"],
        evidence={"review_note": "Endpoint selected by author"},
        source_batch_key="book:2:attached",
    )
    db.add(attached_endpoint)
    await db.flush()
    refreshed = await record_relationship_candidate(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_character_a="Iris",
        raw_character_b="Sol",
        status="pending",
        evidence={"review_note": "Overwrite attempt"},
        source_batch_key="book:2:attached",
    )
    assert refreshed.id == attached_endpoint.id
    assert refreshed.evidence["review_note"] == "Endpoint selected by author"

    author_demoted = CharacterCandidate(
        book_id=book.id,
        chapter_number=2,
        raw_name="Nila",
        proposed_name="Nila",
        normalized_name="nila",
        status="pending",
        source_batch_key=f"manual-demote:{book.id}:{uuid.uuid4()}",
        reason_codes=["manual_demoted_for_review"],
    )
    db.add(author_demoted)
    await db.flush()
    rediscovered = await record_character_candidate(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_name="Nila",
        proposed_name="Nila",
        status="promoted",
        source_batch_key="book:2:new-batch",
    )
    assert rediscovered.id == author_demoted.id
    assert rediscovered.status == "pending"


@pytest.mark.asyncio
async def test_record_character_mention_keeps_distinct_passages_in_same_cluster(db):
    user = User(email="mention-review@lorevia.app", username="mention-review", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Mention Review",
        format="pdf",
        s3_key="books/mention-review.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    await record_character_mention(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_name="Grete",
        normalized_name="grete",
        source_batch_key="book:2:1",
        cluster_key="grete",
        mention_text="Grete opened the door.",
        resolver_status="matched_existing",
        resolver_reasons=["matched_existing_character"],
        evidence={"mention_count": 1},
    )
    await record_character_mention(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_name="Grete",
        normalized_name="grete",
        source_batch_key="book:2:1",
        cluster_key="grete",
        mention_text="Grete carried food into the room.",
        resolver_status="matched_existing",
        resolver_reasons=["matched_existing_character"],
        evidence={"mention_count": 1},
    )
    await db.commit()

    rows = (
        (await db.execute(select(CharacterMention).where(CharacterMention.book_id == book.id)))
        .scalars()
        .all()
    )

    assert len(rows) == 2
    assert {row.mention_text for row in rows} == {
        "Grete opened the door.",
        "Grete carried food into the room.",
    }


@pytest.mark.asyncio
async def test_record_relationship_candidate_upserts_by_source_key(db):
    user = User(
        email="relationship-review@lorevia.app",
        username="relationship-review",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Relationship Review",
        format="pdf",
        s3_key="books/relationship-review.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    await record_relationship_candidate(
        db,
        book_id=book.id,
        chapter_number=4,
        raw_character_a="Grete",
        raw_character_b="Gregor's father",
        rel_type="family",
        status=CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
        reason_codes=["relationship_unresolved"],
        evidence={"marker": "first"},
        source_batch_key="book:4:relationship",
    )
    await record_relationship_candidate(
        db,
        book_id=book.id,
        chapter_number=4,
        raw_character_a="Grete",
        raw_character_b="Gregor's father",
        rel_type="family",
        status=CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
        reason_codes=["relationship_unresolved", "character_b_missing"],
        evidence={"marker": "second"},
        source_batch_key="book:4:relationship",
    )
    await db.commit()

    rows = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book.id
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1
    assert rows[0].reason_codes == ["relationship_unresolved", "character_b_missing"]
    assert rows[0].evidence["marker"] == "second"


def test_build_character_review_payload_includes_relationship_candidates():
    relationship_candidate = CharacterRelationshipCandidate(
        id=uuid.UUID("00000000-0000-0000-0000-000000000111"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        chapter_number=3,
        raw_character_a="Grete",
        raw_character_b="Gregor's father",
        rel_type="family",
        status=CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
        reason_codes=["relationship_unresolved"],
        evidence={"sample": True},
    )

    payload = build_character_review_payload([], [], [relationship_candidate])

    assert payload["counts"]["pending_relationship_candidates"] == 1
    assert payload["relationship_candidates"][0]["raw_character_a"] == "Grete"


def test_build_character_review_payload_does_not_count_suppressed_candidates_as_pending():
    candidate = CharacterCandidate(
        id=uuid.UUID("00000000-0000-0000-0000-000000000121"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        chapter_number=1,
        raw_name="Texte",
        proposed_name="Texte",
        normalized_name="texte",
        status=CHARACTER_CANDIDATE_SUPPRESSED,
        confidence=0,
        reason_codes=["common_single_token_suppressed"],
        evidence={},
    )
    relationship_candidate = CharacterRelationshipCandidate(
        id=uuid.UUID("00000000-0000-0000-0000-000000000122"),
        book_id=candidate.book_id,
        chapter_number=1,
        raw_character_a="Gregor",
        raw_character_b="Texte",
        status=CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED,
        reason_codes=["character_b_suppressed"],
        evidence={},
    )

    payload = build_character_review_payload([candidate], [], [relationship_candidate])

    assert payload["counts"]["pending_candidates"] == 0
    assert payload["counts"]["pending_relationship_candidates"] == 0


def test_build_character_review_payload_surfaces_structured_candidate_and_duplicate_evidence():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000201"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Grete",
        aliases=["Gregor's sister"],
        role="sc",
        first_chapter=1,
        analysis_metadata={"protected_from_repair": True},
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000202"),
        book_id=primary.book_id,
        name="Gregor's sister",
        aliases=[],
        role="sc",
        first_chapter=1,
    )
    candidate = CharacterCandidate(
        id=uuid.UUID("00000000-0000-0000-0000-000000000203"),
        book_id=primary.book_id,
        chapter_number=1,
        raw_name="Gregor's sister",
        proposed_name="Gregor's sister",
        normalized_name="gregor sister",
        aliases=["Grete"],
        status=CHARACTER_CANDIDATE_PENDING,
        confidence=58,
        reason_codes=["role_only_reference"],
        evidence={
            "cluster_names": ["Grete", "Gregor's sister"],
            "cluster_size": 2,
            "cluster_mention_count": 3,
            "resolver_status": "held_for_review",
            "resolver_reasons": ["role_only_reference", "competing_proper_name"],
            "canonical_confidence": 0.58,
            "grounding_coverage": 0.75,
            "snippets": ["Grete brings food to Gregor."],
        },
    )
    duplicate = CharacterDuplicateSuggestion(
        id=uuid.UUID("00000000-0000-0000-0000-000000000204"),
        book_id=primary.book_id,
        primary_character_id=primary.id,
        secondary_character_id=secondary.id,
        confidence=88,
        reasons=["Shared mention clusters"],
        shared_evidence={"shared_chapters": [1]},
        status="pending",
    )
    decision_event = CharacterDecisionEvent(
        id=uuid.UUID("00000000-0000-0000-0000-000000000205"),
        book_id=primary.book_id,
        character_id=secondary.id,
        action="character_demoted_for_review",
        visibility_state="quarantined",
        approval_state="pending_review",
        approval_source="backfill_review",
        reason_codes=["role_only_reference"],
        evidence={"source": "repair"},
    )

    payload = build_character_review_payload(
        [candidate],
        [duplicate],
        [],
        character_map={primary.id: primary, secondary.id: secondary},
        shadow_characters=[secondary],
        decision_events=[decision_event],
    )

    assert payload["candidates"][0]["cluster_names"] == ["Grete", "Gregor's sister"]
    assert payload["candidates"][0]["resolver_status"] == "held_for_review"
    assert payload["candidates"][0]["snippets"] == ["Grete brings food to Gregor."]
    assert payload["candidates"][0]["dossier_summary"]["strict_auto_eligible"] is False
    assert payload["duplicate_suggestions"][0]["primary_is_protected"] is True
    assert isinstance(payload["duplicate_suggestions"][0]["shared_chapters"], list)
    assert payload["shadow_characters"][0]["name"] == "Gregor's sister"
    assert payload["decision_events"][0]["action"] == "character_demoted_for_review"
