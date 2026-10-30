import json

import pytest

from app.utils.advisor_result_utils import identify_character_mentions
from app.utils.voice_review_utils import (
    VoiceReviewFormatError,
    attributed_voice_samples,
    closest_alternate_voice_match,
    disambiguate_voice_aliases,
    first_person_narration_samples,
    grounded_voice_profile_claims,
    make_voice_review_cache_key,
    select_diverse_voice_baseline_samples,
    split_voice_passage,
    validate_voice_section_result,
    voice_baseline_size,
    voice_baseline_style_summary,
    voice_baseline_sufficient,
    voice_current_sample_sufficient,
    voice_finding_key,
    voice_independent_source_texts,
    voice_ranges_cover_text,
    voice_review_character_context,
    voice_review_context_signature,
    voice_samples_have_reliable_attribution,
    voice_source_anchors_for_section,
    voice_source_covers_submitted_passage,
    voice_source_matches_submitted,
    voice_source_ranges_for_section,
)


def test_voice_source_match_accepts_copy_and_light_edit_but_not_generic_fragment():
    source = " ".join(f"detail{index}" for index in range(40))
    edited = source.replace("detail18", "revision18")

    assert voice_source_matches_submitted(source, source)
    assert voice_source_matches_submitted(source, edited)
    assert voice_source_matches_submitted(source, "Unrelated words in a different passage") is False
    assert voice_source_matches_submitted(source, "I") is False
    assert voice_source_matches_submitted("Mara", source + " Mara") is False
    assert voice_source_matches_submitted("", source) is False


def test_voice_source_exact_short_passage_is_not_used_as_its_own_baseline():
    passage = 'Mara said, "Go."'

    assert voice_source_matches_submitted(passage, passage)
    assert voice_source_covers_submitted_passage(passage, passage)
    assert not voice_source_covers_submitted_passage(passage + ' Mara replied, "Wait."', passage)
    assert voice_source_matches_submitted('The storm ended. Mara said, "Go." Lina nodded.', passage)
    assert not voice_source_matches_submitted(
        'The storm ended. The sign read "Go." Lina nodded.', passage
    )


def test_voice_source_match_detects_short_edited_passage_without_generic_false_match():
    source = (
        'Mara said, "Stay near the gate until the storm breaks and the watch changes '
        'at dawn." The lantern shook in her hand.'
    )
    edited = source.replace("the watch changes", "the patrol changes")

    assert voice_source_matches_submitted(source, edited)
    assert not voice_source_matches_submitted(
        source,
        'Lina said, "I shall return after sunset to collect the records." '
        "The lantern shook in her hand.",
    )


def test_voice_source_match_detects_light_edit_in_repeated_dialogue():
    source = 'Mara said, "Wait for me beside the old gate." ' * 8
    edited = source.replace("old gate", "north gate", 1)

    assert voice_source_matches_submitted(source, edited)


def test_voice_source_coverage_detects_copied_passage_but_not_one_repeated_quote():
    submitted = (
        'Mara said, "We will cross the northern bridge at dawn." '
        "She folded the map and marked three safe roads through the hills. "
        "The watchtower stood beyond the river near the old mill."
    )
    copied_from_earlier = "Unrelated opening. " + submitted + " A different ending."
    lightly_edited = submitted.replace("three safe roads", "four safe roads")

    assert voice_source_covers_submitted_passage(copied_from_earlier, submitted)
    assert voice_source_covers_submitted_passage(copied_from_earlier, lightly_edited)
    assert not voice_source_covers_submitted_passage(
        'Mara said, "We will cross the northern bridge at dawn."', submitted
    )
    assert not voice_source_covers_submitted_passage(copied_from_earlier, "The old mill.")


def test_voice_aliases_exclude_shared_surname_and_alias_inside_other_full_name():
    characters = [
        {
            "id": "mother",
            "name": "Madame Meursault",
            "aliases": ["Meursault", "Mother"],
            "first_chapter": 1,
        },
        {
            "id": "son",
            "name": "Monsieur Meursault",
            "aliases": ["Meursault"],
            "first_chapter": 1,
        },
    ]

    resolved = disambiguate_voice_aliases(characters)

    assert resolved[0]["aliases"] == ["Mother"]
    assert resolved[1]["aliases"] == []
    assert characters[0]["aliases"] == ["Meursault", "Mother"]
    source = 'Madame Meursault said, "I will wait here."'
    assert [item["id"] for item in identify_character_mentions(source, resolved)] == ["mother"]
    assert [
        sample["excerpt"]
        for sample in attributed_voice_samples(
            source,
            character_name=resolved[0]["name"],
            aliases=resolved[0]["aliases"],
            chapter_number=1,
        )
    ] == ["I will wait here."]
    assert (
        attributed_voice_samples(
            source,
            character_name=resolved[1]["name"],
            aliases=resolved[1]["aliases"],
            chapter_number=1,
        )
        == []
    )


def test_voice_aliases_exclude_name_collision_but_keep_unique_aliases():
    resolved = disambiguate_voice_aliases(
        [
            {"name": "Mara Vale", "aliases": ["Mara", "the Warden"]},
            {"name": "Mara Veil", "aliases": ["Mara", "the Watcher"]},
        ]
    )

    assert resolved[0]["aliases"] == ["the Warden"]
    assert resolved[1]["aliases"] == ["the Watcher"]
    assert disambiguate_voice_aliases([]) == []


def test_voice_review_cache_key_changes_when_passage_tail_or_baseline_changes():
    first = make_voice_review_cache_key("book", "a" * 5_000 + "first", 2, "Mara", "baseline A")
    assert first != make_voice_review_cache_key(
        "book", "a" * 5_000 + "second", 2, "Mara", "baseline A"
    )
    assert first != make_voice_review_cache_key(
        "book", "a" * 5_000 + "first", 2, "Mara", "baseline B"
    )


