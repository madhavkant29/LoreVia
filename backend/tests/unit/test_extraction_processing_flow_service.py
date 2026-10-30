from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.evaluation.story_intelligence import load_evaluation_cases
from app.services import extraction_processing_flow_service as flow_service
from app.utils.characters.text import (
    extraction_source_coverage,
    source_mention_spans_in_batch,
    split_text_for_token_budget,
    split_text_for_token_budget_ranges,
)


class FakeDb:
    def __init__(self, user: SimpleNamespace | None = None) -> None:
        self.commits = 0
        self.user = user

    async def commit(self) -> None:
        self.commits += 1

    async def get(self, _model, _id):
        return self.user


def test_extraction_batches_count_joined_separator_within_token_budget(monkeypatch):
    monkeypatch.setattr(flow_service.settings, "EXTRACTION_BATCH_MAX_TOKENS", 5)
    monkeypatch.setattr(flow_service.settings, "EXTRACTION_BATCH_MAX_CHUNKS", 10)
    monkeypatch.setattr(flow_service, "count_tokens", lambda text: len(text))

    assert flow_service._group_chunks_for_extraction(["ab", "cd", "e"]) == [
        ["ab"],
        ["cd", "e"],
    ]


def test_oversized_extraction_chunk_is_bounded_and_covers_tail(monkeypatch):
    source = "".join(f"{number:03d}" for number in range(80))
    monkeypatch.setattr(flow_service.settings, "EXTRACTION_BATCH_MAX_TOKENS", 45)
    monkeypatch.setattr(flow_service.settings, "EXTRACTION_BATCH_MAX_CHUNKS", 6)
    monkeypatch.setattr(flow_service, "count_tokens", len)

    batches = flow_service._group_chunks_for_extraction([source])
    passages = [passage for batch in batches for passage in batch]
    previous_end = 0
    for passage in passages:
        start = source.find(passage, max(0, previous_end - 45))
        assert start >= 0
        assert start <= previous_end
        previous_end = start + len(passage)
        assert len(passage) <= 45
    assert previous_end == len(source)
    assert all(len("\n\n".join(batch)) <= 45 for batch in batches)
    assert passages[-1].endswith("079")


def test_long_form_case_batches_cover_late_character_and_ending(monkeypatch):
    corpus = Path(__file__).parents[2] / "evals" / "story_intelligence" / "v1" / "cases.json"
    case = next(
        item
        for item in load_evaluation_cases(corpus)
        if item["id"] == "mystery_long_form_late_arrival_and_two_source_conflicts"
    )
    source = case["text"]
    late_offset = source.index("Leda Voss")
    monkeypatch.setattr(flow_service.settings, "EXTRACTION_BATCH_MAX_TOKENS", 1000)
    monkeypatch.setattr(flow_service.settings, "EXTRACTION_BATCH_MAX_CHUNKS", 1)
    monkeypatch.setattr(flow_service, "count_tokens", len)

    batches = flow_service._group_chunks_for_extraction([source])
    coverage = extraction_source_coverage([source], batches, max_tokens=1000, count_tokens=len)

    assert coverage["complete"] is True
    assert coverage["source_characters"] == len(source)
    assert len(batches) > 1
    assert all(len(batch[0]) <= 1000 for batch in batches)
    assert any(
        item["start"] <= late_offset < item["end"] and item["batch_index"] > 1
        for item in coverage["ranges"]
    )
    assert coverage["ranges"][-1]["end"] == len(source)


def test_extraction_window_rejects_invalid_budget_and_empty_source():
    assert split_text_for_token_budget("", max_tokens=3, count_tokens=len) == []
    with pytest.raises(ValueError, match="invalid_extraction_window"):
        split_text_for_token_budget("abc", max_tokens=0, count_tokens=len)


def test_extraction_source_coverage_records_overlapping_ranges_and_chunk_hashes():
    source = "x" * 83
    passages = split_text_for_token_budget(source, max_tokens=30, count_tokens=len)
    ranges = split_text_for_token_budget_ranges(source, max_tokens=30, count_tokens=len)
    coverage = extraction_source_coverage(
        [source, "end"],
        [[passage] for passage in passages] + [["end"]],
        max_tokens=30,
        count_tokens=len,
    )

    assert coverage["complete"] is True
    assert coverage["source_characters"] == 86
    assert coverage["chunks"][0]["length"] == 83
    assert len(coverage["chunks"][0]["sha256"]) == 64
    assert [(item["start"], item["end"]) for item in coverage["ranges"][:-1]] == ranges
    assert coverage["ranges"][-1] == {
        "chunk_index": 1,
        "start": 0,
        "end": 3,
        "batch_index": len(passages) + 1,
    }
    assert ranges[0][0] == 0
    assert ranges[-1][1] == len(source)
    assert all(next_start <= end for (_, end), (next_start, _) in zip(ranges, ranges[1:]))


