from datetime import UTC, datetime
import uuid

import pytest

from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_register_and_login(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@lorevia.app", "username": "new", "password": "TestPass123!@#", "accepted_terms": True},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@lorevia.app"
    assert body["username"] == "new"
    assert "access_token" not in body
    assert "refresh_token" not in body

    r2 = await client.post("/api/v1/auth/login", json={"email": "new@lorevia.app", "password": "TestPass123!@#"})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["email"] == "new@lorevia.app"
    assert "access_token" not in body2
    assert "refresh_token" not in body2
    access_token = create_access_token(str(r.json()["id"]))
    me = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={access_token}"})
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_refresh_and_logout_use_cookies(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "cookie@lorevia.app", "username": "cookie", "password": "SafePass123!@#", "accepted_terms": True},
    )
    assert register_response.status_code == 201
    user_id = str(register_response.json()["id"])
    refresh_token = create_refresh_token(user_id, session_id="test-session")
    access_token = create_access_token(user_id)

    async def fake_session_active(*args, **kwargs):
        return True

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.api.v1.routes.auth.refresh_session_active", fake_session_active)
        refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    refresh_body = refreshed.json()
    assert "access_token" not in refresh_body
    assert "refresh_token" not in refresh_body

    me = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={access_token}"})
    assert me.status_code == 200

    logout = await client.post("/api/v1/auth/logout", headers={"Cookie": f"lorevia_access_token={access_token}"})
    assert logout.status_code == 200

    after_logout = await client.get("/api/v1/auth/me")
    assert after_logout.status_code in (401, 403)


@pytest.mark.asyncio
async def test_username_update_can_recover_from_refresh_cookie_only(client, db):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh-only@lorevia.app", "username": "refreshonly", "password": "SafePass123!@#", "accepted_terms": True},
    )
    assert register_response.status_code == 201
    user_id = str(register_response.json()["id"])
    user = await db.get(User, uuid.UUID(user_id))
    assert user is not None
    user.username = None
    await db.commit()
    refresh_token = create_refresh_token(user_id, session_id="refresh-only-session")

    async def fake_session_active(*args, **kwargs):
        return True

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.api.deps.auth.refresh_session_active", fake_session_active)
        response = await client.patch(
            "/api/v1/auth/me/username?username=refreshonly2",
            headers={"Cookie": f"lorevia_refresh_token={refresh_token}"},
        )
    assert response.status_code == 200
    assert response.json()["username"] == "refreshonly2"


@pytest.mark.asyncio
async def test_username_update_falls_back_from_stale_access_cookie(client, db):
    user = User(
        email="fallback@lorevia.app",
        username=None,
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    stale_access_token = create_access_token(str(uuid.uuid4()))
    refresh_token = create_refresh_token(str(user.id), session_id="fallback-session")

    async def fake_session_active(*args, **kwargs):
        return True

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.api.deps.auth.refresh_session_active", fake_session_active)
        response = await client.patch(
            "/api/v1/auth/me/username?username=fallback_user",
            headers={
                "Cookie": (
                    f"lorevia_access_token={stale_access_token}; "
                    f"lorevia_refresh_token={refresh_token}"
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["username"] == "fallback_user"


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_valid_token(client, auth_headers):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["tier"] in {"free", "pro"}


@pytest.mark.asyncio
async def test_set_reading_mode(client, auth_headers):
    r = await client.patch("/api/v1/auth/me/reading-mode?mode=analyst", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["reading_mode"] == "analyst"
