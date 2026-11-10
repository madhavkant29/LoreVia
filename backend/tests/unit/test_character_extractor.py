import json

import pytest
from fastapi import HTTPException

from app.engine.character import extractor
from app.engine.character.extractor import (
    CHARACTER_DISCOVERY_SYSTEM,
    CHARACTER_SYSTEM,
    CharacterExtractionFormatError,
    _allow_auto_augmentation,
    _apply_anti_merge_hints,
    _augment_with_named_mentions,
    _candidate_names,
    _clean_character_entries,
    _local_mention_verifier,
    _mention_has_person_context,
    _parse_mention_verifier_results,
    _valid_character_extraction_payload,
    _verify_review_candidates_with_llm,
    collect_character_discovery_hints,
    extract_characters_and_relationships,
    fallback_character_mentions,
    verify_character_candidate_personhood,
)
from app.services.extraction_character_decision_service import (
    _can_auto_save_character,
    _entity_dossier_summary,
)
from app.utils.characters.profile_evidence import PROFILE_SCALAR_FIELDS
from app.utils.llm_usage_utils import LLMIncompleteResponseError


def test_character_prompt_does_not_merge_people_solely_by_shared_surname():
    assert "A shared surname alone does not prove identity" in CHARACTER_SYSTEM
    assert "Madame Meursault" in CHARACTER_SYSTEM
    assert "Monsieur Meursault" in CHARACTER_SYSTEM
    assert "So Raymond" in CHARACTER_DISCOVERY_SYSTEM
    assert "first-person narrator" in CHARACTER_DISCOVERY_SYSTEM
    assert "narrator-attributed line" in CHARACTER_DISCOVERY_SYSTEM


def test_full_character_prompt_requests_citations_for_every_profile_scalar():
    example_text = CHARACTER_SYSTEM.split(
        "Return ONLY valid JSON, no markdown, no commentary:\n", 1
    )[1].split("\n\nIf nothing found", 1)[0]
    example = json.loads(example_text)["characters"][0]

    assert set(PROFILE_SCALAR_FIELDS) <= set(example)
    assert set(PROFILE_SCALAR_FIELDS) <= set(example["claim_evidence"])


def test_repeated_unnamed_role_mentions_count_sentence_initial_case_variant():
    text = (
        "The warden opened the gate. Later the warden checked my pass. "
        "I asked the warden where my mother had gone."
    )

    assert len(extractor._find_name_mentions(text, "the warden")) == 3
    cleaned = _clean_character_entries(
        [
            {
                "name": "the warden",
                "entity_type": "person",
                "is_character": True,
                "confidence": 0.9,
            }
        ],
        _candidate_names(text),
        text,
    )
    assert [item["name"] for item in cleaned] == ["the warden"]
    assert cleaned[0]["mention_count"] == 3


def test_single_name_match_does_not_promote_lowercase_common_verb():
    text = "Will opened the gate. I will ask him later."

    assert len(extractor._find_name_mentions(text, "Will")) == 1


def test_short_name_is_not_counted_inside_distinct_full_or_hyphenated_name():
    text = (
        "Alice Smith asked for a key. Alice-Marie answered. "
        "Alice's coat lay by the door. Alice returned at dusk."
    )

    assert [text[start:end] for start, end in extractor._find_name_mentions(text, "Alice")] == [
        "Alice",
        "Alice",
    ]
    assert len(extractor._find_name_mentions(text, "Alice Smith")) == 1


def test_repeated_full_name_does_not_support_model_invented_short_identity():
    source = "Alice Smith said hello. Alice Smith opened the gate."

    assert (
        _clean_character_entries(
            [{"name": "Alice", "entity_type": "person", "is_character": True, "confidence": 0.99}],
            ["Alice Smith"],
            source,
        )
        == []
    )


def test_standalone_short_name_with_explicit_action_remains_grounded():
    source = "Gregor Samsa woke before dawn. Gregor paced the room."

    assert len(extractor._find_name_mentions(source, "Gregor")) == 1
    assert extractor._local_mention_verifier(source, "Gregor")["confidence_band"] == "accept"


def test_explicit_first_person_name_is_rescued_when_discovery_omits_narrator():
    text = (
        "I arrived at the clinic before sunrise. The receptionist asked for a name; "
        "I told her I was Arun Vale. She wrote it in the visitor book. "
        "Madame Vale was my mother."
    )

    candidates = _candidate_names(text)
    rescued = _augment_with_named_mentions(text, [], candidates)

    assert "Arun Vale" in candidates
    narrator = next(item for item in rescued if item["name"] == "Arun Vale")
    assert narrator["evidence"]["narrator_self_identification"] == "I told her I was Arun Vale"
    assert narrator["evidence"]["strong_mention_count"] >= 1
    assert narrator["confidence"] >= 0.9


def test_discovery_hints_include_narrator_identified_once_by_pass():
    text = "My pass identified me as Leena Voss. The mechanic waved me through the gate."

    strict_hints, review_hints = collect_character_discovery_hints(text)

    assert "Leena Voss" in [*strict_hints, *review_hints]


