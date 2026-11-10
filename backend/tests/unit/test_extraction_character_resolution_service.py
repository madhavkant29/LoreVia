import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.book import Book
from app.models.character import Character, CharacterCandidate, CharacterMention, CharacterState
from app.models.generation import BookDataGeneration
from app.models.operations import AiQualityEvent
from app.models.user import User
from app.services import (
    extraction_character_reporting_service,
    extraction_character_resolution_service,
    extraction_new_character_resolution_service,
)
from app.services.data_generation_service import generation_scope
from app.services.extraction_character_decision_service import (
    _can_update_exact_existing_profile,
    _entity_requires_manual_review,
    load_author_review_holds,
)
from app.utils.characters.constants import CHARACTER_CANDIDATE_SUPPRESSED
from app.utils.characters.cross_chapter import combine_exact_name_chapter_evidence
from app.utils.characters.text import source_mention_spans_in_batch


def _cited_exact_name_entity() -> dict:
    return {
        "name": "Mara Vale",
        "aliases": [],
        "confidence": 0.9,
        "goal": "protect the bridge",
        "cluster_members": [{"name": "Mara Vale", "source_batch_key": "chapter-2-batch-1"}],
        "evidence": {
            "mention_count": 1,
            "strong_mention_count": 1,
            "source_mention_count_verified": True,
            "profile_enrichment_status": "complete",
            "profile_claims": {
                "goal": {
                    "quote": "I will protect the bridge.",
                    "source_batch_key": "chapter-2-batch-1",
                }
            },
            "verifier": {"final": {"confidence_band": "accept"}},
            "cluster_names": ["Mara Vale"],
        },
    }


def _cross_chapter_entity(name: str, *, mentions: int, strong: int) -> dict:
    return {
        "name": name,
        "aliases": [],
        "confidence": 0.9,
        "evidence": {
            "mention_count": mentions,
            "strong_mention_count": strong,
            "source_mention_count_verified": True,
            "has_attributed_speech": True,
            "has_dialogue_or_action": True,
            "snippets": [f'"Nila, answer me," she said. {name} replied to her.'],
            "verifier": {
                "final": {"confidence_band": "accept"},
                "local": {
                    "person_ner_mentions": 1,
                    "mid_sentence_mentions": 1,
                    "person_context_mentions": 1,
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_recurring_unnamed_role_is_recorded_for_review_without_creating_cast_member(db):
    user = User(
        email="role-resolution@lorevia.app", username="roleresolution", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Unnamed role", format="manual", s3_key="role.txt")
    db.add(book)
    await db.flush()

    source = (
        "The examining magistrate questioned the visitor. "
        "Later the examining magistrate checked the record. "
        'The examining magistrate said, "Wait." '
        "I thanked the examining magistrate."
    )
    source_mentions = source_mention_spans_in_batch(
        source,
        ["examining magistrate"],
        [{"chunk_index": 0, "start": 0, "end": len(source), "batch_index": 1}],
    )
    assert len(source_mentions) == 4
    entity = _cross_chapter_entity("examining magistrate", mentions=4, strong=3)
    entity["evidence"]["has_physical_description"] = True
    entity["cluster_members"] = [
        {
            "name": "examining magistrate",
            "source_batch_key": f"{book.id}:1:1",
            "source_text": source,
            "source_mentions": source_mentions,
            "evidence": entity["evidence"],
        }
    ]

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        db,
        book=book,
        chapter_number=1,
        existing_characters=[],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[entity],
        precomputed_embeddings=[[0.01] * 1536],
    )
    await db.flush()

    assert result.saved_character_count == 0
    assert await db.scalar(select(Character.id).where(Character.book_id == book.id)) is None
    candidates = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id)))
        .scalars()
        .all()
    )
    assert any(candidate.status == "pending" for candidate in candidates)


@pytest.mark.asyncio
async def test_character_resolution_rejects_missing_precomputed_embedding_before_database_writes():
    with pytest.raises(RuntimeError, match="character_embedding_result_incomplete"):
        await extraction_character_resolution_service.resolve_chapter_character_entities(
            object(),
            book=SimpleNamespace(id=uuid.uuid4()),
            chapter_number=1,
            existing_characters=[],
            character_key_cache={},
            raw_character_entities=[],
            aggregated_entities=[{"name": "Mara", "evidence": {}}],
            precomputed_embeddings=[],
        )


