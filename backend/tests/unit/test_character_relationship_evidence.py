from app.utils.characters.relationship_evidence import grounded_relationship_evidence


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
