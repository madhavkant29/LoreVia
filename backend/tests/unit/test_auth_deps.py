from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.api.deps.auth import get_current_user


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