def test_cross_chapter_evidence_enables_strict_promotion_without_inventing_profile():
    name = "Nila"
    entity = _cross_chapter_entity(name, mentions=2, strong=1)
    prior = CharacterCandidate(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        chapter_number=1,
        raw_name=name,
        proposed_name=name,
        normalized_name=name.casefold(),
        status="pending",
        source_batch_key="chapter-1-batch-1",
        evidence=_cross_chapter_entity(name, mentions=1, strong=1)["evidence"],
    )
    assert extraction_character_resolution_service._character_save_decision(entity).allowed is False

    combined = combine_exact_name_chapter_evidence(
        entity, chapter_number=2, prior_candidates=[prior]
    )
    assert combined["evidence"]["mention_count"] == 3
    assert combined["evidence"]["strong_mention_count"] == 2
    assert combined["evidence"]["shared_chapters"] == [1, 2]
    assert combined["evidence"]["cross_chapter_candidate_ids"] == [str(prior.id)]
    assert extraction_character_resolution_service._character_save_decision(combined).allowed
    assert "goal" not in combined


def test_repeated_accepted_celeste_mentions_combine_for_promotion():
    from app.utils.characters.candidates import can_auto_persist_character_candidate

    prior_evidence = {
        "source_mention_count_verified": True,
        "mention_count": 9,
        "strong_mention_count": 7,
        "has_dialogue_or_action": True,
        "verifier": {
            "local": {"person_context_mentions": 4, "mid_sentence_mentions": 8},
            "final": {"confidence_band": "accept", "reasons": []},
        },
    }
    current_evidence = {
        "source_mention_count_verified": True,
        "mention_count": 7,
        "strong_mention_count": 4,
        "has_dialogue_or_action": True,
        "verifier": {
            "local": {"person_context_mentions": 3, "mid_sentence_mentions": 5},
            "final": {"confidence_band": "accept", "reasons": []},
        },
    }
    prior = CharacterCandidate(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        chapter_number=2,
        raw_name="Céleste",
        proposed_name="Céleste",
        normalized_name="céleste",
        status="pending",
        reason_codes=["candidate_dossier_needs_review", "single_token_ambiguous"],
        evidence=prior_evidence,
    )
    entity = {"name": "Céleste", "aliases": [], "confidence": 0.9, "evidence": current_evidence}

    combined = combine_exact_name_chapter_evidence(
        entity, chapter_number=3, prior_candidates=[prior]
    )

    assert combined["evidence"]["chapter_numbers"] == [2, 3]
    assert extraction_character_resolution_service._character_save_decision(combined).allowed
    assert can_auto_persist_character_candidate(name="Céleste", evidence=combined["evidence"])


@pytest.mark.parametrize(
    "change",
    [
        {"status": "rejected"},
        {"matched_character_id": uuid.uuid4()},
        {"aliases": ["Nila Vale"]},
        {"rejection_reason": "author_marked_place"},
        {"source_batch_key": "manual-demote:1"},
        {"reason_codes": ["author_rejected_candidate"]},
        {"entity_type": "place"},
        {"evidence": {"anti_merge_names": ["Nila Vale"]}},
        {"evidence": {"profile_enrichment_status": "unanchored_reference"}},
        {"evidence": {"resolver_status": "ambiguous"}},
        {"evidence": {"source_mention_count_verified": False}},
        {"evidence": {"mention_count": 0}},
        {"evidence": {"verifier": {"final": {"confidence_band": "review"}}}},
    ],
)
def test_cross_chapter_evidence_ignores_unverified_or_reviewed_candidates(change):
    entity = _cross_chapter_entity("Nila", mentions=2, strong=1)
    candidate = CharacterCandidate(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        chapter_number=1,
        raw_name="Nila",
        proposed_name="Nila",
        normalized_name="nila",
        status="pending",
        evidence=_cross_chapter_entity("Nila", mentions=1, strong=1)["evidence"],
    )
    for key, value in change.items():
        setattr(candidate, key, {**candidate.evidence, **value} if key == "evidence" else value)
    assert (
        combine_exact_name_chapter_evidence(entity, chapter_number=2, prior_candidates=[candidate])
        is entity
    )


def test_cross_chapter_evidence_does_not_combine_shared_surnames_or_unverified_current():
    entity = _cross_chapter_entity("Madame Vale", mentions=1, strong=1)
    prior = CharacterCandidate(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        chapter_number=1,
        raw_name="Monsieur Vale",
        proposed_name="Monsieur Vale",
        normalized_name="monsieur vale",
        status="pending",
        evidence=_cross_chapter_entity("Monsieur Vale", mentions=1, strong=1)["evidence"],
    )
    assert (
        combine_exact_name_chapter_evidence(entity, chapter_number=2, prior_candidates=[prior])
        is entity
    )
    entity["evidence"]["source_mention_count_verified"] = False
    assert (
        combine_exact_name_chapter_evidence(entity, chapter_number=2, prior_candidates=[prior])
        is entity
    )