def test_alternate_voice_similarity_requires_independent_sufficient_baseline_and_long_sample():
    submitted = (
        "I shall leave the council at dawn because the documents require careful review "
        "before anyone makes a final decision."
    )
    alternate = [
        {
            "chapter_number": chapter,
            "excerpt": (
                "I shall return to the council at dusk because the records require careful "
                f"review before anyone makes a public decision in chapter {chapter}."
            ),
        }
        for chapter in (1, 2, 3)
    ]
    baselines = {
        "Mara": alternate[:1],
        "Iris": alternate,
        "Milo": alternate[:2],
    }

    name, score = closest_alternate_voice_match(
        character_name="Mara",
        submitted_excerpts=[submitted],
        own_score=25,
        baseline_by_name=baselines,
    )
    assert name == "Iris"
    assert score is not None and score >= 60
    assert closest_alternate_voice_match(
        character_name="Mara",
        submitted_excerpts=["Wait now."],
        own_score=25,
        baseline_by_name=baselines,
    ) == (None, None)
    assert closest_alternate_voice_match(
        character_name="Mara",
        submitted_excerpts=[submitted],
        own_score=100,
        baseline_by_name=baselines,
    ) == (None, None)
    assert closest_alternate_voice_match(
        character_name="Mara",
        submitted_excerpts=[submitted],
        own_score=25,
        baseline_by_name={
            "Iris": [{**sample, "attribution_confidence": "contextual"} for sample in alternate]
        },
    ) == (None, None)


def test_voice_review_context_signature_changes_with_profile_story_or_evidence():
    profile = {
        "id": "character-1",
        "generation_id": "generation-1",
        "name": "Mara",
        "motivations": ["find the bridge"],
    }
    samples = {"Mara": [{"chapter_number": 1, "excerpt": "I shall find the bridge."}]}

    def signature(*, story="A bridge is missing.", characters=None, baseline=None):
        return voice_review_context_signature(
            story_context=story,
            characters=characters if characters is not None else [profile],
            baseline_by_name=baseline if baseline is not None else samples,
        )

    original = signature()
    assert original == signature(characters=[dict(reversed(list(profile.items())))])
    assert original != signature(characters=[{**profile, "motivations": ["hide the bridge"]}])
    assert original != signature(characters=[{**profile, "generation_id": "generation-2"}])
    assert original != signature(story="The bridge has collapsed.")
    assert original != signature(
        baseline={"Mara": [{"chapter_number": 1, "excerpt": "The bridge is gone."}]}
    )


def test_voice_baseline_selection_uses_tail_dialogue_and_spreads_chapters():
    submitted = "Opening narration. " * 300 + 'Mara said, "The copper compass points north."'
    samples = [
        {
            "chapter_number": chapter,
            "excerpt": f"Ordinary words from chapter {chapter}.",
        }
        for chapter in range(1, 21)
    ]
    samples[-1]["excerpt"] = "The copper compass points toward the bridge."

    chosen = select_diverse_voice_baseline_samples(
        samples, submitted_text=submitted, character_name="Mara", max_samples=6
    )

    assert len(submitted) > 4_000
    assert len(chosen) == 6
    assert samples[-1] in chosen
    assert len({sample["chapter_number"] for sample in chosen}) == 6


def test_voice_baseline_selection_handles_empty_and_single_sample_limits():
    samples = [
        {"chapter_number": 1, "excerpt": "The old lantern went dark."},
        {"chapter_number": 2, "excerpt": "The copper compass pointed north."},
    ]
    assert select_diverse_voice_baseline_samples(
        samples,
        submitted_text='Mara said, "The copper compass is mine."',
        character_name="Mara",
        max_samples=1,
    ) == [samples[1]]
    assert (
        select_diverse_voice_baseline_samples(
            samples, submitted_text="", character_name="Mara", max_samples=0
        )
        == []
    )
    assert select_diverse_voice_baseline_samples([], submitted_text="", character_name="Mara") == []


def test_current_voice_evidence_requires_independent_dialogue_or_sustained_narration():
    short_speech = {"excerpt": "I will wait by the bridge until dawn."}
    second_speech = {
        "excerpt": "You should take the northern road before the gates close tonight without stopping."
    }
    assert not voice_current_sample_sufficient([], voice_mode="dialogue")
    assert not voice_current_sample_sufficient([short_speech], voice_mode="dialogue")
    assert voice_current_sample_sufficient([short_speech, second_speech], voice_mode="dialogue")
    assert not voice_current_sample_sufficient(
        [{**short_speech, "source_id": "same"}, {**second_speech, "source_id": "same"}],
        voice_mode="dialogue",
    )
    assert not voice_current_sample_sufficient([short_speech], voice_mode="first_person_narration")
    assert voice_current_sample_sufficient(
        [{"excerpt": "I followed the quiet river after sunrise. " * 6}],
        voice_mode="first_person_narration",
    )
    with pytest.raises(ValueError, match="invalid_voice_mode"):
        voice_current_sample_sufficient([], voice_mode="unknown")


def test_voice_finding_key_is_stable_for_same_cited_text():
    issue = {
        "character_name": "Mara",
        "submitted_excerpt": "No way, dude.",
        "baseline_excerpt": "I shall return.",
        "baseline_chapter_number": 1,
    }
    assert voice_finding_key(issue) == voice_finding_key(
        {**issue, "submitted_excerpt": "  No   way, dude.  "}
    )
    assert voice_finding_key(issue) != voice_finding_key({**issue, "baseline_chapter_number": 2})
    assert voice_finding_key(issue, source_fingerprint="scene-one") != voice_finding_key(
        issue, source_fingerprint="scene-two"
    )


