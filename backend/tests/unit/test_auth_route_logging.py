from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest
from fastapi import Response
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.routes.auth import oauth_supabase, refresh
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.schemas.auth import RefreshBody, SupabaseOAuthBody


@pytest.mark.asyncio
async def test_supabase_oauth_failure_does_not_log_response_body(monkeypatch, caplog):
    class FakeResponse:
        status_code = 401
        text = "error: invalid token secret=top-secret-value"

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return FakeResponse()

    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_URL", "https://supabase.example.com", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    body = SupabaseOAuthBody(token="user-token", accepted_terms=True, device_id="device-logging-1234567890")
    response = Response()

    with caplog.at_level("WARNING", logger="lorevia.auth"):
        with pytest.raises(HTTPException) as exc_info:
            await oauth_supabase(body=body, response=response, db=object(), _=None)

    assert exc_info.value.status_code == 401
    assert "top-secret-value" not in caplog.text
    assert "Supabase OAuth verification failed" in caplog.text


@pytest.mark.asyncio
async def test_refresh_route_uses_canonical_local_user_for_supabase_subject(monkeypatch):
    local_user_id = uuid.uuid4()
    supabase_auth_id = uuid.uuid4()
    user = SimpleNamespace(
        id=local_user_id,
        email="supabase-refresh@lorevia.app",
        username="supabaserefresh",
        tier="free",
        reading_mode="casual",
        daily_word_goal=1000,
        today_word_count=0,
        last_login_at=None,
        login_streak_days=0,
        longest_login_streak_days=0,
        email_verified_at=datetime.now(UTC),
        messaging_permission="anyone",
        created_at=datetime.now(UTC),
        token_version=4,
    )

    class FakeDB:
        async def commit(self):
            return None

        async def refresh(self, _user):
            return None

    async def fake_get_user_for_auth_subject(_db, subject: str):
        assert subject == str(supabase_auth_id)
        return user

    async def fake_refresh_session_active(*args, **kwargs):
        return True

    async def fake_revoke_refresh_session(*args, **kwargs):
        return None

    async def fake_record_login_activity(*args, **kwargs):
        return None

    captured: dict[str, str] = {}

    async def fake_mint_token_pair(resolved_user, db=None):
        assert resolved_user is user
        return (
            {"id": str(resolved_user.id)},
            create_access_token(str(resolved_user.id), version=resolved_user.token_version),
            create_refresh_token(str(resolved_user.id), version=resolved_user.token_version, session_id="new-session"),
        )

    def fake_user_response_with_cookies(_response, user_out, access_token: str, refresh_token: str):
        captured["access"] = access_token
        captured["refresh"] = refresh_token
        return user_out

    monkeypatch.setattr(
        "app.api.v1.routes.auth.decode_token",
        lambda token: {
            "sub": str(supabase_auth_id),
            "type": "refresh",
            "ver": user.token_version,
            "sid": "legacy-session",
        } if token == "legacy-refresh-token" else None,
    )
    monkeypatch.setattr("app.api.v1.routes.auth.get_user_for_auth_subject", fake_get_user_for_auth_subject)
    monkeypatch.setattr("app.api.v1.routes.auth.refresh_session_active", fake_refresh_session_active)
    monkeypatch.setattr("app.api.v1.routes.auth.revoke_refresh_session", fake_revoke_refresh_session)
    monkeypatch.setattr("app.api.v1.routes.auth._record_login_activity", fake_record_login_activity)
    monkeypatch.setattr("app.api.v1.routes.auth._mint_token_pair", fake_mint_token_pair)
    monkeypatch.setattr("app.api.v1.routes.auth._user_response_with_cookies", fake_user_response_with_cookies)

    result = await refresh(
        request=Request({"type": "http", "method": "POST", "headers": []}),
        response=Response(),
        body=RefreshBody(refresh_token="legacy-refresh-token"),
        db=FakeDB(),
        _=None,
    )

    assert result == {"id": str(local_user_id)}
    access_payload = decode_token(captured["access"])
    refresh_payload = decode_token(captured["refresh"])
    assert access_payload is not None
    assert refresh_payload is not None
    assert access_payload["sub"] == str(local_user_id)
    assert refresh_payload["sub"] == str(local_user_id)
