import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.database import _apply_book_generation_visibility
from app.engine.character import deduplicator
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
from app.services.data_generation_service import generation_scope
from app.utils.characters import partitioning as character_partitioning
from app.utils.characters.extraction import (
    _entity_mentions_linked_in_text,
    cluster_character_entities,
    resolve_character_reference_from_roster,
)
from app.utils.characters.identity import (
    filter_character_identity_aliases,
    has_conflicting_title_identity,
    partition_identity_key,
)
from app.utils.characters.manual import apply_manual_character_description
from app.utils.characters.merging import merge_characters
from app.utils.characters.partitioning import partition_character
from app.utils.characters.presentation import (
    build_character_dossier_summary,
    compose_character_description,
)
from app.utils.characters.profile_evidence import ground_character_profile_claims
from app.utils.characters.similarity import (
    description_similarity,
    name_similarity,
)

ORIGINAL_FIND_SIMILAR = deduplicator.find_similar


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


def test_french_honorifics_keep_shared_surnames_as_distinct_identities():
    from app.engine.character.deduplicator import names_equivalent

    for left, right in (
        ("Madame Meursault", "Monsieur Meursault"),
        ("Mme Masson", "Monsieur Masson"),
    ):
        assert has_conflicting_title_identity(left, right)
        assert partition_identity_key(left) != partition_identity_key(right)
        assert name_similarity(left, right) < 0.5
        assert not names_equivalent(left, [], right, [])
        assert not names_equivalent(left, [], left.split()[-1], [])


def test_french_titled_people_stay_separate_in_batch_clustering_and_roster_matching():
    from app.engine.character.deduplicator import resolve_character_match_ids

    names = ["Madame Meursault", "Monsieur Meursault"]
    entities = [
        {
            "name": name,
            "aliases": [],
            "confidence": 0.92,
            "evidence": {"mention_count": 2, "strong_mention_count": 2},
        }
        for name in names
    ]
    clustered = cluster_character_entities(entities)
    assert {item["name"] for item in clustered} == set(names)

    madame_id, monsieur_id = uuid.uuid4(), uuid.uuid4()
    roster = [
        (madame_id, "Madame Meursault", []),
        (monsieur_id, "Monsieur Meursault", []),
    ]
    assert resolve_character_match_ids("Madame Meursault", [], roster) == [madame_id]
    assert resolve_character_match_ids("Monsieur Meursault", [], roster) == [monsieur_id]


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


def test_possessive_reference_does_not_merge_with_its_owner():
    from app.engine.character.deduplicator import (
        character_name_keys,
        names_equivalent,
        resolve_character_match_ids,
    )

    raymond_id = uuid.uuid4()
    assert not names_equivalent("Raymond's Arab", [], "Raymond Sintès", [])
    assert not character_name_keys("Raymond's Arab") & character_name_keys("Raymond Sintès")
    assert (
        resolve_character_match_ids(
            "Raymond's Arab", [], [(raymond_id, "Raymond Sintès", ["Raymond"])]
        )
        == []
    )
    assert names_equivalent("Raymond Sintès", [], "Raymond Sintès", [])


def test_generic_review_reason_does_not_claim_character_identity_conflict():
    summary = build_character_dossier_summary(
        name="Marie",
        aliases=[],
        evidence={"resolver_status": "clustered", "mention_count": 51},
        reason_codes=["candidate_dossier_needs_review"],
    )
    assert summary["resolver_ambiguity_count"] == 0
    assert "conflicts_with_existing_character" not in summary["strict_auto_reason_codes"]


