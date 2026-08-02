import uuid
from types import SimpleNamespace

import pytest

from app.utils.books.series_bible import build_series_bible_payload


class FakeResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)

    def scalars(self):
        return self


class FakeDb:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, _statement):
        return FakeResult(self.results.pop(0))


@pytest.mark.asyncio
async def test_build_series_bible_returns_empty_screenplay_payload_without_memberships():
    series = SimpleNamespace(id=uuid.uuid4(), name="Gate Cycle", description=None)

    payload = await build_series_bible_payload(FakeDb([[]]), series=series)

    assert payload.series_id == str(series.id)
    assert payload.work_type == "screenplay"
    assert payload.episode_count == 0
    assert payload.recurring_characters == []
    assert payload.continuity_risks == []


@pytest.mark.asyncio
async def test_build_series_bible_aggregates_recurring_canon_threads_and_continuity_risks():
    series = SimpleNamespace(id=uuid.uuid4(), name="Gate Cycle", description="Two episodes")
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    first = SimpleNamespace(
        id=first_id,
        title="The First Gate",
        work_type="screenplay",
        format="screenplay",
        total_chapters=8,
        status="ready",
    )
    second = SimpleNamespace(
        id=second_id,
        title="The Ash Gate",
        work_type="screenplay",
        format="screenplay",
        total_chapters=10,
        status="processing",
    )
    memberships = [
        (SimpleNamespace(position=1), first),
        (SimpleNamespace(position=2), second),
    ]

    mara_first_id = uuid.uuid4()
    joren_first_id = uuid.uuid4()
    mara_second_id = uuid.uuid4()
    joren_second_id = uuid.uuid4()
    characters = [
        SimpleNamespace(
            id=mara_first_id,
            book_id=first_id,
            name="Mara",
            mention_count=18,
            role="mc",
            first_chapter=1,
        ),
        SimpleNamespace(
            id=joren_first_id,
            book_id=first_id,
            name="Joren",
            mention_count=9,
            role="sc",
            first_chapter=2,
        ),
        SimpleNamespace(
            id=mara_second_id,
            book_id=second_id,
            name="Mara",
            mention_count=22,
            role="sc",
            first_chapter=1,
        ),
        SimpleNamespace(
            id=joren_second_id,
            book_id=second_id,
            name="Joren",
            mention_count=13,
            role="sc",
            first_chapter=1,
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            book_id=second_id,
            name="   ",
            mention_count=1,
            role=None,
            first_chapter=4,
        ),
    ]
    relationships = [
        SimpleNamespace(
            book_id=first_id,
            character_a_id=mara_first_id,
            character_b_id=joren_first_id,
            rel_type="ally",
            description="They guard the gate.",
        ),
        SimpleNamespace(
            book_id=second_id,
            character_a_id=mara_second_id,
            character_b_id=joren_second_id,
            rel_type="ally",
            description=None,
        ),
        SimpleNamespace(
            book_id=second_id,
            character_a_id=mara_second_id,
            character_b_id=joren_second_id,
            rel_type="rival",
            description="A label shift.",
        ),
    ]
    plot_threads = [
        SimpleNamespace(
            book_id=first_id, title="The Brass Key", status="developing", note="Who forged it?"
        ),
        SimpleNamespace(book_id=second_id, title=" the brass key ", status="ongoing", note=None),
        SimpleNamespace(book_id=second_id, title="Closed Door", status="resolved", note=None),
        SimpleNamespace(book_id=second_id, title=" ", status="developing", note=None),
    ]
    wiki_entries = [
        SimpleNamespace(
            book_id=first_id, entry_type="place", name="Ash Gate", description="A silver arch."
        ),
        SimpleNamespace(
            book_id=second_id, entry_type="place", name=" ash gate ", description="A black arch."
        ),
        SimpleNamespace(book_id=second_id, entry_type="object", name="Brass Key", description=None),
        SimpleNamespace(book_id=second_id, entry_type="place", name=" ", description="ignored"),
    ]
    db = FakeDb(
        [
            memberships,
            [(first_id, 12, 8400), (second_id, 14, 9200)],
            [(first_id, 44), (second_id, 51)],
            characters,
            relationships,
            plot_threads,
            wiki_entries,
        ]
    )

    payload = await build_series_bible_payload(db, series=series)

    assert payload.episode_count == 2
    assert payload.episodes[0].total_scenes == 12
    assert payload.episodes[1].total_dialogue_lines == 51
    assert [item.normalized_name for item in payload.recurring_characters] == ["mara", "joren"]
    assert payload.recurring_characters[0].episode_count == 2
    assert payload.recurring_relationships[0].relationship_type == "ally"
    assert payload.unresolved_plot_threads[0].title == "The Brass Key"
    assert payload.unresolved_plot_threads[0].status == "developing"
    assert {entry.name.strip() for entry in payload.canon_entries} == {"Ash Gate", "Brass Key"}
    assert any("differing place descriptions" in risk for risk in payload.continuity_risks)
    assert any("shifts role labels" in risk for risk in payload.continuity_risks)