def test_cross_chapter_evidence_deduplicates_batches_and_ignores_malformed_metadata():
    entity = _cross_chapter_entity("Nila", mentions=2, strong=1)
    first = CharacterCandidate(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        chapter_number=1,
        raw_name="Nila",
        proposed_name="Nila",
        normalized_name="nila",
        status="pending",
        evidence=_cross_chapter_entity("Nila", mentions=1, strong=1)["evidence"],
    )
    duplicate = CharacterCandidate(
        id=uuid.uuid4(),
        book_id=first.book_id,
        chapter_number=1,
        raw_name="Nila",
        proposed_name="Nila",
        normalized_name="nila",
        status="pending",
        evidence=_cross_chapter_entity("Nila", mentions=1, strong=1)["evidence"],
    )
    duplicate.evidence = {**duplicate.evidence, "snippets": "not a list"}
    combined = combine_exact_name_chapter_evidence(
        entity, chapter_number=2, prior_candidates=[first, duplicate]
    )
    assert combined["evidence"]["mention_count"] == 3
    assert len(combined["evidence"]["cross_chapter_candidate_ids"]) == 1

    malformed = _cross_chapter_entity("Nila", mentions=2, strong=1)
    malformed["evidence"]["verifier"] = ["bad"]
    assert (
        combine_exact_name_chapter_evidence(malformed, chapter_number=2, prior_candidates=[first])
        is malformed
    )
    no_source_mentions = _cross_chapter_entity("Nila", mentions=0, strong=0)
    assert (
        combine_exact_name_chapter_evidence(
            no_source_mentions, chapter_number=2, prior_candidates=[first]
        )
        is no_source_mentions
    )


@pytest.mark.parametrize("other_chapter", [1, 3])
@pytest.mark.parametrize("local_mentions", [2, 4])
@pytest.mark.asyncio
async def test_cross_chapter_verified_name_promotes_and_links_other_mentions(
    db, monkeypatch, other_chapter, local_mentions
):
    user = User(email="cross-chapter@lorevia.app", username="crosschapter", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Cross chapter", format="manual", s3_key="cross.txt")
    db.add(book)
    await db.flush()
    active_generation = None
    if other_chapter == 3:
        active_generation = BookDataGeneration(
            book_id=book.id,
            rebuild_run_id=uuid.uuid4().hex,
            status="active",
            reason="test_active_generation",
        )
        db.add(active_generation)
        await db.flush()
    prior_evidence = _cross_chapter_entity("Nila", mentions=1, strong=1)["evidence"]
    source_batch_key = f"chapter-{other_chapter}-batch-1"
    prior_quote = "Nila said she would guard the bridge tonight."
    prior_evidence["entity"] = {"name": "Nila", "goal": "guard the bridge"}
    prior_evidence["profile_claims"] = {
        "goal": {
            "quote": prior_quote,
            "start": 0,
            "end": len(prior_quote),
            "source_batch_key": source_batch_key,
        }
    }
    prior = CharacterCandidate(
        book_id=book.id,
        chapter_number=other_chapter,
        raw_name="Nila",
        proposed_name="Nila",
        normalized_name="nila",
        status="pending",
        generation_id=active_generation.id if active_generation else None,
        source_batch_key=source_batch_key,
        evidence=prior_evidence,
    )
    db.add(prior)
    await db.flush()
    prior_mention = CharacterMention(
        book_id=book.id,
        chapter_number=other_chapter,
        raw_name="Nila",
        normalized_name="nila",
        source_batch_key=source_batch_key,
        mention_text=prior_quote,
        generation_id=active_generation.id if active_generation else None,
        resolver_status="held_for_review",
    )
    db.add(prior_mention)
    await db.flush()

    async def unresolved(_db, **_kwargs):
        return SimpleNamespace(action="needs_review", target_character_id=None, reason="name")

    async def no_similar(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        extraction_character_resolution_service, "resolve_character_mention", unresolved
    )
    monkeypatch.setattr(extraction_new_character_resolution_service, "find_similar", no_similar)
    entity = _cross_chapter_entity(
        "Nila", mentions=local_mentions, strong=2 if local_mentions == 4 else 1
    )
    if local_mentions == 4:
        assert extraction_character_resolution_service._character_save_decision(entity).allowed
    entity["evidence"]["snippets"] = ["Nila walked beside the crew. Nila waved."]
    entity["evidence"]["cross_chapter_candidate_ids"] = [str(uuid.uuid4())]
    entity["cluster_members"] = [
        {
            "name": "Nila",
            "source_batch_key": "chapter-2-batch-1",
            "source_text": "Nila spoke to the crew. Nila waved.",
            "source_mentions": [
                {"chunk_index": 0, "start": 0, "end": 4},
                {"chunk_index": 0, "start": 24, "end": 28},
            ],
            "evidence": entity["evidence"],
        }
    ]

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        db,
        book=book,
        chapter_number=2,
        existing_characters=[],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[entity],
        precomputed_embeddings=[[0.01] * 1536],
    )
    await db.flush()
    assert result.saved_character_count == 1
    character = (
        await db.execute(select(Character).where(Character.book_id == book.id))
    ).scalar_one()
    assert prior.status == "accepted"
    assert prior.matched_character_id == character.id
    assert prior_mention.matched_character_id == character.id
    assert character.name == "Nila"
    assert character.first_chapter == min(2, other_chapter)
    assert character.last_seen_chapter == max(2, other_chapter)
    state = (
        await db.execute(select(CharacterState).where(CharacterState.character_id == character.id))
    ).scalar_one()
    assert state.at_chapter == max(2, other_chapter)
    assert character.goal == "guard the bridge"
    assert any(
        claim["field"] == "goal"
        and claim["quote"] == prior_quote
        and claim["chapter_number"] == other_chapter
        for claim in character.analysis_metadata["profile_claims"]
    )
    new_candidate = (
        await db.execute(
            select(CharacterCandidate).where(
                CharacterCandidate.book_id == book.id,
                CharacterCandidate.chapter_number == 2,
                CharacterCandidate.status == "promoted",
            )
        )
    ).scalar_one()
    assert new_candidate.evidence["cross_chapter_candidate_ids"] == [str(prior.id)]


