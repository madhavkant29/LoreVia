import uuid

import pytest

from app.services.supabase_auth_service import delete_supabase_auth_user


@pytest.mark.asyncio
async def test_delete_supabase_auth_user_requires_configuration(monkeypatch):
    monkeypatch.setattr("app.services.supabase_auth_service.settings.SUPABASE_URL", None, raising=False)
    monkeypatch.setattr("app.services.supabase_auth_service.settings.SUPABASE_SERVICE_KEY", None, raising=False)

    result = await delete_supabase_auth_user(uuid.UUID("00000000-0000-0000-0000-000000000123"))

    assert result == {"configured": False, "deleted": False, "followup_required": True}


@pytest.mark.asyncio
async def test_delete_supabase_auth_user_success(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 204

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def delete(self, url, headers=None):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.services.supabase_auth_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient())
    monkeypatch.setattr("app.services.supabase_auth_service.settings.SUPABASE_URL", "https://example.supabase.co", raising=False)
    monkeypatch.setattr("app.services.supabase_auth_service.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False)

    result = await delete_supabase_auth_user("sb-user-1")

    assert result == {"configured": True, "deleted": True, "followup_required": False}
    assert captured["url"] == "https://example.supabase.co/auth/v1/admin/users/sb-user-1"
    assert captured["headers"]["Authorization"] == "Bearer service-key"
