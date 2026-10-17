import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.engine.character.entity_filters import VISIBILITY_THRESHOLD, character_visibility_score
from app.engine.character.profile_builder import build_description
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import (
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    QuoteEntry,
    WikiEntry,
)
from app.models.user import User
from app.utils.characters import partitioning as character_partitioning
from app.utils.characters.extraction import (
    _entity_mentions_linked_in_text,
    cluster_character_entities,
    resolve_character_reference_from_roster,
)
from app.utils.characters.identity import filter_character_identity_aliases
from app.utils.characters.manual import apply_manual_character_description
from app.utils.characters.merging import merge_characters
from app.utils.characters.partitioning import partition_character
from app.utils.characters.presentation import (
    build_character_dossier_summary,
    compose_character_description,
)
from app.utils.characters.similarity import (
    description_similarity,
    name_similarity,
)


def test_name_similarity_scores_shared_surname_high():
    assert name_similarity("Meme Oshino", "Mister Oshino") > 0.85


def test_name_similarity_rejects_unrelated_names():
    assert name_similarity("Meme Oshino", "Akane Kurokawa") < 0.5


@pytest.mark.parametrize(
    "text",
    ["Mara's sister met Jon at the gate.", "Mara’s sister met Jon at the gate."],
)
def test_family_role_relationship_evidence_accepts_straight_and_curly_apostrophes(text):
    assert _entity_mentions_linked_in_text("Mara sister", "Jon", text) is True


def test_name_similarity_does_not_collapse_conflicting_honorifics():
    assert name_similarity("Mr. Samsa", "Mrs. Samsa") < 0.5


def test_names_equivalent_matches_honorific_short_name_to_full_name():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Houko-chan", [], "Yamiguchi Houko", []) is True


def test_names_equivalent_keeps_mr_and_mrs_with_shared_surname_separate():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Mr. Samsa", [], "Mrs. Samsa", []) is False


def test_names_equivalent_does_not_merge_shared_surname_with_different_given_names():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Saitou Kengo", [], "Saitou Masami", []) is False


def test_names_equivalent_does_not_merge_titled_and_bare_shared_surname():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Mr. Samsa", [], "Samsa", []) is False


def test_names_equivalent_matches_reversed_japanese_name_order():
    from app.engine.character.deduplicator import names_equivalent

    assert names_equivalent("Akira Kajou", [], "Kajou Akira", []) is True


def test_resolve_character_match_ids_prefers_honorific_and_alias_variants():
    from app.engine.character.deduplicator import resolve_character_match_ids

    aikawa_id = uuid.uuid4()
    houko_id = uuid.uuid4()
    roster = [
        (aikawa_id, "Aikawa Jun", ["Jun", "Aikawa"]),
        (houko_id, "Yamiguchi Houko", ["Houko-chan"]),
    ]

    assert resolve_character_match_ids("Aikawa", [], roster) == [aikawa_id]
    assert resolve_character_match_ids("Houko-chan", [], roster) == [houko_id]


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


def test_description_similarity_propagates_unexpected_tokenizer_errors(monkeypatch):
    from app.utils.characters import similarity

    def fail_tokens(_text: str):
        raise RuntimeError("tokenizer regression")

    monkeypatch.setattr(similarity, "_similarity_tokens", fail_tokens)

    with pytest.raises(RuntimeError, match="tokenizer regression"):
        similarity.description_similarity("left text", "right text")


