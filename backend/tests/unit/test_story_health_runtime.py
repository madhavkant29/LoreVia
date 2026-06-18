import uuid
from types import SimpleNamespace

import pytest

from app.utils import book_utils


class FakeResult:
    def __init__(self, values=None, scalar=None):
        self.values = list(values or [])
        self.scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return list(self.values)

    def scalar_one_or_none(self):
        return self.scalar


class FakeDb:
    def __init__(self, results, scalar_values):
        self.results = list(results)
        self.scalar_values = list(scalar_values)

    async def execute(self, _statement):
        return self.results.pop(0)

    async def scalar(self, _statement):
        return self.scalar_values.pop(0)


@pytest.mark.asyncio
async def test_build_story_health_payload_scores_all_runtime_dimensions(monkeypatch):
    book_id = uuid.uuid4()
    mara_id = uuid.uuid4()
    joren_id = uuid.uuid4()
    characters = [
        SimpleNamespace(
            id=mara_id,
            role="mc",
            mention_count=24,
            arc_summary="Learns to trust.",
            personality_tags=["guarded"],
            archetype=None,
            trait_state={"eyes": "gray"},
            motivations=["protect the gate"],
            fears=["betrayal"],
            growth_events=[{"event": "Shares the key"}],
        ),
        SimpleNamespace(
            id=joren_id,
            role="sc",
            mention_count=12,
            arc_summary=None,
            personality_tags=[],
            archetype="scholar",
            trait_state={},
            motivations=[],
            fears=[],
            growth_events=[],
        ),
    ]
    relationships = [SimpleNamespace(character_a_id=mara_id, character_b_id=joren_id)]
    plot_threads = [
        SimpleNamespace(status="resolved", introduced_at=1, last_mentioned_at=5, resolved_at=5),
        SimpleNamespace(status="ongoing", introduced_at=2, last_mentioned_at=3, resolved_at=None),
        SimpleNamespace(status="abandoned", introduced_at=8, last_mentioned_at=8, resolved_at=4),
    ]
    world_gap = SimpleNamespace(priority_gaps=[{"gap": "law"}], consistency_flags=[{"flag": "color"}, {"flag": "age"}])
    voice_profiles = [
        SimpleNamespace(character_id=mara_id, sample_dialogue_count=5, signature_phrases=["Hold the gate"], dominant_markers=[]),
        SimpleNamespace(character_id=joren_id, sample_dialogue_count=2, signature_phrases=[], dominant_markers=["questions"]),
    ]
    db = FakeDb(
        [
            FakeResult(characters),
            FakeResult(relationships),
            FakeResult([(mara_id, 2), (joren_id, 0)]),
            FakeResult(plot_threads),
            FakeResult(scalar=world_gap),
            FakeResult(voice_profiles),
            FakeResult([900, 1000, 1100, 3000]),
        ],
        [7, 2],
    )
    book = SimpleNamespace(id=book_id, total_chapters=12)

    async def fake_reports(_db, _book, limit):
        assert limit == 6
        return [
            SimpleNamespace(continuity_flags=[{"flag": "eye color"}]),
            SimpleNamespace(continuity_flags=[]),
        ]

    monkeypatch.setattr("app.utils.character_utils.is_displayable_character", lambda character: True)
    monkeypatch.setattr(book_utils, "list_chapter_consistency_reports", fake_reports)

    payload = await book_utils.build_story_health_payload(db, book)

    assert 0 <= payload.score <= 94
    assert payload.status in {"Excellent", "Good", "Fair", "Needs Attention"}
    assert [metric.label for metric in payload.metrics] == [
        "Continuity",
        "Character consistency",
        "Timeline clarity",
        "Plot thread closure",
        "Worldbuilding consistency",
        "Pacing",
        "Dialogue/voice consistency",
    ]
    details = " ".join(metric.detail for metric in payload.metrics)
    assert "1 recent continuity flags" in details
    assert "1 chronology conflicts" in details
    assert "cached world-analysis issues" in details
    assert "pacing outliers" in details


@pytest.mark.asyncio
async def test_build_story_health_payload_handles_empty_runtime_data(monkeypatch):
    db = FakeDb(
        [
            FakeResult([]),
            FakeResult([]),
            FakeResult([]),
            FakeResult([]),
            FakeResult(scalar=None),
            FakeResult([]),
            FakeResult([]),
        ],
        [0, 0],
    )
    book = SimpleNamespace(id=uuid.uuid4(), total_chapters=0)

    async def no_reports(*_args, **_kwargs):
        return []

    monkeypatch.setattr("app.utils.character_utils.is_displayable_character", lambda character: True)
    monkeypatch.setattr(book_utils, "list_chapter_consistency_reports", no_reports)

    payload = await book_utils.build_story_health_payload(db, book)

    assert payload.score >= 0
    assert next(metric for metric in payload.metrics if metric.label == "Pacing").detail.startswith("No persisted")
    assert "fresh pass" in next(metric for metric in payload.metrics if metric.label == "Worldbuilding consistency").detail
