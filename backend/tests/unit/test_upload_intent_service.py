import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import upload_intent_service


class _BookStorageResult:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


def _intent(*, created_at: datetime | None = None):
    intent = upload_intent_service.build_book_upload_intent(
        book_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        filename="../draft.txt",
        has_cover=True,
        cover_suffix="PNG!",
    )
    if created_at is None:
        return intent
    return upload_intent_service.BookUploadIntent(
        intent_key=intent.intent_key,
        book_id=intent.book_id,
        user_id=intent.user_id,
        source_key=intent.source_key,
        cover_key=intent.cover_key,
        created_at=created_at,
    )


def test_upload_intent_round_trips_and_scopes_object_keys():
    intent = _intent()
    parsed = upload_intent_service.parse_upload_intent(
        intent.intent_key,
        upload_intent_service.serialize_upload_intent(intent),
    )

    assert parsed == intent
    assert parsed.source_key.endswith("/draft.txt")
    assert parsed.cover_key and parsed.cover_key.endswith(".png")


def test_upload_intent_rejects_an_object_outside_its_book_scope():
    intent = _intent()
    raw = upload_intent_service.serialize_upload_intent(intent).replace(
        intent.source_key.encode(),
        b"books/another-user/stolen.txt",
    )

    with pytest.raises(ValueError, match="outside its book scope"):
        upload_intent_service.parse_upload_intent(intent.intent_key, raw)


async def test_reconciler_deletes_abandoned_objects_after_grace(monkeypatch):
    now = datetime.now(UTC)
    intent = _intent(created_at=now - timedelta(days=2))
    monkeypatch.setattr(
        upload_intent_service.storage,
        "list_object_keys",
        lambda *_args, **_kwargs: [intent.intent_key],
    )
    monkeypatch.setattr(
        upload_intent_service.storage,
        "download_book",
        lambda _key: upload_intent_service.serialize_upload_intent(intent),
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(upload_intent_service, "delete_storage_key_best_effort", cleanup)
    db = SimpleNamespace(execute=AsyncMock(return_value=_BookStorageResult(None)))

    result = await upload_intent_service.reconcile_stale_upload_intents(db, now=now)

    assert result["reconciled"] == 1
    assert [call.args[0] for call in cleanup.await_args_list] == [
        intent.source_key,
        intent.cover_key,
        intent.intent_key,
    ]


async def test_reconciler_keeps_objects_referenced_by_committed_book(monkeypatch):
    now = datetime.now(UTC)
    intent = _intent(created_at=now - timedelta(days=2))
    monkeypatch.setattr(
        upload_intent_service.storage,
        "list_object_keys",
        lambda *_args, **_kwargs: [intent.intent_key],
    )
    monkeypatch.setattr(
        upload_intent_service.storage,
        "download_book",
        lambda _key: upload_intent_service.serialize_upload_intent(intent),
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(upload_intent_service, "delete_storage_key_best_effort", cleanup)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_BookStorageResult((intent.source_key, intent.cover_key)))
    )

    result = await upload_intent_service.reconcile_stale_upload_intents(db, now=now)

    assert result["committed"] == 1
    cleanup.assert_awaited_once_with(intent.intent_key, context="book_upload_intent")
