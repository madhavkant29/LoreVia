import pytest

from app.utils.characters.profile_evidence import (
    bundle_profile_evidence_packets,
    character_mention_weight,
    ground_character_profile_claims,
    map_profile_citations_to_source,
    merge_grounded_profile_claims,
    merge_profile_claim_records,
    profile_claim_records,
    profile_claims_complete,
    profile_evidence_packets,
    shift_profile_citations,
    source_quote_span,
)


def test_character_mention_weight_uses_verified_occurrences_not_cluster_rows():
    assert (
        character_mention_weight(
            {
                "cluster_size": 4,
                "evidence": {
                    "source_mention_count_verified": True,
                    "mention_count": 2,
                    "cluster_size": 4,
                },
            }
        )
        == 2
    )


def test_character_mention_weight_handles_missing_and_malformed_evidence():
    assert character_mention_weight({"cluster_size": 3}) == 3
    assert character_mention_weight({"cluster_size": 2, "evidence": {"mention_count": 9}}) == 2
    assert (
        character_mention_weight(
            {"evidence": {"source_mention_count_verified": True, "mention_count": 0}}
        )
        == 0
    )
    assert (
        character_mention_weight({"cluster_size": "invalid", "evidence": {"cluster_size": True}})
        == 1
    )


def test_source_quote_span_matches_exact_words_across_pdf_line_breaks():
    source = "Mara said she would\nprotect the child."
    span = source_quote_span(source, "she would protect the child")

    assert span is not None
    assert source[span[0] : span[1]] == "she would\nprotect the child"


def test_source_quote_span_rejects_short_fabricated_and_empty_quotes():
    source = "Mara promised to protect the child."

    assert source_quote_span(source, "Mara") is None
    assert source_quote_span(source, "Mara secretly feared the sea") is None
    assert source_quote_span("", "Mara promised") is None


def test_ground_character_profile_claims_keeps_only_cited_values():
    source = (
        "Mara promised to protect the child. "
        "Mara feared losing the child. Her black hair was wet from the rain."
    )
    raw = {
        "goal": "protect the child",
        "fears": ["losing the child", "the sea"],
        "motivations": ["duty"],
        "personality_tags": ["devoted"],
        "arc_summary": "Mara has changed her mind.",
        "traits": {
            "hair": {"value": "black", "confidence": 0.9, "type": "objective"},
            "eyes": {"value": "green", "confidence": 0.9, "type": "objective"},
        },
        "growth_event": {"event": "Mara changes her mind"},
        "claim_evidence": {
            "goal": "Mara promised to protect the child.",
            "fears": {"losing the child": "Mara feared losing the child."},
            "motivations": {"duty": "Mara was on duty"},
            "personality_tags": {"devoted": "Mara promised to protect the child."},
            "arc_summary": "Mara has changed her mind.",
            "traits": {
                "hair": "Her black hair was wet from the rain.",
                "eyes": "Her green eyes flashed.",
            },
        },
    }

    grounded, verified = ground_character_profile_claims(raw, source)

    assert grounded["goal"] == "protect the child"
    assert grounded["fears"] == ["losing the child"]
    assert grounded["motivations"] == []
    assert grounded["personality_tags"] == ["devoted"]
    assert grounded["arc_summary"] is None
    assert grounded["growth_event"] is None
    assert grounded["traits"] == {
        "hair": {"value": "black", "confidence": 0.9, "type": "objective"}
    }
    assert verified["goal"]["quote"] == "Mara promised to protect the child."
    assert verified["traits"]["hair"]["quote"] == "Her black hair was wet from the rain."
    assert "eyes" not in verified["traits"]


def test_ground_character_profile_claims_missing_citations_leave_unknown_profile():
    grounded, verified = ground_character_profile_claims(
        {
            "goal": "become king",
            "fears": ["water"],
            "traits": {"hair": {"value": "red"}},
            "growth_event": {"event": "a victory"},
        },
        "He crossed the bridge.",
    )

    assert grounded["goal"] is None
    assert grounded["fears"] == []
    assert grounded["traits"] == {}
    assert grounded["growth_event"] is None
    assert verified == {}


def test_merge_grounded_profile_claims_accumulates_verified_claims_and_batch_sources():
    first = {
        "goal": "find the gate",
        "motivations": ["protect her sister"],
        "traits": {"hair": {"value": "black", "confidence": 0.8}},
        "_source_batch_key": "book:1:1",
        "evidence": {
            "profile_claims": {
                "goal": {"quote": "Mara searched for the gate."},
                "motivations": {"protect her sister": {"quote": "Mara shielded her sister."}},
                "traits": {"hair": {"quote": "Mara had black hair."}},
            }
        },
    }
    later = {
        "goal": "cross the bridge",
        "fears": ["the dark"],
        "traits": {"hair": {"value": "brown", "confidence": 0.95}},
        "_source_batch_key": "book:1:2",
        "evidence": {
            "profile_claims": {
                "goal": {"quote": "Mara crossed the bridge."},
                "fears": {"the dark": {"quote": "Mara feared the dark."}},
                "traits": {"hair": {"quote": "Mara had brown hair."}},
            }
        },
    }

    merged, citations = merge_grounded_profile_claims(
        [first, later], {"hair": {"value": "brown", "confidence": 0.95}}
    )

    assert merged["goal"] == "find the gate"
    assert merged["motivations"] == ["protect her sister"]
    assert merged["fears"] == ["the dark"]
    assert merged["traits"]["hair"]["value"] == "brown"
    assert citations["goal"]["source_batch_key"] == "book:1:1"
    assert citations["fears"]["the dark"]["source_batch_key"] == "book:1:2"
    assert citations["traits"]["hair"]["source_batch_key"] == "book:1:2"


