import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.database import (
    _apply_book_generation_visibility,
    _assign_or_preserve_book_generation,
)
from app.models.book import Book
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDecisionEvent,
    CharacterIdentityConstraint,
    CharacterRelationshipCandidate,
)
from app.models.generation import BookDataGeneration
from app.models.intelligence import BookChunk, ChapterSummary
from app.models.operations import AiQualityEvent
from app.models.user import User
from app.services.data_generation_service import (
    create_staging_generation,
    current_generation_id,
    ensure_active_generation,
    generation_scope,
    promote_staging_generation,
)
from app.utils.characters.serialization import is_protected_character


def test_generation_scope_sets_and_restores_context():
    rebuild_run_id = uuid.uuid4().hex

    assert current_generation_id() is None
    with generation_scope(rebuild_run_id) as generation_id:
        assert generation_id == uuid.UUID(rebuild_run_id)
        assert current_generation_id() == generation_id
    assert current_generation_id() is None


def test_generation_scope_restores_context_after_error():
    try:
        with generation_scope(uuid.uuid4().hex):
            raise RuntimeError("provider failed")
    except RuntimeError:
        pass

    assert current_generation_id() is None


def test_replaceable_models_reference_generation_table():
    assert BookDataGeneration.__table__.name == "book_data_generations"
    for model in (BookChunk, ChapterSummary, Character):
        foreign_keys = {
            foreign_key.target_fullname for foreign_key in model.generation_id.foreign_keys
        }
        assert foreign_keys == {"book_data_generations.id"}


def test_new_generated_rows_receive_the_current_generation():
    generation_id = uuid.uuid4()
    session = Session()
    chunk = BookChunk(
        book_id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        chunk_index=0,
        text="Text",
    )
    session.add(chunk)

    with generation_scope(generation_id.hex):
        _assign_or_preserve_book_generation(session, None, None)

    assert chunk.generation_id == generation_id


def test_curated_character_is_removed_from_replaceable_generation():
    session = Session()
    character = Character(
        book_id=uuid.uuid4(),
        name="Mara",
        normalized_name="mara",
        first_chapter=1,
        generation_id=uuid.uuid4(),
        analysis_metadata={"user_curated": True},
    )
    session.add(character)

    _assign_or_preserve_book_generation(session, None, None)

    assert character.generation_id is None


def test_reviewed_character_is_protected_from_automatic_merges_and_generation_replacement():
    session = Session()
    character = Character(
        book_id=uuid.uuid4(),
        name="Mara",
        first_chapter=1,
        generation_id=uuid.uuid4(),
        analysis_metadata={"user_reviewed": True, "review_note": "Keep this person distinct."},
    )
    session.add(character)

    _assign_or_preserve_book_generation(session, None, None)

    assert character.generation_id is None
    assert is_protected_character(character)


def test_legacy_manual_review_source_is_protected_without_metadata_flags():
    session = Session()
    character = Character(
        book_id=uuid.uuid4(),
        name="Mara",
        first_chapter=1,
        generation_id=uuid.uuid4(),
        approval_source="manual_review",
    )
    session.add(character)

    _assign_or_preserve_book_generation(session, None, None)

    assert character.generation_id is None
    assert is_protected_character(character)


def test_protected_approval_state_is_generation_independent_without_metadata_flags():
    session = Session()
    character = Character(
        book_id=uuid.uuid4(),
        name="Mara",
        first_chapter=1,
        generation_id=uuid.uuid4(),
        approval_state="protected",
    )
    session.add(character)

    _assign_or_preserve_book_generation(session, None, None)

    assert character.generation_id is None
    assert is_protected_character(character)


