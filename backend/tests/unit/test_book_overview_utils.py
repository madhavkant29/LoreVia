from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.utils.books.overview import build_book_world_stats


class _ScalarResult:
    def __init__(self, value: int):
        self.value = value

    def scalar(self):
        return self.value


class _FakeSession:
    def __init__(self, values: list[int]):
        self.values = values
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _ScalarResult(self.values.pop(0))


@pytest.mark.asyncio
async def test_build_book_world_stats_uses_real_document_and_element_counts():
    db = _FakeSession([1, 120, 1])
    book = SimpleNamespace(id=uuid.uuid4())

    stats = await build_book_world_stats(db, book)

    assert stats.active_documents == 1
    assert stats.corpus_words == 120
    assert stats.extracted_elements == 1
    assert stats.total_items == 2
    assert len(db.statements) == 3