def test_split_voice_passage_covers_long_text_and_last_characters():
    passage = "Opening words. " * 300 + "At the end, she changed her voice."
    ranges = split_voice_passage(passage)

    assert len(ranges) > 1
    assert all(len(item["text"]) <= 3_500 for item in ranges)
    assert all(item["text"] == passage[item["start"] : item["end"]] for item in ranges)
    assert voice_ranges_cover_text(ranges, len(passage))
    assert "changed her voice" in ranges[-1]["text"]


def test_voice_ranges_reject_gaps_and_invalid_section_sizes():
    assert not voice_ranges_cover_text([{"start": 0, "end": 2}, {"start": 3, "end": 5}], 5)
    assert not voice_ranges_cover_text([], 1)
    assert split_voice_passage("") == []
    with pytest.raises(ValueError, match="invalid_voice_section_size"):
        split_voice_passage("hello", max_chars=100, overlap=100)


def test_voice_source_anchors_cover_attributed_quote_across_section_boundary():
    passage = 'Mara said, "' + "steady " * 600 + 'No way, dude."'
    sections = split_voice_passage(passage)
    samples = attributed_voice_samples(
        passage, character_name="Mara", chapter_number=2, include_offsets=True
    )

    assert len(sections) == 2
    assert len(samples) > 1
    assert all(0 < len(sample["excerpt"]) <= 700 for sample in samples)
    assert len({sample["source_id"] for sample in samples}) == 1
    assert voice_baseline_size(samples)[0] == 1
    assert not voice_baseline_sufficient(samples)
    assert all(
        passage[sample["source_start"] : sample["source_end"]] == sample["excerpt"]
        for sample in samples
    )
    assert voice_source_anchors_for_section(passage, sections[0], samples)
    late_anchors = voice_source_anchors_for_section(passage, sections[1], samples)
    assert late_anchors
    assert any("No way, dude." in anchor for anchor in late_anchors)
    assert all(anchor in sections[1]["text"] for anchor in late_anchors)


def test_voice_baseline_size_counts_all_words_of_split_speech_once():
    speech = "steady " * 170 + "I shall return at dawn."
    source = f'Mara said, "{speech}"'
    samples = attributed_voice_samples(
        source, character_name="Mara", chapter_number=1, include_offsets=True
    )

    assert len(samples) > 1
    assert voice_baseline_size(samples) == (1, len(speech.split()))
    assert not voice_baseline_sufficient(samples, min_samples=2)
    assert voice_baseline_size(samples[:1])[1] < len(speech.split())


def test_voice_baseline_size_keeps_distinct_narration_around_quoted_speech():
    first = "I walked beside the river and watched the lanterns pass. " * 6
    second = "I returned home and waited for the morning train. " * 6
    source = f'{first}"This is someone else speaking."{second}'
    samples = first_person_narration_samples(source, chapter_number=2, include_offsets=True)

    assert len(samples) >= 2
    assert voice_baseline_size(samples) == (1, len(first.split()) + len(second.split()))


def test_identical_first_person_paragraphs_in_different_chapters_remain_independent():
    passage = "I waited beside the river until the sun had risen over the village. " * 3
    first = first_person_narration_samples(passage, chapter_number=1, include_offsets=True)
    second = first_person_narration_samples(passage, chapter_number=2, include_offsets=True)

    assert first[0]["source_id"] != second[0]["source_id"]
    assert voice_baseline_size([*first, *second]) == (2, 2 * len(passage.split()))


def test_voice_baseline_selection_prefers_distinct_speeches_over_long_quote_segments():
    source = (
        'Mara said, "' + "steady " * 1500 + 'Enough." '
        'Mara said, "I will wait by the bridge until sunrise." '
        'Mara said, "The road still belongs to us tonight."'
    )
    samples = attributed_voice_samples(source, character_name="Mara", chapter_number=1)

    selected = select_diverse_voice_baseline_samples(
        samples,
        submitted_text='Mara said, "Stay here."',
        character_name="Mara",
        max_samples=3,
    )

    assert len(selected) == 3
    assert any("bridge until sunrise" in sample["excerpt"] for sample in selected)
    assert any("road still belongs" in sample["excerpt"] for sample in selected)
    assert voice_baseline_sufficient(selected, min_words=1)


def test_voice_source_anchors_reject_invalid_ranges_and_skip_unattributed_text():
    section = {"start": 0, "end": 12, "text": "Mara waited."}
    assert voice_source_anchors_for_section("Mara waited.", section, []) == []
    assert (
        voice_source_anchors_for_section(
            "Mara waited.",
            section,
            [{"excerpt": "Mara", "source_start": 5, "source_end": 9}],
        )
        == []
    )
    with pytest.raises(ValueError, match="invalid_voice_anchor_size"):
        voice_source_anchors_for_section("Mara waited.", section, [], anchor_chars=0)
    with pytest.raises(ValueError, match="invalid_voice_section_range"):
        voice_source_anchors_for_section("Mara waited.", {"start": 2, "end": 20}, [])


def test_voice_source_anchors_use_attributed_occurrence_when_quote_text_repeats():
    passage = 'The sign read "Wait here." Mara said, "Wait here."'
    samples = attributed_voice_samples(
        passage, character_name="Mara", chapter_number=2, include_offsets=True
    )
    first = {
        "start": 0,
        "end": passage.index("Mara said"),
        "text": passage[: passage.index("Mara said")],
    }
    second = {
        "start": passage.index("Mara said"),
        "end": len(passage),
        "text": passage[passage.index("Mara said") :],
    }

    assert len(samples) == 1
    assert passage[samples[0]["source_start"] : samples[0]["source_end"]] == "Wait here."
    assert voice_source_anchors_for_section(passage, first, samples) == []
    assert voice_source_anchors_for_section(passage, second, samples) == ["Wait here."]
    assert voice_source_ranges_for_section(passage, first, samples) == []
    assert voice_source_ranges_for_section(passage, second, samples) == [
        {"start": samples[0]["source_start"], "end": samples[0]["source_end"]}
    ]


