from app.utils.characters.relationship_evidence import (
    grounded_relationship_evidence,
    relationship_quote_anchors_participants,
)


def test_relationship_evidence_matches_quote_and_records_source_offsets():
    source = "Mara promised to\nprotect Ilya before dawn."
    evidence = grounded_relationship_evidence(
        {
            "character_a": "Mara",
            "character_b": "Ilya",
            "label_evidence": {
                "quote": "Mara promised to protect Ilya",
                "confidence": 0.88,
            },
        },
        source,
    )

    assert evidence is not None
    assert evidence["quote"] == "Mara promised to\nprotect Ilya"
    assert source[evidence["source_start"] : evidence["source_end"]] == evidence["quote"]
    assert evidence["confidence"] == 0.88


def test_relationship_evidence_rejects_missing_or_fabricated_quotes():
    source = "Mara and Ilya stood by the gate."

    assert (
        grounded_relationship_evidence({"label_evidence": {"quote": "They were siblings."}}, source)
        is None
    )
    assert grounded_relationship_evidence({"label_evidence": {}}, source) is None
    assert grounded_relationship_evidence({}, source) is None


def test_relationship_quote_requires_both_named_participants():
    assert relationship_quote_anchors_participants(
        "Mara promised to protect Ilya.", "Mara Vale", "Ilya Ren"
    )
    assert not relationship_quote_anchors_participants(
        "He was a friend of the family.", "Mara Vale", "Ilya Ren"
    )
    assert not relationship_quote_anchors_participants(
        "Mara was a friend of the family.", "Mara Vale", "Ilya Ren"
    )
    assert not relationship_quote_anchors_participants("", "Mara", "Ilya")
    assert not relationship_quote_anchors_participants("Mara and Ilya met.", "", "Ilya")
    assert relationship_quote_anchors_participants(
        "Monsieur Meursault spoke to Marie.", "Monsieur Meursault", "Marie Cardona"
    )
    assert not relationship_quote_anchors_participants(
        "Madame Meursault spoke to Marie.", "Monsieur Meursault", "Marie Cardona"
    )
    assert not relationship_quote_anchors_participants(
        "Mme Masson spoke alone.", "Masson", "Mme Masson"
    )
    assert not relationship_quote_anchors_participants(
        "Marie left early.", "Marie Cardona", "Marie Laurent"
    )