@pytest.mark.asyncio
async def test_cross_chapter_failed_adjudication_keeps_new_candidate_chapter_local(db, monkeypatch):
    user = User(email="cross-pending@lorevia.app", username="crosspending", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id, title="Pending cross chapter", format="manual", s3_key="pending.txt"
    )
    db.add(book)
    await db.flush()
    prior_evidence = _cross_chapter_entity("Nila", mentions=1, strong=1)["evidence"]
    prior_evidence["snippets"] = []
    prior = CharacterCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_name="Nila",
        proposed_name="Nila",
        normalized_name="nila",
        status="pending",
        evidence=prior_evidence,
    )
    db.add(prior)
    await db.flush()

    async def unresolved(_db, **_kwargs):
        return SimpleNamespace(action="needs_review", target_character_id=None, reason="name")

    async def no_new_characters(_db, **kwargs):
        assert kwargs["pending_new_entities"] == []
        return SimpleNamespace(
            saved_character_count=kwargs["saved_character_count"],
            quarantined_candidate_count=kwargs["quarantined_candidate_count"],
            ambiguous_entity_count=kwargs["ambiguous_entity_count"],
        )

    monkeypatch.setattr(
        extraction_character_resolution_service, "resolve_character_mention", unresolved
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "promote_or_match_new_character_entities",
        no_new_characters,
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "adjudicate_character_candidate",
        lambda *_args, **_kwargs: SimpleNamespace(
            adjudication_status="quarantined", reason_codes=("needs_review",)
        ),
    )
    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        db,
        book=book,
        chapter_number=2,
        existing_characters=[],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[_cross_chapter_entity("Nila", mentions=2, strong=1)],
        precomputed_embeddings=[[0.01] * 1536],
    )
    await db.flush()
    assert result.saved_character_count == 0
    chapter_two = (
        await db.execute(
            select(CharacterCandidate).where(
                CharacterCandidate.book_id == book.id,
                CharacterCandidate.chapter_number == 2,
            )
        )
    ).scalar_one()
    assert chapter_two.mention_count == 2
    assert "cross_chapter_candidate_ids" not in chapter_two.evidence


def test_exact_existing_full_name_accepts_cited_profile_without_ner_support():
    entity = _cited_exact_name_entity()
    assert _can_update_exact_existing_profile(entity, "Mara Vale") is True

    assert _can_update_exact_existing_profile(entity, "Nila Vale") is False
    assert _can_update_exact_existing_profile({**entity, "name": "Mara"}, "Mara") is False
    assert _can_update_exact_existing_profile({**entity, "aliases": ["Mara"]}, "Mara Vale") is False
    assert _can_update_exact_existing_profile({**entity, "name": "Mr. Vale"}, "Mr. Vale") is False
    assert (
        _can_update_exact_existing_profile(
            {**entity, "evidence": {**entity["evidence"], "ambiguous_full_name_fragment": True}},
            "Mara Vale",
        )
        is False
    )
    assert (
        _can_update_exact_existing_profile(
            {**entity, "evidence": {**entity["evidence"], "profile_claims": {}}},
            "Mara Vale",
        )
        is False
    )
    assert (
        _can_update_exact_existing_profile(
            {**entity, "evidence": {**entity["evidence"], "source_mention_count_verified": False}},
            "Mara Vale",
        )
        is False
    )