def test_profile_claim_records_preserve_exact_quotes_and_chapter_provenance():
    extracted = {
        "goal": "find the gate",
        "fears": ["the dark"],
        "traits": {"hair": {"value": "black"}},
        "evidence": {
            "profile_claims": {
                "goal": {"quote": "Mara sought the gate.", "source_batch_key": "book:2:1"},
                "fears": {"the dark": {"quote": "Mara feared the dark."}},
                "traits": {"hair": {"quote": "Her black hair shone."}},
            }
        },
    }

    records = profile_claim_records(extracted, chapter_number=2)

    assert {(record["field"], record["value"]) for record in records} == {
        ("goal", "find the gate"),
        ("fears", "the dark"),
        ("trait:hair", "black"),
    }
    assert all(record["chapter_number"] == 2 for record in records)
    assert records[0]["source_batch_key"] == "book:2:1"


def test_merge_profile_claim_records_deduplicates_and_limits_history():
    first = {"field": "goal", "value": "leave", "quote": "She left the hall."}
    second = {"field": "goal", "value": "return", "quote": "She returned home."}

    assert merge_profile_claim_records([first], [first, second]) == [first, second]
    assert merge_profile_claim_records([first], [second], limit=1) == [second]
    assert merge_profile_claim_records(None, None) == []


def test_profile_evidence_packets_keep_distinct_passages_and_source_offsets():
    entity = {
        "cluster_members": [
            {"source_batch_key": "book:2:1", "source_start": 100, "source_text": "Mara spoke."},
            {"source_batch_key": "book:2:1", "source_start": 100, "source_text": "Mara spoke."},
            {"source_batch_key": "book:2:2", "source_start": 0, "source_text": "Mara left."},
            {"source_batch_key": "book:2:3", "source_text": ""},
        ]
    }

    assert profile_evidence_packets(entity) == [
        {"source_batch_key": "book:2:1", "source_start": 100, "text": "Mara spoke."},
        {"source_batch_key": "book:2:2", "source_start": 0, "text": "Mara left."},
    ]
    assert profile_evidence_packets({"cluster_members": None}) == []
    assert (
        profile_evidence_packets(
            {"cluster_members": [{"source_windows": [], "source_text": "Unrelated opening."}]}
        )
        == []
    )


def test_profile_evidence_packets_use_every_distinct_mention_window():
    entity = {
        "cluster_members": [
            {
                "source_batch_key": "book:2:1",
                "source_start": 0,
                "source_text": "Mara arrived.",
                "source_windows": [
                    {"start": 0, "text": "Mara arrived."},
                    {"start": 3000, "text": "Mara feared the storm."},
                ],
            }
        ]
    }

    assert profile_evidence_packets(entity) == [
        {"source_batch_key": "book:2:1", "source_start": 0, "text": "Mara arrived."},
        {"source_batch_key": "book:2:1", "source_start": 3000, "text": "Mara feared the storm."},
    ]


def test_bundled_profile_evidence_preserves_offsets_and_rejects_header_citations():
    windows = [
        {"source_batch_key": "book:2:1", "source_start": 0, "text": "Mara arrived."},
        {
            "source_batch_key": "book:2:1",
            "source_start": 3000,
            "text": "Mara feared the storm.",
        },
    ]
    bundles = bundle_profile_evidence_packets(windows)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert all(window["text"] in bundle["text"] for window in windows)
    quote_start = bundle["text"].index("Mara feared the storm.")
    mapped = map_profile_citations_to_source(
        {
            "fear": {
                "quote": "Mara feared the storm.",
                "start": quote_start,
                "end": quote_start + 22,
            }
        },
        bundle["segments"],
    )
    assert mapped["fear"]["start"] == 3000
    assert mapped["fear"]["source_batch_key"] == "book:2:1"
    with pytest.raises(ValueError, match="outside_source_passage"):
        map_profile_citations_to_source({"fake": {"start": 0, "end": 10}}, bundle["segments"])
    assert len(bundle_profile_evidence_packets(windows, max_chars=50)) == 2
    with pytest.raises(ValueError, match="exceeds_packet_size"):
        bundle_profile_evidence_packets(windows, max_chars=10)
    with pytest.raises(ValueError, match="invalid_profile_packet_size"):
        bundle_profile_evidence_packets(windows, max_chars=0)


def test_profile_claim_completion_rejects_uncited_claims_and_malformed_fields():
    source = "Mara promised to protect the gate."
    raw = {
        "goal": "protect the gate",
        "claim_evidence": {"goal": "Mara promised to protect the gate."},
    }
    grounded, citations = ground_character_profile_claims(raw, source)

    assert profile_claims_complete(raw, grounded)
    assert not profile_claims_complete({**raw, "fears": ["the sea"]}, grounded)
    assert not profile_claims_complete({**raw, "goal": ["protect the gate"]}, grounded)
    assert not profile_claims_complete({"fears": [], "claim_evidence": []}, {"fears": []})
    assert not profile_claims_complete(
        {"fears": [{"name": "the sea"}], "claim_evidence": {}}, {"fears": []}
    )
    assert not profile_claims_complete(
        {"traits": {"hair": {"value": 42}}, "claim_evidence": {}}, {"traits": {}}
    )
    assert not profile_claims_complete(
        {"growth_event": {"event": {"name": "escaped"}}, "claim_evidence": {}},
        {"growth_event": None},
    )
    assert not profile_claims_complete(
        {"growth_event": {"impact": "became wary"}, "claim_evidence": {}},
        {"growth_event": None},
    )
    shifted = shift_profile_citations(citations, 75)
    assert shifted["goal"]["start"] == 75
    assert shifted["goal"]["end"] == 75 + len(source)
