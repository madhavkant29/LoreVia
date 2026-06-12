import pytest

from app.utils import storage_utils


@pytest.mark.asyncio
async def test_delete_storage_key_best_effort_deletes_key(monkeypatch):
    deleted: list[str] = []

    monkeypatch.setattr(storage_utils, "delete_object", lambda key: deleted.append(key))

    assert await storage_utils.delete_storage_key_best_effort("covers/old.png", context="cover") is True
    assert deleted == ["covers/old.png"]


@pytest.mark.asyncio
async def test_delete_storage_keys_best_effort_dedupes_and_skips_empty(monkeypatch):
    deleted: list[str] = []

    monkeypatch.setattr(storage_utils, "delete_object", lambda key: deleted.append(key))

    result = await storage_utils.delete_storage_keys_best_effort(
        ["world/one.txt", None, "world/one.txt", "", "world/two.txt"],
        context="world",
    )

    assert result == ["world/one.txt", "world/two.txt"]
    assert deleted == ["world/one.txt", "world/two.txt"]


@pytest.mark.asyncio
async def test_delete_storage_key_best_effort_swallows_storage_errors(monkeypatch):
    def _raise(_key):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(storage_utils, "delete_object", _raise)

    assert await storage_utils.delete_storage_key_best_effort("forum/old.png", context="forum") is False