@pytest.mark.parametrize(
    "verifier_reason", ["ambiguous_single_token_mention", "ambiguous_multi_token_mention"]
)
def test_llm_accepted_mention_ambiguity_is_not_identity_conflict(verifier_reason):
    summary = build_character_dossier_summary(
        name="Marie Cardona",
        aliases=["Marie"],
        evidence={
            "resolver_status": "clustered",
            "mention_count": 43,
            "strong_mention_count": 22,
            "has_dialogue_or_action": True,
            "verifier": {
                "local": {"mid_sentence_mentions": 29},
                "final": {
                    "confidence_band": "accept",
                    "reasons": ["llm_confirmed_person", verifier_reason],
                },
            },
        },
        reason_codes=["llm_confirmed_person", verifier_reason],
    )
    assert summary["resolver_ambiguity_count"] == 0
    assert summary["strict_auto_eligible"] is True
    assert "conflicts_with_existing_character" not in summary["strict_auto_reason_codes"]


def test_ambiguous_roster_match_remains_an_identity_conflict():
    summary = build_character_dossier_summary(
        name="Marie Cardona",
        evidence={"verifier": {"final": {"confidence_band": "accept"}}},
        reason_codes=["ambiguous_roster_match"],
    )
    assert summary["resolver_ambiguity_count"] == 1
    assert "conflicts_with_existing_character" in summary["strict_auto_reason_codes"]


def test_repeated_accepted_single_name_across_chapters_can_be_promoted():
    from app.utils.characters.candidates import can_auto_persist_character_candidate

    evidence = {
        "source_mention_count_verified": True,
        "mention_count": 16,
        "strong_mention_count": 7,
        "chapter_numbers": [2, 3],
        "has_dialogue_or_action": True,
        "verifier": {
            "local": {
                "person_context_mentions": 5,
                "mid_sentence_mentions": 13,
            },
            "final": {"confidence_band": "accept", "reasons": []},
        },
    }
    summary = build_character_dossier_summary(name="Céleste", evidence=evidence)
    assert summary["recurring_single_name_eligible"] is True
    assert summary["strict_auto_eligible"] is True
    assert can_auto_persist_character_candidate(name="Céleste", evidence=evidence) is True

    evidence["chapter_numbers"] = [2]
    summary = build_character_dossier_summary(name="Céleste", evidence=evidence)
    assert summary["recurring_single_name_eligible"] is False
    assert can_auto_persist_character_candidate(name="Céleste", evidence=evidence) is False

    evidence["chapter_numbers"] = [2, 3]
    evidence["verifier"]["local"]["non_person_ner_mentions"] = 2
    summary = build_character_dossier_summary(name="Céleste", evidence=evidence)
    assert summary["recurring_single_name_eligible"] is False
    assert can_auto_persist_character_candidate(name="Céleste", evidence=evidence) is False


def test_named_narrator_address_supports_full_name_promotion():
    from app.services.extraction_character_decision_service import _character_save_decision
    from app.utils.characters.candidates import can_auto_persist_character_candidate

    evidence = {
        "source_mention_count_verified": True,
        "mention_count": 3,
        "strong_mention_count": 1,
        "narrator_addressed_as": "you, Monsieur Meursault",
        "verifier": {
            "local": {"mid_sentence_mentions": 3},
            "final": {
                "confidence_band": "accept",
                "reasons": ["llm_confirmed_person", "ambiguous_multi_token_mention"],
            },
        },
    }
    summary = build_character_dossier_summary(name="Monsieur Meursault", evidence=evidence)
    assert summary["explicit_narrator_full_name_eligible"] is True
    assert can_auto_persist_character_candidate(name="Monsieur Meursault", evidence=evidence)
    assert _character_save_decision(
        {"name": "Monsieur Meursault", "confidence": 0.9, "evidence": evidence}
    ).allowed


