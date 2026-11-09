from pathlib import Path

from app.engine.character import entity_filters, extractor
from app.engine.character.extractor import collect_character_discovery_hints
from app.evaluation import character_hints
from app.evaluation.character_hints import (
    evaluate_character_name_hints,
    evaluate_gold_candidate_auto_promotion,
    evaluate_gold_character_candidate_survival,
    evaluate_unlabeled_hint_auto_promotion,
)
from app.evaluation.story_intelligence import load_evaluation_cases

CORPUS = Path(__file__).parents[2] / "evals" / "story_intelligence" / "v1" / "cases.json"


def test_name_hint_evaluation_counts_named_people_but_not_unnamed_narrators():
    cases = [
        {
            "id": "named",
            "text": 'Mira said, "Wait." Later, Mira spoke to Rowan.',
            "labels": {
                "characters": [
                    {"canonical_name": "Mira", "mentions": ["Mira"]},
                    {"canonical_name": "Rowan", "mentions": ["Rowan"]},
                ]
            },
        },
        {
            "id": "unnamed",
            "text": "I left the room before dawn.",
            "labels": {"characters": [{"canonical_name": "Narrator", "mentions": ["I"]}]},
        },
    ]

    result = evaluate_character_name_hints(cases)

    assert result["scope"] == "deterministic_name_hints_only"
    assert result["scored_character_count"] == 2
    assert result["unscored_character_count"] == 1
    assert result["hinted_character_count"] >= 1
    assert result["named_hint_coverage"] is not None


def test_gold_candidate_cleaner_evaluation_tracks_unnamed_roles_and_unscored_pronouns():
    cases = [
        {
            "id": "porter",
            "text": "The porter opened the gate. I thanked the porter. The porter smiled.",
            "labels": {
                "characters": [
                    {"canonical_name": "the porter", "mentions": ["the porter"]},
                    {"canonical_name": "Narrator", "mentions": ["I"]},
                ]
            },
        }
    ]

    result = evaluate_gold_character_candidate_survival(cases)

    assert result["scope"] == "gold_candidate_deterministic_cleaner_only"
    assert result["scored_character_count"] == 1
    assert result["survived_character_count"] == 1
    assert result["unscored_character_count"] == 1
    assert result["conditional_survival_rate"] == 1.0


def test_gold_candidate_promotion_evaluation_separates_speech_from_action_without_ner(
    monkeypatch,
):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    result = evaluate_gold_candidate_auto_promotion(
        [
            {
                "id": "spoken",
                "text": 'Nyra said, "Wait." I followed Nyra. Nyra replied, "Go."',
                "labels": {"characters": [{"canonical_name": "Nyra", "mentions": ["Nyra"]}]},
            },
            {
                "id": "action_only",
                "text": "Mara crossed the bridge. I followed Mara. Mara opened the gate.",
                "labels": {"characters": [{"canonical_name": "Mara", "mentions": ["Mara"]}]},
            },
        ]
    )

    assert result["scope"] == "gold_candidate_local_verifier_and_save_gate_no_ai"
    assert result["scored_character_count"] == 2
    assert result["cleaner_survived_count"] == 2
    assert result["auto_save_eligible_count"] == 1
    assert result["auto_save_eligibility_rate"] == 0.5


def test_gold_candidate_promotion_evaluation_handles_empty_corpus():
    result = evaluate_gold_candidate_auto_promotion([])

    assert result["scored_character_count"] == 0
    assert result["auto_save_eligibility_rate"] is None


