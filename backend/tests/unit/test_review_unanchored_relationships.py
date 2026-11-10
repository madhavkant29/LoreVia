import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.character import Character, CharacterRelationshipCandidate
from app.models.generation import BookDataGeneration
from app.models.intelligence import CharacterRelationship
from app.models.user import User
from scripts.review_unanchored_relationships import apply_plan, build_plan


@pytest.mark.asyncio
async def test_review_unanchored_relationships_preserves_grounded_and_curated_rows(db, monkeypatch):
    user = User(
        email="relationship-repair@example.com",
        username="relationship-repair",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Relationship Repair",
        format="pdf",
        s3_key="books/relationship-repair.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    generation = BookDataGeneration(
        book_id=book.id, rebuild_run_id=uuid.uuid4().hex, status="active", reason="test"
    )
    db.add(generation)
    db.add(Chapter(book_id=book.id, number=1, s3_key="chapters/relationship-repair.txt"))
    await db.flush()
    alice = Character(book_id=book.id, generation_id=generation.id, name="Alice", first_chapter=1)
    bob = Character(book_id=book.id, generation_id=generation.id, name="Bob", first_chapter=1)
    db.add_all([alice, bob])
    await db.flush()
    grounded = CharacterRelationship(
        book_id=book.id,
        generation_id=generation.id,
        character_a_id=alice.id,
        character_b_id=bob.id,
        rel_type="friends",
        from_chapter=1,
        label_evidence={"quote": "Alice and Bob walked home together."},
        edited_by_author=False,
    )
    unanchored = CharacterRelationship(
        book_id=book.id,
        generation_id=generation.id,
        character_a_id=alice.id,
        character_b_id=bob.id,
        rel_type="rivals",
        from_chapter=1,
        label_evidence={"quote": "Alice walked home alone that night."},
        edited_by_author=False,
    )
    missing = CharacterRelationship(
        book_id=book.id,
        generation_id=generation.id,
        character_a_id=alice.id,
        character_b_id=bob.id,
        rel_type="supportive",
        from_chapter=1,
        label_evidence={},
        edited_by_author=False,
    )
    curated = CharacterRelationship(
        book_id=book.id,
        character_a_id=alice.id,
        character_b_id=bob.id,
        rel_type="family",
        from_chapter=1,
        edited_by_author=True,
    )
    db.add_all([grounded, unanchored, missing, curated])
    await db.flush()
    monkeypatch.setattr(
        "scripts.review_unanchored_relationships.download_book",
        lambda _key: b"Alice and Bob walked home together. Alice walked home alone that night.",
    )

    plan = await build_plan(db, book.id)
    assert plan["review_count"] == 2
    assert {item["reason"] for item in plan["review"]} == {
        "relationship_participants_unanchored",
        "relationship_source_quote_missing",
    }
    assert (await db.get(CharacterRelationship, unanchored.id)) is not None

    with pytest.raises(ValueError, match="Active generation changed"):
        await apply_plan(db, book_id=book.id, expected_generation_id=uuid.uuid4())
    result = await apply_plan(db, book_id=book.id, expected_generation_id=generation.id)
    assert result["review_count"] == 2
    assert (await db.get(CharacterRelationship, grounded.id)) is not None
    assert (await db.get(CharacterRelationship, curated.id)) is not None
    assert (await db.get(CharacterRelationship, unanchored.id)) is None
    assert (await db.get(CharacterRelationship, missing.id)) is None
    candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book.id,
                    CharacterRelationshipCandidate.generation_id == generation.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(candidates) == 2
    assert all(candidate.status == "pending" for candidate in candidates)
    assert all(candidate.evidence["repaired_relationship_id"] for candidate in candidates)