def test_voice_source_ranges_do_not_claim_ambiguous_legacy_quotes():
    passage = 'The sign read "Wait here." Mara said, "Wait here."'
    section = {"start": 0, "end": len(passage), "text": passage}

    assert voice_source_ranges_for_section(passage, section, [{"excerpt": "Wait here."}]) == []
    assert voice_source_anchors_for_section(passage, section, [{"excerpt": "Wait here."}]) == []


def test_first_person_source_offsets_exclude_matching_quoted_speech():
    prose = (
        "I walked beside the river after dawn and counted the empty boats at the pier. "
        "My coat was damp, and I knew the bridge would be closed before I reached it."
    )
    passage = f'"{prose}"\n\n{prose}'
    samples = first_person_narration_samples(passage, chapter_number=2, include_offsets=True)
    quoted = {"start": 0, "end": len(prose) + 2, "text": passage[: len(prose) + 2]}
    narration = {
        "start": len(prose) + 2,
        "end": len(passage),
        "text": passage[len(prose) + 2 :],
    }

    assert len(samples) == 1
    assert samples[0]["source_start"] > quoted["end"]
    assert voice_source_anchors_for_section(passage, quoted, samples) == []
    assert voice_source_anchors_for_section(passage, narration, samples)


def test_voice_review_character_context_separates_dialogue_from_selected_narrator():
    dialogue = voice_review_character_context("Mara", "dialogue", ["I will wait."])
    narrator = voice_review_character_context(
        "Mara", "first_person_narration", ["I crossed the bridge."]
    )

    assert "unattributed dialogue" in dialogue
    assert "user-selected" not in dialogue
    assert "selected by the author" in narrator
    assert "do not assign quoted dialogue" in narrator
    assert "I will wait." in dialogue
    assert "I crossed the bridge." in narrator
    assert "do not make a voice finding" in voice_review_character_context("Mara", "dialogue", [])
    with pytest.raises(ValueError, match="invalid_voice_mode"):
        voice_review_character_context("Mara", "generic", [])


def test_voice_baseline_style_summary_uses_only_cited_independent_excerpts():
    samples = [
        {
            "chapter_number": 1,
            "source_id": "one",
            "excerpt": "I shall wait. I shall wait!",
        },
        {
            "chapter_number": 2,
            "source_id": "two",
            "excerpt": "I shall wait? We cannot leave.",
        },
    ]

    summary = voice_baseline_style_summary(samples)
    context = voice_review_character_context(
        "Mara", "dialogue", ["I shall wait."], baseline_style=summary
    )

    assert "2 independent excerpts" in summary
    assert "chapter 1, 2" in summary
    assert "punctuation per 100 words" in summary
    assert "observed sentence-length range" in summary
    assert "formal vocabulary markers" in summary
    assert "not a voice verdict" in summary
    assert summary in context
    assert voice_baseline_style_summary([]) == ""
    assert voice_baseline_style_summary([{"excerpt": "  ", "source_id": "empty"}]) == ""


def test_voice_baseline_style_summary_does_not_count_overlapping_source_twice():
    samples = [
        {
            "source_id": "same",
            "source_start": 0,
            "source_end": 12,
            "excerpt": "I shall wait.",
        },
        {"source_id": "same", "source_start": 8, "source_end": 12, "excerpt": "ait."},
    ]

    assert "1 independent excerpt" in voice_baseline_style_summary(samples)


def test_voice_profile_context_uses_only_current_claims_cited_in_baseline_passages():
    quote = "Mara counted each coin before making her careful promise."
    baseline = [{"chapter_number": 1, "excerpt": f"At the counter, {quote} Then she left."}]
    character = {
        "personality_tags": ["measured"],
        "motivations": ["Protect the town"],
        "arc_summary": "She becomes a leader.",
        "analysis_metadata": {
            "profile_claims": [
                {
                    "field": "personality_tags",
                    "value": "measured",
                    "chapter_number": 1,
                    "quote": quote,
                },
                {
                    "field": "motivations",
                    "value": "Protect the town",
                    "chapter_number": 2,
                    "quote": quote,
                },
                {
                    "field": "arc_summary",
                    "value": "She becomes a leader.",
                    "chapter_number": 1,
                    "quote": "An uncited change in her character.",
                },
                {
                    "field": "personality_tags",
                    "value": "reckless",
                    "chapter_number": 1,
                    "quote": quote,
                },
                {"field": ["personality_tags"], "value": "measured", "quote": quote},
            ]
        },
    }

    claims = grounded_voice_profile_claims(character, baseline)
    context = voice_review_character_context(
        "Mara", "dialogue", ["Wait here."], profile_claims=claims
    )

    assert claims == [
        {
            "field": "personality_tags",
            "value": "measured",
            "chapter_number": 1,
            "quote": quote,
        }
    ]
    assert "measured" in context and quote in context
    assert "Protect the town" not in context
    assert "She becomes a leader" not in context
    assert grounded_voice_profile_claims(character, baseline, limit=0) == []
    assert grounded_voice_profile_claims({"analysis_metadata": None}, baseline) == []


def test_attributed_voice_samples_require_explicit_nearby_speaker_and_keep_titles_distinct():
    source = (
        'Madame Arlen said, "I shall call tomorrow." '
        'Monsieur Arlen replied, "I do not agree." '
        '"Unattributed speech should not count."'
    )
    madame = attributed_voice_samples(source, character_name="Madame Arlen", chapter_number=1)
    monsieur = attributed_voice_samples(source, character_name="Monsieur Arlen", chapter_number=1)

    assert [item["excerpt"] for item in madame] == ["I shall call tomorrow."]
    assert [item["excerpt"] for item in monsieur] == ["I do not agree."]