def test_production_like_accepted_marie_profile_passes_initial_save_gates():
    from app.services.extraction_character_decision_service import _character_save_decision
    from app.utils.characters.candidates import can_auto_persist_character_candidate

    evidence = {
        "source_mention_count_verified": True,
        "mention_count": 43,
        "strong_mention_count": 22,
        "cluster_names": ["Marie Cardona", "Marie"],
        "has_dialogue_or_action": True,
        "has_direct_communication": True,
        "verifier": {
            "local": {"person_context_mentions": 11, "mid_sentence_mentions": 29},
            "final": {
                "confidence_band": "accept",
                "reasons": ["llm_confirmed_person", "ambiguous_multi_token_mention"],
            },
        },
    }
    entity = {
        "name": "Marie Cardona",
        "aliases": ["Marie"],
        "confidence": 0.95,
        "entity_type": "person",
        "evidence": evidence,
    }
    assert _character_save_decision(entity).allowed
    assert can_auto_persist_character_candidate(
        name=entity["name"], aliases=entity["aliases"], evidence=evidence
    )


def test_embedding_match_uses_generation_scoped_character_query():
    character_id = uuid.uuid4()
    blocked_id = uuid.uuid4()
    book_id = uuid.uuid4()

    class SessionStub:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return SimpleNamespace(scalar_one_or_none=lambda: character_id)

    db = SessionStub()
    coroutine = ORIGINAL_FIND_SIMILAR(db, book_id, [0.1] * 1536, excluded_ids=[blocked_id])
    with pytest.raises(StopIteration) as finished:
        coroutine.send(None)
    result = finished.value.value
    assert result == character_id
    assert db.statement.column_descriptions[0]["entity"] is Character
    compiled = db.statement.compile()
    assert "characters.id NOT IN" in str(compiled)
    assert blocked_id in compiled.params.values() or [blocked_id] in compiled.params.values()
    state = SimpleNamespace(
        execution_options={},
        is_select=True,
        is_update=False,
        is_delete=False,
        statement=db.statement,
    )
    with generation_scope(str(uuid.uuid4())):
        _apply_book_generation_visibility(state)
        assert "characters.generation_id" in str(state.statement.compile())


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


@pytest.mark.asyncio
async def test_partition_enrichment_reviews_source_tail_without_silent_truncation(monkeypatch):
    marker = "FINAL_SOURCE_MARKER"
    source_text = "Gregor waited in the room. " * 12 + marker
    seen: list[str] = []

    async def capture_extraction(passage: str, **_kwargs):
        seen.append(passage)
        return {"characters": []}

    monkeypatch.setattr(
        character_partitioning, "extract_characters_and_relationships", capture_extraction
    )
    monkeypatch.setattr(character_partitioning, "count_tokens", len)
    monkeypatch.setattr(character_partitioning.settings, "EXTRACTION_BATCH_MAX_TOKENS", 60)

    await character_partitioning._build_partition_payload(
        source=SimpleNamespace(first_chapter=1, last_seen_chapter=1, role="supporting"),
        book_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Gregor",
        aliases=[],
        evidence={
            "snippets": [source_text],
            "first_chapter": 1,
            "last_seen_chapter": 1,
            "mention_count": 12,
        },
    )

    assert len(seen) > 1
    assert all(len(passage) <= 60 for passage in seen)
    assert seen[-1].endswith(marker)


@pytest.mark.asyncio
async def test_partition_profile_keeps_only_cited_claims_with_source_chapter(monkeypatch):
    source_text = "Mara guarded the ledger."

    async def extract_with_one_unsupported_claim(passage: str, **_kwargs):
        raw = {
            "name": "Mara",
            "goal": "guard the ledger",
            "motivations": ["seek fame"],
            "claim_evidence": {"goal": source_text},
        }
        grounded, citations = ground_character_profile_claims(raw, passage)
        return {
            "characters": [{"name": "Mara", **grounded, "evidence": {"profile_claims": citations}}],
            "relationships": [],
        }

    monkeypatch.setattr(
        character_partitioning,
        "extract_characters_and_relationships",
        extract_with_one_unsupported_claim,
    )
    payload = await character_partitioning._build_partition_payload(
        source=SimpleNamespace(first_chapter=4, last_seen_chapter=4, role="supporting"),
        book_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Mara",
        aliases=[],
        evidence={
            "snippets": [source_text],
            "snippet_chapters": [4],
            "first_chapter": 4,
            "last_seen_chapter": 4,
            "mention_count": 1,
        },
    )

    assert payload["goal"] == "guard the ledger"
    assert payload["motivations"] == []
    assert payload["analysis_metadata"]["profile_claims"] == [
        {"field": "goal", "value": "guard the ledger", "quote": source_text, "chapter_number": 4}
    ]


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