def test_unlabeled_hint_evaluation_exposes_false_save_risk_without_ai(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    cases = [
        {
            "id": "place_hint",
            "text": "Paris opened the gate. I followed Paris. Paris closed the door.",
            "labels": {"characters": []},
        },
        {
            "id": "named_person",
            "text": "Mara crossed the bridge. I followed Mara. Mara raised her hand.",
            "labels": {"characters": [{"canonical_name": "Mara", "mentions": ["Mara"]}]},
        },
    ]

    result = evaluate_unlabeled_hint_auto_promotion(cases)

    assert result["scope"] == "unlabeled_hint_local_verifier_and_save_gate_no_ai"
    assert result["auto_save_eligible_count"] == 0
    assert result["auto_save_eligible_hints"] == []


def test_corpus_single_name_speech_case_is_promoted_but_action_case_is_held_without_ner(
    monkeypatch,
):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    cases = {
        case["id"]: case
        for case in load_evaluation_cases(CORPUS)
        if case["id"]
        in {
            "contemporary_repeated_single_name_attributed_speech",
            "contemporary_single_name_action_without_speech",
        }
    }

    speech = evaluate_gold_candidate_auto_promotion(
        [cases["contemporary_repeated_single_name_attributed_speech"]]
    )
    action = evaluate_gold_candidate_auto_promotion(
        [cases["contemporary_single_name_action_without_speech"]]
    )

    assert speech["auto_save_eligible_count"] == 1
    assert action["auto_save_eligible_count"] == 0


def test_corpus_explicit_human_self_action_can_promote_named_person_without_ner(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    case = next(
        case
        for case in load_evaluation_cases(CORPUS)
        if case["id"] == "contemporary_single_name_explicit_human_self_action"
    )

    result = evaluate_gold_candidate_auto_promotion([case])

    assert result["auto_save_eligible_count"] >= 1


def test_gold_candidate_cleaner_evaluation_reports_rejected_gold_person(monkeypatch):
    def reject_gold(_candidates, _hints, _source, *, rejected_characters):
        rejected_characters.append({"reason": "fails_character_name_shape"})
        return []

    monkeypatch.setattr(character_hints, "_clean_character_entries", reject_gold)
    result = evaluate_gold_character_candidate_survival(
        [
            {
                "id": "named_person",
                "text": "Mara spoke to the guard.",
                "labels": {"characters": [{"canonical_name": "Mara", "mentions": ["Mara"]}]},
            }
        ]
    )

    assert result["scored_character_count"] == 1
    assert result["survived_character_count"] == 0
    assert result["misses"] == [
        {
            "case_id": "named_person",
            "character": "Mara",
            "source_name": "Mara",
            "rejection_reasons": ["fails_character_name_shape"],
        }
    ]


def test_gold_candidate_cleaner_preserves_two_people_with_a_shared_surname():
    result = evaluate_gold_character_candidate_survival(
        [
            {
                "id": "shared_surname",
                "text": "Madame Vale opened the door. Monsieur Vale waited outside.",
                "labels": {
                    "characters": [
                        {"canonical_name": "Madame Vale", "mentions": ["Madame Vale"]},
                        {"canonical_name": "Monsieur Vale", "mentions": ["Monsieur Vale"]},
                    ]
                },
            }
        ]
    )

    assert result["conditional_survival_rate"] == 1.0
    assert result["joint_identity_cases_scored"] == 1
    assert result["joint_identity_cases_preserved"] == 1
    assert result["joint_identity_risks"] == []


def test_gold_candidate_cleaner_reports_joint_identity_loss(monkeypatch):
    original_clean = character_hints._clean_character_entries

    def collapse_joint(candidates, hints, source, **kwargs):
        cleaned = original_clean(candidates, hints, source, **kwargs)
        return cleaned[:1] if len(candidates) > 1 else cleaned

    monkeypatch.setattr(character_hints, "_clean_character_entries", collapse_joint)
    result = evaluate_gold_character_candidate_survival(
        [
            {
                "id": "collapsed",
                "text": "Madame Vale opened the door. Monsieur Vale waited outside.",
                "labels": {
                    "characters": [
                        {"canonical_name": "Madame Vale", "mentions": ["Madame Vale"]},
                        {"canonical_name": "Monsieur Vale", "mentions": ["Monsieur Vale"]},
                    ]
                },
            }
        ]
    )

    assert result["joint_identity_cases_preserved"] == 0
    assert result["joint_identity_risks"] == [
        {"case_id": "collapsed", "missing_or_collapsed": ["Monsieur Vale"]}
    ]


def test_name_hint_evaluation_handles_empty_and_malformed_mentions():
    assert evaluate_character_name_hints([])["named_hint_coverage"] is None
    result = evaluate_character_name_hints(
        [
            {
                "id": "missing",
                "text": "Lina crossed the square.",
                "labels": {
                    "characters": [
                        {"canonical_name": "Lina", "mentions": [None, "unknown", "Lina"]}
                    ]
                },
            }
        ]
    )
    assert result["scored_character_count"] == 1


def test_name_hint_evaluation_counts_a_person_after_the_first_twenty_four_hints(monkeypatch):
    monkeypatch.setattr(
        character_hints,
        "collect_character_discovery_hints",
        lambda _source: ([f"Decoy{index}" for index in range(24)] + ["Zora"], []),
    )
    result = evaluate_character_name_hints(
        [
            {
                "id": "late_hint",
                "text": "Zora crossed the square.",
                "labels": {"characters": [{"canonical_name": "Zora", "mentions": ["Zora"]}]},
            }
        ]
    )

    assert result["named_hint_coverage"] == 1.0
    assert result["misses"] == []


def test_name_hint_evaluation_reports_unlabeled_strict_hints_separately(monkeypatch):
    monkeypatch.setattr(
        character_hints,
        "collect_character_discovery_hints",
        lambda _source: (["Mira", "Window"], ["Rowan"]),
    )
    result = evaluate_character_name_hints(
        [
            {
                "id": "hint_precision",
                "text": "Mira greeted Rowan beside the Window.",
                "labels": {
                    "characters": [
                        {"canonical_name": "Mira", "mentions": ["Mira"]},
                        {"canonical_name": "Rowan", "mentions": ["Rowan"]},
                    ]
                },
            }
        ]
    )

    assert result["named_hint_coverage"] == 1.0
    assert result["strict_hint_count"] == 2
    assert result["labeled_strict_hint_count"] == 1
    assert result["strict_hint_label_match_rate"] == 0.5
    assert result["unlabeled_strict_hints"] == [{"case_id": "hint_precision", "hint": "Window"}]


def test_discovery_hints_include_single_occurrence_subjects_and_numbered_names():
    source = (
        "Nadia texted Dad before dinner. Sam broke his right wrist. "
        "Ren-2 descended while Ren Ko stayed in orbit."
    )

    strict_hints, review_hints = collect_character_discovery_hints(source)

    assert {"Nadia", "Sam", "Ren-2"}.issubset(set(strict_hints + review_hints))


def test_discovery_hints_do_not_promote_sentence_start_objects_from_breaking():
    strict_hints, review_hints = collect_character_discovery_hints("Door broke during the storm.")

    assert "Door" not in strict_hints + review_hints


def test_long_form_case_discovers_late_arriving_character():
    case = next(
        case
        for case in load_evaluation_cases(CORPUS)
        if case["id"] == "mystery_long_form_late_arrival_and_two_source_conflicts"
    )
    assert case["text"].index("Leda Voss") > 4000

    result = evaluate_character_name_hints([case])

    assert result["misses"] == []
    assert result["hinted_character_count"] == result["scored_character_count"]
    assert result["unlabeled_strict_hints"] == []


def test_narrator_dialogue_case_hints_all_distinct_shared_surname_people():
    case = next(
        case
        for case in load_evaluation_cases(CORPUS)
        if case["id"] == "contemporary_narrator_named_in_dialogue_with_shared_surname"
    )

    result = evaluate_character_name_hints([case])

    assert result["misses"] == []
    assert result["hinted_character_count"] == 3
    assert result["unscored_character_count"] == 1