def test_single_mention_narrator_can_auto_save_only_after_person_verifier_accepts():
    source = "My pass identified me as Leena Voss. I showed it to the mechanic."
    strict_hints, _review_hints = collect_character_discovery_hints(source)
    entity = _clean_character_entries(
        [{"name": "Leena Voss", "entity_type": "person", "is_character": True, "confidence": 0.95}],
        strict_hints,
        source,
    )[0]
    assert entity["evidence"]["narrator_self_identification"] == (
        "My pass identified me as Leena Voss"
    )
    assert _can_auto_save_character(entity) is False

    entity["evidence"]["verifier"] = {
        "final": {"confidence_band": "accept", "is_person_like": True, "reasons": []},
        "llm": {"used": True, "is_person_like": True},
    }
    assert _entity_dossier_summary(entity)["explicit_narrator_full_name_eligible"] is True
    assert _can_auto_save_character(entity) is True

    entity["evidence"]["deterministic_fallback"] = True
    assert _can_auto_save_character(entity) is False
    entity["evidence"]["deterministic_fallback"] = False
    entity["evidence"]["anti_merge_names"] = ["another Leena Voss"]
    assert _can_auto_save_character(entity) is False


def test_quoted_first_person_name_does_not_rescue_a_narrator():
    text = 'The stranger said, "I was Arun Vale." The narrator watched him.'

    rescued = _augment_with_named_mentions(text, [], _candidate_names(text))

    assert all("narrator_self_identification" not in item["evidence"] for item in rescued)


def test_narrator_attributed_quoted_name_is_rescued_without_merging_shared_surname():
    text = 'I said, "My name is Arun Vale." Madame Vale, my mother, waited outside the office.'

    rescued = _augment_with_named_mentions(text, [], _candidate_names(text))

    narrator = next(item for item in rescued if item["name"] == "Arun Vale")
    assert narrator["evidence"]["narrator_self_identification"] == "My name is Arun Vale"
    assert all(item["name"] != "Vale" for item in rescued)


def test_direct_address_is_recorded_without_claiming_explicit_narrator_identity():
    text = (
        'The registrar said, "I will leave you here, Monsieur Vale." '
        "I thanked her. Madame Vale waited in the garden."
    )

    evidence = extractor._build_evidence(text, "Monsieur Vale", {}, [])

    assert evidence["narrator_addressed_as"] == "you here, Monsieur Vale"
    assert "narrator_self_identification" not in evidence
    assert "narrator_addressed_as" not in extractor._build_evidence(text, "Madame Vale", {}, [])


def test_mention_verifier_parser_rejects_missing_or_fabricated_candidate_decisions():
    expected = {"candidate-0", "candidate-1"}
    complete = {
        "results": [
            {"id": "candidate-0", "is_person": True, "confidence": 0.9},
            {"id": "candidate-1", "is_person": None, "confidence": None},
        ]
    }
    assert set(_parse_mention_verifier_results(json.dumps(complete), expected)) == expected
    for malformed in (
        "not json",
        json.dumps({"results": complete["results"][:1]}),
        json.dumps({"results": [complete["results"][0], complete["results"][0]]}),
        json.dumps({"results": [*complete["results"], {"id": "invented", "is_person": True}]}),
        json.dumps(
            {
                "results": [
                    {**complete["results"][0], "confidence": 1.5},
                    complete["results"][1],
                ]
            }
        ),
        json.dumps(
            {
                "results": [
                    {**complete["results"][0], "is_person": "maybe"},
                    complete["results"][1],
                ]
            }
        ),
        json.dumps(
            {
                "results": [
                    {
                        **complete["results"][0],
                        "canonical_name_or_null": {"name": "Mother"},
                    },
                    complete["results"][1],
                ]
            }
        ),
    ):
        with pytest.raises(CharacterExtractionFormatError):
            _parse_mention_verifier_results(malformed, expected)


@pytest.mark.asyncio
async def test_mention_verifier_sends_late_windows_in_bounded_groups(monkeypatch):
    source = "Opening material. " * 300 + "Tail: Mara spoke to Elias."
    prompts: list[dict] = []
    candidates = [
        {
            "id": f"candidate-{index}",
            "name": f"Person {index}",
            "verifier_local": {"windows": [{"text": f"Tail context for Person {index}."}]},
        }
        for index in range(10)
    ]

    async def fake_complete(**kwargs):
        prompt = json.loads(kwargs["user"])
        prompts.append(prompt)
        return json.dumps(
            {
                "results": [
                    {"id": item["id"], "is_person": True, "confidence": 0.8}
                    for item in prompt["candidates"]
                ]
            }
        )

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    results = await _verify_review_candidates_with_llm(source, candidates)

    assert len(source) > 4000
    assert [len(prompt["candidates"]) for prompt in prompts] == [8, 2]
    assert all(prompt["source_length_chars"] == len(source) for prompt in prompts)
    assert all("Opening material" not in json.dumps(prompt) for prompt in prompts)
    assert "Tail context for Person 9." in prompts[1]["candidates"][1]["windows"]
    assert len(results) == 10