@pytest.mark.asyncio
async def test_exact_existing_full_name_routes_cited_claim_to_profile_update(monkeypatch):
    book_id = uuid.uuid4()
    existing = Character(id=uuid.uuid4(), book_id=book_id, name="Mara Vale", aliases=[])
    entity = _cited_exact_name_entity()
    accepted = []
    mentions = []

    async def no_holds(_db, **_kwargs):
        return {}

    async def unresolved(_db, **_kwargs):
        return SimpleNamespace(action="needs_review", target_character_id=None, reason="full_name")

    async def update_existing(_db, **kwargs):
        accepted.append(kwargs)
        return True

    async def record_mentions(_db, **kwargs):
        mentions.append(kwargs)

    async def no_cluster_candidates(_db, **_kwargs):
        return None

    async def no_new_characters(_db, **kwargs):
        assert kwargs["pending_new_entities"] == []
        return SimpleNamespace(
            saved_character_count=kwargs["saved_character_count"],
            quarantined_candidate_count=kwargs["quarantined_candidate_count"],
            ambiguous_entity_count=kwargs["ambiguous_entity_count"],
        )

    monkeypatch.setattr(
        extraction_character_resolution_service, "load_author_review_holds", no_holds
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "resolve_character_mention", unresolved
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "is_cast_visible_character", lambda _char: True
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "_character_save_decision",
        lambda _entity: SimpleNamespace(allowed=False, reasons=("candidate_dossier_needs_review",)),
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "_should_update_existing_character",
        lambda _entity: False,
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "_accept_existing_character_match", update_existing
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "_record_entity_cluster_mentions", record_mentions
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "_record_cluster_member_candidates",
        no_cluster_candidates,
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "promote_or_match_new_character_entities",
        no_new_characters,
    )

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        object(),
        book=SimpleNamespace(id=book_id),
        chapter_number=2,
        existing_characters=[existing],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[entity],
        precomputed_embeddings=[[0.01] * 1536],
    )

    assert result.saved_character_count == 1
    assert result.quarantined_candidate_count == 0
    assert accepted[0]["existing_id"] == existing.id
    assert mentions[0]["matched_character_id"] == existing.id


@pytest.mark.asyncio
async def test_author_hold_blocks_exact_existing_full_name_profile_update(monkeypatch):
    book_id = uuid.uuid4()
    existing = Character(id=uuid.uuid4(), book_id=book_id, name="Mara Vale", aliases=[])
    mentions = []

    async def author_holds(_db, **_kwargs):
        return {"mara vale": "manual_demoted_for_review"}

    async def record_mentions(_db, **kwargs):
        mentions.append(kwargs)

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("An author hold must block automatic profile updates")

    async def no_new_characters(_db, **kwargs):
        assert kwargs["pending_new_entities"] == []
        return SimpleNamespace(
            saved_character_count=kwargs["saved_character_count"],
            quarantined_candidate_count=kwargs["quarantined_candidate_count"],
            ambiguous_entity_count=kwargs["ambiguous_entity_count"],
        )

    monkeypatch.setattr(
        extraction_character_resolution_service, "load_author_review_holds", author_holds
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "_record_entity_cluster_mentions", record_mentions
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "resolve_character_mention", unexpected
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "_accept_existing_character_match", unexpected
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "promote_or_match_new_character_entities",
        no_new_characters,
    )

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        object(),
        book=SimpleNamespace(id=book_id),
        chapter_number=2,
        existing_characters=[existing],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[_cited_exact_name_entity()],
        precomputed_embeddings=[[0.01] * 1536],
    )
    assert result.saved_character_count == 0
    assert result.quarantined_candidate_count == 1
    assert mentions[0]["matched_character_id"] is None
    assert mentions[0]["resolver_reasons"] == ["manual_demoted_for_review"]