def test_cluster_keeps_distinct_single_names_separate_even_with_suggested_alias():
    entities = [
        {
            "name": "Paris",
            "aliases": ["Marie"],
            "confidence": 0.8,
            "evidence": {"mention_count": 4},
        },
        {
            "name": "Marie",
            "aliases": [],
            "confidence": 0.9,
            "evidence": {"mention_count": 51},
        },
    ]

    clustered = cluster_character_entities(entities)
    assert [item["name"] for item in clustered] == ["Paris", "Marie"]


def test_distinct_single_names_do_not_prevent_supported_full_name_cluster():
    entities = [
        {"name": "Paris", "aliases": ["Marie"], "evidence": {"mention_count": 4}},
        {
            "name": "Marie",
            "aliases": [],
            "evidence": {
                "mention_count": 51,
                "strong_mention_count": 25,
                "has_dialogue_or_action": True,
            },
        },
        {
            "name": "Marie Cardona",
            "aliases": [],
            "evidence": {"mention_count": 1, "has_dialogue_or_action": False},
        },
    ]

    clustered = cluster_character_entities(entities)

    assert [item["name"] for item in clustered] == ["Paris", "Marie Cardona"]
    assert "Marie" in clustered[1]["aliases"]
    assert "Paris" not in clustered[1]["aliases"]
    assert clustered[1]["evidence"]["strong_mention_count"] == 25
    assert clustered[1]["evidence"]["has_dialogue_or_action"] is True
    assert (
        build_character_dossier_summary(
            name=clustered[1]["name"],
            aliases=clustered[1]["aliases"],
            evidence=clustered[1]["evidence"],
        )["strict_auto_eligible"]
        is True
    )


def test_suggested_alias_does_not_merge_a_different_name_with_a_full_name():
    source = "Paris met Marie Cardona at the station."
    clustered = cluster_character_entities(
        [
            {"name": "Paris", "aliases": ["Marie"], "_source_text": source},
            {"name": "Marie Cardona", "aliases": [], "_source_text": source},
        ]
    )

    assert [item["name"] for item in clustered] == ["Paris", "Marie Cardona"]


def test_possessive_reference_stays_separate_when_both_names_share_a_passage():
    source = "Raymond Sintès argued with Raymond's Arab."
    clustered = cluster_character_entities(
        [
            {"name": "Raymond Sintès", "aliases": ["Raymond"], "_source_text": source},
            {"name": "Raymond's Arab", "aliases": [], "_source_text": source},
        ]
    )

    assert [item["name"] for item in clustered] == ["Raymond Sintès", "Raymond's Arab"]


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


def test_character_cluster_keeps_narrator_identity_evidence_from_nonprimary_batch():
    entities = [
        {
            "name": "Arun Vale",
            "confidence": 0.7,
            "evidence": {
                "mention_count": 1,
                "strong_mention_count": 1,
                "narrator_self_identification": "I told her I was Arun Vale",
                "narrator_addressed_as": "you here, Arun Vale",
            },
        },
        {
            "name": "Arun Vale",
            "confidence": 0.95,
            "evidence": {"mention_count": 3, "strong_mention_count": 2},
        },
    ]

    clustered = cluster_character_entities(entities)

    assert len(clustered) == 1
    assert clustered[0]["evidence"]["narrator_self_identification"] == (
        "I told her I was Arun Vale"
    )
    assert clustered[0]["evidence"]["narrator_addressed_as"] == "you here, Arun Vale"


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