def test_attributed_voice_samples_link_narrator_tagged_dialogue_only_after_identity_verification():
    source = (
        'I am Mara Vale. I said, "Keep the lamps low." '
        '"The road is clear," I replied. '
        'Lina said, "I will check the gate."'
    )

    unverified = attributed_voice_samples(source, character_name="Mara Vale", chapter_number=2)
    verified = attributed_voice_samples(
        source,
        character_name="Mara Vale",
        chapter_number=2,
        first_person_speaker=True,
        include_offsets=True,
    )

    assert unverified == []
    assert [sample["excerpt"] for sample in verified] == [
        "Keep the lamps low.",
        "The road is clear,",
    ]
    assert all(
        source[sample["source_start"] : sample["source_end"]] == sample["excerpt"]
        for sample in verified
    )
    assert (
        attributed_voice_samples(
            'I am Mara Vale. I walked to the gate. He said, "Not yet."',
            character_name="Mara Vale",
            chapter_number=2,
            first_person_speaker=True,
        )
        == []
    )


def test_attributed_voice_samples_accept_name_then_speech_verb_after_a_quote():
    source = (
        'Mara watched the door. "The gate is open," Lina said. '
        '"Wait," said Mara. "No speaker here." Lina watched the street.'
    )

    mara = attributed_voice_samples(source, character_name="Mara", chapter_number=2)
    lina = attributed_voice_samples(source, character_name="Lina", chapter_number=2)

    assert [sample["excerpt"] for sample in mara] == ["Wait,"]
    assert [sample["excerpt"] for sample in lina] == ["The gate is open,"]


def test_attributed_voice_samples_do_not_assign_later_quotes_to_an_earlier_speaker():
    source = (
        'Mara said the map was wrong. Lina replied, "Leave now." '
        '"Wait," said Mara. "The gate is open." Lina pointed to the street. '
        'Mara spoke quietly. Lina said, "Follow me." '
        'Mara said to Lina and Lina replied, "I understand."'
    )

    mara = attributed_voice_samples(source, character_name="Mara", chapter_number=2)
    lina = attributed_voice_samples(source, character_name="Lina", chapter_number=2)

    assert [sample["excerpt"] for sample in mara] == ["Wait,"]
    assert [sample["excerpt"] for sample in lina] == [
        "Leave now.",
        "Follow me.",
        "I understand.",
    ]


def test_attributed_voice_samples_do_not_claim_explicit_speaker_when_later_pronoun_reports_quote():
    source = 'Mara said that he whispered, "Keep the gate closed." Mara replied, "I will guard it."'

    samples = attributed_voice_samples(source, character_name="Mara", chapter_number=2)

    assert [sample["excerpt"] for sample in samples] == ["I will guard it."]
    assert "attribution_confidence" not in samples[0]


def test_attributed_voice_samples_link_pronoun_only_to_single_nearby_named_antecedent():
    source = (
        'Mara closed the window. She said, "I need the ledger." '
        'Mara checked the lock. "The door is sealed," she replied.'
    )

    samples = attributed_voice_samples(source, character_name="Mara", chapter_number=2)

    assert [sample["excerpt"] for sample in samples] == [
        "I need the ledger.",
        "The door is sealed,",
    ]
    assert all(sample["attribution_confidence"] == "contextual" for sample in samples)


def test_attributed_voice_samples_do_not_guess_pronoun_after_two_named_people():
    source = 'Mara watched Lina cross the room. She said, "I need the ledger."'

    assert attributed_voice_samples(source, character_name="Mara", chapter_number=2) == []
    assert attributed_voice_samples(source, character_name="Lina", chapter_number=2) == []


def test_first_person_narration_samples_ignore_quote_only_first_person():
    narrative = (
        "I walked through the empty station after the storm and tried to remember the road "
        "we had taken the previous evening. The lights were still on, but nobody spoke to me. "
        "I waited until the final train had passed."
    )
    quoted = (
        'The guard said, "I walked through the empty station after the storm and tried to '
        'remember the road we had taken the previous evening." The room stayed quiet and '
        "the clock struck twice before anyone moved from the bench near the door."
    )
    samples = first_person_narration_samples(f"{narrative}\n\n{quoted}", chapter_number=2)

    assert [item["excerpt"] for item in samples] == [narrative]


def test_narrator_baseline_never_includes_interleaved_dialogue():
    prose = (
        "I walked through the square as the rain stopped. I did not know what waited "
        "inside the station, but I could hear the train whistle beyond the empty street. "
        "I kept walking because I was afraid to turn back."
    )
    source = prose + ' "I know your secret," the guard said.'

    samples = first_person_narration_samples(source, chapter_number=2)

    assert [sample["excerpt"] for sample in samples] == [prose]
    assert "I know your secret" not in samples[0]["excerpt"]


def test_short_first_person_paragraphs_build_sufficient_evidence_without_dialogue():
    paragraphs = [
        f"I crossed the quiet square at dawn and checked the blue gate again {index}."
        for index in range(9)
    ]
    expected_paragraphs = paragraphs[:5] + ["I waited."] + paragraphs[5:]
    source = "\n\n".join(
        paragraphs[:5]
        + ["— I crossed the quiet square, the guard said.", "I waited."]
        + paragraphs[5:]
    )

    samples = first_person_narration_samples(source, chapter_number=2, include_offsets=True)

    assert len(samples) == len(expected_paragraphs)
    assert [sample["excerpt"] for sample in samples] == expected_paragraphs
    assert all(
        source[sample["source_start"] : sample["source_end"]] == sample["excerpt"]
        for sample in samples
    )
    assert voice_current_sample_sufficient(samples, voice_mode="first_person_narration")
    assert voice_baseline_sufficient(samples, min_words=120)
    assert not voice_baseline_sufficient(samples[:2], min_words=120)


