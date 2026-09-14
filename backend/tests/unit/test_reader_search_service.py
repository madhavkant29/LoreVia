import uuid

import pytest

from app.services import reader_search_service


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, *, execute_rows, scalar_values):
        self.execute_rows = list(execute_rows)
        self.scalar_values = list(scalar_values)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Rows(self.execute_rows.pop(0))

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.scalar_values.pop(0)


@pytest.mark.asyncio
async def test_lexical_reader_chunk_search_uses_full_text_and_bounded_fallback(monkeypatch):
    book_id = uuid.uuid4()
    db = _FakeDB(
        execute_rows=[[], [("Silver gate", 2, 4, "The Gate", 0.4)]],
        scalar_values=[],
    )
    monkeypatch.setattr(reader_search_service, "build_search_result", lambda **kwargs: kwargs)

    results = await reader_search_service.lexical_reader_chunk_search(
        db,
        book_id=book_id,
        query="silver gate",
        max_chapter=4,
        limit=3,
    )

    assert results == [
        {
            "text": "Silver gate",
            "chunk_index": 2,
            "chapter_num": 4,
            "chapter_title": "The Gate",
            "relevance": 0.4,
        }
    ]
    sql = "\n".join(str(statement).lower() for statement in db.statements)
    assert "to_tsvector" in sql
    assert "websearch_to_tsquery" in sql
    assert "ilike" not in sql
    assert "limit" in sql


@pytest.mark.asyncio
async def test_thematic_reader_search_uses_indexed_chunks_without_storage_fallback():
    book_id = uuid.uuid4()
    db = _FakeDB(
        execute_rows=[[], [(4, "The Gate", "The silver gate opens at dawn.", 0.7)]],
        scalar_values=[1],
    )

    payload = await reader_search_service.thematic_reader_search(
        db,
        book_id=book_id,
        visible_chapters={4},
        query="silver gate",
    )

    assert payload["index_status"] == "ready"
    assert payload["results"] == [
        {
            "chapter_number": 4,
            "chapter_title": "The Gate",
            "score": 0.7,
            "summary": "The silver gate opens at dawn",
        }
    ]
    assert "download_book" not in reader_search_service.__dict__
    assert "asyncio" not in reader_search_service.__dict__


@pytest.mark.asyncio
async def test_thematic_reader_search_marks_missing_chunk_projection_as_building():
    db = _FakeDB(
        execute_rows=[[(1, "One", "A signal opens the gate.", [], [])]],
        scalar_values=[0],
    )

    payload = await reader_search_service.thematic_reader_search(
        db,
        book_id=uuid.uuid4(),
        visible_chapters={1},
        query="signal",
    )

    assert payload == {
        "results": [
            {
                "chapter_number": 1,
                "chapter_title": "One",
                "score": 1,
                "summary": "A signal opens the gate.",
            }
        ],
        "index_status": "building",
    }


@pytest.mark.asyncio
async def test_thematic_reader_search_marks_partially_indexed_chapters_as_building():
    db = _FakeDB(
        execute_rows=[[], [(1, "One", "The silver gate opens.", 0.6)]],
        scalar_values=[1],
    )

    payload = await reader_search_service.thematic_reader_search(
        db,
        book_id=uuid.uuid4(),
        visible_chapters={1, 2},
        query="silver gate",
    )

    assert payload["index_status"] == "building"
    assert payload["results"][0]["chapter_number"] == 1