@pytest.mark.asyncio
async def test_mention_verifier_retries_invalid_output_then_fails_visibly(monkeypatch):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        return '{"results": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    candidate = {
        "id": "candidate-0",
        "name": "Mother",
        "verifier_local": {"windows": [{"text": "Mother paused in the doorway."}]},
    }
    with pytest.raises(CharacterExtractionFormatError, match="mention_verifier_incomplete_results"):
        await _verify_review_candidates_with_llm("Mother paused in the doorway.", [candidate])
    assert calls == 2


@pytest.mark.asyncio
async def test_mention_verifier_recovers_after_one_malformed_response(monkeypatch):
    prompts: list[str] = []

    async def fake_complete(**kwargs):
        prompts.append(kwargs["user"])
        if len(prompts) == 1:
            return "not json"
        return json.dumps(
            {"results": [{"id": "candidate-0", "is_person": True, "confidence": 0.88}]}
        )

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    results = await _verify_review_candidates_with_llm(
        "Mother paused in the doorway.",
        [
            {
                "id": "candidate-0",
                "name": "Mother",
                "verifier_local": {"windows": [{"text": "Mother paused in the doorway."}]},
            }
        ],
    )
    assert results["candidate-0"]["is_person_like"] is True
    assert len(prompts) == 2
    assert "Validation feedback" in prompts[1]


@pytest.mark.asyncio
async def test_discovery_pass_asks_for_identities_without_profile_fields(monkeypatch):
    captured_system = None

    async def fake_complete(**kwargs):
        nonlocal captured_system
        captured_system = kwargs["system"]
        return '{"characters": [], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(extractor, "_candidate_names", lambda _text, **_kwargs: [])

    await extract_characters_and_relationships("No named person appears.", discovery_only=True)

    assert captured_system == CHARACTER_DISCOVERY_SYSTEM
    assert '"goal"' not in captured_system


@pytest.mark.asyncio
async def test_discovery_prompt_reviews_single_names_without_automatic_promotion(
    monkeypatch,
):
    prompts: list[str] = []
    text = (
        "In Chapter 2, June and Mateo agreed they were colleagues. "
        "Before the sync, Aya did not know the station code."
    )

    async def fake_complete(**kwargs):
        prompts.append(kwargs["user"])
        return '{"characters": [], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)

    result = await extract_characters_and_relationships(text, discovery_only=True)

    assert "Uncertain capitalized references to verify" in prompts[0]
    assert "June" in prompts[0]
    assert "Mateo" in prompts[0]
    assert "Aya" in prompts[0]
    assert result["characters"] == []


@pytest.mark.asyncio
async def test_discovery_prompt_includes_hints_after_the_twenty_fourth_name(monkeypatch):
    candidate_names = [f"Candidate {number}" for number in range(30)]
    review_names = [f"Review {number}" for number in range(30)]
    captured_prompts: list[str] = []

    async def fake_complete(**kwargs):
        captured_prompts.append(kwargs["user"])
        return '{"characters": [], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(
        extractor,
        "collect_character_discovery_hints",
        lambda _text: (candidate_names, review_names),
    )

    await extract_characters_and_relationships("An empty hallway.", discovery_only=True)

    assert "- Candidate 29" in captured_prompts[0]
    assert "- Review 29" in captured_prompts[0]


@pytest.mark.asyncio
async def test_character_extraction_sends_full_bounded_batch_to_model(monkeypatch):
    captured_prompts: list[str] = []
    text = "Opening scene. " * 1000 + "The final scene names Ilya."

    async def fake_complete(**kwargs):
        captured_prompts.append(kwargs["user"])
        return '{"characters": [], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(extractor, "_candidate_names", lambda _text, **_kwargs: [])

    await extract_characters_and_relationships(text)

    assert len(text) > 12000
    assert text in captured_prompts[0]
    assert "The final scene names Ilya." in captured_prompts[0]


@pytest.mark.asyncio
async def test_character_extraction_sends_late_roster_alias_when_it_occurs_in_passage(monkeypatch):
    captured_prompts: list[str] = []
    roster = [{"name": f"Filler {index}"} for index in range(30)]
    roster.append({"name": "Mara Vale", "aliases": ["Mara"]})

    async def fake_complete(**kwargs):
        captured_prompts.append(kwargs["user"])
        return '{"characters": [], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(extractor, "_candidate_names", lambda _text, **_kwargs: [])

    await extract_characters_and_relationships("Mara entered the garden.", known_characters=roster)

    assert "Mara Vale [known character]" in captured_prompts[0]
    assert "Filler 23 [known character]" not in captured_prompts[0]