def test_single_quoted_dialogue_is_not_mistaken_for_first_person_narration():
    prose = (
        "I crossed the station in the rain and waited beside the empty ticket counter. "
        "The last train had already left, so I decided to walk through the city alone. "
        "I kept my coat closed against the wind."
    )
    for dialogue in (
        "'I can't leave the gate open,'",
        "‘I can’t leave the gate open,’",
    ):
        source = f"{prose} {dialogue} the guard said."
        samples = first_person_narration_samples(source, chapter_number=2, include_offsets=True)

        assert [sample["excerpt"] for sample in samples] == [prose]
        assert source[samples[0]["source_start"] : samples[0]["source_end"]] == prose


def test_single_quoted_dialogue_retains_exact_attribution_and_offsets():
    for dialogue in (
        "'I can't leave the gate open,'",
        "‘I can’t leave the gate open,’",
        "‘It’s late and we’ll leave the gate open,’",
    ):
        source = f"Mara said, {dialogue} Lina waited at the threshold."
        samples = attributed_voice_samples(
            source, character_name="Mara", chapter_number=2, include_offsets=True
        )

        assert [sample["excerpt"] for sample in samples] == [dialogue[1:-1]]
        assert source[samples[0]["source_start"] : samples[0]["source_end"]] == dialogue[1:-1]


def test_narrator_contractions_are_not_parsed_as_single_quoted_dialogue():
    prose = (
        "I couldn't find the letter that morning, although I'd searched every drawer. "
        "My brother's coat was still by the door, and I didn't know whether he had "
        "left it for me or forgotten it in his hurry. I waited until dusk."
    )

    samples = first_person_narration_samples(prose, chapter_number=2)

    assert [sample["excerpt"] for sample in samples] == [prose]


def test_narrator_sampling_excludes_dialogue_spanning_multiple_paragraphs():
    opening = (
        "I reached the station before the rain and watched the platform empty slowly. "
        "I carried the old letter in my pocket, but I could not bring myself to read it. "
        "The lamps came on while I waited beside the door."
    )
    closing = (
        "I left after the guard closed the gate and the last train had departed. "
        "My coat was wet by then, and I took the long road home through the market. "
        "I had not expected to return so late."
    )
    speech = (
        '"I heard the bell from the far end of the platform and looked for you.\n\n'
        'I waited there until the guard told me that you had already gone."'
    )
    source = f"{opening}\n\n{speech}\n\n{closing}"

    samples = first_person_narration_samples(source, chapter_number=2, include_offsets=True)

    assert [sample["excerpt"] for sample in samples] == [opening, closing]
    assert all(
        source[sample["source_start"] : sample["source_end"]] == sample["excerpt"]
        for sample in samples
    )


def test_narrator_sampling_excludes_paragraph_opening_dialogue_dashes():
    prose = (
        "I crossed the square before sunrise and waited at the old fountain. "
        "The market stalls were still closed, and I could hear the first bus coming. "
        "I turned toward the station when the bells began."
    )
    speech = (
        "— I told the guard that I would stay until morning, but he would not listen. "
        "I tried again when the station lights came on and the last passengers left."
    )
    source = f"{prose}\n\n{speech}\n\n{prose}"

    samples = first_person_narration_samples(source, chapter_number=2)

    assert [sample["excerpt"] for sample in samples] == [prose, prose]


def test_narrator_sampling_covers_late_source_without_inflating_baseline_count():
    passage = (
        "I crossed the empty square. "
        + "The rain had stopped, but the street stayed silent. " * 180
        + "I remembered the promise I made before the train departed."
    )

    samples = first_person_narration_samples(passage, chapter_number=2)

    assert len(passage) > 4_000
    assert len(samples) > 3
    assert any("I remembered the promise" in item["excerpt"] for item in samples)
    assert all(item["excerpt"] in passage for item in samples)
    assert not voice_baseline_sufficient(samples)


def test_narrator_baseline_counts_one_paragraph_once_even_with_dialogue_breaks():
    prose = (
        "I crossed the field after the rain and saw the road ahead. "
        "I wanted to turn back, but the others were already waiting at the gate. "
        "My hands shook as I reached for the latch and listened for footsteps."
    )
    source = f'{prose} "Wait," said the guard. {prose} "Go," said the guard. {prose}'

    samples = first_person_narration_samples(source, chapter_number=1)

    assert len(samples) >= 3
    assert len({sample["source_id"] for sample in samples}) == 1
    assert not voice_baseline_sufficient(samples)


def test_attributed_dialogue_preserves_exact_source_line_breaks():
    source = 'Mara said, "I shall\nreturn at dawn."'

    samples = attributed_voice_samples(source, character_name="Mara", chapter_number=1)

    assert samples[0]["excerpt"] == "I shall\nreturn at dawn."
    assert samples[0]["excerpt"] in source


def test_attributed_dialogue_preserves_repeated_utterances_at_distinct_positions():
    source = 'Mara said, "Wait here." Lina replied, "Go on." Mara said, "Wait here."'

    samples = attributed_voice_samples(
        source, character_name="Mara", chapter_number=1, include_offsets=True
    )

    assert [sample["excerpt"] for sample in samples] == ["Wait here.", "Wait here."]
    assert len({sample["source_id"] for sample in samples}) == 2
    assert len({sample["source_start"] for sample in samples}) == 2
    assert all(
        source[sample["source_start"] : sample["source_end"]] == sample["excerpt"]
        for sample in samples
    )
    assert voice_baseline_size(samples) == (2, 4)


def test_voice_baseline_threshold_requires_samples_and_words():
    samples = [{"excerpt": "formal speech " * 21}] * 3
    assert voice_baseline_sufficient(samples)
    assert not voice_baseline_sufficient(samples[:2])
    assert not voice_baseline_sufficient([{"excerpt": "yes"}] * 3)