@pytest.mark.asyncio
async def test_partition_payload_enrichment_only_swallows_expected_extractor_failures(monkeypatch):
    source = SimpleNamespace(
        first_chapter=1,
        last_seen_chapter=2,
        role="supporting",
    )
    evidence = {
        "snippets": ["Gregor crossed the room."],
        "first_chapter": 1,
        "last_seen_chapter": 2,
        "mention_count": 1,
    }

    async def _expected_extractor_failure(_text: str, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(
        character_partitioning,
        "extract_characters_and_relationships",
        _expected_extractor_failure,
    )

    payload = await character_partitioning._build_partition_payload(
        source=source,
        book_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Gregor",
        aliases=[],
        evidence=evidence,
    )

    assert payload["name"] == "Gregor"
    assert payload["personality_tags"] == []

    async def _unexpected_extractor_bug(_text: str, **_kwargs):
        raise AssertionError("extractor invariant")

    monkeypatch.setattr(
        character_partitioning,
        "extract_characters_and_relationships",
        _unexpected_extractor_bug,
    )

    with pytest.raises(AssertionError, match="extractor invariant"):
        await character_partitioning._build_partition_payload(
            source=source,
            book_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Gregor",
            aliases=[],
            evidence=evidence,
        )


def test_visibility_score_penalizes_phrase_like_noise():
    assert character_visibility_score("On Mother") < VISIBILITY_THRESHOLD
    assert (
        character_visibility_score(
            "Meme Oshino",
            role="mentor",
            aliases=["Mr. Oshino"],
            arc_summary="A steady mentor with a clear arc.",
        )
        >= VISIBILITY_THRESHOLD
    )


def test_compose_character_description_prefers_arc_summary_and_relationships_when_traits_are_sparse():
    description = compose_character_description(
        trait_state={},
        archetype=None,
        arc_summary="Gregor is the family provider, now trapped in a body he cannot control",
        personality_tags=["anxious"],
        motivations=["protect his sister"],
        relationship_summaries=["Family bond with Grete."],
    )

    assert description == (
        "Gregor is the family provider, now trapped in a body he cannot control. Family bond with Grete."
    )


def test_cluster_character_entities_keeps_family_role_out_of_identity_cluster():
    entities = [
        {
            "name": "Grete",
            "aliases": [],
            "confidence": 0.72,
            "traits": {},
            "evidence": {
                "mention_count": 1,
                "strong_mention_count": 1,
                "snippets": ["Grete, Gregor's sister, stepped closer to the door."],
            },
            "_source_text": "Grete, Gregor's sister, stepped closer to the door.",
            "_source_batch_key": "book:1:1",
        },
        {
            "name": "Gregor's sister",
            "aliases": [],
            "confidence": 0.68,
            "traits": {},
            "evidence": {
                "mention_count": 1,
                "strong_mention_count": 1,
                "snippets": ["Grete, Gregor's sister, stepped closer to the door."],
            },
            "_source_text": "Grete, Gregor's sister, stepped closer to the door.",
            "_source_batch_key": "book:1:1",
        },
    ]

    clustered = cluster_character_entities(entities)

    assert [item["name"] for item in clustered] == ["Grete", "Gregor's sister"]


def test_filter_character_identity_aliases_keeps_only_safe_deterministic_variants():
    aliases = filter_character_identity_aliases(
        "Gregor Samsa",
        ["Gregor", "Samsa", "Samsa Gregor", "Mr. Samsa", "Gregor's sister", "Grete", "Father"],
    )

    assert aliases == ["Gregor", "Samsa Gregor"]


def test_cluster_character_entities_keeps_distinct_nearby_names_separate():
    entities = [
        {
            "name": "Gregor Samsa",
            "aliases": ["Gregor"],
            "confidence": 0.92,
            "traits": {},
            "evidence": {
                "mention_count": 2,
                "strong_mention_count": 2,
                "snippets": ["Gregor Samsa warned Grete to stay back."],
            },
            "_source_text": "Gregor Samsa warned Grete to stay back.",
            "_source_batch_key": "book:1:1",
        },
        {
            "name": "Grete",
            "aliases": [],
            "confidence": 0.88,
            "traits": {},
            "evidence": {
                "mention_count": 1,
                "strong_mention_count": 1,
                "snippets": ["Gregor Samsa warned Grete to stay back."],
            },
            "_source_text": "Gregor Samsa warned Grete to stay back.",
            "_source_batch_key": "book:1:1",
        },
    ]

    clustered = cluster_character_entities(entities)

    assert [item["name"] for item in clustered] == ["Gregor Samsa", "Grete"]


def test_cluster_character_entities_prefers_full_name_over_repeated_given_name():
    entities = [
        {
            "name": "Gregor",
            "aliases": [],
            "confidence": 0.92,
            "traits": {},
            "evidence": {
                "mention_count": 2,
                "strong_mention_count": 2,
                "snippets": ["Gregor paced the room. Gregor watched the door."],
            },
        },
        {
            "name": "Gregor Samsa",
            "aliases": [],
            "confidence": 0.92,
            "traits": {},
            "evidence": {
                "mention_count": 1,
                "strong_mention_count": 1,
                "snippets": ["Gregor Samsa woke before dawn."],
            },
        },
    ]

    clustered = cluster_character_entities(entities)

    assert clustered[0]["name"] == "Gregor Samsa"
    assert "Gregor" in clustered[0]["aliases"]


def test_cluster_character_entities_keeps_title_surname_separate_from_canonical_full_name():
    entities = [
        {
            "name": "Mr. Samsa",
            "aliases": [],
            "confidence": 0.96,
            "traits": {},
            "evidence": {
                "mention_count": 6,
                "strong_mention_count": 4,
            },
        },
        {
            "name": "Gregor Samsa",
            "aliases": [],
            "confidence": 0.92,
            "traits": {},
            "evidence": {
                "mention_count": 2,
                "strong_mention_count": 1,
            },
        },
    ]

    clustered = cluster_character_entities(entities)

    assert [item["name"] for item in clustered] == ["Mr. Samsa", "Gregor Samsa"]


def test_dossier_allows_strong_deterministic_fallback_with_full_name_alias():
    summary = build_character_dossier_summary(
        name="Gregor",
        aliases=["Gregor Samsa"],
        evidence={
            "deterministic_fallback": True,
            "mention_count": 3,
            "strong_mention_count": 2,
            "has_dialogue_or_action": True,
            "cluster_names": ["Gregor", "Gregor Samsa"],
            "verifier": {
                "local": {
                    "person_ner_mentions": 0,
                    "non_person_ner_mentions": 0,
                    "sentence_start_mentions": 1,
                    "mid_sentence_mentions": 1,
                },
                "final": {"confidence_band": "accept", "reasons": ["subject_action_context"]},
            },
        },
    )

    assert summary["strict_auto_eligible"] is True
    assert "single_token_ambiguous" not in summary["strict_auto_reason_codes"]


def test_dossier_offsets_incidental_non_person_ner_label_when_person_evidence_is_stronger():
    summary = build_character_dossier_summary(
        name="Gregor Samsa",
        aliases=["Gregor"],
        evidence={
            "deterministic_fallback": True,
            "mention_count": 3,
            "strong_mention_count": 3,
            "has_dialogue_or_action": True,
            "cluster_names": ["Gregor Samsa", "Gregor"],
            "verifier": {
                "local": {
                    "person_ner_mentions": 2,
                    "non_person_ner_mentions": 1,
                    "sentence_start_mentions": 3,
                    "mid_sentence_mentions": 0,
                },
                "final": {"confidence_band": "accept", "reasons": []},
            },
        },
    )

    assert summary["raw_non_person_signal_count"] == 1
    assert summary["non_person_signal_count"] == 0
    assert summary["strict_auto_eligible"] is True
    assert "non_person_ner_signal" not in summary["strict_auto_reason_codes"]


def test_resolve_character_reference_from_roster_uses_context_to_match_family_role_reference():
    grete = Character(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        name="Grete",
        aliases=[],
        first_chapter=1,
        mention_count=3,
    )
    gregor = Character(
        id=uuid.uuid4(),
        book_id=grete.book_id,
        name="Gregor",
        aliases=[],
        first_chapter=1,
        mention_count=3,
    )

    matched = resolve_character_reference_from_roster(
        [grete, gregor],
        "Gregor's sister",
        context_text="Grete, Gregor's sister, pleaded with him to eat something.",
    )

    assert matched is not None
    assert matched.id == grete.id


def test_resolve_character_reference_from_roster_does_not_map_unresolved_family_role_to_anchor():
    gregor = Character(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        name="Gregor Samsa",
        aliases=["Gregor"],
        first_chapter=1,
        mention_count=3,
    )
    grete = Character(
        id=uuid.uuid4(),
        book_id=gregor.book_id,
        name="Grete",
        aliases=[],
        first_chapter=1,
        mention_count=3,
    )

    matched = resolve_character_reference_from_roster(
        [gregor, grete],
        "Gregor's mother",
        context_text="Gregor's mother cares for him but struggles with the changes in their relationship.",
    )

    assert matched is None


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

    apply_manual_character_description(primary, "A dry-witted mentor with a watchful presence.")
    apply_manual_character_description(secondary, "He hides concern behind teasing advice.")

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

    db.add(
        CharacterState(
            character_id=secondary.id,
            at_chapter=4,
            trait_snapshot={"hair": {"value": "black", "confidence": 0.9}},
        )
    )
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
    db.add(
        QuoteEntry(
            user_id=user.id,
            book_id=book.id,
            chapter_number=4,
            character_name=secondary.name,
            quote_text="Trust me.",
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
    assert build_description(merged.trait_state or {}, merged.archetype) == (
        "A dry-witted mentor with a watchful presence. He hides concern behind teasing advice."
    )
    await db.refresh(merged, ["voice_profile"])
    assert merged.voice_profile is not None
    assert merged.voice_profile.sample_dialogue_count == 5
    assert merged.voice_profile.sample_word_count == 43
    assert merged.voice_profile.avg_sentence_length == 11
    assert merged.voice_profile.dominant_markers == {"tone": "calm"}
    assert merged.voice_profile.signature_phrases == ["Let's keep moving."]

    states = (
        (await db.execute(select(CharacterState).where(CharacterState.character_id == merged.id)))
        .scalars()
        .all()
    )
    assert len(states) == 1
    voice_profiles = (
        (
            await db.execute(
                select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(voice_profiles) == 1

    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    assert relationships == []
    updated_thread = (
        await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))
    ).scalar_one()
    updated_wiki = (
        await db.execute(select(WikiEntry).where(WikiEntry.book_id == book.id))
    ).scalar_one()
    updated_summary = (
        await db.execute(select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id))
    ).scalar_one()
    updated_quote = (
        await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == book.id))
    ).scalar_one()
    assert updated_thread.character_ids == ["Meme Oshino"]
    assert updated_wiki.related_char_ids == [str(merged.id)]
    assert updated_summary.key_events[0]["involved_characters"] == [str(merged.id)]
    assert updated_summary.char_changes[0]["character"] == "Meme Oshino"
    assert updated_quote.character_name == "Meme Oshino"


@pytest.mark.asyncio
async def test_partition_character_splits_record_and_reassigns_references(db, monkeypatch):
    user = User(email="partition-user@lorevia.app", username="partition-user", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Partition Test",
        format="pdf",
        s3_key="books/partition-test.pdf",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()

    chapter_one = Chapter(book_id=book.id, number=1, title="Arrival", s3_key="chapters/1.txt")
    chapter_two = Chapter(book_id=book.id, number=2, title="Kitchen", s3_key="chapters/2.txt")
    db.add_all([chapter_one, chapter_two])
    await db.flush()

    from app.models.intelligence import BookChunk

    db.add(
        BookChunk(
            book_id=book.id,
            chapter_id=chapter_one.id,
            chunk_index=0,
            text="Mr. Samsa coughed while Gregor watched.",
        )
    )
    db.add(
        BookChunk(
            book_id=book.id,
            chapter_id=chapter_two.id,
            chunk_index=0,
            text="Mrs. Samsa called softly from the kitchen.",
        )
    )

    source = Character(
        book_id=book.id,
        name="Samsa",
        aliases=["Mr. Samsa", "Mrs. Samsa"],
        role="sc",
        first_chapter=1,
        last_seen_chapter=2,
        mention_count=4,
    )
    counterpart = Character(
        book_id=book.id,
        name="Gregor",
        aliases=[],
        role="mc",
        first_chapter=1,
        last_seen_chapter=2,
        mention_count=5,
    )
    db.add_all([source, counterpart])
    await db.flush()

    db.add(
        CharacterState(
            character_id=source.id,
            at_chapter=1,
            trait_snapshot={"hair": {"value": "gray", "confidence": 0.9}},
        )
    )
    db.add(
        CharacterRelationship(
            book_id=book.id,
            character_a_id=source.id,
            character_b_id=counterpart.id,
            rel_type="family",
            description="Parent of Gregor",
            from_chapter=1,
        )
    )
    db.add(
        PlotThread(
            book_id=book.id,
            title="Samsa household",
            status="ongoing",
            introduced_at=1,
            character_ids=["Samsa"],
        )
    )
    db.add(
        WikiEntry(
            book_id=book.id,
            entry_type="concept",
            name="Household",
            related_char_ids=[str(source.id)],
        )
    )
    db.add(
        ChapterSummary(
            chapter_id=chapter_one.id,
            mode="short",
            content="Mr. Samsa arrives.",
            key_events=[{"event_title": "Arrival", "involved_characters": [str(source.id)]}],
            char_changes=[{"character": "Samsa", "change": "Arrives upset"}],
        )
    )
    db.add(
        QuoteEntry(
            user_id=user.id,
            book_id=book.id,
            chapter_number=2,
            character_name="Samsa",
            quote_text="Mrs. Samsa whispered a prayer.",
        )
    )
    await db.commit()

    async def _fake_extract(text: str) -> dict:
        if "Mrs. Samsa" in text:
            return {
                "characters": [
                    {
                        "name": "Mrs. Samsa",
                        "aliases": [],
                        "traits": {},
                        "personality_tags": ["gentle"],
                        "motivations": ["protect her son"],
                        "fears": ["losing Gregor"],
                        "arc_summary": "Protective and worried.",
                    }
                ],
                "relationships": [],
            }
        return {
            "characters": [
                {
                    "name": "Mr. Samsa",
                    "aliases": [],
                    "traits": {},
                    "personality_tags": ["stern"],
                    "motivations": ["restore order"],
                    "fears": ["financial ruin"],
                    "arc_summary": "Rigid and anxious.",
                }
            ],
            "relationships": [],
        }

    monkeypatch.setattr(
        "app.utils.characters.partitioning.extract_characters_and_relationships", _fake_extract
    )

    created = await partition_character(
        db,
        source=source,
        user_id=user.id,
        partitions=[
            {"name": "Mr. Samsa", "aliases": []},
            {"name": "Mrs. Samsa", "aliases": []},
        ],
    )
    await db.commit()

    assert {character.name for character in created} == {"Mr. Samsa", "Mrs. Samsa"}
    assert await db.get(Character, source.id) is None

    plot_thread = (
        await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))
    ).scalar_one()
    wiki_entry = (
        await db.execute(select(WikiEntry).where(WikiEntry.book_id == book.id))
    ).scalar_one()
    summary = (
        await db.execute(select(ChapterSummary).where(ChapterSummary.chapter_id == chapter_one.id))
    ).scalar_one()
    quote = (await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == book.id))).scalar_one()

    assert plot_thread.character_ids == ["Mr. Samsa", "Mrs. Samsa"]
    assert len(wiki_entry.related_char_ids or []) == 2
    assert summary.key_events[0]["involved_characters"] == [
        str(next(character.id for character in created if character.name == "Mr. Samsa"))
    ]
    assert summary.char_changes[0]["character"] == "Mr. Samsa"
    assert quote.character_name == "Mrs. Samsa"