@pytest.mark.asyncio
async def test_character_extraction_rejects_malformed_model_responses_after_bounded_retry(
    monkeypatch,
):
    calls = 0
    prompts = []

    async def fake_complete(**kwargs):
        nonlocal calls
        calls += 1
        prompts.append(kwargs["user"])
        return '{"characters": ['

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(extractor, "_candidate_names", lambda _text, **_kwargs: [])

    with pytest.raises(
        CharacterExtractionFormatError, match="character_extraction_invalid_response"
    ):
        await extract_characters_and_relationships("Ilya crossed the bridge.")

    assert calls == 2
    assert "Validation feedback" not in prompts[0]
    assert "characters and relationships arrays" in prompts[1]


@pytest.mark.asyncio
async def test_character_discovery_retries_provider_truncation_without_accepting_empty_json(
    monkeypatch,
):
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise LLMIncompleteResponseError("llm_response_incomplete")
        return '{"characters":[],"relationships":[]}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(extractor, "_candidate_names", lambda _text, **_kwargs: [])

    await extract_characters_and_relationships("An empty hallway.", discovery_only=True)

    assert len(calls) == 2
    assert all(call["require_complete_output"] is True for call in calls)
    assert "previous answer was cut off" in calls[1]["user"]


@pytest.mark.asyncio
async def test_character_extraction_retry_accepts_corrected_complete_response(
    monkeypatch,
):
    prompts = []

    async def fake_complete(**kwargs):
        prompts.append(kwargs["user"])
        if len(prompts) == 1:
            return '{"characters": [}'
        return '{"characters": [{"name": "Ilya", "entity_type": "person", "is_character": true, "confidence": 0.9}], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(extractor, "_candidate_names", lambda _text, **_kwargs: ["Ilya"])

    async def passthrough_verification(_source_text, characters, **_kwargs):
        return characters

    monkeypatch.setattr(
        extractor, "_apply_contextual_mention_verification", passthrough_verification
    )

    result = await extract_characters_and_relationships(
        "Ilya crossed the bridge. Later Ilya waved to Mara."
    )

    assert len(prompts) == 2
    assert "Validation feedback" in prompts[1]
    assert [character["name"] for character in result["characters"]] == ["Ilya"]


@pytest.mark.asyncio
async def test_character_discovery_retries_one_short_slot_wait(monkeypatch):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPException(
                429,
                "LLM capacity is temporarily busy. Retry shortly.",
                headers={"Retry-After": "0.01"},
            )
        return '{"characters": [], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    result = await extract_characters_and_relationships(
        "A quiet road at dawn.", discovery_only=True
    )

    assert calls == 2
    assert result["characters"] == []


@pytest.mark.asyncio
async def test_character_discovery_does_not_retry_monthly_budget_denial(monkeypatch):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        raise HTTPException(429, {"kind": "llm_budget", "message": "Monthly AI budget reached."})

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    with pytest.raises(HTTPException) as caught:
        await extract_characters_and_relationships("Mara crossed the bridge.", discovery_only=True)

    assert caught.value.detail["kind"] == "llm_budget"
    assert calls == 1


@pytest.mark.asyncio
async def test_character_discovery_stops_after_one_transient_timeout_retry(monkeypatch):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary provider timeout")

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    with pytest.raises(TimeoutError, match="temporary provider timeout"):
        await extract_characters_and_relationships("Mara crossed the bridge.", discovery_only=True)

    assert calls == 2


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"characters": [], "relationships": None},
        {"characters": ["Ilya"], "relationships": []},
        {"characters": [{"name": ""}], "relationships": []},
        {"characters": [], "relationships": ["Ilya knows Mara"]},
        {"characters": [], "relationships": [{"character_a": "Ilya"}]},
    ],
)
def test_character_extraction_rejects_partially_malformed_json_shapes(payload):
    assert _valid_character_extraction_payload(payload) is False


def test_character_extraction_accepts_empty_and_named_valid_json_shapes():
    assert _valid_character_extraction_payload({"characters": [], "relationships": []}) is True
    assert (
        _valid_character_extraction_payload(
            {
                "characters": [{"name": "Ilya"}],
                "relationships": [{"character_a": "Ilya", "character_b": "Mara"}],
            }
        )
        is True
    )


@pytest.mark.asyncio
async def test_character_extraction_retries_invalid_entry_shape_instead_of_returning_empty_result(
    monkeypatch,
):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        return '{"characters": ["Ilya"], "relationships": []}'

    monkeypatch.setattr(extractor, "complete_with_fallback", fake_complete)
    monkeypatch.setattr(extractor, "_candidate_names", lambda _text, **_kwargs: [])

    with pytest.raises(CharacterExtractionFormatError):
        await extract_characters_and_relationships("Ilya crossed the bridge.")

    assert calls == 2


def test_candidate_names_strip_sentence_words_but_keep_separate_titled_people():
    text = (
        "Presently Marie entered. Marie said hello. So Raymond arrived, and Raymond replied. "
        "Madame Arlen spoke. Monsieur Arlen replied."
    )

    names = _candidate_names(text)

    assert "Presently Marie" not in names
    assert "So Raymond" not in names
    assert "Marie" in names
    assert "Raymond" in names
    assert "Madame Arlen" in names
    assert "Monsieur Arlen" in names