def test_voice_metrics_reconstruct_overlapping_source_only_once():
    source = "I will wait by the old gate until dawn."
    samples = [
        {
            "source_id": "one-utterance",
            "excerpt": source[:28],
            "source_start": 0,
            "source_end": 28,
        },
        {
            "source_id": "one-utterance",
            "excerpt": source[20:],
            "source_start": 20,
            "source_end": len(source),
        },
    ]

    assert voice_independent_source_texts(samples) == [source]
    assert voice_baseline_size(samples) == (1, len(source.split()))
    assert voice_independent_source_texts([]) == []
    assert voice_independent_source_texts(
        [
            {"source_id": "legacy", "excerpt": "a short quote"},
            {"source_id": "legacy", "excerpt": "a longer source quote"},
        ]
    ) == ["a longer source quote"]


def test_voice_match_requires_only_reliably_attributed_current_samples():
    assert not voice_samples_have_reliable_attribution([])
    assert voice_samples_have_reliable_attribution([{"excerpt": "I shall go."}])
    assert not voice_samples_have_reliable_attribution(
        [
            {"excerpt": "I shall go."},
            {"excerpt": "Maybe.", "attribution_confidence": "contextual"},
        ]
    )
    assert not voice_samples_have_reliable_attribution(
        [
            {
                "excerpt": "I crossed the square.",
                "attribution_confidence": "unverified_narrator",
            }
        ]
    )


def test_voice_result_validation_accepts_exact_evidence_only():
    baseline = [{"chapter_number": 1, "excerpt": "I shall be there at six."}]
    issue = {
        "character_name": "Mara",
        "classification": "possible",
        "severity": "moderate",
        "title": "Unexpected slang",
        "description": "The new phrase differs from the earlier formal speech.",
        "submitted_excerpt": "No way, dude.",
        "baseline_excerpt": "I shall be there at six.",
        "baseline_chapter_number": 1,
        "confidence": 0.7,
        "revision_direction": "Keep the urgency, but check the register.",
        "intentionality_prompt": "Is the change intentional under pressure?",
    }
    raw = json.dumps({"issues": [issue], "overall_verdict": "One possible shift."})
    assert validate_voice_section_result(
        raw,
        section_text='Mara said "No way, dude."',
        baseline_samples=baseline,
        submitted_samples=[{"excerpt": "No way, dude."}],
        character_name="Mara",
    )["issues"] == [issue]
    for accepted_severity in ("minor", "critical"):
        accepted = {**issue, "severity": accepted_severity}
        assert validate_voice_section_result(
            json.dumps({"issues": [accepted], "overall_verdict": "A shift."}),
            section_text='Mara said "No way, dude."',
            baseline_samples=baseline,
            submitted_samples=[{"excerpt": "No way, dude."}],
            character_name="Mara",
        )["issues"] == [accepted]
    for override in (
        {"submitted_excerpt": "Fabricated line"},
        {"submitted_excerpt": "Mara said"},
        {"baseline_excerpt": "Invented baseline"},
        {"baseline_chapter_number": 2},
        {"baseline_chapter_number": True},
        {"character_name": "Other person"},
        {"severity": "high"},
        {"severity": None},
    ):
        with pytest.raises(VoiceReviewFormatError):
            validate_voice_section_result(
                json.dumps({"issues": [{**issue, **override}], "overall_verdict": "A shift."}),
                section_text='Mara said "No way, dude."',
                baseline_samples=baseline,
                submitted_samples=[{"excerpt": "No way, dude."}],
                character_name="Mara",
            )


def test_voice_result_validation_rejects_same_words_at_unattributed_source_offset():
    passage = 'The sign read "Wait here." Mara said, "Wait here."'
    samples = attributed_voice_samples(
        passage, character_name="Mara", chapter_number=2, include_offsets=True
    )
    issue = {
        "character_name": "Mara",
        "classification": "possible",
        "severity": "moderate",
        "title": "Register shift",
        "description": "The wording differs from the established dialogue.",
        "submitted_excerpt": "Wait here.",
        "baseline_excerpt": "I shall remain at this location.",
        "baseline_chapter_number": 1,
        "confidence": 0.6,
        "revision_direction": "Check whether the shorter command is intentional.",
        "intentionality_prompt": "Was this change deliberate?",
    }
    raw = json.dumps({"issues": [issue], "overall_verdict": "A possible shift."})
    baseline = [{"chapter_number": 1, "excerpt": issue["baseline_excerpt"]}]
    later_start = passage.index("Mara said")

    with pytest.raises(VoiceReviewFormatError, match="voice_review_unsupported_evidence"):
        validate_voice_section_result(
            raw,
            section_text=passage[:later_start],
            baseline_samples=baseline,
            submitted_samples=samples,
            character_name="Mara",
        )
    with pytest.raises(VoiceReviewFormatError, match="voice_review_unsupported_evidence"):
        validate_voice_section_result(
            raw,
            section_text=passage,
            baseline_samples=baseline,
            submitted_samples=samples,
            character_name="Mara",
        )
    assert validate_voice_section_result(
        raw,
        section_text=passage[later_start:],
        section_start=later_start,
        baseline_samples=baseline,
        submitted_samples=samples,
        character_name="Mara",
    )["issues"] == [issue]


