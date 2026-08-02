from app.engine.analysis.summariser import (
    _analysis_passages,
    _merge_detailed_summary_payloads,
    _normalize_summary_payload,
)


def test_analysis_passages_cover_long_chapter_without_truncation():
    paragraphs = [f"Paragraph {index} " + ("word " * 80) for index in range(40)]
    chapter = "\n\n".join(paragraphs)

    passages = _analysis_passages(chapter, max_chars=1200)

    assert len(passages) > 1
    rebuilt = "\n\n".join(passages)
    assert "Paragraph 0" in rebuilt
    assert "Paragraph 39" in rebuilt
    assert all(len(passage) <= 1200 for passage in passages)


def test_map_reduce_summary_preserves_unique_evidence_from_every_part():
    merged = _merge_detailed_summary_payloads(
        [
            {
                "content": "Mira finds the key.",
                "key_events": [{"event_title": "Discovery", "description": "Key found"}],
                "char_changes": [],
                "clues": [{"clue": "Silver dust", "why_it_matters": "Marks the lock"}],
                "themes": [],
            },
            {
                "content": "Mira opens the gate.",
                "key_events": [{"event_title": "Gate", "description": "Gate opened"}],
                "char_changes": [],
                "clues": [{"clue": "Silver dust", "why_it_matters": "Marks the lock"}],
                "themes": [],
            },
        ]
    )

    assert merged["content"] == "Mira finds the key.\n\nMira opens the gate."
    assert len(merged["key_events"]) == 2
    assert len(merged["clues"]) == 1


def test_detailed_summary_preserves_cited_structured_continuity_facts():
    payload = _normalize_summary_payload(
        {
            "summary": "Mira crosses the gate.",
            "key_events": [
                {
                    "event_title": "Crossing",
                    "description": "Mira crosses the gate.",
                    "continuity_facts": [
                        {
                            "subject": "Mira",
                            "subject_type": "character",
                            "predicate": "knowledge.used",
                            "value": "the gate needs royal blood",
                            "fact_key": "royal blood opens gate",
                            "evidence": "Mira cuts her royal palm against the lock.",
                        },
                        {
                            "subject": "Mira",
                            "predicate": "knowledge.used",
                            "value": "missing evidence",
                        },
                    ],
                }
            ],
        },
        fallback="",
    )

    facts = payload["key_events"][0]["continuity_facts"]
    assert len(facts) == 1
    assert facts[0]["predicate"] == "knowledge.used"
    assert facts[0]["fact_key"] == "royal blood opens gate"
