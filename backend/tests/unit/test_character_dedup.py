import uuid

import pytest
from sqlalchemy import select

from app.engine.character.entity_filters import VISIBILITY_THRESHOLD, character_visibility_score
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, QuoteEntry, WikiEntry
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

    db.add(
        CharacterVoiceProfile(
            book_id=book.id,
            character_id=primary.id,
            sample_dialogue_count=3,
            sample_word_count=24,
            dominant_markers={"tone": "calm"},
            signature_phrases=["Let's keep moving."],
        )
    )
    db.add(
        CharacterVoiceProfile(
            book_id=book.id,
            character_id=secondary.id,
            sample_dialogue_count=2,
            sample_word_count=19,
            avg_sentence_length=11,
            dominant_markers={"tone": "wry"},
            signature_phrases=["Trust me."],
        )
    )

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
    chapter = Chapter(book_id=book.id, number=4, title="Meeting", s3_key="chapters/4.txt")
    db.add(chapter)
    await db.flush()
    db.add(
        PlotThread(
            book_id=book.id,
            title="Hidden Debt",
            status="ongoing",
            introduced_at=4,
            character_ids=[secondary.name],
        )
    )
    db.add(
        WikiEntry(
            book_id=book.id,
            entry_type="concept",
            name="Debt Ledger",
            related_char_ids=[str(secondary.id)],
        )
    )
    db.add(
        ChapterSummary(
            chapter_id=chapter.id,
            mode="short",
            content="The mentor arrives.",
            key_events=[{"event_title": "Oshino arrives", "involved_characters": [secondary.name]}],
            char_changes=[{"character": secondary.name, "change": "Takes charge"}],
        )
    )
    db.add(QuoteEntry(user_id=user.id, book_id=book.id, chapter_number=4, character_name=secondary.name, quote_text="Trust me."))
    await db.commit()

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    await db.commit()
    await db.refresh(merged)

    assert merged.name == "Meme Oshino"
    assert "Mister Oshino" in (merged.aliases or [])
    assert "Mr. Oshino" in (merged.aliases or [])
    assert merged.mention_count == 5
    await db.refresh(merged, ["voice_profile"])
    assert merged.voice_profile is not None
    assert merged.voice_profile.sample_dialogue_count == 5
    assert merged.voice_profile.sample_word_count == 43
    assert merged.voice_profile.avg_sentence_length == 11
    assert merged.voice_profile.dominant_markers == {"tone": "calm"}
    assert merged.voice_profile.signature_phrases == ["Let's keep moving."]

    states = (await db.execute(select(CharacterState).where(CharacterState.character_id == merged.id))).scalars().all()
    assert len(states) == 1
    voice_profiles = (await db.execute(select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id))).scalars().all()
    assert len(voice_profiles) == 1

    relationships = (
        await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book.id))
    ).scalars().all()
    assert relationships == []
    updated_thread = (await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))).scalar_one()
    updated_wiki = (await db.execute(select(WikiEntry).where(WikiEntry.book_id == book.id))).scalar_one()
    updated_summary = (await db.execute(select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id))).scalar_one()
    updated_quote = (await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == book.id))).scalar_one()
    assert updated_thread.character_ids == ["Meme Oshino"]
    assert updated_wiki.related_char_ids == [str(merged.id)]
    assert updated_summary.key_events[0]["involved_characters"] == [str(merged.id)]
    assert updated_summary.char_changes[0]["character"] == "Meme Oshino"
    assert updated_quote.character_name == "Meme Oshino"
