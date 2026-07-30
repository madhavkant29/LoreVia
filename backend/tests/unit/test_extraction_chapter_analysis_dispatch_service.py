from types import SimpleNamespace

import pytest

from app.services.extraction_chapter_analysis_dispatch_service import (
    dispatch_chapter_analysis_after_extraction,
)


class _EmptyScalars:
    @staticmethod
    def first():
        return None


class _EmptyResult:
    @staticmethod
    def scalars():
        return _EmptyScalars()


class _FakeDb:
    def __init__(self):
        self.commits = 0

    async def execute(self, _statement):
        return _EmptyResult()

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_dispatch_without_active_run_closes_lookup_transaction():
    db = _FakeDb()

    await dispatch_chapter_analysis_after_extraction(
        db,
        book=SimpleNamespace(id="book-id"),
        chapter=SimpleNamespace(id="chapter-id"),
        chapter_number=1,
        rebuild_run_id=None,
        manual_reprocess=False,
    )

    assert db.commits == 1
