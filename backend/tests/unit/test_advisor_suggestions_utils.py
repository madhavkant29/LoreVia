import re
import uuid
from types import SimpleNamespace

import pytest

from app.utils.advisor_suggestions_utils import (
    advisor_clue_evidence,
    advisor_scan_output_token_budget,
    build_advisor_chapter_evidence_blocks,
    build_advisor_item_evidence_blocks,
    build_open_thread_review_suggestions,
    build_relationship_drift_suggestions,
    build_world_drift_suggestions,
    partition_advisor_scan_evidence,
    proactive_advisor_finding_id,
)


def test_proactive_finding_id_stays_stable_across_group_and_wording_changes():
    finding = {
        "type": "event_conflict",
        "chapter_ref": 3,
        "evidence_excerpt": "The gate was locked before they arrived.",
        "title": "Check the gate timing",
    }

    identity = proactive_advisor_finding_id(finding)

    assert identity.startswith("proactive-")
    assert identity == proactive_advisor_finding_id(
        {
            **finding,
            "title": "Gate timing conflict",
            "evidence_excerpt": " the GATE was locked before they arrived. ",
        }
    )
    assert identity != proactive_advisor_finding_id({**finding, "chapter_ref": 4})
    assert identity != proactive_advisor_finding_id({**finding, "type": "future_direction"})
    assert identity != proactive_advisor_finding_id(
        {**finding, "evidence_excerpt": "The gate opened after they arrived."}
    )
    with pytest.raises(ValueError, match="advisor_finding_missing_evidence"):
        proactive_advisor_finding_id({**finding, "evidence_excerpt": " "})


def test_advisor_clue_evidence_keeps_structured_details_and_skips_empty_values():
    assert advisor_clue_evidence(
        [
            {
                "clue": "Brass key",
                "foreshadows": "A locked cellar",
                "why_it_matters": "The permit is hidden there",
            },
            "A blue ribbon",
            {"clue": "   "},
            {"why_it_matters": "An unsupported orphan rationale"},
            None,
        ]
    ) == ["Brass key | A locked cellar | The permit is hidden there", "A blue ribbon"]
    assert advisor_clue_evidence({"Brass key": "Points to the cellar"}) == [
        "Brass key | Points to the cellar"
    ]
    assert advisor_clue_evidence(None) == []


def test_advisor_chapter_evidence_blocks_cover_late_summary_and_every_key_event():
    content = "The gate was open. " + "The travelers waited in the courtyard. " * 55
    content += "At last the gate was sealed."
    event_titles = [f"Event {number} changed the route" for number in range(5)]

    blocks = build_advisor_chapter_evidence_blocks(
        chapter_number=8,
        chapter_title="The Gate",
        content=content,
        key_events=[{"event_title": title} for title in event_titles],
        max_chars=180,
        overlap=30,
    )

    prefix = "Chapter 8 (The Gate): "
    bodies = [block.removeprefix(prefix) for block in blocks]
    assert len(blocks) > 2
    assert all(block.startswith(prefix) and len(body) <= 180 for block, body in zip(blocks, bodies))
    assert bodies[0].startswith("The gate was open.")
    assert any("At last the gate was sealed." in body for body in bodies)
    assert all(any(title in body for body in bodies) for title in event_titles)
    assert all(left[-30:] == right[:30] for left, right in zip(bodies, bodies[1:]))


def test_advisor_chapter_evidence_blocks_include_event_detail_and_continuity_facts():
    blocks = build_advisor_chapter_evidence_blocks(
        chapter_number=9,
        chapter_title="The Ledger",
        content="The courier returned to the market.",
        key_events=[
            {
                "event_title": "The courier opens the ledger",
                "description": "The ledger records the missing key.",
                "impact": "The guard changes her route.",
                "involved_characters": ["Mara", "Lina"],
                "continuity_facts": [
                    {
                        "subject": "ledger",
                        "predicate": "object.location",
                        "value": "market",
                        "evidence": "She left the ledger in the market stall.",
                    }
                ],
            },
            "The courier leaves at dusk.",
        ],
    )

    assert len(blocks) == 1
    for detail in (
        "The ledger records the missing key.",
        "The guard changes her route.",
        "Involved: Mara, Lina",
        "ledger object.location market",
        "She left the ledger in the market stall.",
        "The courier leaves at dusk.",
    ):
        assert detail in blocks[0]


def test_advisor_chapter_evidence_blocks_include_late_clues_without_truncation():
    clue = "The copper compass points inland after the river crossing."
    blocks = build_advisor_chapter_evidence_blocks(
        chapter_number=12,
        chapter_title="The Crossing",
        content="The crew reached the river. " * 40,
        key_events=[],
        clues=[{"clue": clue, "foreshadows": "The hidden road near the harbor."}],
        max_chars=160,
        overlap=25,
    )

    assert len(blocks) > 2
    assert any(clue in block for block in blocks)
    assert any("The hidden road near the harbor." in block for block in blocks)
    assert all(block.startswith("Chapter 12 (The Crossing): ") for block in blocks)


