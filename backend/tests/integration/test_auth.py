import uuid
from datetime import UTC, datetime

import pytest

from app.core.redis import get_redis, key_email_verification_user
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.book import Book
from app.models.user import User


@pytest.mark.asyncio
async def test_register_requires_email_verification_before_login(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@lorevia.app",
            "username": "new",
            "password": "TestPass123!@#",
            "accepted_terms": True,
            "device_id": "new-device-trial-0001",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@lorevia.app"
    assert body["username"] == "new"
    assert body["email_verification_required"] is True
    assert body["verification_email_sent"] is True

    r2 = await client.post("/api/v1/auth/login", json={"email": "new@lorevia.app", "password": "TestPass123!@#"})
    assert r2.status_code == 403
    assert r2.json()["detail"] == "Please verify your email before signing in."
    access_token = create_access_token(str(r.json()["id"]))
    me = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={access_token}"})
    assert me.status_code == 200
    assert me.json()["email_verified"] is False


@pytest.mark.asyncio
async def test_verify_email_completes_signup_and_allows_login(client, db):
    email = "verifyme@lorevia.app"
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": "verifyme",
            "password": "TestPass123!@#",
            "accepted_terms": True,
            "device_id": "verify-device-trial01",
        },
    )
    assert register.status_code == 201

    user_id = str(register.json()["id"])
    redis = await get_redis()
    token = await redis.get(key_email_verification_user(user_id))
    assert token

    verify = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify.status_code == 200
    verify_body = verify.json()
    assert verify_body["email"] == email
    assert verify_body["email_verified"] is True

    user = await db.get(User, uuid.UUID(user_id))
    assert user is not None
    assert user.email_verified_at is not None

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!@#"})
    assert login.status_code == 200
    assert login.json()["email_verified"] is True


@pytest.mark.asyncio
async def test_resend_verification_rotates_token(client):
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "resend@lorevia.app",
            "username": "resend",
            "password": "TestPass123!@#",
            "accepted_terms": True,
            "device_id": "resend-device-trial01",
        },
    )
    assert register.status_code == 201

    user_id = str(register.json()["id"])
    redis = await get_redis()
    first_token = await redis.get(key_email_verification_user(user_id))
    assert first_token

    resend = await client.post("/api/v1/auth/resend-verification", json={"email": "resend@lorevia.app"})
    assert resend.status_code == 200
    assert resend.json()["ok"] is True

    second_token = await redis.get(key_email_verification_user(user_id))
    assert second_token
    assert second_token != first_token


@pytest.mark.asyncio
async def test_supabase_oauth_requires_terms_for_new_users(client, monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"email": "oauth-new@lorevia.app"}

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

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "oauth-token", "accepted_terms": False, "device_id": "oauth-terms-device01"},
    )

    assert response.status_code == 400
    assert "accept the Terms" in response.json()["detail"]


@pytest.mark.asyncio
async def test_supabase_oauth_allows_existing_user_without_terms(client, db, monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"email": "oauth-existing@lorevia.app"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return FakeResponse()

    existing_user = User(
        email="oauth-existing@lorevia.app",
        username="oauth-existing",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
    )
    db.add(existing_user)
    await db.commit()

    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_URL", "https://supabase.example.com", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "oauth-token", "accepted_terms": False, "device_id": "oauth-existing-device01"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "oauth-existing@lorevia.app"
    assert response.json()["email_verified"] is True


@pytest.mark.asyncio
async def test_refresh_and_logout_use_cookies(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cookie@lorevia.app",
            "username": "cookie",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "cookie-device-trial01",
        },
    )
    assert register_response.status_code == 201
    user_id = str(register_response.json()["id"])
    verify_token = await (await get_redis()).get(key_email_verification_user(user_id))
    assert verify_token
    verify_response = await client.post("/api/v1/auth/verify-email", json={"token": verify_token})
    assert verify_response.status_code == 200
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
        json={
            "email": "refresh-only@lorevia.app",
            "username": "refreshonly",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "refresh-device-trial01",
        },
    )
    assert register_response.status_code == 201
    user_id = str(register_response.json()["id"])
    verify_token = await (await get_redis()).get(key_email_verification_user(user_id))
    assert verify_token
    verify_response = await client.post("/api/v1/auth/verify-email", json={"token": verify_token})
    assert verify_response.status_code == 200
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
async def test_register_blocks_third_trial_from_same_device(client):
    first = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "first@lorevia.app",
            "username": "firsttrial",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "shared-trial-device01",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "second@lorevia.app",
            "username": "secondtrial",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "shared-trial-device01",
        },
    )
    assert second.status_code == 201

    third = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "third@lorevia.app",
            "username": "thirdtrial",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "shared-trial-device01",
        },
    )

    assert third.status_code == 403
    assert "maximum of 2 trial accounts" in third.json()["detail"]


@pytest.mark.asyncio
async def test_supabase_oauth_blocks_new_user_when_device_trial_limit_is_reached(client, monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"email": "oauth-blocked@lorevia.app"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return FakeResponse()

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@lorevia.app",
            "username": "trialowner",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "oauth-used-device0001",
        },
    )
    assert register_response.status_code == 201

    second_register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner2@lorevia.app",
            "username": "trialowner2",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "oauth-used-device0001",
        },
    )
    assert second_register_response.status_code == 201

    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_URL", "https://supabase.example.com", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "oauth-token", "accepted_terms": True, "device_id": "oauth-used-device0001"},
    )

    assert response.status_code == 403
    assert "maximum of 2 trial accounts" in response.json()["detail"]


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_valid_token(client, auth_headers):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["tier"] == "author"
    assert r.json()["plan_tier"] == "free"
    assert r.json()["trial_active"] is True
    assert "email_verified" in r.json()


@pytest.mark.asyncio
async def test_set_reading_mode(client, auth_headers):
    r = await client.patch("/api/v1/auth/me/reading-mode?mode=analyst", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["reading_mode"] == "analyst"


@pytest.mark.asyncio
async def test_me_includes_goal_and_login_streak_fields(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["daily_word_goal"] == 1000
    assert payload["today_word_count"] == 0
    assert payload["login_streak_days"] >= 1
    assert isinstance(payload["login_activity_dates"], list)
    assert payload["last_login_at"] is not None


@pytest.mark.asyncio
async def test_daily_word_goal_can_be_updated(client, auth_headers):
    response = await client.patch(
        "/api/v1/auth/me/daily-word-goal",
        headers=auth_headers,
        json={"daily_word_goal": 1800},
    )

    assert response.status_code == 200
    assert response.json()["daily_word_goal"] == 1800


@pytest.mark.asyncio
async def test_manuscript_import_updates_today_word_count(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    draft_book = Book(
        user_id=user_id,
        title="Draft Tracker",
        format="manual",
        work_type="novel",
        s3_key="drafts/tracker.txt",
        status="ready",
        mode="author",
    )
    db.add(draft_book)
    await db.commit()
    await db.refresh(draft_book)

    response = await client.post(
        f"/api/v1/books/{draft_book.id}/manuscript/import",
        headers=auth_headers,
        data={
            "text": "One two three four",
            "title": "Chapter 1",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )

    assert response.status_code == 200

    refreshed = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["today_word_count"] == 4
