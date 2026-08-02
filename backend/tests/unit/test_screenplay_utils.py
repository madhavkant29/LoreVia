from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.utils import screenplay_utils


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, *, scalar=None, scalars=None, first=None, all_rows=None):
        self._scalar = scalar
        self._scalars = [] if scalars is None else scalars
        self._first = first
        self._all_rows = [] if all_rows is None else all_rows

    def scalar(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _ScalarRows(self._scalars)

    def first(self):
        return self._first

    def all(self):
        return list(self._all_rows)


class _FakeDB:
    def __init__(self, execute_results=None):
        self.execute_results = list(execute_results or [])
        self.added = []
        self.deleted = []
        self.flush_count = 0
        self.commit_count = 0

    async def execute(self, *_args, **_kwargs):
        if self.execute_results:
            return self.execute_results.pop(0)
        return _Result()

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def flush(self):
        self.flush_count += 1

    async def commit(self):
        self.commit_count += 1


def _scene(**overrides):
    values = {
        "id": uuid.uuid4(),
        "book_id": uuid.uuid4(),
        "chapter_id": None,
        "number": 1,
        "heading": "INT. ARCHIVE - NIGHT",
        "location": "ARCHIVE",
        "time_of_day": "NIGHT",
        "interior": True,
        "exterior": False,
        "scene_number": None,
        "description": "A lamp flickers.\nA door opens.",
        "word_count": 500,
        "page_number": 7,
        "created_at": datetime(2026, 6, 11, tzinfo=UTC),
        "dialogue": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _dialogue(character_name="MIRA", line_number=1):
    return SimpleNamespace(
        id=uuid.uuid4(),
        scene_id=uuid.uuid4(),
        character_name=character_name,
        character_extension=None,
        dialogue_text="We should not be here.",
        parenthetical=None,
        line_number=line_number,
        word_count=6,
        created_at=datetime(2026, 6, 11, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_get_owned_scene_returns_matching_scene():
    scene = _scene()
    found = await screenplay_utils.get_owned_scene(
        _FakeDB([_Result(scalar=scene)]),
        scene.id,
        uuid.uuid4(),
    )

    assert found is scene


@pytest.mark.asyncio
async def test_get_owned_scene_raises_404_when_missing():
    with pytest.raises(screenplay_utils.HTTPException) as exc:
        await screenplay_utils.get_owned_scene(
            _FakeDB([_Result(scalar=None)]), uuid.uuid4(), uuid.uuid4()
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Scene not found"


@pytest.mark.asyncio
async def test_list_scenes_for_book_returns_ordered_scene_rows():
    scenes = [_scene(number=1), _scene(number=2)]

    result = await screenplay_utils.list_scenes_for_book(
        _FakeDB([_Result(scalars=scenes)]),
        uuid.uuid4(),
        uuid.uuid4(),
    )

    assert result == scenes


@pytest.mark.asyncio
async def test_get_scene_with_dialogue_attaches_ordered_dialogue(monkeypatch):
    scene = _scene()
    dialogue = [_dialogue("MIRA", 1), _dialogue("JON", 2)]

    async def get_owned_scene(*_args, **_kwargs):
        return scene

    monkeypatch.setattr(screenplay_utils, "get_owned_scene", get_owned_scene)

    result = await screenplay_utils.get_scene_with_dialogue(
        _FakeDB([_Result(scalars=dialogue)]),
        scene.id,
        uuid.uuid4(),
    )

    assert result is scene
    assert result.dialogue == dialogue


@pytest.mark.asyncio
async def test_scene_out_serializes_scene_with_dialogue_rows():
    scene = _scene()
    dialogue = [_dialogue("MIRA", 1)]
    dialogue[0].scene_id = scene.id

    payload = await screenplay_utils.scene_out(
        _FakeDB([_Result(scalars=dialogue)]),
        scene,
    )

    assert payload.id == scene.id
    assert payload.heading == "INT. ARCHIVE - NIGHT"
    assert payload.dialogue[0].character_name == "MIRA"


@pytest.mark.asyncio
async def test_get_scene_analysis_counts_characters_dialogue_and_action_lines(monkeypatch):
    scene = _scene(number=4, word_count=375)
    dialogue = [_dialogue("MIRA", 1), _dialogue("JON", 2), _dialogue("MIRA", 3)]

    async def get_owned_scene(*_args, **_kwargs):
        return scene

    monkeypatch.setattr(screenplay_utils, "get_owned_scene", get_owned_scene)

    analysis = await screenplay_utils.get_scene_analysis(
        _FakeDB([_Result(scalars=dialogue)]),
        scene.id,
        uuid.uuid4(),
    )

    assert analysis.scene_number == 4
    assert sorted(analysis.characters_present) == ["JON", "MIRA"]
    assert analysis.dialogue_count == 3
    assert analysis.action_lines == 2
    assert analysis.estimated_duration_minutes == 1.5


@pytest.mark.asyncio
async def test_get_screenplay_stats_builds_aggregate_payload():
    character_rows = [("MIRA", 3), ("JON", 1)]
    stats = await screenplay_utils.get_screenplay_stats(
        _FakeDB(
            [
                _Result(scalar=SimpleNamespace(id=uuid.uuid4())),
                _Result(
                    first=SimpleNamespace(
                        total_scenes=3, total_words=700, int_scenes=2, ext_scenes=1
                    )
                ),
                _Result(first=SimpleNamespace(total_dialogue_lines=4, dialogue_words=120)),
                _Result(all_rows=character_rows),
            ]
        ),
        uuid.uuid4(),
        uuid.uuid4(),
    )

    assert stats.total_scenes == 3
    assert stats.total_dialogue_lines == 4
    assert stats.total_words == 820
    assert stats.estimated_pages == 3
    assert stats.character_dialogue_counts == {"MIRA": 3, "JON": 1}
    assert stats.scene_types == {"INT": 2, "EXT": 1, "OTHER": 0}


@pytest.mark.asyncio
async def test_get_screenplay_stats_raises_404_for_unowned_book():
    with pytest.raises(screenplay_utils.HTTPException) as exc:
        await screenplay_utils.get_screenplay_stats(
            _FakeDB([_Result(scalar=None)]),
            uuid.uuid4(),
            uuid.uuid4(),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Book not found"


@pytest.mark.asyncio
async def test_create_scenes_from_screenplay_persists_scene_and_dialogue(monkeypatch):
    book_id = uuid.uuid4()
    first_dialogue = SimpleNamespace(scene_id=None)
    second_dialogue = SimpleNamespace(scene_id=None)
    scene = SimpleNamespace(id=uuid.uuid4(), dialogue=[first_dialogue, second_dialogue])

    monkeypatch.setattr(
        "app.parsers.screenplay_parser.parse_screenplay",
        lambda text: [{"heading": text}],
    )
    monkeypatch.setattr(
        "app.parsers.screenplay_parser.create_scene_models",
        lambda scenes_data, incoming_book_id: [scene],
    )

    db = _FakeDB()
    created = await screenplay_utils.create_scenes_from_screenplay(db, book_id, "INT. LAB - DAY")

    assert created == [scene]
    assert db.added == [scene, first_dialogue, second_dialogue]
    assert first_dialogue.scene_id == scene.id
    assert second_dialogue.scene_id == scene.id
    assert db.flush_count == 1
    assert db.commit_count == 1


@pytest.mark.asyncio
async def test_replace_book_scenes_deletes_selected_rows_and_maps_chapter_ids(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    old_scene = _scene(book_id=book.id, number=3)
    dialogue = SimpleNamespace(scene_id=None)
    new_scene = SimpleNamespace(id=uuid.uuid4(), number=99, chapter_id=None, dialogue=[dialogue])
    chapter_id = uuid.uuid4()

    monkeypatch.setattr(
        "app.parsers.screenplay_parser.create_scene_models",
        lambda parsed_scenes, incoming_book_id: [new_scene],
    )

    db = _FakeDB([_Result(scalars=[old_scene])])
    created = await screenplay_utils.replace_book_scenes(
        db,
        book=book,
        parsed_scenes=[{"heading": "EXT. ROOF - DAWN"}],
        chapter_ids_by_number={5: chapter_id},
        starting_number=5,
        replace_scene_numbers={3},
    )

    assert db.deleted == [old_scene]
    assert created == [new_scene]
    assert new_scene.number == 5
    assert new_scene.chapter_id == chapter_id
    assert dialogue.scene_id == new_scene.id
    assert db.added == [new_scene, dialogue]
    assert db.flush_count == 3
    assert db.commit_count == 0


@pytest.mark.asyncio
async def test_get_character_dialogue_verifies_book_before_returning_lines():
    lines = [_dialogue("MIRA", 1), _dialogue("MIRA", 2)]

    result = await screenplay_utils.get_character_dialogue(
        _FakeDB([_Result(scalar=SimpleNamespace(id=uuid.uuid4())), _Result(scalars=lines)]),
        uuid.uuid4(),
        "MIRA",
        uuid.uuid4(),
    )

    assert result == lines


@pytest.mark.asyncio
async def test_search_and_filter_helpers_raise_404_for_unowned_book():
    with pytest.raises(screenplay_utils.HTTPException) as search_exc:
        await screenplay_utils.search_scenes(
            _FakeDB([_Result(scalar=None)]), uuid.uuid4(), "archive", uuid.uuid4()
        )
    with pytest.raises(screenplay_utils.HTTPException) as filter_exc:
        await screenplay_utils.filter_scenes_by_type(
            _FakeDB([_Result(scalar=None)]), uuid.uuid4(), "INT", uuid.uuid4()
        )
    with pytest.raises(screenplay_utils.HTTPException) as location_exc:
        await screenplay_utils.get_scene_by_location(
            _FakeDB([_Result(scalar=None)]), uuid.uuid4(), "Archive", uuid.uuid4()
        )

    assert search_exc.value.status_code == 404
    assert filter_exc.value.status_code == 404
    assert location_exc.value.status_code == 404


@pytest.mark.asyncio
async def test_search_location_and_type_helpers_return_scene_rows():
    scenes = [_scene(number=1), _scene(number=2)]

    search_result = await screenplay_utils.search_scenes(
        _FakeDB([_Result(scalar=SimpleNamespace(id=uuid.uuid4())), _Result(scalars=scenes)]),
        uuid.uuid4(),
        "archive",
        uuid.uuid4(),
    )
    location_result = await screenplay_utils.get_scene_by_location(
        _FakeDB([_Result(scalar=SimpleNamespace(id=uuid.uuid4())), _Result(scalars=scenes[:1])]),
        uuid.uuid4(),
        "Archive",
        uuid.uuid4(),
    )
    int_result = await screenplay_utils.filter_scenes_by_type(
        _FakeDB([_Result(scalar=SimpleNamespace(id=uuid.uuid4())), _Result(scalars=scenes[:1])]),
        uuid.uuid4(),
        "INT",
        uuid.uuid4(),
    )
    all_result = await screenplay_utils.filter_scenes_by_type(
        _FakeDB([_Result(scalar=SimpleNamespace(id=uuid.uuid4())), _Result(scalars=scenes)]),
        uuid.uuid4(),
        "ALL",
        uuid.uuid4(),
    )

    assert search_result == scenes
    assert location_result == scenes[:1]
    assert int_result == scenes[:1]
    assert all_result == scenes
