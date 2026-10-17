from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services import public_asset_service


def _public_book():
    return SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        public_status="published",
        moderation_status="clean",
        public_share_status="approved",
        source_kind="user_public_share",
        hidden_at=None,
        archived_at=None,
    )


def test_public_chapter_asset_url_is_versioned_and_requires_enabled_base(monkeypatch):
    book = _public_book()
    chapter = SimpleNamespace(id=uuid.uuid4(), content_version=7, public_asset_version=7)
    monkeypatch.setattr(public_asset_service.settings, "DIRECT_PUBLIC_ASSETS_ENABLED", True)
    monkeypatch.setattr(
        public_asset_service.settings,
        "PUBLIC_ASSET_BASE_URL",
        "https://assets.getlorevia.com/content/",
    )

    url = public_asset_service.public_chapter_content_url(book, chapter)

    assert url == (
        f"https://assets.getlorevia.com/content/public-assets/{book.id}/{chapter.id}/v7.txt"
    )


def test_private_book_never_gets_direct_public_asset_url(monkeypatch):
    book = _public_book()
    book.is_public = False
    chapter = SimpleNamespace(id=uuid.uuid4(), content_version=1, public_asset_version=1)
    monkeypatch.setattr(public_asset_service.settings, "DIRECT_PUBLIC_ASSETS_ENABLED", True)
    monkeypatch.setattr(
        public_asset_service.settings,
        "PUBLIC_ASSET_BASE_URL",
        "https://assets.getlorevia.com",
    )

    assert public_asset_service.public_chapter_content_url(book, chapter) is None


@pytest.mark.asyncio
async def test_publish_public_chapter_asset_writes_reader_safe_text(monkeypatch):
    book = _public_book()
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=4,
        content_version=3,
        s3_key="chapters/source.json",
    )
    uploaded = {}
    invalidated = []
    monkeypatch.setattr(public_asset_service.settings, "DIRECT_PUBLIC_ASSETS_ENABLED", True)
    monkeypatch.setattr(
        public_asset_service.settings,
        "PUBLIC_ASSET_BASE_URL",
        "https://assets.getlorevia.com",
    )
    monkeypatch.setattr(
        public_asset_service.storage,
        "download_book",
        lambda _key: b'{"format":"rich_text_v1","text":"Safe text","html":"<script>x</script>"}',
    )

    def upload(key, content, *, cache_max_age):
        uploaded.update(key=key, content=content, cache_max_age=cache_max_age)
        return key

    monkeypatch.setattr(public_asset_service.storage, "upload_public_text_asset", upload)

    async def invalidate(key):
        invalidated.append(key)

    monkeypatch.setattr(public_asset_service, "cache_del", invalidate)

    key = await public_asset_service.publish_public_chapter_asset(book=book, chapter=chapter)

    assert key == f"public-assets/{book.id}/{chapter.id}/v3.txt"
    assert uploaded["content"] == "x"
    assert "script" not in uploaded["content"]
    assert chapter.public_asset_version == 3
    assert invalidated == [f"public:chapter:{book.id}:4"]


def test_direct_url_waits_for_the_current_version_to_be_uploaded(monkeypatch):
    book = _public_book()
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        content_version=4,
        public_asset_version=3,
    )
    monkeypatch.setattr(public_asset_service.settings, "DIRECT_PUBLIC_ASSETS_ENABLED", True)
    monkeypatch.setattr(
        public_asset_service.settings,
        "PUBLIC_ASSET_BASE_URL",
        "https://assets.getlorevia.com",
    )

    assert public_asset_service.public_chapter_content_url(book, chapter) is None


@pytest.mark.asyncio
async def test_revoke_public_book_assets_deletes_every_version(monkeypatch):
    book_id = uuid.uuid4()
    keys = [
        f"public-assets/{book_id}/chapter-1/v1.txt",
        f"public-assets/{book_id}/chapter-1/v2.txt",
    ]
    monkeypatch.setattr(public_asset_service.settings, "DIRECT_PUBLIC_ASSETS_ENABLED", False)
    monkeypatch.setattr(
        public_asset_service.storage,
        "list_object_keys",
        lambda *_args, **_kwargs: keys,
    )

    async def delete(found, *, context):
        assert found == keys
        assert context == "public_asset_revoke"
        return found

    monkeypatch.setattr(public_asset_service, "delete_storage_keys_best_effort", delete)

    assert await public_asset_service.revoke_public_book_assets(book_id) == 2


@pytest.mark.asyncio
async def test_strict_revocation_fails_closed_when_any_asset_delete_fails(monkeypatch):
    book_id = uuid.uuid4()
    keys = [
        f"public-assets/{book_id}/chapter-1/v1.txt",
        f"public-assets/{book_id}/chapter-2/v1.txt",
    ]
    monkeypatch.setattr(
        public_asset_service.storage,
        "list_object_keys",
        lambda *_args, **_kwargs: keys,
    )

    async def partially_delete(_found, *, context):
        assert context == "public_asset_revoke"
        return keys[:1]

    monkeypatch.setattr(
        public_asset_service,
        "delete_storage_keys_best_effort",
        partially_delete,
    )

    with pytest.raises(public_asset_service.PublicAssetRevocationError):
        await public_asset_service.revoke_public_book_assets(book_id, strict=True)


@pytest.mark.asyncio
async def test_successful_revocation_clears_persisted_asset_readiness(monkeypatch):
    book_id = uuid.uuid4()
    statements = []

    class _Db:
        async def execute(self, statement):
            statements.append(statement)

    monkeypatch.setattr(
        public_asset_service.storage,
        "list_object_keys",
        lambda *_args, **_kwargs: [],
    )

    assert (
        await public_asset_service.revoke_public_book_assets(
            book_id,
            db=_Db(),
            strict=True,
        )
        == 0
    )
    assert len(statements) == 1
    assert "public_asset_version" in str(statements[0])


@pytest.mark.asyncio
async def test_failed_public_asset_replacement_preserves_existing_versions(monkeypatch):
    book = _public_book()
    chapters = [
        SimpleNamespace(id=uuid.uuid4(), content_version=1),
        SimpleNamespace(id=uuid.uuid4(), content_version=2),
    ]
    db = SimpleNamespace()

    class _Scalars:
        def all(self):
            return chapters

    class _Result:
        def scalars(self):
            return _Scalars()

    async def execute(_statement):
        return _Result()

    db.execute = execute

    async def commit():
        return None

    db.commit = commit
    monkeypatch.setattr(public_asset_service.settings, "DIRECT_PUBLIC_ASSETS_ENABLED", True)
    monkeypatch.setattr(
        public_asset_service.settings,
        "PUBLIC_ASSET_BASE_URL",
        "https://assets.getlorevia.com",
    )

    async def publish(*, book, chapter):
        if chapter is chapters[0]:
            return f"public-assets/{book.id}/{chapter.id}/v1.txt"
        return None

    monkeypatch.setattr(public_asset_service, "publish_public_chapter_asset", publish)

    def unexpected_list(*_args, **_kwargs):
        raise AssertionError("existing assets must not be pruned after a partial failure")

    monkeypatch.setattr(public_asset_service.storage, "list_object_keys", unexpected_list)

    assert await public_asset_service.publish_public_book_assets(db, book=book) == 1