def test_shared_surname_is_review_only_when_multiple_people_are_named():
    text = (
        "Madame Quill entered while Monsieur Quill waited outside. "
        "Quill said they would return, but the witness did not say which one."
    )

    strict_names = _candidate_names(text)
    review_names = _candidate_names(text, allow_review_singletons=True)

    assert {"Madame Quill", "Monsieur Quill"} <= set(strict_names)
    assert "Quill" not in strict_names
    assert "Quill" in review_names


def test_candidate_hints_keep_source_present_single_mention_full_names_for_review():
    text = (
        "John Carter raised the moon-key. Across the hall, John Reed warned Mira. "
        "Alexandra Moreno signed the lease. The old Academy remained closed."
    )

    names = _candidate_names(text)

    assert "John Carter" in names
    assert "John Reed" in names
    assert "Alexandra Moreno" in names
    assert "The old Academy" not in names


def test_shared_first_name_is_review_only_when_two_people_have_that_name():
    text = "John Carter raised the moon-key. John Reed warned Mira. Later, John hid the key."

    strict, review = collect_character_discovery_hints(text)

    assert "John Carter" in strict
    assert "John Reed" in strict
    assert "John" not in strict
    assert "John" in review


def test_candidate_hints_rescue_contextual_surname_ending_in_s_without_noun_phrase():
    text = (
        "Inspector Leda Voss arrived after midday. Leda Voss asked the porter to wait. "
        "The Cracked Stairs stayed closed while the porter spoke. "
        "Mara crossed the Cracked Stairs at dawn. The Cracked Stairs remained wet."
    )

    names = _candidate_names(text)

    assert "Leda Voss" in names
    assert "Cracked Stairs" not in names
    assert "The Cracked Stairs" not in names
    assert "Cracked" not in names


def test_repeated_accented_surname_is_a_full_name_discovery_hint():
    text = "Raymond Sintès spoke to Marie Cardona. Later Raymond Sintès returned."

    names = _candidate_names(text)

    assert "Raymond Sintès" in names
    assert "Marie Cardona" in names
    assert "Later Raymond" not in names


def test_candidate_hints_do_not_treat_chapter_heading_fragments_as_people(monkeypatch):
    text = "In Chapter 3, Detective Bell examined the locked room."
    monkeypatch.setattr(
        extractor,
        "contextual_ner_entity_label",
        lambda _text, name: "ORG" if name == "Detective Bell" else None,
    )

    names = _candidate_names(text)

    assert "Detective Bell" in names
    assert "In Chapter" not in names


def test_cleaner_keeps_short_person_name_and_supported_nickname_from_model():
    text = (
        "Alexandra Moreno signed the lease. Her old friend Dev called her Lex, "
        "the name only he used."
    )
    cleaned = _clean_character_entries(
        [
            {
                "name": "Alexandra Moreno",
                "aliases": ["Lex"],
                "entity_type": "person",
                "confidence": 0.9,
            },
            {"name": "Dev", "entity_type": "person", "confidence": 0.9},
        ],
        _candidate_names(text),
        text,
    )

    assert [item["name"] for item in cleaned] == ["Alexandra Moreno", "Dev"]
    assert cleaned[0]["aliases"] == ["Lex"]


def test_cleaner_sends_confident_contextual_single_names_to_verifier(monkeypatch):
    text = "In Chapter 2, June and Mateo agreed they were colleagues. Later Aya entered the code."
    monkeypatch.setattr(
        extractor,
        "contextual_ner_entity_label",
        lambda _text, name: "PERSON" if name == "Aya" else None,
    )
    cleaned = _clean_character_entries(
        [
            {"name": "June", "entity_type": "person", "confidence": 0.9},
            {"name": "Mateo", "entity_type": "person", "confidence": 0.9},
            {"name": "Aya", "entity_type": "person", "confidence": 0.9},
        ],
        [],
        text,
    )

    assert [item["name"] for item in cleaned] == ["June", "Mateo", "Aya"]
    assert (
        _clean_character_entries(
            [{"name": "Aya", "entity_type": "person", "confidence": 0.2}], [], text
        )
        == []
    )


def test_cleaner_still_rejects_unsupported_common_sentence_starter():
    text = "Now, the bell rang. Mara opened the door."
    rejected = []

    cleaned = _clean_character_entries(
        [{"name": "Now", "entity_type": "person", "confidence": 0.9}],
        _candidate_names(text),
        text,
        rejected_characters=rejected,
    )

    assert cleaned == []
    assert rejected


def test_rejected_character_log_does_not_include_manuscript_name(caplog):
    text = "Crystal Academy stood across the river."

    with caplog.at_level("INFO", logger="lorevia.character.extractor"):
        cleaned = _clean_character_entries(
            [{"name": "Crystal Academy", "entity_type": "person", "confidence": 0.9}],
            _candidate_names(text),
            text,
        )

    assert cleaned == []
    assert "non_person_token" in caplog.text
    assert "Crystal Academy" not in caplog.text