def test_voice_result_validation_accepts_exact_citations_across_same_source_sample_boundaries():
    submitted_source = 'Mara said "' + " ".join(f"urgent{i:03d}" for i in range(180)) + '"'
    baseline_source = 'Mara said "' + " ".join(f"formal{i:03d}" for i in range(180)) + '"'
    submitted = attributed_voice_samples(
        submitted_source, character_name="Mara", chapter_number=2, include_offsets=True
    )
    baseline = attributed_voice_samples(
        baseline_source, character_name="Mara", chapter_number=1, include_offsets=True
    )
    assert len(submitted) > 1 and len(baseline) > 1
    submitted_excerpt = submitted_source[
        submitted[1]["source_start"] - 10 : submitted[0]["source_end"] + 10
    ]
    baseline_excerpt = baseline_source[
        baseline[1]["source_start"] - 10 : baseline[0]["source_end"] + 10
    ]
    assert all(submitted_excerpt not in item["excerpt"] for item in submitted)
    assert all(baseline_excerpt not in item["excerpt"] for item in baseline)
    issue = {
        "character_name": "Mara",
        "classification": "confirmed",
        "severity": "moderate",
        "title": "Changed register",
        "description": "The current wording differs from the earlier speech.",
        "submitted_excerpt": submitted_excerpt,
        "baseline_excerpt": baseline_excerpt,
        "baseline_chapter_number": 1,
        "confidence": 0.9,
        "revision_direction": "Retain the intent while considering the earlier register.",
        "intentionality_prompt": "Is the change intentional?",
    }
    raw = json.dumps({"issues": [issue], "overall_verdict": "A supported shift."})

    assert validate_voice_section_result(
        raw,
        section_text=submitted_source,
        baseline_samples=baseline,
        submitted_samples=submitted,
        character_name="Mara",
    )["issues"] == [issue]

    with pytest.raises(VoiceReviewFormatError, match="voice_review_unsupported_evidence"):
        validate_voice_section_result(
            raw,
            section_text=submitted_source,
            baseline_samples=[
                baseline[0],
                {**baseline[1], "source_id": "another-quote"},
            ],
            submitted_samples=submitted,
            character_name="Mara",
        )
    with pytest.raises(VoiceReviewFormatError, match="voice_review_unsupported_evidence"):
        validate_voice_section_result(
            raw,
            section_text=submitted_source,
            baseline_samples=baseline,
            submitted_samples=[
                submitted[0],
                {**submitted[1], "source_id": "another-quote"},
            ],
            character_name="Mara",
        )


def test_voice_result_validation_downgrades_mixed_attribution_across_sample_boundary():
    passage = 'Mara said "A voice with mixed attribution."'
    start = passage.index("A voice")
    submitted = [
        {
            "excerpt": "A voice with ",
            "source_start": start,
            "source_end": start + len("A voice with "),
            "source_id": "one-quote",
            "attribution_confidence": "contextual",
        },
        {
            "excerpt": "mixed attribution.",
            "source_start": start + len("A voice with "),
            "source_end": start + len("A voice with mixed attribution."),
            "source_id": "one-quote",
        },
    ]
    issue = {
        "character_name": "Mara",
        "classification": "confirmed",
        "severity": "moderate",
        "title": "Changed voice",
        "description": "The voice differs from the baseline.",
        "submitted_excerpt": "with mixed",
        "baseline_excerpt": "I shall remain here.",
        "baseline_chapter_number": 1,
        "confidence": 0.95,
        "revision_direction": "Check the intended register.",
        "intentionality_prompt": "Is this variation deliberate?",
    }
    raw = json.dumps({"issues": [issue], "overall_verdict": "A possible shift."})

    result = validate_voice_section_result(
        raw,
        section_text=passage,
        baseline_samples=[{"chapter_number": 1, "excerpt": issue["baseline_excerpt"]}],
        submitted_samples=submitted,
        character_name="Mara",
    )
    assert result["issues"][0]["classification"] == "possible"
    assert result["issues"][0]["confidence"] == 0.75


def test_voice_result_validation_downgrades_contextually_attributed_speaker_claim():
    issue = {
        "character_name": "Mara",
        "classification": "confirmed",
        "severity": "moderate",
        "title": "Unexpected slang",
        "description": "The phrase differs from the earlier formal speech.",
        "submitted_excerpt": "No way, dude.",
        "baseline_excerpt": "I shall be there at six.",
        "baseline_chapter_number": 1,
        "confidence": 0.94,
        "revision_direction": "Keep the urgency while reviewing the register.",
        "intentionality_prompt": "Is this shift intentional?",
    }
    result = validate_voice_section_result(
        json.dumps({"issues": [issue], "overall_verdict": "A shift."}),
        section_text='Mara closed the window. She said, "No way, dude."',
        baseline_samples=[{"chapter_number": 1, "excerpt": "I shall be there at six."}],
        submitted_samples=[{"excerpt": "No way, dude.", "attribution_confidence": "contextual"}],
        character_name="Mara",
    )

    assert result["issues"][0]["classification"] == "possible"
    assert result["issues"][0]["confidence"] == 0.75

    contextual_baseline = validate_voice_section_result(
        json.dumps({"issues": [issue], "overall_verdict": "A shift."}),
        section_text='Mara said, "No way, dude."',
        baseline_samples=[
            {
                "chapter_number": 1,
                "excerpt": "I shall be there at six.",
                "attribution_confidence": "contextual",
            }
        ],
        submitted_samples=[{"excerpt": "No way, dude."}],
        character_name="Mara",
    )
    assert contextual_baseline["issues"][0]["classification"] == "possible"
    assert contextual_baseline["issues"][0]["confidence"] == 0.75

    unverified_narrator_baseline = validate_voice_section_result(
        json.dumps({"issues": [issue], "overall_verdict": "A shift."}),
        section_text='Mara said, "No way, dude."',
        baseline_samples=[
            {
                "chapter_number": 1,
                "excerpt": "I shall be there at six.",
                "attribution_confidence": "unverified_narrator",
            }
        ],
        submitted_samples=[{"excerpt": "No way, dude."}],
        character_name="Mara",
    )
    assert unverified_narrator_baseline["issues"][0]["classification"] == "possible"


def test_voice_result_validation_rejects_malformed_empty_success():
    for raw in (
        "not json",
        "{}",
        '{"issues": []}',
        '{"issues": "none", "overall_verdict": "Fine"}',
    ):
        with pytest.raises(VoiceReviewFormatError):
            validate_voice_section_result(
                raw,
                section_text="hello",
                baseline_samples=[],
                submitted_samples=[],
                character_name="Mara",
            )