def test_advisor_chapter_evidence_blocks_handle_empty_and_invalid_section_sizes():
    assert (
        build_advisor_chapter_evidence_blocks(
            chapter_number=1, chapter_title=None, content=None, key_events=[]
        )
        == []
    )
    assert (
        build_advisor_chapter_evidence_blocks(
            chapter_number=1, chapter_title=None, content="  ", key_events=None
        )
        == []
    )
    with pytest.raises(ValueError, match="invalid_advisor_summary_section_size"):
        build_advisor_chapter_evidence_blocks(
            chapter_number=1,
            chapter_title=None,
            content="Some summary",
            key_events=[],
            max_chars=100,
            overlap=100,
        )


def test_advisor_item_evidence_blocks_keep_late_details_and_source_label():
    prefix = "- Ferryman bargain [introduced] introduced ch.3"
    detail = "Earlier terms remain in force. " * 35 + "The fare changed at the last crossing."
    blocks = build_advisor_item_evidence_blocks(
        prefix, detail, separator=": ", max_chars=180, overlap=30
    )
    bodies = [block.removeprefix(prefix + ": ") for block in blocks]

    assert len(blocks) > 2
    assert all(
        block.startswith(prefix + ": ") and len(body) <= 180 for block, body in zip(blocks, bodies)
    )
    assert bodies[0] + "".join(body[30:] for body in bodies[1:]) == detail
    assert "The fare changed at the last crossing." in blocks[-1]
    assert build_advisor_item_evidence_blocks(prefix, None) == [prefix]
    assert build_advisor_item_evidence_blocks(" ", detail) == []
    with pytest.raises(ValueError, match="invalid_advisor_item_section_size"):
        build_advisor_item_evidence_blocks(prefix, detail, max_chars=30, overlap=30)


def test_partition_advisor_scan_evidence_covers_all_late_items_without_oversized_groups():
    summaries = [f"Chapter {number}" for number in range(11)]
    threads = [f"Thread {number}" for number in range(19)]
    relationships = [f"Relationship {number}" for number in range(7)]
    world_elements = [f"World {number}" for number in range(13)]

    groups = partition_advisor_scan_evidence(
        summaries=summaries,
        threads=threads,
        relationships=relationships,
        world_elements=world_elements,
    )

    assert len(groups) == 3
    for key, originals, limit in (
        ("summaries", summaries, 4),
        ("threads", threads, 8),
        ("relationships", relationships, 5),
        ("world_elements", world_elements, 6),
    ):
        observed: list[str] = []
        for group in groups:
            for item in group[key]:
                if not observed or observed[-1] != item:
                    observed.append(item)
        assert observed == originals
        assert all(len(group[key]) <= limit + 1 for group in groups)
        if len(originals) > limit:
            assert groups[1][key][0] == groups[0][key][-1]


def test_partition_advisor_scan_evidence_keeps_boundary_contradiction_together():
    blocks = [
        "Chapter 1: the gate is open",
        "Chapter 2: the watch leaves",
        "Chapter 3: the gate is locked",
        "Chapter 4: the key is lost",
        "Chapter 5: the gate opens without a key",
    ]

    groups = partition_advisor_scan_evidence(
        summaries=blocks, threads=[], relationships=[], world_elements=[]
    )

    assert len(groups) == 2
    assert groups[0]["summaries"] == blocks[:4]
    assert groups[1]["summaries"] == blocks[3:]
    assert groups[1]["threads"] == []


def test_partition_advisor_scan_evidence_anchors_all_late_thread_groups_to_source_chapters():
    summaries = [
        "Chapter 1: The gate is locked.",
        "Chapter 2: The watch leaves the bridge.",
        "Chapter 3: The key goes missing.",
    ]
    threads = [
        f"- Thread {number} [developing] introduced ch.{number % 3 + 1}: unresolved"
        for number in range(165)
    ]

    groups = partition_advisor_scan_evidence(
        summaries=summaries, threads=threads, relationships=[], world_elements=[]
    )

    assert len(groups) == 21
    assert groups[0]["summaries"] == summaries
    assert all(1 <= len(group["summaries"]) <= 4 for group in groups)
    assert all(len(group["threads"]) <= 9 for group in groups)
    for group in groups[1:]:
        referenced = {
            int(match.group(1))
            for thread in group["threads"][1:]
            if (match := re.search(r"introduced ch\.(\d+)", thread))
        }
        anchored = {
            int(match.group(1))
            for summary in group["summaries"]
            if (match := re.match(r"Chapter (\d+)", summary))
        }
        assert referenced <= anchored


