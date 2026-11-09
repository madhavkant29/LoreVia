import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_chapter_processing_service


@pytest.mark.parametrize("diagnostic_persistence_failure", [False, True])
@pytest.mark.parametrize("rebuild_run_id", [None, "rebuild-run"])
async def test_chapter_extraction_preserves_provider_error_when_diagnostics_fail(
    monkeypatch,
    diagnostic_persistence_failure,
    rebuild_run_id,
):
    class StopAfterProviderChecks(Exception):
        pass

    class Db:
        transaction_open = False
        commits = 0

        async def commit(self):
            self.commits += 1
            if diagnostic_persistence_failure and self.commits == 5:
                raise OSError("diagnostic commit failed")
            self.transaction_open = False

        async def rollback(self):
            if diagnostic_persistence_failure:
                raise OSError("diagnostic rollback failed")
            self.transaction_open = False

        async def execute(self, _statement):
            self.transaction_open = True
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db = Db()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        is_editor_project=bool(rebuild_run_id),
        writer_workspace={},
    )
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        title="One",
        analysis_state={"source_integrity": {"text_present": True}},
    )

    async def no(*_args, **_kwargs):
        return False

    async def yes(*_args, **_kwargs):
        return True

    async def frozen_read(_db, _book_id):
        db.transaction_open = True
        return False

    async def stage(*_args, **kwargs):
        assert kwargs["rebuild_existing_chapter"] is bool(rebuild_run_id)
        return chapter

    async def embed(*_args, **_kwargs):
        assert db.transaction_open is False
        return SimpleNamespace(texts=["chunk"])

    async def extract(*_args, **kwargs):
        assert db.transaction_open is False
        assert kwargs["chunks"] == ["Mara waits."]
        await kwargs["on_incomplete_batch"](
            {
                "complete": False,
                "failure_stage": "character_discovery",
                "batch_outcomes": [
                    {"batch_index": 1, "status": "failed", "error_type": "TimeoutError"}
                ],
            }
        )
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
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda _: rebuild_run_id
    )

    with pytest.raises(StopAfterProviderChecks):
        await extraction_chapter_processing_service._process_chapter_in_generation(
            db,
            book,
            {"number": 1, "text": "Mara waits.", "title": "One"},
            rebuild_run_id=rebuild_run_id,
        )

    assert db.commits == 5
    if not diagnostic_persistence_failure:
        assert chapter.analysis_state["source_integrity"]["extraction_attempt"] == {
            "complete": False,
            "failure_stage": "character_discovery",
            "batch_outcomes": [
                {"batch_index": 1, "status": "failed", "error_type": "TimeoutError"}
            ],
        }


@pytest.mark.asyncio
async def test_character_embeddings_run_before_chapter_records_are_replaced(monkeypatch):
    class StopAtEmbedding(Exception):
        pass

    class Db:
        transaction_open = False

        async def commit(self):
            self.transaction_open = False

        async def execute(self, _statement):
            self.transaction_open = True
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db = Db()
    book = SimpleNamespace(
        id=uuid.uuid4(), user_id=uuid.uuid4(), is_editor_project=False, writer_workspace={}
    )
    chapter = SimpleNamespace(id=uuid.uuid4(), title="One", analysis_state={})

    async def no(*_args, **_kwargs):
        return False

    async def yes(*_args, **_kwargs):
        return True

    async def frozen_read(_db, _book_id):
        db.transaction_open = True
        return False

    async def stage(*_args, **_kwargs):
        return chapter

    async def chunk_embeddings(*_args, **_kwargs):
        assert db.transaction_open is False
        return SimpleNamespace(texts=["chunk"])

    async def extract(*_args, **_kwargs):
        assert db.transaction_open is False
        return SimpleNamespace(aggregated_character_entities=[{"name": "Mara", "evidence": {}}])

    async def character_embeddings(candidates, **kwargs):
        assert db.transaction_open is False
        assert [item["name"] for item in candidates] == ["Mara"]
        raise StopAtEmbedding

    async def unexpected_replace(*_args, **_kwargs):
        raise AssertionError("Chapter rows must not be replaced before embeddings finish")

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
        chunk_embeddings,
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service, "collect_chapter_llm_extraction", extract
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service,
        "precompute_chapter_character_embeddings",
        character_embeddings,
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service,
        "replace_chapter_extraction_records",
        unexpected_replace,
    )
    monkeypatch.setattr("app.services.editor_project_service.get_rebuild_run_id", lambda _: None)

    with pytest.raises(StopAtEmbedding):
        await extraction_chapter_processing_service._process_chapter_in_generation(
            db, book, {"number": 1, "text": "Mara waits.", "title": "One"}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("freeze_call", [4, 5])
async def test_freeze_during_character_embedding_or_resolution_preserves_chapter_records(
    monkeypatch, freeze_call
):
    class Db:
        transaction_open = False
        rolled_back = False

        async def commit(self):
            self.transaction_open = False

        async def rollback(self):
            self.rolled_back = True
            self.transaction_open = False

        async def execute(self, _statement):
            self.transaction_open = True
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db = Db()
    book = SimpleNamespace(
        id=uuid.uuid4(), user_id=uuid.uuid4(), is_editor_project=False, writer_workspace={}
    )
    chapter = SimpleNamespace(id=uuid.uuid4(), title="One", analysis_state={})
    freeze_reads = 0
    replaced = False

    async def no(*_args, **_kwargs):
        return False

    async def yes(*_args, **_kwargs):
        return True

    async def frozen_read(_db, _book_id):
        nonlocal freeze_reads
        freeze_reads += 1
        db.transaction_open = True
        return freeze_reads == freeze_call

    async def stage(*_args, **_kwargs):
        return chapter

    async def chunk_embeddings(*_args, **_kwargs):
        assert db.transaction_open is False
        return SimpleNamespace(texts=["chunk"])

    async def extract(*_args, **_kwargs):
        return SimpleNamespace(
            aggregated_character_entities=[{"name": "Mara", "evidence": {}}],
            pending_relationships=[],
            raw_character_entities=[],
        )

    async def character_embeddings(_candidates, **_kwargs):
        assert db.transaction_open is False
        return [[0.1] * 1536]

    async def load_signatures(*_args, **_kwargs):
        db.transaction_open = True
        return set()

    async def replace_chunks(*_args, **_kwargs):
        nonlocal replaced
        replaced = True
        db.transaction_open = True

    async def replace_records(*_args, **_kwargs):
        db.transaction_open = True
        return set()

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
        chunk_embeddings,
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service, "collect_chapter_llm_extraction", extract
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service,
        "precompute_chapter_character_embeddings",
        character_embeddings,
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service,
        "load_persisted_relationship_signatures",
        load_signatures,
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service, "replace_chapter_chunks", replace_chunks
    )
    monkeypatch.setattr(
        extraction_chapter_processing_service, "replace_chapter_extraction_records", replace_records
    )
    monkeypatch.setattr("app.services.editor_project_service.get_rebuild_run_id", lambda _: None)

    assert (
        await extraction_chapter_processing_service._process_chapter_in_generation(
            db, book, {"number": 1, "text": "Mara waits.", "title": "One"}
        )
        is False
    )
    assert freeze_reads == freeze_call
    assert replaced is (freeze_call == 5)
    assert db.rolled_back is (freeze_call == 5)
    assert db.transaction_open is False