def test_clean_character_entries_strips_fragment_prefixes_and_keeps_supported_name():
    source_text = (
        "Meeting Kunagisa in the hall, Aikawa Junya called to Kunagisa and Kunagisa frowned."
    )
    characters = [
        {
            "name": "Meeting Kunagisa",
            "entity_type": "person",
            "is_character": True,
            "confidence": 0.92,
            "aliases": [],
            "traits": {
                "distinguishing": {
                    "value": "sharp gaze",
                    "confidence": 0.88,
                    "type": "objective",
                }
            },
            "arc_summary": "sharp observer",
        }
    ]

    cleaned = _clean_character_entries(characters, ["Meeting Kunagisa"], source_text)

    assert len(cleaned) == 1
    assert cleaned[0]["name"] == "Kunagisa"


def test_clean_character_entries_keeps_only_profile_claims_with_source_quotes():
    source = (
        "Mara Vale promised to protect the child. Mara Vale's black hair was wet from the rain."
    )
    cleaned = _clean_character_entries(
        [
            {
                "name": "Mara Vale",
                "entity_type": "person",
                "is_character": True,
                "confidence": 0.95,
                "aliases": [],
                "goal": "protect the child",
                "fears": ["the sea"],
                "traits": {
                    "hair": {"value": "black", "confidence": 0.9, "type": "objective"},
                    "eyes": {"value": "blue", "confidence": 0.9, "type": "objective"},
                },
                "claim_evidence": {
                    "goal": "Mara Vale promised to protect the child.",
                    "fears": {"the sea": "Mara Vale feared the sea."},
                    "traits": {
                        "hair": "Mara Vale's black hair was wet from the rain.",
                        "eyes": "Mara Vale had blue eyes.",
                    },
                },
            }
        ],
        ["Mara Vale"],
        source,
    )

    assert len(cleaned) == 1
    assert cleaned[0]["goal"] == "protect the child"
    assert cleaned[0]["fears"] == []
    assert set(cleaned[0]["traits"]) == {"hair"}
    assert cleaned[0]["evidence"]["profile_claims"]["goal"]["quote"] in source


def test_clean_character_entries_rejects_locations_and_discourse_noise():
    source_text = "Feather Island was quiet. Well, Aikawa Junya kept walking toward the harbor. Help, he shouted toward the pier."
    characters = [
        {
            "name": "Feather Island",
            "entity_type": "location",
            "is_character": False,
            "confidence": 0.98,
            "aliases": [],
        },
        {
            "name": "Well",
            "entity_type": "unknown",
            "is_character": True,
            "confidence": 0.81,
            "aliases": [],
        },
        {
            "name": "Help",
            "entity_type": "unknown",
            "is_character": True,
            "confidence": 0.88,
            "aliases": [],
        },
    ]

    cleaned = _clean_character_entries(characters, ["Feather Island", "Well", "Help"], source_text)

    assert [item["name"] for item in cleaned] == ["Help"]


def test_local_mention_verifier_rejects_interjection_like_help():
    result = _local_mention_verifier("Help, he shouted toward the pier.", "Help")

    assert result["confidence_band"] == "reject"
    assert (
        "interjection_like_usage" in result["reasons"]
        or "sentence_start_capitalization_only" in result["reasons"]
    )


def test_local_mention_verifier_accepts_grounded_single_name_with_action_context():
    result = _local_mention_verifier("Gregor woke before dawn and watched the door.", "Gregor")

    assert result["confidence_band"] == "accept"
    assert result["is_person_like"] is True


@pytest.mark.parametrize(
    "noise_name",
    [
        "Actually",
        "Maybe",
        "Sure",
        "Wait",
        "Okay",
        "However",
        "Though",
        "Please",
        "Thanks",
    ],
)
def test_local_mention_verifier_routes_discourse_markers_to_reject_or_review(
    noise_name: str,
):
    result = _local_mention_verifier(f"{noise_name}, he said toward the doorway.", noise_name)

    assert result["confidence_band"] in {"reject", "review"}
    assert result["is_person_like"] is False


def test_local_mention_verifier_keeps_role_only_singletons_in_review():
    result = _local_mention_verifier("Mother paused in the doorway and looked back once.", "Mother")

    assert result["confidence_band"] == "review"
    assert result["is_person_like"] is False


def test_local_mention_verifier_distinguishes_sentence_start_noise_from_real_name():
    noise = _local_mention_verifier("Well, the room stayed quiet.", "Well")
    person = _local_mention_verifier("Gregor woke before dawn and watched the door.", "Gregor")

    assert noise["confidence_band"] == "reject"
    assert person["confidence_band"] == "accept"


def test_local_mention_verifier_uses_sentence_window_for_contextual_ner(monkeypatch):
    seen_windows: list[str] = []

    def _fake_contextual_ner(window: str, _name: str):
        seen_windows.append(window)
        return None

    monkeypatch.setattr(
        "app.engine.character.extractor.contextual_ner_entity_label",
        _fake_contextual_ner,
    )

    _local_mention_verifier("Gregor woke before dawn and watched the door.", "Gregor")

    assert seen_windows
    assert any("woke before dawn" in window for window in seen_windows)


