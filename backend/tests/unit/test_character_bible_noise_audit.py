import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.audit_character_bible_noise import _is_obvious_noise_character, build_noise_report


def _make_character(
    *,
    name: str = "Test",
    mention_count: int = 1,
    first_chapter: int = 1,
    role: str | None = None,
    aliases: list | None = None,
    personality_tags: list | None = None,
    motivations: list | None = None,
    fears: list | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
    trait_state: dict | None = None,
    goal: str | None = None,
    relationships_as_a: list | None = None,
    relationships_as_b: list | None = None,
    states: list | None = None,
    voice_profile=None,
    is_manual: bool = False,
    book_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id or uuid.uuid4(),
        name=name,
        mention_count=mention_count,
        first_chapter=first_chapter,
        last_seen_chapter=None,
        role=role,
        aliases=aliases or [],
        personality_tags=personality_tags or [],
        motivations=motivations or [],
        fears=fears or [],
        archetype=archetype,
        arc_summary=arc_summary,
        trait_state=trait_state or {},
        goal=goal,
        lie_they_believe=None,
        backstory_wound=None,
        arc_type=None,
        relationships_as_a=relationships_as_a or [],
        relationships_as_b=relationships_as_b or [],
        states=states or [],
        voice_profile=voice_profile,
        is_manual=is_manual,
    )


def test_is_obvious_noise_character_flags_low_mention_stopwords():
    well = _make_character(name="Well", mention_count=1, role=None)
    is_noise, reasons = _is_obvious_noise_character(well)
    assert is_noise is True
    assert len(reasons) > 0


def test_is_obvious_noise_character_keeps_meaningful_character():
    gregor = _make_character(
        name="Gregor",
        mention_count=4,
        role="mc",
        personality_tags=["anxious"],
        motivations=["protect his family"],
        arc_summary="A grounded central character.",
    )
    is_noise, reasons = _is_obvious_noise_character(gregor)
    assert is_noise is False


def test_is_obvious_noise_character_keeps_manual_characters():
    manual = _make_character(name="Well", mention_count=1, is_manual=True)
    is_noise, _ = _is_obvious_noise_character(manual)
    assert is_noise is False


def test_is_obvious_noise_character_keeps_connected_characters():
    rel = SimpleNamespace(id=uuid.uuid4())
    connected = _make_character(
        name="Minor",
        mention_count=1,
        relationships_as_a=[rel],
    )
    is_noise, _ = _is_obvious_noise_character(connected)
    assert is_noise is False


@pytest.mark.asyncio
async def test_noise_audit_report_aggregates_findings(monkeypatch):
    book_id = uuid.uuid4()
    well = _make_character(name="Well", mention_count=1, book_id=book_id)
    gregor = _make_character(
        name="Gregor",
        mention_count=4,
        book_id=book_id,
        personality_tags=["anxious"],
        motivations=["protect his family"],
        arc_summary="A grounded central character.",
    )

    class _ScalarList:
        def __init__(self, items):
            self._items = items

        def all(self):
            return list(self._items)

    class _Result:
        def __init__(self, *, scalars=None):
            self._scalars = _ScalarList(scalars or [])

        def scalars(self):
            return self._scalars

    class _FakeDB:
        def __init__(self, execute_results):
            self._results = list(execute_results)

        async def execute(self, *_args, **_kwargs):
            return self._results.pop(0)

        async def close(self):
            pass

    db = _FakeDB(execute_results=[_Result(scalars=[well, gregor])])

    report = await build_noise_report(book_id, db=db)

    assert report["total_characters"] == 2
    assert report["noise_count"] == 1
    assert str(book_id) in report["books"]
    assert report["books"][str(book_id)][0]["name"] == "Well"
    assert report["books"][str(book_id)][0]["reasons"]