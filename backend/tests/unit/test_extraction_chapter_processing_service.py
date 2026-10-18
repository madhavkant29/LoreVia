import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_chapter_processing_service


async def test_chapter_extraction_releases_freeze_read_transactions_before_provider_calls(
    monkeypatch,
):
    class StopAfterProviderChecks(Exception):
        pass

    class Db:
        transaction_open = False
        commits = 0

        async def commit(self):
            self.commits += 1
            self.transaction_open = False

        async def execute(self, _statement):
            self.transaction_open = True
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db = Db()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        is_editor_project=False,
        writer_workspace={},
    )
    chapter = SimpleNamespace(id=uuid.uuid4(), title="One")

    async def no(*_args, **_kwargs):
        return False

    async def yes(*_args, **_kwargs):
        return True

    async def frozen_read(_db, _book_id):
        db.transaction_open = True
        return False

    async def stage(*_args, **_kwargs):
        return chapter

    async def embed(*_args, **_kwargs):
        assert db.transaction_open is False
        return SimpleNamespace(texts=["chunk"])

    async def extract(*_args, **_kwargs):
        assert db.transaction_open is False
        raise StopAfterProviderChecks

    monkeypatch.setattr(extraction_chapter_processing_service, "is_book_hidden", no)
    monkeypatch.setattr(extraction_chapter_processing_service, "book_is_frozen", frozen_read)
    monkeypatch.setattr(extraction_chapter_processing_service, "cache_set_if_absent", yes)
    monkeypatch.setattr(extraction_chapter_processing_service, "cache_del", no)
    monkeypatch.setattr(
        extraction_chapter_processing_service, "stage_chapter_for_extraction", stage
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service,
        "prepare_chapter_chunks_with_embeddings",
        embed,
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service, "collect_chapter_llm_extraction", extract
    )
    monkeypatch.setattr("app.services.editor_project_service.get_rebuild_run_id", lambda _: None)

    with pytest.raises(StopAfterProviderChecks):
        await extraction_chapter_processing_service._process_chapter_in_generation(
            db,
            book,
            {"number": 1, "text": "Mara waits.", "title": "One"},
        )

    assert db.commits == 4