@pytest.mark.asyncio
async def test_exact_existing_full_name_persists_cited_claim_without_ner(db, monkeypatch):
    user = User(email="exact-profile@lorevia.app", username="exactprofile", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Exact profile", format="manual", s3_key="exact.txt")
    db.add(book)
    await db.flush()
    existing = Character(
        book_id=book.id,
        name="Mara Vale",
        aliases=[],
        first_chapter=1,
        visibility_state="visible",
        approval_state="approved",
    )
    db.add(existing)
    await db.flush()

    entity = _cited_exact_name_entity()
    entity["cluster_members"][0].update(
        source_text="Mara Vale said, 'I will protect the bridge.'",
        source_mentions=[{"chunk_index": 0, "start": 0, "end": 9}],
        evidence={"mention_count": 1, "strong_mention_count": 1},
    )

    async def unresolved(_db, **_kwargs):
        return SimpleNamespace(action="needs_review", target_character_id=None, reason="full_name")

    monkeypatch.setattr(
        extraction_character_resolution_service, "resolve_character_mention", unresolved
    )

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        db,
        book=book,
        chapter_number=2,
        existing_characters=[existing],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[entity],
        precomputed_embeddings=[[0.01] * 1536],
    )
    await db.flush()

    assert result.saved_character_count == 1
    assert existing.goal == "protect the bridge"
    assert existing.last_seen_chapter == 2
    assert any(
        claim["field"] == "goal" and claim["quote"] == "I will protect the bridge."
        for claim in existing.analysis_metadata["profile_claims"]
    )
    candidate = (
        await db.execute(
            select(CharacterCandidate).where(
                CharacterCandidate.book_id == book.id,
                CharacterCandidate.chapter_number == 2,
            )
        )
    ).scalar_one()
    assert candidate.status == "accepted"
    assert candidate.matched_character_id == existing.id
    mention = (
        await db.execute(
            select(CharacterMention).where(
                CharacterMention.book_id == book.id,
                CharacterMention.chapter_number == 2,
            )
        )
    ).scalar_one()
    assert mention.matched_character_id == existing.id


