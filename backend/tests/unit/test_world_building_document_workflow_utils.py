from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.intelligence import WorldBuildingDocument
from app.utils import world_building_document_workflow_utils


class _FakeDB:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.flushes = 0

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def flush(self):
        self.flushes += 1


@pytest.fixture(autouse=True)
def _stub_world_analysis_staleness(monkeypatch):
    async def no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        world_building_document_workflow_utils,
        "mark_book_world_analysis_stale",
        no_op,
    )
    monkeypatch.setattr(
        world_building_document_workflow_utils,
        "mark_related_series_world_analysis_stale",
        no_op,
    )
    monkeypatch.setattr(world_building_document_workflow_utils, "mark_book_cache_dirty", no_op)
    monkeypatch.setattr(
        world_building_document_workflow_utils, "mark_user_dashboard_cache_dirty", no_op
    )


@pytest.mark.asyncio
async def test_create_world_building_documents_uploads_active_documents(monkeypatch):
    async def sync_elements(_db, _book, **_kwargs):
        return []

    monkeypatch.setattr(
        world_building_document_workflow_utils, "sync_world_document_elements", sync_elements
    )
    monkeypatch.setattr(
        world_building_document_workflow_utils,
        "upload_binary",
        lambda key, _payload, _content_type: f"stored:{key}",
    )
    db = _FakeDB()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    created = await world_building_document_workflow_utils.create_world_building_documents(
        db,
        book=book,
        user_id=uuid.uuid4(),
        documents=[
            {"title": " Atlas ", "source_name": " atlas.md ", "text": "Glass Harbor lore"},
            {"title": "Blank", "text": "   "},
        ],
    )

    assert len(created) == 1
    assert isinstance(created[0], WorldBuildingDocument)
    assert created[0].title == "Atlas"
    assert created[0].source_name == "atlas.md"
    assert created[0].s3_key.startswith("stored:worldbuilding/")
    assert db.added == created
    assert db.flushes == 1


@pytest.mark.asyncio
async def test_update_world_building_document_replaces_storage_and_requires_text(monkeypatch):
    async def sync_elements(_db, _book, **_kwargs):
        return []

    monkeypatch.setattr(
        world_building_document_workflow_utils, "sync_world_document_elements", sync_elements
    )
    monkeypatch.setattr(
        world_building_document_workflow_utils,
        "upload_binary",
        lambda key, _payload, _content_type: f"stored:{key}",
    )
    db = _FakeDB()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    document = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        title="Old",
        word_count=0,
        s3_key="old-key",
        is_active=False,
        archived_at="archived",
        updated_at=None,
    )

    with pytest.raises(world_building_document_workflow_utils.HTTPException):
        await world_building_document_workflow_utils.update_world_building_document(
            db,
            book=book,
            document=document,
            title="Ignored",
            text="   ",
        )

    updated = await world_building_document_workflow_utils.update_world_building_document(
        db,
        book=book,
        document=document,
        title=" New Atlas ",
        text="One two three",
        html="<p>One two three</p>",
    )

    assert updated is document
    assert document.title == "New Atlas"
    assert document.word_count == 3
    assert document.s3_key.startswith("stored:worldbuilding/")
    assert document.is_active is True
    assert document.archived_at is None
    assert db.flushes == 1


@pytest.mark.asyncio
async def test_delete_world_building_document_validates_book_ownership(monkeypatch):
    async def sync_elements(_db, _book, **_kwargs):
        return []

    monkeypatch.setattr(
        world_building_document_workflow_utils, "sync_world_document_elements", sync_elements
    )
    db = _FakeDB()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    document = SimpleNamespace(id=uuid.uuid4(), book_id=uuid.uuid4())

    with pytest.raises(world_building_document_workflow_utils.HTTPException):
        await world_building_document_workflow_utils.delete_world_building_document(
            db,
            book=book,
            document=document,
        )

    document.book_id = book.id
    await world_building_document_workflow_utils.delete_world_building_document(
        db,
        book=book,
        document=document,
    )

    assert db.deleted == [document]
    assert db.flushes == 1
