import uuid
from types import SimpleNamespace

from app.models.character import CharacterState
from app.services.continuity.observation_service import (
    ChapterEvidence,
    _evidence_for_value,
    _state_observed_trait_keys,
    normalize_observation_value,
    trait_value_and_confidence,
)


def test_observation_value_normalization_ignores_case_and_whitespace():
    assert normalize_observation_value("  Bright   BLUE ") == "bright blue"


def test_exact_evidence_excerpt_uses_the_actual_flexible_whitespace_match():
    chunk_id = uuid.uuid4()
    chapter = ChapterEvidence(
        id=uuid.uuid4(),
        number=3,
        content_version=2,
        word_count=20,
        processed=True,
        chunks=(
            SimpleNamespace(
                id=chunk_id,
                text=(
                    "Opening context that must not be mistaken for the citation. "
                    "Much later, the Silver\n\nGate opened under Nora's hand."
                ),
            ),
        ),
    )

    excerpt, source_chunk_id, quality = _evidence_for_value(
        chapter,
        value="silver gate",
        fallback="fallback",
    )

    assert quality == "exact"
    assert source_chunk_id == chunk_id
    assert "Silver Gate opened" in excerpt


def test_trait_value_preserves_equal_confidence_contradiction_value():
    value, confidence = trait_value_and_confidence({"value": "green", "confidence": 0.8})

    assert value == "green"
    assert confidence == 0.8


def test_empty_trait_value_is_not_recorded():
    assert trait_value_and_confidence({"value": "  ", "confidence": 1}) == (None, 0.0)


def test_state_observation_uses_explicit_trait_keys_instead_of_carry_forward():
    state = CharacterState(
        character_id=None,
        at_chapter=4,
        trait_snapshot={
            "eyes": {"value": "green"},
            "hair": {"value": "black"},
        },
        observed_trait_keys=["eyes"],
    )

    assert _state_observed_trait_keys(state) == {"eyes"}