@pytest.mark.asyncio
async def test_character_embedding_requires_one_nonempty_vector_per_candidate(monkeypatch):
    candidates = [
        ({"name": "Mara"}, set()),
        ({"name": "Nila"}, set()),
    ]

    calls = 0

    async def incomplete_embeddings(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return [[0.1, 0.2]]

    monkeypatch.setattr(
        extraction_character_reporting_service, "embed_batch", incomplete_embeddings
    )
    with pytest.raises(RuntimeError, match="character_embedding_result_incomplete"):
        await extraction_character_reporting_service._embed_new_character_candidates(
            candidates, db=object(), user_id=uuid.uuid4(), book_id=uuid.uuid4()
        )
    assert calls == 2

    async def empty_vector(*_args, **_kwargs):
        return [[0.1, 0.2], []]

    monkeypatch.setattr(extraction_character_reporting_service, "embed_batch", empty_vector)
    with pytest.raises(RuntimeError, match="character_embedding_result_incomplete"):
        await extraction_character_reporting_service._embed_new_character_candidates(
            candidates, db=object(), user_id=uuid.uuid4(), book_id=uuid.uuid4()
        )

    async def complete_embeddings(*_args, **_kwargs):
        return [[0.1, 0.2], [0.3, 0.4]]

    monkeypatch.setattr(extraction_character_reporting_service, "embed_batch", complete_embeddings)
    assert await extraction_character_reporting_service._embed_new_character_candidates(
        candidates, db=object(), user_id=uuid.uuid4(), book_id=uuid.uuid4()
    ) == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_character_embedding_recovers_from_one_incomplete_response(monkeypatch):
    responses = [
        [[0.1, 0.2]],
        [[0.1, 0.2], [0.3, 0.4]],
    ]

    async def embed_sequence(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(extraction_character_reporting_service, "embed_batch", embed_sequence)
    assert await extraction_character_reporting_service._embed_new_character_candidates(
        [({"name": "Mara"}, set()), ({"name": "Nila"}, set())],
        db=object(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
    ) == [[0.1, 0.2], [0.3, 0.4]]
    assert responses == []


@pytest.mark.asyncio
async def test_precompute_character_embeddings_skips_unanchored_proposals_and_preserves_order(
    monkeypatch,
):
    observed = []

    async def embed(candidates, **kwargs):
        observed.extend(entity["name"] for entity, _blocked_ids in candidates)
        assert kwargs["db"] is None
        return [[0.1, 0.2], [0.3, 0.4]]

    monkeypatch.setattr(
        extraction_character_reporting_service, "_embed_new_character_candidates", embed
    )
    vectors = await extraction_character_reporting_service.precompute_chapter_character_embeddings(
        [
            {"name": "Mara", "evidence": {}},
            {"name": "Noise", "evidence": {"profile_enrichment_status": "unanchored_reference"}},
            {"name": "Nila", "evidence": {}},
        ],
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
    )

    assert observed == ["Mara", "Nila"]
    assert vectors == [[0.1, 0.2], [], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_precompute_character_embeddings_handles_empty_or_only_unanchored_proposals():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    assert (
        await extraction_character_reporting_service.precompute_chapter_character_embeddings(
            [], user_id=user_id, book_id=book_id
        )
        == []
    )
    assert await extraction_character_reporting_service.precompute_chapter_character_embeddings(
        [{"name": "Noise", "evidence": {"profile_enrichment_status": "unanchored_reference"}}],
        user_id=user_id,
        book_id=book_id,
    ) == [[]]


@pytest.mark.asyncio
async def test_new_character_resolution_never_skips_missing_embedding(monkeypatch):
    with pytest.raises(RuntimeError, match="character_embedding_result_incomplete"):
        await extraction_new_character_resolution_service.promote_or_match_new_character_entities(
            object(),
            book=SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4()),
            chapter_number=1,
            existing_characters=[],
            character_key_cache={},
            pending_first_chapter_candidates={},
            pending_first_chapter_updates={},
            pending_new_entities=[({"name": "Mara"}, set(), "source-1", [])],
            saved_character_count=0,
            quarantined_candidate_count=0,
            ambiguous_entity_count=0,
        )


def test_french_titled_names_are_not_automatically_held_when_grounded():
    evidence = {
        "mention_count": 2,
        "strong_mention_count": 2,
        "has_dialogue_or_action": True,
        "verifier": {"final": {"confidence_band": "accept"}},
    }
    for name in ("Madame Vale", "Monsieur Vale", "Mme Vale"):
        assert (
            _entity_requires_manual_review({"name": name, "confidence": 0.9, "evidence": evidence})
            is None
        )

    assert (
        _entity_requires_manual_review(
            {"name": "Mr. Vale", "confidence": 0.9, "evidence": evidence}
        )
        == "title_name_requires_review"
    )
    assert (
        _entity_requires_manual_review(
            {"name": "Madame Vale", "confidence": 0.3, "evidence": {"mention_count": 1}}
        )
        == "low_confidence_requires_review"
    )


@pytest.mark.asyncio
async def test_author_review_holds_keep_decisions_and_ignore_automatic_rejections(db):
    user = User(email="review-holds@lorevia.app", username="reviewholds", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Review holds", format="manual", s3_key="books/hold.txt")
    db.add(book)
    await db.flush()
    cases = [
        ("Old Pier", "suppressed", "author_marked_place", None, []),
        ("Mira", "rejected", "candidate_rejected", None, ["author_rejected_candidate"]),
        ("Nila", "pending", None, f"manual-demote:{book.id}:1", []),
        ("Discard", "rejected", "automatic_rejection", None, []),
        ("Sera", "rejected", "candidate_rejected", None, []),
    ]
    historical_id = None
    for name, status, rejection_reason, source_key, reasons in cases:
        candidate = CharacterCandidate(
            book_id=book.id,
            chapter_number=2,
            raw_name=name,
            proposed_name=name,
            normalized_name=name.casefold(),
            status=status,
            rejection_reason=rejection_reason,
            source_batch_key=source_key,
            reason_codes=reasons,
        )
        db.add(candidate)
        await db.flush()
        if name == "Sera":
            historical_id = candidate.id
    db.add(
        AiQualityEvent(
            book_id=book.id,
            user_id=user.id,
            actor_user_id=user.id,
            entity_type="character_candidate",
            entity_id=str(historical_id),
            outcome="rejected",
        )
    )
    await db.flush()

    expected_holds = {
        "old pier": "author_marked_place",
        "mira": "author_rejected_candidate",
        "nila": "manual_demoted_for_review",
        "sera": "author_rejected_candidate",
    }
    assert await load_author_review_holds(db, book_id=book.id, chapter_number=2) == expected_holds
    with generation_scope(str(uuid.uuid4())):
        assert (
            await load_author_review_holds(db, book_id=book.id, chapter_number=None)
            == expected_holds
        )


@pytest.mark.asyncio
async def test_author_review_hold_prevents_character_repromotion(monkeypatch):
    book_id = uuid.uuid4()
    mentions = []

    async def author_holds(_db, **_kwargs):
        return {"nila": "manual_demoted_for_review"}

    async def record_mention(_db, **kwargs):
        mentions.append(kwargs)

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("A reviewed candidate must not be automatically promoted")

    async def finish_without_new_entities(_db, **kwargs):
        assert kwargs["pending_new_entities"] == []
        return SimpleNamespace(
            saved_character_count=kwargs["saved_character_count"],
            quarantined_candidate_count=kwargs["quarantined_candidate_count"],
            ambiguous_entity_count=kwargs["ambiguous_entity_count"],
        )

    monkeypatch.setattr(
        extraction_character_resolution_service, "load_author_review_holds", author_holds
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "_record_entity_cluster_mentions",
        record_mention,
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "resolve_character_mention", unexpected
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "promote_or_match_new_character_entities",
        finish_without_new_entities,
    )

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        object(),
        book=SimpleNamespace(id=book_id),
        chapter_number=2,
        existing_characters=[],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[{"name": "Nila", "evidence": {}, "cluster_members": []}],
        precomputed_embeddings=[[0.01] * 1536],
    )

    assert result.saved_character_count == 0
    assert result.quarantined_candidate_count == 1
    assert mentions[0]["resolver_status"] == "held_for_review"
    assert mentions[0]["resolver_reasons"] == ["manual_demoted_for_review"]


@pytest.mark.asyncio
async def test_unanchored_identity_is_recorded_but_cannot_update_matching_cast_member(monkeypatch):
    book_id = uuid.uuid4()
    existing = Character(
        id=uuid.uuid4(),
        book_id=book_id,
        name="Mara Vale",
        first_chapter=1,
    )
    recorded = []

    async def record(_db, **kwargs):
        recorded.append(kwargs)
        return CHARACTER_CANDIDATE_SUPPRESSED, kwargs["reason_codes"], {}

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("Unanchored identity must not resolve or persist a mention")

    async def finish_without_new_entities(_db, **kwargs):
        assert kwargs["pending_new_entities"] == []
        return SimpleNamespace(
            saved_character_count=kwargs["saved_character_count"],
            quarantined_candidate_count=kwargs["quarantined_candidate_count"],
            ambiguous_entity_count=kwargs["ambiguous_entity_count"],
        )

    monkeypatch.setattr(
        extraction_character_resolution_service,
        "_record_character_disposition_candidate",
        record,
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "resolve_character_mention", unexpected
    )
    monkeypatch.setattr(
        extraction_character_resolution_service, "_accept_existing_character_match", unexpected
    )
    monkeypatch.setattr(
        extraction_character_resolution_service,
        "promote_or_match_new_character_entities",
        finish_without_new_entities,
    )

    async def no_author_holds(_db, **_kwargs):
        return {}

    monkeypatch.setattr(
        extraction_character_resolution_service, "load_author_review_holds", no_author_holds
    )

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        object(),
        book=SimpleNamespace(id=book_id),
        chapter_number=2,
        existing_characters=[existing],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[
            {
                "name": "Mara Vale",
                "confidence": 0.99,
                "evidence": {"profile_enrichment_status": "unanchored_reference"},
                "cluster_members": [{"source_batch_key": f"{book_id}:2:1", "source_windows": []}],
            }
        ],
        precomputed_embeddings=[[0.01] * 1536],
    )

    assert result.saved_character_count == 0
    assert result.quarantined_candidate_count == 1
    assert result.strict_hold_count == 1
    assert recorded[0]["matched_character_id"] is None
    assert recorded[0]["reason_codes"] == ["unanchored_character_reference"]
    assert existing.mention_count in (None, 0)


@pytest.mark.asyncio
async def test_unanchored_identity_persists_suppressed_candidate_without_false_mention(db):
    user = User(
        email="unanchored-candidate@lorevia.app",
        username="unanchoredcandidate",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Unanchored", format="manual", s3_key="books/test.txt")
    db.add(book)
    await db.flush()
    character = Character(
        book_id=book.id,
        name="Mara Vale",
        first_chapter=1,
        mention_count=2,
    )
    db.add(character)
    await db.flush()

    result = await extraction_character_resolution_service.resolve_chapter_character_entities(
        db,
        book=book,
        chapter_number=2,
        existing_characters=[character],
        character_key_cache={},
        raw_character_entities=[],
        aggregated_entities=[
            {
                "name": "Mara Vale",
                "confidence": 0.99,
                "evidence": {
                    "mention_count": 2,
                    "profile_enrichment_status": "unanchored_reference",
                },
                "cluster_members": [{"source_batch_key": f"{book.id}:2:1", "source_windows": []}],
            }
        ],
        precomputed_embeddings=[[0.01] * 1536],
    )
    await db.flush()
    candidate = (
        await db.scalars(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id))
    ).one()
    mentions = (
        await db.scalars(select(CharacterMention).where(CharacterMention.book_id == book.id))
    ).all()

    assert result.saved_character_count == 0
    assert candidate.status == CHARACTER_CANDIDATE_SUPPRESSED
    assert "unanchored_character_reference" in candidate.reason_codes
    assert candidate.matched_character_id is None
    assert mentions == []
    assert character.mention_count == 2
