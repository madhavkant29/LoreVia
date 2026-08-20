import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from app.api.v1.routes.auth import (
    login,
    oauth_supabase,
    refresh,
)
from app.api.v1.routes.auth_shared import (
    _record_login_activity,
    _schedule_trial_email_events_best_effort,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.schemas.auth import LoginBody, RefreshBody, SupabaseOAuthBody


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


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

    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL",
        "https://supabase.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    body = SupabaseOAuthBody(
        token="user-token", accepted_terms=True, device_id="device-logging-1234567890"
    )
    response = Response()

    with caplog.at_level("WARNING", logger="lorevia.auth"):
        with pytest.raises(HTTPException) as exc_info:
            await oauth_supabase(
                request=Request({"type": "http", "method": "POST", "headers": []}),
                body=body,
                response=response,
                db=object(),
                _=None,
            )

    assert exc_info.value.status_code == 401
    assert "top-secret-value" not in caplog.text
    assert "Supabase OAuth verification failed" in caplog.text
    verification_records = [
        record
        for record in caplog.records
        if record.getMessage() == "Supabase OAuth verification failed"
    ]
    assert verification_records
    assert all(not hasattr(record, "response_text") for record in verification_records)


@pytest.mark.asyncio
async def test_trial_email_schedule_failure_does_not_block_auth(monkeypatch, caplog):
    class FakeDB:
        def begin_nested(self):
            return _AsyncContext()

    async def fake_schedule(*_args, **_kwargs):
        raise SQLAlchemyError("trial_email_events unavailable")

    monkeypatch.setattr("app.api.v1.routes.auth_shared.schedule_trial_email_events", fake_schedule)

    with caplog.at_level("WARNING", logger="lorevia.auth"):
        await _schedule_trial_email_events_best_effort(FakeDB(), SimpleNamespace(id="user-1"))

    assert "trial_email_schedule_failed_during_auth" in caplog.text


@pytest.mark.asyncio
async def test_trial_email_schedule_unexpected_failure_propagates(monkeypatch):
    class FakeDB:
        def begin_nested(self):
            return _AsyncContext()

    async def fake_schedule(*_args, **_kwargs):
        raise RuntimeError("programming error")

    monkeypatch.setattr("app.api.v1.routes.auth_shared.schedule_trial_email_events", fake_schedule)

    with pytest.raises(RuntimeError, match="programming error"):
        await _schedule_trial_email_events_best_effort(FakeDB(), SimpleNamespace(id="user-1"))


@pytest.mark.asyncio
async def test_login_activity_cache_failure_does_not_block_auth(monkeypatch, caplog):
    user = SimpleNamespace(
        id="user-1",
        last_login_at=None,
        last_login_date=None,
        login_streak_days=0,
        longest_login_streak_days=0,
    )

    async def fake_record_login_activity_row(*_args, **_kwargs):
        return None

    async def fake_mark_cache_dirty(*_args, **_kwargs):
        raise RedisError("redis unavailable")

    monkeypatch.setattr(
        "app.api.v1.routes.auth_shared.record_login_activity_row", fake_record_login_activity_row
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth_shared.mark_user_dashboard_cache_dirty", fake_mark_cache_dirty
    )

    with caplog.at_level("WARNING", logger="lorevia.auth"):
        await _record_login_activity(object(), user)

    assert "login_activity_cache_invalidation_failed" in caplog.text
    assert user.last_login_date is not None


@pytest.mark.asyncio
async def test_login_activity_unexpected_cache_failure_propagates(monkeypatch):
    user = SimpleNamespace(
        id="user-1",
        last_login_at=None,
        last_login_date=None,
        login_streak_days=0,
        longest_login_streak_days=0,
    )

    async def fake_record_login_activity_row(*_args, **_kwargs):
        return None

    async def fake_mark_cache_dirty(*_args, **_kwargs):
        raise RuntimeError("programming error")

    monkeypatch.setattr(
        "app.api.v1.routes.auth_shared.record_login_activity_row", fake_record_login_activity_row
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth_shared.mark_user_dashboard_cache_dirty", fake_mark_cache_dirty
    )

    with pytest.raises(RuntimeError, match="programming error"):
        await _record_login_activity(object(), user)


@pytest.mark.asyncio
async def test_login_unknown_email_runs_dummy_password_verification(monkeypatch):
    class _Result:
        def scalar(self):
            return None

    class FakeDB:
        async def execute(self, *_args, **_kwargs):
            return _Result()

    verified_hashes: list[str] = []

    def fake_verify_password(_plain: str, hashed: str) -> bool:
        verified_hashes.append(hashed)
        return False

    monkeypatch.setattr("app.api.v1.routes.auth.verify_password", fake_verify_password)

    with pytest.raises(HTTPException) as exc_info:
        await login(
            request=Request({"type": "http", "method": "POST", "headers": []}),
            body=LoginBody(
                email="missing@example.com",
                password="wrong-password",
                device_id="missing-email-device01",
            ),
            response=Response(),
            db=FakeDB(),
            _=None,
        )

    assert exc_info.value.status_code == 401
    assert verified_hashes == [DUMMY_PASSWORD_HASH]


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

    async def fake_consume_refresh_session(*args, **kwargs):
        return True

    async def fake_record_login_activity(*args, **kwargs):
        return None

    captured: dict[str, str] = {}

    async def fake_mint_token_pair(resolved_user, db=None):
        assert resolved_user is user
        return (
            {"id": str(resolved_user.id)},
            create_access_token(str(resolved_user.id), version=resolved_user.token_version),
            create_refresh_token(
                str(resolved_user.id), version=resolved_user.token_version, session_id="new-session"
            ),
        )

    def fake_user_response_with_cookies(
        _response, user_out, access_token: str, refresh_token: str, **_kwargs
    ):
        captured["access"] = access_token
        captured["refresh"] = refresh_token
        return user_out

    monkeypatch.setattr(
        "app.api.v1.routes.auth.decode_token",
        lambda token: (
            {
                "sub": str(supabase_auth_id),
                "type": "refresh",
                "ver": user.token_version,
                "sid": "legacy-session",
            }
            if token == "legacy-refresh-token"
            else None
        ),
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.get_user_for_auth_subject", fake_get_user_for_auth_subject
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.consume_refresh_session", fake_consume_refresh_session
    )
    monkeypatch.setattr("app.api.v1.routes.auth._record_login_activity", fake_record_login_activity)
    monkeypatch.setattr("app.api.v1.routes.auth._mint_token_pair", fake_mint_token_pair)
    monkeypatch.setattr(
        "app.api.v1.routes.auth._user_response_with_cookies", fake_user_response_with_cookies
    )

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