def test_clean_character_entries_drops_low_confidence_generic_summary():
    source_text = "Yeah, someone spoke once. Aikawa Junya glanced over."
    characters = [
        {
            "name": "Yeah",
            "entity_type": "unknown",
            "is_character": True,
            "confidence": 0.40,
            "aliases": [],
            "arc_summary": "mysterious figure",
        }
    ]

    cleaned = _clean_character_entries(characters, ["Yeah"], source_text)

    assert cleaned == []


def test_auto_augmentation_allows_strong_single_token_name_with_context():
    source_text = "His sister Grete called to him twice."

    assert _allow_auto_augmentation(source_text, "Grete") is True


def test_auto_augmentation_retains_every_supported_name_beyond_ten(monkeypatch):
    monkeypatch.setattr(extractor, "_allow_auto_augmentation", lambda *_args, **_kwargs: True)
    rejected = []
    names = [
        "Mara Vale",
        "Lio Ward",
        "Nera Cole",
        "Iris Stone",
        "Oren Pike",
        "Ada Reed",
        "Tara Moss",
        "Eli North",
        "Vera Holt",
        "Milo Gray",
        "Lena Shore",
        "Rosa Finch",
    ]
    source = " ".join(f"{name} spoke." for name in names)

    characters = _augment_with_named_mentions(
        source,
        [],
        names,
        rejected_characters=rejected,
    )

    assert [character["name"] for character in characters] == names
    assert rejected == []


def test_candidate_names_includes_supported_single_names():
    source_text = "Gregor Samsa woke before dawn. Gregor paced the room while his sister Grete called to him twice."

    candidates = _candidate_names(source_text)

    assert "Gregor Samsa" in candidates
    assert "Grete" in candidates


def test_candidate_names_include_grounded_sentence_start_singletons():
    source_text = "Gregor woke before dawn and watched the door."

    candidates = _candidate_names(source_text)

    assert "Gregor" in candidates


def test_candidate_names_excludes_discourse_singletons_with_action_nearby():
    source_text = "Actually, he said nothing. Maybe, she looked away."

    candidates = _candidate_names(source_text)

    assert "Actually" not in candidates
    assert "Maybe" not in candidates


def test_candidate_names_excludes_french_sentence_starters_and_pronouns():
    source_text = (
        "Chapitre 2\n"
        "Texte extrait. Mais elle regarde la porte. Nous attendons. Vous viendrez plus tard. "
        "Pourquoi les rideaux rouges et violet tremblent-ils ? Jaune, le ciel paraissait malade."
    )

    candidates = _candidate_names(source_text, allow_review_singletons=True)

    assert "Chapitre" not in candidates
    assert "Mais" not in candidates
    assert "Elle" not in candidates
    assert "Nous" not in candidates
    assert "Vous" not in candidates
    assert "Texte" not in candidates
    assert "Pourquoi" not in candidates
    assert "Rouges" not in candidates
    assert "Violet" not in candidates
    assert "Jaune" not in candidates


def test_candidate_names_excludes_french_apostrophe_fragments():
    source_text = "Aujourd'hui, Quelqu'un cria dans le couloir."

    candidates = _candidate_names(source_text, allow_review_singletons=True)

    assert "Aujourd" not in candidates
    assert "Quelqu" not in candidates


@pytest.mark.asyncio
async def test_fallback_character_mentions_recovers_single_name_characters():
    source_text = "Gregor Samsa woke before dawn. Gregor paced the room while his sister Grete called to him twice."

    recovered = await fallback_character_mentions(source_text)

    recovered_names = [item["name"] for item in recovered["characters"]]

    assert "Gregor" in recovered_names
    assert "Grete" in recovered_names


@pytest.mark.asyncio
async def test_fallback_character_mentions_uses_llm_for_review_band(monkeypatch):
    monkeypatch.setattr(
        "app.engine.character.extractor._local_mention_verifier",
        lambda *_args, **_kwargs: {
            "confidence_band": "review",
            "is_person_like": False,
            "reasons": ["ambiguous_single_token_mention"],
            "windows": [{"text": "Mother paused in the doorway."}],
        },
    )

    async def _fake_verify(*_args, **_kwargs):
        return {
            "candidate-0": {
                "used": True,
                "is_person_like": True,
                "confidence": 0.84,
                "canonical_name": None,
                "reason": "Used as a person in the passage.",
            }
        }

    monkeypatch.setattr(
        "app.engine.character.extractor._verify_review_candidates_with_llm",
        _fake_verify,
    )

    recovered = await fallback_character_mentions("Mother paused in the doorway.")

    assert [item["name"] for item in recovered["characters"]] == ["Mother"]
    verifier = recovered["characters"][0]["evidence"]["verifier"]
    assert verifier["final"]["confidence_band"] == "accept"
    assert verifier["llm"]["is_person_like"] is True


