import time

from app.engine.analysis.summariser import derive_summary_modes_from_detailed
from app.utils.ingestion_utils import (
    apply_chapter_number_strategy,
    build_chapter_dispatch_plan,
    extract_queue_wait_ms,
)


def test_build_chapter_dispatch_plan_staggers_non_eager_chapters():
    plan = build_chapter_dispatch_plan(
        [1, 2, 3, 4, 5],
        eager_limit=1,
        dispatch_window=2,
        dispatch_delay_seconds=3,
    )

    assert [(item.chapter_number, item.countdown) for item in plan] == [
        (1, 0),
        (2, 3),
        (3, 3),
        (4, 6),
        (5, 6),
    ]


def test_extract_queue_wait_ms_ignores_missing_and_invalid_headers():
    assert extract_queue_wait_ms(None) is None
    assert extract_queue_wait_ms({}) is None
    assert extract_queue_wait_ms({"enqueued_at": "nope"}) is None


def test_extract_queue_wait_ms_uses_epoch_seconds():
    now = time.time()
    wait_ms = extract_queue_wait_ms({"enqueued_at": str(now - 1.25)})

    assert wait_ms is not None
    assert 1000 <= wait_ms <= 4000


def test_derive_summary_modes_from_detailed_prefers_key_events():
    payload = {
        "content": "Aoi confronts Ren in the archive. They uncover a sealed ledger. The chapter ends with a pact.",
        "key_events": [
            {"event_title": "Archive confrontation", "description": "Aoi corners Ren over the missing ledger."},
            {"event_title": "Ledger discovery", "description": "They find the sealed ledger behind a false wall."},
        ],
        "char_changes": [],
        "clues": [],
        "themes": [],
    }

    derived = derive_summary_modes_from_detailed(payload)

    assert "Aoi confronts Ren" in derived["short"]["content"]
    assert "1. Archive confrontation: Aoi corners Ren over the missing ledger." in derived["key_points"]["content"]
    assert "2. Ledger discovery: They find the sealed ledger behind a false wall." in derived["key_points"]["content"]


def test_apply_chapter_number_strategy_preserves_clean_contiguous_numbers():
    chapters = [
        {"number": 1, "source_number": 1, "title": "Chapter 1", "text": "One"},
        {"number": 2, "source_number": 2, "title": "Chapter 2", "text": "Two"},
        {"number": 3, "source_number": 3, "title": "Chapter 3", "text": "Three"},
    ]

    normalized = apply_chapter_number_strategy(chapters, preserve_chapter_numbers=True)

    assert [chapter["number"] for chapter in normalized] == [1, 2, 3]


def test_apply_chapter_number_strategy_falls_back_for_gaps():
    chapters = [
        {"number": 1, "source_number": 1, "title": "Chapter 1", "text": "One"},
        {"number": 2, "source_number": 3, "title": "Chapter 3", "text": "Three"},
    ]

    normalized = apply_chapter_number_strategy(chapters, preserve_chapter_numbers=True)

    assert [chapter["number"] for chapter in normalized] == [1, 2]


def test_apply_chapter_number_strategy_preserves_letter_derived_sequence():
    chapters = [
        {"number": 1, "source_number": 1, "title": "Chapter A", "text": "One"},
        {"number": 2, "source_number": 2, "title": "Chapter B", "text": "Two"},
        {"number": 3, "source_number": 3, "title": "Chapter C", "text": "Three"},
    ]

    normalized = apply_chapter_number_strategy(chapters, preserve_chapter_numbers=True)

    assert [chapter["number"] for chapter in normalized] == [1, 2, 3]
