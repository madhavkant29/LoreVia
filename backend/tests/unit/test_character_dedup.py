import uuid

import pytest
from sqlalchemy import select

from app.engine.character.entity_filters import VISIBILITY_THRESHOLD, character_visibility_score
from app.models.book import Book
from app.models.character import Character, CharacterState
from app.models.intelligence import CharacterRelationship
from app.models.user import User
from app.utils.character_utils import description_similarity, merge_characters, name_similarity


def test_name_similarity_scores_shared_surname_high():
    assert name_similarity("Meme Oshino", "Mister Oshino") > 0.85


def test_name_similarity_rejects_unrelated_names():
    assert name_similarity("Meme Oshino", "Akane Kurokawa") < 0.5


def test_names_equivalent_matches_honorific_short_name_to_full_name():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Houko-chan", [], "Yamiguchi Houko", []) is True


def test_names_equivalent_does_not_merge_shared_surname_with_different_given_names():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Saitou Kengo", [], "Saitou Masami", []) is False


def test_names_equivalent_matches_reversed_japanese_name_order():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Akira Kajou", [], "Kajou Akira", []) is True


def test_description_similarity_prefers_related_text():
    related = description_similarity(
        "A quiet mentor who guides the main character through difficult choices.",
        "A calm mentor figure who helps the protagonist make hard choices.",
    )
    unrelated = description_similarity(
        "A quiet mentor who guides the main character through difficult choices.",
        "A storm rolls over the city while the army prepares for battle.",
    )

    assert related > unrelated
    assert related > 0.2


def test_visibility_score_penalizes_phrase_like_noise():
    assert character_visibility_score("On Mother") < VISIBILITY_THRESHOLD
    assert character_visibility_score(
        "Meme Oshino",
        role="mentor",
        aliases=["Mr. Oshino"],
        arc_summary="A steady mentor with a clear arc.",
    ) >= VISIBILITY_THRESHOLD


@pytest.mark.asyncio
async def test_merge_characters_reparents_related_rows(db):
    user = User(email="dedup-user@lorevia.app", username="dedup-user", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Dedup Test",
        format="pdf",
        s3_key="books/dedup-test.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    primary = Character(
        book_id=book.id,
        name="Meme Oshino",
        aliases=["Meme"],
        role="mentor",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=3,
        personality_tags=["calm"],
        motivations=["help others"],
        fears=["failure"],
        arc_summary="A mentor who guides others.",
        archetype="mentor",
    )
    secondary = Character(
        book_id=book.id,
        name="Mister Oshino",
        aliases=["Mr. Oshino"],
        role="mentor",
        first_chapter=4,
        last_seen_chapter=6,
        mention_count=2,
        personality_tags=["wise"],
        motivations=["protect"],
        fears=["loss"],
        arc_summary="A steady teacher with hidden depths.",
        archetype="mentor",
    )
    db.add_all([primary, secondary])
    await db.flush()

    db.add(CharacterState(character_id=secondary.id, at_chapter=4, trait_snapshot={"hair": {"value": "black", "confidence": 0.9}}))
    db.add(
        CharacterRelationship(
            book_id=book.id,
            character_a_id=secondary.id,
            character_b_id=primary.id,
            rel_type="mentor",
            from_chapter=4,
        )
    )
    await db.commit()

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    await db.commit()
    await db.refresh(merged)

    assert merged.name == "Meme Oshino"
    assert "Mister Oshino" in (merged.aliases or [])
    assert "Mr. Oshino" in (merged.aliases or [])
    assert merged.mention_count == 5

    states = (await db.execute(select(CharacterState).where(CharacterState.character_id == merged.id))).scalars().all()
    assert len(states) == 1

    relationships = (
        await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book.id))
    ).scalars().all()
    assert relationships == []