@pytest.mark.asyncio
async def test_legacy_generation_adoption_preserves_reviewed_and_manual_identity_decisions(db):
    user = User(
        email=f"review-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"review{uuid.uuid4().hex[:8]}",
        password_hash="test",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Review anchors",
        format="manual",
        s3_key="review-anchors.txt",
        status="ready",
    )
    db.add(book)
    await db.flush()
    reviewed = Character(
        book_id=book.id,
        name="Reviewed",
        first_chapter=1,
        analysis_metadata={"user_reviewed": True, "review_note": "Distinct character."},
    )
    kept_separate_a = Character(book_id=book.id, name="Ada", first_chapter=1)
    kept_separate_b = Character(book_id=book.id, name="Adele", first_chapter=1)
    generated = Character(book_id=book.id, name="Generated", first_chapter=1)
    db.add_all([reviewed, kept_separate_a, kept_separate_b, generated])
    await db.flush()
    manual_demote = CharacterCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_name="Dismissed",
        proposed_name="Dismissed",
        normalized_name="dismissed",
        source_batch_key="manual-demote:legacy",
        status="pending",
    )
    attached_relationship = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Ada",
        raw_character_b="Adele",
        status="pending",
        reason_codes=["author_attached_endpoint"],
    )
    db.add_all([manual_demote, attached_relationship])
    db.add(
        CharacterIdentityConstraint(
            book_id=book.id,
            left_character_id=kept_separate_a.id,
            right_character_id=kept_separate_b.id,
            left_text="Ada",
            right_text="Adele",
            constraint_type="not_same_character",
            source="manual",
        )
    )
    await db.flush()

    active_id = await ensure_active_generation(db, book_id=book.id)
    await db.refresh(reviewed)
    await db.refresh(kept_separate_a)
    await db.refresh(kept_separate_b)
    await db.refresh(generated)

    assert reviewed.generation_id is None
    assert kept_separate_a.generation_id is None
    assert kept_separate_b.generation_id is None
    assert generated.generation_id == active_id
    await db.refresh(manual_demote)
    await db.refresh(attached_relationship)
    assert manual_demote.generation_id is None
    assert attached_relationship.generation_id is None
    assert reviewed.analysis_metadata["review_note"] == "Distinct character."

    rebuild_run_id = uuid.uuid4().hex
    await create_staging_generation(
        db,
        book_id=book.id,
        rebuild_run_id=rebuild_run_id,
        reason="test_rebuild",
    )
    assert await promote_staging_generation(db, book_id=book.id, rebuild_run_id=rebuild_run_id)
    visible_ids = set(
        (await db.execute(select(Character.id).where(Character.book_id == book.id))).scalars().all()
    )
    assert visible_ids == {reviewed.id, kept_separate_a.id, kept_separate_b.id}
    assert (
        await db.scalar(
            select(CharacterCandidate.id).where(CharacterCandidate.id == manual_demote.id)
        )
        == manual_demote.id
    )
    assert (
        await db.scalar(
            select(CharacterRelationshipCandidate.id).where(
                CharacterRelationshipCandidate.id == attached_relationship.id
            )
        )
        == attached_relationship.id
    )
    assert (
        await db.scalar(
            select(CharacterIdentityConstraint.id).where(
                CharacterIdentityConstraint.book_id == book.id,
                CharacterIdentityConstraint.source == "manual",
            )
        )
        is not None
    )


@pytest.mark.asyncio
async def test_rebuild_preserves_author_candidate_decisions_from_old_generation(db):
    user = User(
        email=f"candidate-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"candidate{uuid.uuid4().hex[:8]}",
        password_hash="test",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Reviewed candidates",
        format="manual",
        s3_key="reviewed-candidates.txt",
        status="ready",
    )
    db.add(book)
    await db.flush()
    active_id = await ensure_active_generation(db, book_id=book.id)

    candidates = [
        CharacterCandidate(
            book_id=book.id,
            chapter_number=1,
            raw_name=name,
            proposed_name=name,
            normalized_name=name.lower(),
            status=status,
            source_batch_key=batch,
            rejection_reason=rejection,
            generation_id=active_id,
        )
        for name, status, batch, rejection in (
            ("Held", "pending", "manual-demote:old", None),
            ("Place", "suppressed", "old", "author_marked_place"),
            ("Reviewed", "rejected", "old", "candidate_rejected"),
            ("Automatic", "pending", "old", None),
        )
    ]
    relationships = [
        CharacterRelationshipCandidate(
            book_id=book.id,
            chapter_number=1,
            raw_character_a="A",
            raw_character_b=name,
            status=status,
            generation_id=active_id,
        )
        for name, status in (
            ("Attached", "pending"),
            ("Rejected", "rejected"),
            ("Automatic", "pending"),
        )
    ]
    anchor = Character(
        book_id=book.id,
        name="Anchor",
        first_chapter=1,
        analysis_metadata={"user_reviewed": True},
    )
    db.add_all([*candidates, *relationships, anchor])
    await db.flush()
    db.add_all(
        [
            AiQualityEvent(
                book_id=book.id,
                entity_type="character_candidate",
                entity_id=str(candidates[2].id),
                outcome="rejected",
                actor_user_id=user.id,
            ),
            CharacterDecisionEvent(
                book_id=book.id,
                character_id=anchor.id,
                action="relationship_candidate_attached_b",
                evidence={"relationship_candidate_id": str(relationships[0].id)},
            ),
        ]
    )
    await db.flush()

    assert await ensure_active_generation(db, book_id=book.id) == active_id
    rebuild_run_id = uuid.uuid4().hex
    await create_staging_generation(
        db, book_id=book.id, rebuild_run_id=rebuild_run_id, reason="test_rebuild"
    )
    assert await promote_staging_generation(db, book_id=book.id, rebuild_run_id=rebuild_run_id)
    visible_candidates = set(
        (
            await db.scalars(
                select(CharacterCandidate.id).where(CharacterCandidate.book_id == book.id)
            )
        ).all()
    )
    visible_relationships = set(
        (
            await db.scalars(
                select(CharacterRelationshipCandidate.id).where(
                    CharacterRelationshipCandidate.book_id == book.id
                )
            )
        ).all()
    )
    assert visible_candidates == {item.id for item in candidates[:3]}
    assert visible_relationships == {item.id for item in relationships[:2]}
    await db.refresh(relationships[0])
    assert "author_attached_endpoint" in relationships[0].reason_codes


def test_default_query_visibility_includes_only_curated_and_active_rows():
    state = SimpleNamespace(
        execution_options={},
        is_select=True,
        is_update=False,
        is_delete=False,
        statement=select(BookChunk),
    )

    _apply_book_generation_visibility(state)
    sql = str(state.statement.compile(dialect=postgresql.dialect()))

    assert "book_chunks.generation_id IS NULL" in sql
    assert "book_data_generations.status" in sql