def test_partition_advisor_scan_evidence_rotates_summary_when_thread_has_no_chapter():
    groups = partition_advisor_scan_evidence(
        summaries=["Chapter 1: An opening event.", "Chapter 2: A later event."],
        threads=[f"- Untimed thread {index}" for index in range(17)],
        relationships=[],
        world_elements=[],
    )

    assert len(groups) == 3
    assert all(group["summaries"] for group in groups)
    assert groups[1]["summaries"] == ["Chapter 2: A later event."]


def test_partition_advisor_scan_evidence_with_no_evidence_has_no_groups():
    assert (
        partition_advisor_scan_evidence(
            summaries=[], threads=[], relationships=[], world_elements=[]
        )
        == []
    )


def test_advisor_scan_output_budget_scales_with_bounded_group_size():
    assert advisor_scan_output_token_budget(0) == 2048
    assert advisor_scan_output_token_budget(4) == 2048
    assert advisor_scan_output_token_budget(20) == 6144
    assert advisor_scan_output_token_budget(100) == 8192
    with pytest.raises(ValueError, match="invalid_advisor_source_block_count"):
        advisor_scan_output_token_budget(-1)


def test_open_thread_review_suggestions_surface_multiple_grounded_checks_without_false_warnings():
    threads = [
        SimpleNamespace(
            id=uuid.uuid4(),
            title=f"Thread {number}",
            description=f"Evidence {number}",
            status="developing",
            introduced_at=1,
            last_mentioned_at=2,
            importance=8,
            mention_count=3,
        )
        for number in range(6)
    ]
    statuses = {thread.id: "developing" for thread in threads}

    suggestions = build_open_thread_review_suggestions(threads, statuses, total_chapters=3)

    assert len(suggestions) == 4
    assert all(item["severity"] == "direction" for item in suggestions)
    assert all(item["chapter_ref"] == 2 for item in suggestions)
    assert all("Check whether" in item["description"] for item in suggestions)


def test_open_thread_review_suggestions_skip_duplicates_unverified_and_resolved_threads():
    first = SimpleNamespace(
        id=uuid.uuid4(),
        title="The letter",
        description="A letter is mentioned.",
        introduced_at=1,
        last_mentioned_at=2,
        importance=8,
        mention_count=2,
    )
    duplicate = SimpleNamespace(**{**vars(first), "id": uuid.uuid4(), "title": " the letter "})
    unverified = SimpleNamespace(
        **{**vars(first), "id": uuid.uuid4(), "title": "A rumour", "mention_count": 1}
    )
    resolved = SimpleNamespace(**{**vars(first), "id": uuid.uuid4(), "title": "The key"})
    future = SimpleNamespace(
        **{**vars(first), "id": uuid.uuid4(), "title": "The map", "last_mentioned_at": 9}
    )

    suggestions = build_open_thread_review_suggestions(
        [first, duplicate, unverified, resolved, future],
        {
            first.id: "developing",
            duplicate.id: "developing",
            unverified.id: "developing",
            resolved.id: "resolved",
            future.id: "developing",
        },
        total_chapters=3,
    )

    assert [item["id"] for item in suggestions] == [f"thread-review-{first.id}"]


def test_build_relationship_drift_suggestions_flags_type_changes():
    character_a_id = uuid.uuid4()
    character_b_id = uuid.uuid4()

    suggestions = build_relationship_drift_suggestions(
        [
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="allies",
                sentiment=0.5,
                from_chapter=2,
                description="They work together.",
            ),
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="enemies",
                sentiment=-0.9,
                from_chapter=8,
                description="They betray each other.",
            ),
        ],
        {character_a_id: "Mara", character_b_id: "Ilan"},
    )

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "relationship_flip"
    assert suggestions[0]["severity"] == "warning"
    assert suggestions[0]["title"] == "Relationship drift: Mara / Ilan"
    assert suggestions[0]["chapter_ref"] == 8


def test_build_relationship_drift_suggestions_flags_sentiment_swings():
    character_a_id = uuid.uuid4()
    character_b_id = uuid.uuid4()

    suggestions = build_relationship_drift_suggestions(
        [
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="siblings",
                sentiment=0.8,
                from_chapter=1,
                description=None,
            ),
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="siblings",
                sentiment=-0.5,
                from_chapter=4,
                description=None,
            ),
        ],
        {character_a_id: "Mara", character_b_id: "Ilan"},
    )

    assert len(suggestions) == 1
    assert suggestions[0]["severity"] == "info"
    assert "emotional tone" in suggestions[0]["description"]


def test_build_world_drift_suggestions_flags_conflicting_canon():
    suggestions = build_world_drift_suggestions(
        [
            SimpleNamespace(
                element_type="location",
                name="Glass Harbor",
                description="Glass Harbor is north of the capital.",
            ),
            SimpleNamespace(
                element_type="location",
                name="Glass Harbor",
                description="Glass Harbor sits south of the capital beyond the marsh.",
            ),
        ]
    )

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "location_conflict"
    assert suggestions[0]["title"] == "Location details drift: Glass Harbor"
    assert suggestions[0]["ask_prompt"].startswith("Check the canon for Glass Harbor")
