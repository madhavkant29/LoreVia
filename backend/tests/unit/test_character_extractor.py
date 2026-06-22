import pytest

from app.engine.character.extractor import (
    _allow_auto_augmentation,
    _apply_anti_merge_hints,
    _candidate_names,
    _clean_character_entries,
    _local_mention_verifier,
    _mention_has_person_context,
    fallback_character_mentions,
    verify_character_candidate_personhood,
)


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
                "distinguishing": {"value": "sharp gaze", "confidence": 0.88, "type": "objective"}
            },
            "arc_summary": "sharp observer",
        }
    ]

    cleaned = _clean_character_entries(characters, ["Meeting Kunagisa"], source_text)

    assert len(cleaned) == 1
    assert cleaned[0]["name"] == "Kunagisa"


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
    ["Actually", "Maybe", "Sure", "Wait", "Okay", "However", "Though", "Please", "Thanks"],
)
def test_local_mention_verifier_routes_discourse_markers_to_reject_or_review(noise_name: str):
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
        "app.engine.character.extractor.contextual_ner_entity_label", _fake_contextual_ner
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
        "app.engine.character.extractor._verify_review_candidates_with_llm", _fake_verify
    )

    recovered = await fallback_character_mentions("Mother paused in the doorway.")

    assert [item["name"] for item in recovered["characters"]] == ["Mother"]
    verifier = recovered["characters"][0]["evidence"]["verifier"]
    assert verifier["final"]["confidence_band"] == "accept"
    assert verifier["llm"]["is_person_like"] is True


@pytest.mark.asyncio
async def test_fallback_character_mentions_rejects_review_candidate_when_llm_rejects(monkeypatch):
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
        "app.engine.character.extractor._verify_review_candidates_with_llm", _fake_verify
    )

    recovered = await fallback_character_mentions("Mother paused in the doorway.")

    assert recovered["characters"] == []
    assert recovered["rejected_characters"]
    assert recovered["rejected_characters"][0]["stage"] == "mention_verifier"


@pytest.mark.asyncio
async def test_fallback_character_mentions_drops_unconfirmed_review_candidate(monkeypatch):
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
        "app.engine.character.extractor._verify_review_candidates_with_llm", _fake_verify
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
        "app.engine.character.extractor._verify_review_candidates_with_llm", _fake_verify
    )

    result = await verify_character_candidate_personhood("Mother paused in the doorway.", "Mother")

    assert result["final"]["confidence_band"] == "accept"
    assert result["llm"]["is_person_like"] is True
