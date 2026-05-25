from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.api.deps.auth import (
    _claim_version,
    _decode_access_payload,
    _decode_refresh_payload,
    _load_user_from_claims,
    get_admin,
    get_current_user,
)


@pytest.mark.parametrize("payload", [{}, {"ver": None}, {"ver": "abc"}])
def test_claim_version_rejects_missing_or_invalid_values(payload):
    with pytest.raises(HTTPException) as exc_info:
        _claim_version(payload)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


def test_decode_access_payload_only_accepts_access_tokens(monkeypatch):
    monkeypatch.setattr("app.api.deps.auth.decode_token", lambda token: {"type": "access", "sub": "user"} if token == "good" else {"type": "refresh"})

    assert _decode_access_payload("good") == {"type": "access", "sub": "user"}
    assert _decode_access_payload("wrong-type") is None
    assert _decode_access_payload(None) is None


def test_decode_refresh_payload_swallows_decode_errors(monkeypatch):
    def fake_decode(_token: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.api.deps.auth.decode_token", fake_decode)

    assert _decode_refresh_payload("bad-token") is None


@pytest.mark.asyncio
async def test_get_current_user_falls_back_to_refresh_when_access_user_is_missing(monkeypatch):
    request = Request({"type": "http", "headers": []})
    response = Response()
    user = SimpleNamespace(id="user-id", username="fallback")

    def fake_get_auth_token(_request, bearer_token=None, cookie_name="lorevia_access_token"):
        if cookie_name == "lorevia_refresh_token":
            return "refresh-token"
        return "access-token"

    async def fake_load_user_from_claims(user_id: str, claimed_version: int, db):
        if user_id == "stale-user":
            raise HTTPException(401, "User not found")
        return user

    async def fake_refresh_session_active(*args, **kwargs):
        return True

    monkeypatch.setattr("app.api.deps.auth.get_auth_token", fake_get_auth_token)
    monkeypatch.setattr("app.api.deps.auth._decode_access_payload", lambda token: {"sub": "stale-user", "ver": 1, "type": "access"} if token == "access-token" else None)
    monkeypatch.setattr("app.api.deps.auth._decode_refresh_payload", lambda token: {"sub": "valid-user", "ver": 1, "sid": "session-1", "type": "refresh"} if token == "refresh-token" else None)
    monkeypatch.setattr("app.api.deps.auth._load_user_from_claims", fake_load_user_from_claims)
    monkeypatch.setattr("app.api.deps.auth.refresh_session_active", fake_refresh_session_active)

    set_access_cookie_calls: list[str] = []

    def fake_set_access_cookie(_response, access_token: str):
        set_access_cookie_calls.append(access_token)

    monkeypatch.setattr("app.api.deps.auth.set_access_cookie", fake_set_access_cookie)

    result = await get_current_user(request, response, credentials=None, db=SimpleNamespace())

    assert result is user
    assert len(set_access_cookie_calls) == 1


@pytest.mark.asyncio
async def test_get_current_user_rejects_refresh_tokens_without_session_id(monkeypatch):
    request = Request({"type": "http", "headers": []})
    response = Response()

    monkeypatch.setattr(
        "app.api.deps.auth.get_auth_token",
        lambda _request, bearer_token=None, cookie_name="lorevia_access_token": "refresh-token" if cookie_name == "lorevia_refresh_token" else None,
    )
    monkeypatch.setattr("app.api.deps.auth._decode_access_payload", lambda token: None)
    monkeypatch.setattr(
        "app.api.deps.auth._decode_refresh_payload",
        lambda token: {"sub": "valid-user", "ver": 1, "type": "refresh"} if token == "refresh-token" else None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request, response, credentials=None, db=SimpleNamespace())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_refresh_sessions_without_resetting_cookie(monkeypatch):
    request = Request({"type": "http", "headers": []})
    response = Response()
    user = SimpleNamespace(id="user-id", username="inactive")

    monkeypatch.setattr(
        "app.api.deps.auth.get_auth_token",
        lambda _request, bearer_token=None, cookie_name="lorevia_access_token": "refresh-token" if cookie_name == "lorevia_refresh_token" else None,
    )
    monkeypatch.setattr("app.api.deps.auth._decode_access_payload", lambda token: None)
    monkeypatch.setattr(
        "app.api.deps.auth._decode_refresh_payload",
        lambda token: {"sub": "valid-user", "ver": 3, "sid": "session-9", "type": "refresh"} if token == "refresh-token" else None,
    )

    async def fake_load_user_from_claims(user_id: str, claimed_version: int, db):
        return user

    monkeypatch.setattr("app.api.deps.auth._load_user_from_claims", fake_load_user_from_claims)

    async def fake_refresh_session_active(*args, **kwargs):
        return False

    monkeypatch.setattr("app.api.deps.auth.refresh_session_active", fake_refresh_session_active)

    set_access_cookie_calls: list[str] = []
    monkeypatch.setattr("app.api.deps.auth.set_access_cookie", lambda _response, access_token: set_access_cookie_calls.append(access_token))

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request, response, credentials=None, db=SimpleNamespace())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Session expired. Please sign in again."
    assert set_access_cookie_calls == []


@pytest.mark.asyncio
async def test_load_user_from_claims_uses_database_token_version():
    user = SimpleNamespace(id="user-id", token_version=4)

    class _FakeDB:
        async def get(self, _model, _user_id):
            return user

    result = await _load_user_from_claims("00000000-0000-0000-0000-000000000001", 4, _FakeDB())

    assert result is user


@pytest.mark.asyncio
async def test_load_user_from_claims_rejects_stale_token_version():
    user = SimpleNamespace(id="user-id", token_version=5)

    class _FakeDB:
        async def get(self, _model, _user_id):
            return user

    with pytest.raises(HTTPException) as exc_info:
        await _load_user_from_claims("00000000-0000-0000-0000-000000000001", 4, _FakeDB())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Session expired. Please sign in again."


@pytest.mark.asyncio
async def test_get_admin_rejects_non_admin_users(monkeypatch):
    request = Request({"type": "http", "headers": []})

    class _FakeDB:
        def add(self, _event):
            return None

        async def commit(self):
            return None

    async def fake_get_active_admin_principal(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.api.deps.auth.get_active_admin_principal", fake_get_active_admin_principal)

    with pytest.raises(HTTPException) as exc_info:
        await get_admin(request=request, current_user=SimpleNamespace(id="00000000-0000-0000-0000-000000000001"), db=_FakeDB())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin only"
