"""Source-backed single names can survive without the optional spaCy model."""

from copy import deepcopy

from app.engine.character import entity_filters, extractor
from app.services.extraction_character_decision_service import (
    _can_auto_save_character,
    _entity_dossier_summary,
)


def _local_candidate(source: str, name: str) -> dict:
    strict_hints, _review_hints = extractor.collect_character_discovery_hints(source)
    candidates = extractor._clean_character_entries(
        [{"name": name, "entity_type": "person", "is_character": True, "confidence": 0.95}],
        strict_hints,
        source,
    )
    assert len(candidates) == 1
    entity = candidates[0]
    local = extractor._local_mention_verifier(source, entity["name"])
    entity["evidence"]["verifier"] = {
        "local": local,
        "llm": {"used": False},
        "final": {
            "confidence_band": local["confidence_band"],
            "is_person_like": local["is_person_like"],
            "reasons": local["reasons"],
        },
    }
    return entity


def test_repeated_attributed_single_name_can_auto_save_without_optional_ner(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = (
        'Nyra said, "Wait by the bridge." '
        "I followed Nyra toward the square. "
        'Nyra replied, "I will return."'
    )

    entity = _local_candidate(source, "Nyra")

    assert entity["evidence"]["has_attributed_speech"] is True
    assert entity["evidence"]["verifier"]["final"]["confidence_band"] == "accept"
    assert _entity_dossier_summary(entity)["explicit_speech_single_name_eligible"] is True
    assert _can_auto_save_character(entity) is True


def test_repeated_action_only_single_name_still_needs_review_without_ner(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = "Nyra crossed the bridge. I followed Nyra. Nyra opened the gate."

    entity = _local_candidate(source, "Nyra")

    assert entity["evidence"]["has_attributed_speech"] is False
    summary = _entity_dossier_summary(entity)
    assert summary["explicit_speech_single_name_eligible"] is False
    assert "single_token_ambiguous" in summary["strict_auto_reason_codes"]
    assert "insufficient_cross_chapter_support" not in summary["strict_auto_reason_codes"]
    assert _can_auto_save_character(entity) is False


def test_repeated_place_name_with_person_like_actions_stays_in_review_without_ner(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = "Paris crossed the bridge. I followed Paris. Paris opened the gate."

    entity = _local_candidate(source, "Paris")

    assert entity["evidence"]["verifier"]["final"]["confidence_band"] == "accept"
    assert _can_auto_save_character(entity) is False


def test_repeated_human_self_action_can_auto_save_without_optional_ner(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = "Mara crossed the bridge. I followed Mara. Mara raised her hand."

    entity = _local_candidate(source, "Mara")

    assert entity["evidence"]["has_human_self_action"] is True
    assert _entity_dossier_summary(entity)["human_self_action_single_name_eligible"] is True
    assert _can_auto_save_character(entity) is True

    fallback = deepcopy(entity)
    fallback["evidence"]["deterministic_fallback"] = True
    conflict = deepcopy(entity)
    conflict["evidence"]["anti_merge_names"] = ["Mara Vale"]
    assert _can_auto_save_character(fallback) is False
    assert _can_auto_save_character(conflict) is False


def test_shared_surname_fragment_cannot_auto_save_as_an_extra_person(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = (
        "Madame Quill waited at home. Monsieur Quill called from the station. "
        "I followed Quill to the gate. Quill answered the porter. "
        "Quill texted me before dawn."
    )

    entity = _local_candidate(source, "Quill")

    assert entity["evidence"]["ambiguous_full_name_fragment"] is True
    assert (
        "ambiguous_full_name_fragment"
        in _entity_dossier_summary(entity)["strict_auto_reason_codes"]
    )
    assert _can_auto_save_character(entity) is False


def test_discourse_prefix_does_not_block_repeated_named_speaker(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = 'So Raymond said, "Wait." I followed Raymond. Raymond replied, "Go."'

    entity = _local_candidate(source, "Raymond")

    assert entity["evidence"]["ambiguous_full_name_fragment"] is False
    assert _can_auto_save_character(entity) is True


def test_shared_name_fragments_are_collected_across_separate_source_batches():
    fragments = extractor.ambiguous_full_name_fragments(
        [
            "Madame Quill checked the ledger. John Reed waited.",
            "So Raymond arrived. Presently Marie called.",
            "Monsieur Quill called. John Stone answered.",
        ]
    )

    assert {"quill", "john"} <= fragments
    assert "raymond" not in fragments
    assert "marie" not in fragments


def test_shared_surname_fragment_uses_earlier_roster_name_as_context():
    fragments = extractor.ambiguous_full_name_fragments(
        ["Monsieur Quill arrived at the gate.", "Madame Quill"]
    )

    assert "quill" in fragments


def test_repeated_named_communication_can_auto_save_without_optional_ner(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = (
        "Paz warned Sera that the gate was sealed. "
        "Sera listened to Paz. Paz answered the engineer. "
        "Paz texted Sera at dawn. Sera thanked Paz."
    )

    entity = _local_candidate(source, "Paz")

    assert entity["evidence"]["has_direct_communication"] is True
    assert entity["evidence"]["has_attributed_speech"] is False
    assert _entity_dossier_summary(entity)["direct_communication_single_name_eligible"] is True
    assert _can_auto_save_character(entity) is True

    fallback = deepcopy(entity)
    fallback["evidence"]["deterministic_fallback"] = True
    conflict = deepcopy(entity)
    conflict["evidence"]["anti_merge_names"] = ["Paz Nix"]
    assert _can_auto_save_character(fallback) is False
    assert _can_auto_save_character(conflict) is False


def test_single_name_speech_never_overrides_fallback_or_conflicting_identity(monkeypatch):
    monkeypatch.setattr(extractor, "contextual_ner_entity_label", lambda *_args: None)
    monkeypatch.setattr(entity_filters, "ner_entity_score", lambda _name: 0)
    source = 'Nyra said, "Wait." I followed Nyra. Nyra replied, "Go."'
    entity = _local_candidate(source, "Nyra")

    fallback = deepcopy(entity)
    fallback["evidence"]["deterministic_fallback"] = True
    conflict = deepcopy(entity)
    conflict["evidence"]["anti_merge_names"] = ["Nyra Vale"]

    assert _can_auto_save_character(fallback) is False
    assert _can_auto_save_character(conflict) is False