@pytest.mark.asyncio
async def test_fallback_character_mentions_rejects_review_candidate_when_llm_rejects(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.engine.character.extractor._local_mention_verifier",
        lambda *_args, **_kwargs: {
            "confidence_band": "review",
            "is_person_like": False,
            "reasons": ["ambiguous_single_token_mention"],
            "windows": [{"text": "Mother paused in the doorway."}],
        },
    )

    async def _fake_verify(*_args, **_kwargs):
        return {
            "candidate-0": {
                "used": True,
                "is_person_like": False,
                "confidence": 0.81,
                "canonical_name": None,
                "reason": "Used as an exclamation, not a person.",
            }
        }

    monkeypatch.setattr(
        "app.engine.character.extractor._verify_review_candidates_with_llm",
        _fake_verify,
    )

    recovered = await fallback_character_mentions("Mother paused in the doorway.")

    assert recovered["characters"] == []
    assert recovered["rejected_characters"]
    assert recovered["rejected_characters"][0]["stage"] == "mention_verifier"


@pytest.mark.asyncio
async def test_fallback_character_mentions_drops_unconfirmed_review_candidate(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.engine.character.extractor._local_mention_verifier",
        lambda *_args, **_kwargs: {
            "confidence_band": "review",
            "is_person_like": False,
            "reasons": ["ambiguous_single_token_mention"],
            "windows": [{"text": "Mother paused in the doorway."}],
        },
    )

    async def _fake_verify(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(
        "app.engine.character.extractor._verify_review_candidates_with_llm",
        _fake_verify,
    )

    recovered = await fallback_character_mentions("Mother paused in the doorway.")

    assert recovered["characters"] == []
    assert recovered["rejected_characters"]
    assert recovered["rejected_characters"][0]["stage"] == "deterministic_fallback"


def test_apply_anti_merge_hints_marks_same_sentence_characters_as_distinct():
    source_text = "Saitou Kengo and Saitou Masami entered the room together."
    characters = [
        {"name": "Saitou Kengo", "aliases": []},
        {"name": "Saitou Masami", "aliases": []},
    ]

    hinted = _apply_anti_merge_hints(source_text, characters)

    assert "Saitou Masami" in hinted[0]["anti_merge_names"]
    assert "Saitou Kengo" in hinted[1]["anti_merge_names"]


def test_clean_character_entries_keeps_titled_surname_only_names_distinct():
    source_text = "Mr. Samsa spoke first. Mrs. Samsa answered him from the doorway."
    characters = [
        {
            "name": "Mr. Samsa",
            "entity_type": "person",
            "is_character": True,
            "confidence": 0.91,
            "aliases": [],
            "traits": {},
            "arc_summary": "stern and worried",
        },
        {
            "name": "Mrs. Samsa",
            "entity_type": "person",
            "is_character": True,
            "confidence": 0.9,
            "aliases": [],
            "traits": {},
            "arc_summary": "protective and anxious",
        },
    ]

    cleaned = _clean_character_entries(characters, ["Mr. Samsa", "Mrs. Samsa"], source_text)

    assert [item["name"] for item in cleaned] == ["Mr. Samsa", "Mrs. Samsa"]


def test_clean_character_entries_keeps_madame_and_monsieur_surname_only_names_distinct():
    source_text = "Madame Moss spoke first. Monsieur Moss answered from the doorway."
    characters = [
        {
            "name": name,
            "entity_type": "person",
            "is_character": True,
            "confidence": 0.9,
            "aliases": [],
            "traits": {},
        }
        for name in ("Madame Moss", "Monsieur Moss")
    ]

    cleaned = _clean_character_entries(characters, ["Madame Moss", "Monsieur Moss"], source_text)

    assert [item["name"] for item in cleaned] == ["Madame Moss", "Monsieur Moss"]
    assert "Moss" not in _candidate_names(source_text)


def test_mention_has_person_context_treats_narrative_action_as_character_evidence():
    assert _mention_has_person_context("When ", "Gregor awoke from uneasy dreams.") is True
    assert _mention_has_person_context("", "Gregor watched the door in silence.") is True


@pytest.mark.asyncio
async def test_verify_character_candidate_personhood_uses_llm_for_review(monkeypatch):
    monkeypatch.setattr(
        "app.engine.character.extractor._local_mention_verifier",
        lambda *_args, **_kwargs: {
            "confidence_band": "review",
            "is_person_like": False,
            "reasons": ["ambiguous_single_token_mention"],
            "windows": [{"text": "Mother paused in the doorway."}],
        },
    )

    async def _fake_verify(*_args, **_kwargs):
        return {
            "candidate-0": {
                "used": True,
                "is_person_like": True,
                "confidence": 0.84,
                "canonical_name": None,
                "reason": "Used as a person in the passage.",
            }
        }

    monkeypatch.setattr(
        "app.engine.character.extractor._verify_review_candidates_with_llm",
        _fake_verify,
    )

    result = await verify_character_candidate_personhood("Mother paused in the doorway.", "Mother")

    assert result["final"]["confidence_band"] == "accept"
    assert result["llm"]["is_person_like"] is True