def test_extraction_source_coverage_rejects_missing_or_modified_passage():
    with pytest.raises(ValueError, match="source_coverage_incomplete"):
        extraction_source_coverage(["scene one"], [], max_tokens=20, count_tokens=len)
    with pytest.raises(ValueError, match="source_coverage_incomplete"):
        extraction_source_coverage(["scene one"], [["scene two"]], max_tokens=20, count_tokens=len)
    with pytest.raises(ValueError, match="source_coverage_incomplete"):
        extraction_source_coverage(
            ["scene one"], [["scene one", "extra"]], max_tokens=20, count_tokens=len
        )


def test_joined_batch_mentions_map_to_distinct_original_chunks():
    spans = source_mention_spans_in_batch(
        "Mara\n\nMara",
        ["Mara"],
        [
            {"chunk_index": 0, "start": 0, "end": 4},
            {"chunk_index": 1, "start": 0, "end": 4},
        ],
    )

    assert spans == [
        {"chunk_index": 0, "start": 0, "end": 4},
        {"chunk_index": 1, "start": 0, "end": 4},
    ]
    assert (
        source_mention_spans_in_batch(
            "They will wait.", ["Will"], [{"chunk_index": 0, "start": 0, "end": 15}]
        )
        == []
    )
    assert source_mention_spans_in_batch(
        "Mara Vale spoke.",
        ["Mara Vale", "Vale"],
        [{"chunk_index": 0, "start": 0, "end": 16}],
    ) == [{"chunk_index": 0, "start": 0, "end": 9}]


@pytest.mark.asyncio
async def test_finalize_book_completion_returns_false_when_book_not_complete(monkeypatch):
    async def claim(_db, _book_id):
        return False

    monkeypatch.setattr(flow_service, "_claim_book_completion", claim)

    db = FakeDb()
    completed = await flow_service.finalize_book_completion_after_chapter(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter=SimpleNamespace(title="Chapter 1"),
        chapter_number=1,
        processed_count=1,
        processing_total=2,
        queue_wait_ms=None,
        extraction_diagnostics={},
    )

    assert completed is False
    assert db.commits == 1


@pytest.mark.asyncio
async def test_finalize_book_completion_updates_ready_state_and_sends_notification(monkeypatch):
    sent: list[dict] = []

    async def claim(_db, _book_id):
        return True

    async def reconcile_aliases(_db, **_kwargs):
        return 1

    async def reconcile_relationships(_db, **_kwargs):
        return {"merged": 0}

    async def collect_stats(_db, _book):
        return SimpleNamespace(
            analysis_complete=True,
            character_count=3,
            relationship_count=2,
            plot_thread_count=1,
            continuity_issue_count=0,
        )

    def processing_state(*, analysis_complete):
        assert analysis_complete is True
        return "ready", "ready"

    def update_state(_book, **kwargs):
        return {"processing": kwargs}

    async def complete_rebuild(_db, _book):
        _book.rebuild_completed = True

    async def upsert_notification(_db, _book, _stats):
        return SimpleNamespace(), True

    async def send_email(email, **kwargs):
        sent.append({"email": email, **kwargs})

    monkeypatch.setattr(flow_service, "_claim_book_completion", claim)
    monkeypatch.setattr(
        flow_service,
        "reconcile_pending_first_name_alias_candidates",
        reconcile_aliases,
    )
    monkeypatch.setattr(flow_service, "reconcile_extracted_relationships", reconcile_relationships)
    monkeypatch.setattr(flow_service, "collect_book_ready_stats", collect_stats)
    monkeypatch.setattr(flow_service, "processing_state_for_completed_extraction", processing_state)
    monkeypatch.setattr(flow_service, "update_book_processing_state", update_state)
    monkeypatch.setattr(flow_service, "complete_rebuild_if_ready", complete_rebuild)
    monkeypatch.setattr(flow_service, "upsert_book_ready_notification", upsert_notification)
    monkeypatch.setattr(flow_service, "send_processing_complete_with_stats", send_email)

    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="The Test Book",
        mode="reader",
        total_chapters=1,
        writer_workspace={},
    )
    db = FakeDb(user=SimpleNamespace(email="author@example.test"))

    completed = await flow_service.finalize_book_completion_after_chapter(
        db,
        book=book,
        chapter=SimpleNamespace(title="Chapter 1"),
        chapter_number=1,
        processed_count=1,
        processing_total=1,
        queue_wait_ms=25,
        extraction_diagnostics={"summary": "ok"},
    )

    assert completed is True
    assert book.status == "ready"
    assert book.rebuild_completed is True
    assert book.writer_workspace["processing"]["stage"] == "ready"
    assert db.commits == 1
    assert sent == [
        {
            "email": "author@example.test",
            "book_title": "The Test Book",
            "character_count": 3,
            "relationship_count": 2,
            "plot_thread_count": 1,
            "continuity_issue_count": 0,
        }
    ]
