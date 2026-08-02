import uuid

import pytest

from app.services.library_stats_service import load_library_aggregate_stats


class _Result:
    def __init__(self, *, one=None, rows=None):
        self._one = one
        self._rows = rows or []

    def one(self):
        return self._one

    def all(self):
        return self._rows


class _Database:
    def __init__(self, book_count: int):
        self.calls = 0
        self.book_count = book_count

    async def execute(self, _statement, _parameters=None):
        self.calls += 1
        if self.calls == 1:
            return _Result(one=(self.book_count * 2, self.book_count * 100))
        return _Result(one=(0, self.book_count * 150))


@pytest.mark.parametrize("book_count", [1, 100, 1000])
async def test_library_stats_query_count_is_constant(book_count: int) -> None:
    db = _Database(book_count)
    stats = await load_library_aggregate_stats(db, uuid.uuid4())
    assert db.calls == 2
    assert stats.total_words_read == book_count * 150
    assert stats.total_chapters_tracked == book_count * 2
