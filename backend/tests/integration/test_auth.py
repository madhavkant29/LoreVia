import hashlib
import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

from app.core.redis import (
    consume_password_reset_token,
    get_redis,
    key_email_verification_user,
    key_password_reset_cooldown,
    key_password_reset_user,
)
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.book import Book
from app.models.user import DeviceTrial, User, UserLoginActivity
from app.utils.auth_csrf import AUTH_CSRF_COOKIE_NAME, AUTH_CSRF_HEADER_NAME, create_auth_csrf_token


def cookie_auth_headers(*cookies: str, csrf_token: str | None = None) -> dict[str, str]:
    resolved_csrf = csrf_token or create_auth_csrf_token()
    cookie_parts = [f"{AUTH_CSRF_COOKIE_NAME}={resolved_csrf}", *cookies]
    return {
        "Cookie": "; ".join(cookie_parts),
        AUTH_CSRF_HEADER_NAME: resolved_csrf,
        "Origin": "https://getlorevia.com",
    }


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

    r2 = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "new@lorevia.app",
            "password": "TestPass123!@#",
            "device_id": "new-device-trial-0001",
        },
    )
    assert r2.status_code == 403
    assert r2.json()["detail"] == "Please verify your email before signing in."
    access_token = create_access_token(str(r.json()["id"]))
    me = await client.get(
        "/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={access_token}"}
    )
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

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "TestPass123!@#",
            "device_id": "verify-device-trial01",
        },
    )
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

    resend = await client.post(
        "/api/v1/auth/resend-verification", json={"email": "resend@lorevia.app"}
    )
    assert resend.status_code == 200
    assert resend.json()["ok"] is True

    second_token = await redis.get(key_email_verification_user(user_id))
    assert second_token
    assert second_token != first_token


@pytest.mark.asyncio
async def test_supabase_oauth_rejects_new_users_without_account(client, monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(uuid.uuid4()),
                "email": "oauth-new@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

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

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "oauth-token", "accepted_terms": False, "device_id": "oauth-terms-device01"},
    )

    assert response.status_code == 401
    assert "Register page" in response.json()["detail"]


@pytest.mark.asyncio
async def test_supabase_oauth_allows_existing_user_without_terms(client, db, monkeypatch):
    supabase_auth_id = uuid.uuid4()

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id),
                "email": "oauth-existing@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

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

    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL",
        "https://supabase.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": False,
            "device_id": "oauth-existing-device01",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "oauth-existing@lorevia.app"
    assert response.json()["email_verified"] is True
    await db.refresh(existing_user)
    assert existing_user.supabase_auth_id == supabase_auth_id


@pytest.mark.asyncio
async def test_supabase_oauth_creates_account_with_accepted_terms(client, db, monkeypatch):
    """Test that OAuth registration creates a new account when accepted_terms=True"""
    supabase_auth_id = uuid.uuid4()

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id),
                "email": "oauth-created@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

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

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": True,
            "device_id": "oauth-create-device0001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "oauth-created@lorevia.app"
    assert body["email_verified"] is True

    # Verify the user was created in the database
    created_user = (
        await db.execute(sa.select(User).where(User.email == "oauth-created@lorevia.app"))
    ).scalar()
    assert created_user is not None
    assert created_user.supabase_auth_id == supabase_auth_id
    assert created_user.email_verified_at is not None

    # Verify device was linked
    device_trial = (
        await db.execute(sa.select(DeviceTrial).where(DeviceTrial.user_id == created_user.id))
    ).scalar()
    assert device_trial is not None

    # Verify login activity was recorded
    login_activity = (
        await db.execute(
            sa.select(UserLoginActivity).where(UserLoginActivity.user_id == created_user.id)
        )
    ).scalar()
    assert login_activity is not None


@pytest.mark.asyncio
async def test_supabase_oauth_registration_sets_correct_fields(client, db, monkeypatch):
    """Test that OAuth registration sets all required fields correctly"""
    supabase_auth_id = uuid.uuid4()
    email = "oauth-fields-check@lorevia.app"

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id),
                "email": email,
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

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

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "oauth-token", "accepted_terms": True, "device_id": "oauth-fields-device01"},
    )

    assert response.status_code == 200

    # Verify all critical fields
    created_user = (await db.execute(sa.select(User).where(User.email == email))).scalar()
    assert created_user is not None
    assert created_user.email == email
    assert created_user.supabase_auth_id == supabase_auth_id
    assert created_user.email_verified_at is not None

    # Verify auth cookies are set in response
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("lorevia_access_token" in header for header in set_cookie_headers)
    assert any("lorevia_refresh_token" in header for header in set_cookie_headers)
    assert any("lorevia_device_id=oauth-fields-device01" in header for header in set_cookie_headers)


@pytest.mark.asyncio
async def test_supabase_oauth_login_rejects_nonexistent_user_without_terms(client, monkeypatch):
    """Test that OAuth login flow rejects users who don't exist when accepted_terms=False"""
    supabase_auth_id = uuid.uuid4()

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id),
                "email": "oauth-login-reject@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

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

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": False,
            "device_id": "oauth-login-reject-device01",
        },
    )

    assert response.status_code == 401
    assert "Register page" in response.json()["detail"]


@pytest.mark.asyncio
async def test_supabase_oauth_registration_respects_device_trial_limit(client, db, monkeypatch):
    """Test that OAuth registration enforces device trial limits"""
    shared_device_id = "oauth-trial-limit-device01"
    shared_device_hash = hashlib.sha256(shared_device_id.encode("utf-8")).hexdigest()

    # Create two existing users on the same device
    for i in range(2):
        user = User(
            email=f"oauth-trial-user{i}@lorevia.app",
            username=f"oauthtrialuser{i}",
            password_hash=hash_password("SafePass123!@#"),
            legal_accepted_at=datetime.now(UTC),
            legal_version="2026-04",
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        await db.flush()
        db.add(DeviceTrial(user_id=user.id, device_id_hash=shared_device_hash))
    await db.commit()

    # Try to create a third user via OAuth on the same device
    supabase_auth_id = uuid.uuid4()

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id),
                "email": "oauth-trial-third@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

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

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "oauth-token", "accepted_terms": True, "device_id": shared_device_id},
    )

    assert response.status_code == 429
    assert "maximum of 2 accounts" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_supabase_oauth_prevents_registration_login_confusion(client, db, monkeypatch):
    """
    Integration test ensuring OAuth registration and login flows are properly separated.
    This prevents the bug where users clicking Google sign-in on /register page
    would see "create an account" error even though they were trying to register.
    """
    supabase_auth_id_register = uuid.uuid4()
    supabase_auth_id_login = uuid.uuid4()

    class FakeResponseRegister:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id_register),
                "email": "oauth-flow-test@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

    class FakeResponseLogin:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id_login),
                "email": "oauth-different-user@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

    responses = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return responses.pop(0)

    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL",
        "https://supabase.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    # Scenario 1: User clicks Google sign-in on /register page (accepted_terms=True)
    # This should CREATE a new account
    responses.append(FakeResponseRegister())
    register_response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": True,
            "device_id": "oauth-flow-register-device01",
        },
    )
    assert register_response.status_code == 200
    assert register_response.json()["email"] == "oauth-flow-test@lorevia.app"

    # Verify account was created
    created_user = (
        await db.execute(sa.select(User).where(User.email == "oauth-flow-test@lorevia.app"))
    ).scalar()
    assert created_user is not None

    # Scenario 2: Different user clicks Google sign-in on /login page (accepted_terms=False)
    # This should REJECT since they don't have an account
    responses.append(FakeResponseLogin())
    login_response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": False,
            "device_id": "oauth-flow-login-device01",
        },
    )
    assert login_response.status_code == 401
    assert "Register page" in login_response.json()["detail"]

    # Scenario 3: The first user now tries to log in from /login page (accepted_terms=False)
    # This should SUCCEED because they have an account
    responses.append(FakeResponseRegister())
    returning_login_response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": False,
            "device_id": "oauth-flow-returning-device01",
        },
    )
    assert returning_login_response.status_code == 200
    assert returning_login_response.json()["email"] == "oauth-flow-test@lorevia.app"


@pytest.mark.asyncio
async def test_supabase_oauth_debug_mode_still_rejects_new_users(client, monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(uuid.uuid4()),
                "email": "oauth-local-recovery@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return FakeResponse()

    monkeypatch.setattr("app.api.v1.routes.auth.settings.DEBUG", True, raising=False)
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL",
        "https://supabase.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": False,
            "device_id": "oauth-recovery-device01",
        },
    )

    assert response.status_code == 401
    assert "Register page" in response.json()["detail"]


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

    async def fake_consume_refresh_session(*args, **kwargs):
        return True

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.api.v1.routes.auth.consume_refresh_session", fake_consume_refresh_session)
        refreshed = await client.post(
            "/api/v1/auth/refresh",
            headers=cookie_auth_headers(f"lorevia_refresh_token={refresh_token}"),
        )
    assert refreshed.status_code == 200
    refresh_body = refreshed.json()
    assert "access_token" not in refresh_body
    assert "refresh_token" not in refresh_body

    me = await client.get(
        "/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={access_token}"}
    )
    assert me.status_code == 200

    logout = await client.post(
        "/api/v1/auth/logout",
        headers=cookie_auth_headers(f"lorevia_access_token={access_token}"),
    )
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
            headers=cookie_auth_headers(f"lorevia_refresh_token={refresh_token}"),
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
            headers=cookie_auth_headers(
                f"lorevia_access_token={stale_access_token}",
                f"lorevia_refresh_token={refresh_token}",
            ),
        )

    assert response.status_code == 200
    assert response.json()["username"] == "fallback_user"


@pytest.mark.asyncio
async def test_username_update_allows_existing_user_to_rename_and_me_returns_updated_username(
    client,
):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rename-me@lorevia.app",
            "username": "rename_me",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "rename-device-trial01",
        },
    )
    assert register_response.status_code == 201

    user_id = str(register_response.json()["id"])
    access_token = create_access_token(user_id)
    headers = cookie_auth_headers(f"lorevia_access_token={access_token}")

    rename_response = await client.patch(
        "/api/v1/auth/me/username?username=renamed_writer", headers=headers
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["username"] == "renamed_writer"

    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "renamed_writer"


@pytest.mark.asyncio
async def test_username_update_rejects_duplicate_username_for_existing_user(client, db):
    first = User(
        email="first-rename@lorevia.app",
        username="first_writer",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
    )
    second = User(
        email="second-rename@lorevia.app",
        username="second_writer",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(second)

    access_token = create_access_token(str(second.id))
    response = await client.patch(
        "/api/v1/auth/me/username?username=first_writer",
        headers=cookie_auth_headers(f"lorevia_access_token={access_token}"),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"


@pytest.mark.asyncio
async def test_username_update_rejects_invalid_username_for_existing_user(client, db):
    user = User(
        email="invalid-rename@lorevia.app",
        username="valid_writer",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    response = await client.patch(
        "/api/v1/auth/me/username?username=bad name",
        headers=cookie_auth_headers(f"lorevia_access_token={access_token}"),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Username can only contain letters, numbers, underscores, and hyphens"
    )


@pytest.mark.asyncio
async def test_cookie_authenticated_write_requires_csrf_header(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "csrf-required@lorevia.app",
            "username": "csrfrequired",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "csrf-required-device1",
        },
    )
    assert register_response.status_code == 201

    access_token = create_access_token(str(register_response.json()["id"]))
    response = await client.patch(
        "/api/v1/auth/me/username?username=csrfrequired2",
        headers={"Cookie": f"lorevia_access_token={access_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid CSRF token."


@pytest.mark.asyncio
async def test_refresh_with_cookie_requires_csrf_header(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "csrf-refresh@lorevia.app",
            "username": "csrfrefresh",
            "password": "SafePass123!@#",
            "accepted_terms": True,
            "device_id": "csrf-refresh-device01",
        },
    )
    assert register_response.status_code == 201

    refresh_token = create_refresh_token(
        str(register_response.json()["id"]), session_id="csrf-refresh-session"
    )
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"lorevia_refresh_token={refresh_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid CSRF token."


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
    assert "maximum of 2 accounts" in third.json()["detail"]


@pytest.mark.asyncio
async def test_login_allows_unlinked_account_even_when_device_at_capacity(client, db):
    shared_device_id = "shared-login-device01"

    for email, username in (
        ("login-first@lorevia.app", "loginfirst"),
        ("login-second@lorevia.app", "loginsecond"),
    ):
        register = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": "SafePass123!@#",
                "accepted_terms": True,
                "device_id": shared_device_id,
            },
        )
        assert register.status_code == 201
        user_id = str(register.json()["id"])
        token = await (await get_redis()).get(key_email_verification_user(user_id))
        assert token
        verify = await client.post("/api/v1/auth/verify-email", json={"token": token})
        assert verify.status_code == 200

    third_user = User(
        email="login-third@lorevia.app",
        username="loginthird",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(third_user)
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login-third@lorevia.app",
            "password": "SafePass123!@#",
            "device_id": shared_device_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "login-third@lorevia.app"


@pytest.mark.asyncio
async def test_login_allows_prelinked_account_even_when_device_has_more_than_limit(client, db):
    shared_device_id = "grandfathered-login001"
    shared_device_hash = hashlib.sha256(shared_device_id.encode("utf-8")).hexdigest()

    users = []
    for email, username in (
        ("grandfather-first@lorevia.app", "grandfatherfirst"),
        ("grandfather-second@lorevia.app", "grandfathersecond"),
        ("grandfather-third@lorevia.app", "grandfatherthird"),
    ):
        user = User(
            email=email,
            username=username,
            password_hash=hash_password("SafePass123!@#"),
            legal_accepted_at=datetime.now(UTC),
            legal_version="2026-04",
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        users.append(user)
    await db.flush()
    for user in users:
        db.add(DeviceTrial(user_id=user.id, device_id_hash=shared_device_hash))
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "grandfather-third@lorevia.app",
            "password": "SafePass123!@#",
            "device_id": shared_device_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "grandfather-third@lorevia.app"


@pytest.mark.asyncio
async def test_login_allows_unlinked_account_when_device_has_grandfathered_links(client, db):
    shared_device_id = "grandfathered-block001"
    shared_device_hash = hashlib.sha256(shared_device_id.encode("utf-8")).hexdigest()

    for email, username in (
        ("grandfather-block-one@lorevia.app", "grandfatherblockone"),
        ("grandfather-block-two@lorevia.app", "grandfatherblocktwo"),
        ("grandfather-block-three@lorevia.app", "grandfatherblockthree"),
    ):
        user = User(
            email=email,
            username=username,
            password_hash=hash_password("SafePass123!@#"),
            legal_accepted_at=datetime.now(UTC),
            legal_version="2026-04",
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        await db.flush()
        db.add(DeviceTrial(user_id=user.id, device_id_hash=shared_device_hash))
    unlinked_user = User(
        email="grandfather-block-four@lorevia.app",
        username="grandfatherblockfour",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(unlinked_user)
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "grandfather-block-four@lorevia.app",
            "password": "SafePass123!@#",
            "device_id": shared_device_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "grandfather-block-four@lorevia.app"


@pytest.mark.asyncio
async def test_login_prefers_device_cookie_and_allows_existing_user(client, db):
    cookie_device_id = "cookie-priority-dev01"
    cookie_device_hash = hashlib.sha256(cookie_device_id.encode("utf-8")).hexdigest()
    request_device_id = "request-priority-dev2"
    request_device_hash = hashlib.sha256(request_device_id.encode("utf-8")).hexdigest()

    linked_one = User(
        email="cookie-priority-one@lorevia.app",
        username="cookiepriorityone",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    linked_two = User(
        email="cookie-priority-two@lorevia.app",
        username="cookieprioritytwo",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    existing_user = User(
        email="cookie-priority-three@lorevia.app",
        username="cookieprioritythree",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add_all([linked_one, linked_two, existing_user])
    await db.flush()
    db.add_all(
        [
            DeviceTrial(user_id=linked_one.id, device_id_hash=cookie_device_hash),
            DeviceTrial(user_id=linked_two.id, device_id_hash=cookie_device_hash),
        ]
    )
    db.add(DeviceTrial(user_id=existing_user.id, device_id_hash=request_device_hash))
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "cookie-priority-three@lorevia.app",
            "password": "SafePass123!@#",
            "device_id": request_device_id,
        },
        headers={"Cookie": f"lorevia_device_id={cookie_device_id}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "cookie-priority-three@lorevia.app"


@pytest.mark.asyncio
async def test_login_allows_missing_device_id_when_no_cookie(client, db):
    user = User(
        email="missing-device@lorevia.app",
        username="missingdevice",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "missing-device@lorevia.app",
            "password": "SafePass123!@#",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "missing-device@lorevia.app"


@pytest.mark.asyncio
async def test_login_uses_device_cookie_when_request_body_omits_device_id(client, db):
    cookie_device_id = "cookie-only-device01"
    user = User(
        email="cookie-only-login@lorevia.app",
        username="cookieonlylogin",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "cookie-only-login@lorevia.app",
            "password": "SafePass123!@#",
        },
        headers={"Cookie": f"lorevia_device_id={cookie_device_id}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "cookie-only-login@lorevia.app"


@pytest.mark.asyncio
async def test_login_sets_device_cookie_and_records_device_id(client, db):
    user = User(
        email="records-device@lorevia.app",
        username="recordsdevice",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "records-device@lorevia.app",
            "password": "SafePass123!@#",
            "device_id": "records-device-id01",
        },
    )

    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("lorevia_device_id=records-device-id01" in header for header in set_cookie_headers)

    result = await db.execute(sa.select(DeviceTrial).where(DeviceTrial.user_id == user.id))
    trial_links = list(result.scalars().all())
    assert len(trial_links) == 1

    activity = await db.execute(
        sa.select(UserLoginActivity).where(UserLoginActivity.user_id == user.id)
    )
    login_rows = list(activity.scalars().all())
    assert login_rows[-1].device_id == "records-device-id01"


@pytest.mark.asyncio
async def test_supabase_oauth_registration_respects_device_limit_when_at_capacity(
    client, monkeypatch
):
    """Test that OAuth registration enforces device trial limits even when accepted_terms=True"""

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(uuid.uuid4()),
                "email": "oauth-blocked@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

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

    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL",
        "https://supabase.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "oauth-token", "accepted_terms": True, "device_id": "oauth-used-device0001"},
    )

    assert response.status_code == 429
    assert "maximum of 2 accounts" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_supabase_oauth_handles_legacy_user_with_missing_reading_mode(
    client, db, monkeypatch
):
    supabase_auth_id = uuid.uuid4()

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": str(supabase_auth_id),
                "email": "oauth-legacy@lorevia.app",
                "email_confirmed_at": "2026-05-01T00:00:00Z",
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return FakeResponse()

    legacy_user = User(
        email="oauth-legacy@lorevia.app",
        username="oauthlegacy",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        reading_mode=None,
        email_verified_at=datetime.now(UTC),
    )
    db.add(legacy_user)
    await db.commit()

    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL",
        "https://supabase.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    response = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": False,
            "device_id": "oauth-legacy-device001",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "oauth-legacy@lorevia.app"
    assert response.json()["reading_mode"] == "casual"
    await db.refresh(legacy_user)
    assert legacy_user.supabase_auth_id == supabase_auth_id


@pytest.mark.asyncio
async def test_me_accepts_access_token_with_supabase_auth_subject(client, db):
    supabase_auth_id = uuid.uuid4()
    user = User(
        email="supabase-subject@lorevia.app",
        username="supabasesubject",
        supabase_auth_id=supabase_auth_id,
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()

    access_token = create_access_token(str(supabase_auth_id))
    response = await client.get(
        "/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "supabase-subject@lorevia.app"


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_forgot_password_rotates_to_latest_reset_token_only(client, db):
    user = User(
        email="reset-rotate@lorevia.app",
        username="resetrotate",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    first = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert first.status_code == 200
    redis = await get_redis()
    first_token = await redis.get(key_password_reset_user(str(user.id)))
    assert first_token

    await redis.delete(key_password_reset_cooldown(str(user.id)))

    second = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert second.status_code == 200
    second_token = await redis.get(key_password_reset_user(str(user.id)))
    assert second_token
    assert second_token != first_token

    assert await consume_password_reset_token(first_token) is None
    assert await consume_password_reset_token(second_token) == str(user.id)


@pytest.mark.asyncio
async def test_forgot_password_cooldown_suppresses_repeat_emails_for_same_account(
    client, db, monkeypatch
):
    deliveries: list[str] = []

    async def _fake_deliver(email: str, token: str) -> tuple[bool, str]:
        deliveries.append(token)
        return True, f"https://app.example/reset-password?token={token}"

    monkeypatch.setattr(
        "app.api.v1.routes.auth_recovery.deliver_password_reset_email", _fake_deliver
    )

    user = User(
        email="reset-cooldown@lorevia.app",
        username="resetcooldown",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()

    first = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    second = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(deliveries) == 1


@pytest.mark.asyncio
async def test_reset_password_token_is_single_use(client, db):
    user = User(
        email="single-use-reset@lorevia.app",
        username="singleusereset",
        password_hash=hash_password("SafePass123!@#"),
        legal_accepted_at=datetime.now(UTC),
        legal_version="2026-04",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    forgot = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert forgot.status_code == 200
    token = await (await get_redis()).get(key_password_reset_user(str(user.id)))
    assert token

    first_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "NewResetPass123!@"},
    )
    assert first_reset.status_code == 200

    second_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "AnotherPass123!@"},
    )
    assert second_reset.status_code == 400
    assert second_reset.json()["detail"] == "Invalid or expired reset token"


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
    before = await client.get("/api/v1/auth/me", headers=auth_headers)
    r = await client.patch("/api/v1/auth/me/reading-mode?mode=analyst", headers=auth_headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload["reading_mode"] == "analyst"
    assert payload["id"] == before.json()["id"]
    assert payload["email"] == before.json()["email"]
    assert payload["tier"] == "author"
    assert payload["plan_tier"] == "free"


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
async def test_tier_limits_reflect_strict_free_plan(client, auth_headers):
    response = await client.get("/api/v1/auth/tier-limits", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["free_max_books"] == 0
    assert payload["free_total_token_budget"] == 150000
    assert payload["free_search_per_day"] == 0
    assert payload["free_prediction_per_day"] == 1
    assert payload["free_recall_per_day"] == 0
    assert payload["free_advisor_per_day"] == 0
    assert payload["free_advisor_per_week"] == 1
    assert payload["free_advisor_per_month"] == 4
    assert payload["free_continuity_per_day"] == 0
    assert payload["free_continuity_per_minute"] == 0


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
async def test_manuscript_import_updates_today_word_count(client, db, auth_headers, monkeypatch):
    async def _fake_embed_batch(texts: list[str], **_kwargs) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]

    async def _fake_character_extraction(_text: str, **_kwargs) -> dict:
        return {"characters": [], "relationships": [], "rejected_characters": []}

    monkeypatch.setattr(
        "app.services.extraction_chapter_embedding_service.embed_batch", _fake_embed_batch
    )
    monkeypatch.setattr(
        "app.services.extraction_character_reporting_service.embed_batch", _fake_embed_batch
    )
    monkeypatch.setattr(
        "app.services.extraction_character_reporting_service.embed_batch",
        _fake_embed_batch,
    )
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_character_extraction,
    )

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

    assert response.status_code == 200, response.text

    refreshed = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["today_word_count"] == 4


@pytest.mark.asyncio
async def test_session_uses_valid_access_cookie_then_rotates_refresh_cookie(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user = await db.get(User, uuid.UUID(me.json()["id"]))
    user.email_verified_at = datetime.now(UTC)
    await db.commit()

    access_token = create_access_token(str(user.id), version=user.token_version)
    access_response = await client.post(
        "/api/v1/auth/session",
        headers={"Cookie": f"lorevia_access_token={access_token}"},
    )
    assert access_response.status_code == 200
    assert access_response.json()["id"] == str(user.id)

    session_id = uuid.uuid4().hex
    refresh_token = create_refresh_token(
        str(user.id),
        version=user.token_version,
        session_id=session_id,
    )

    async def consume_refresh(user_id, sid):
        assert user_id == str(user.id)
        assert sid == session_id
        return True

    monkeypatch.setattr("app.api.v1.routes.auth.consume_refresh_session", consume_refresh)
    refresh_response = await client.post(
        "/api/v1/auth/session",
        headers=cookie_auth_headers(f"lorevia_refresh_token={refresh_token}"),
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["id"] == str(user.id)
    assert "lorevia_access_token=" in refresh_response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_supabase_oauth_creates_user_and_links_existing_email(client, db, monkeypatch):
    supabase_id = uuid.uuid4()

    class VerificationResponse:
        status_code = 200
        text = "ok"

        @staticmethod
        def json():
            return {"id": str(supabase_id), "email": "oauth-user@example.com"}

    class FakeHttpClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url, headers):
            assert url.endswith("/auth/v1/user")
            assert headers["Authorization"] == "Bearer oauth-token"
            return VerificationResponse()

    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL", "https://supabase.example", raising=False
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeHttpClient)

    created = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": True,
            "device_id": f"oauth-device-{uuid.uuid4().hex[:16]}",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["email"] == "oauth-user@example.com"
    created_user = await db.get(User, uuid.UUID(created.json()["id"]))
    assert created_user.supabase_auth_id == supabase_id
    assert created_user.email_verified_at is not None

    second = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "oauth-token",
            "accepted_terms": False,
            "device_id": "oauth-existing-device-123456",
        },
    )
    assert second.status_code == 200
    assert second.json()["id"] == created.json()["id"]


@pytest.mark.asyncio
async def test_supabase_oauth_rejects_missing_config_and_bad_provider_token(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_URL", None, raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", None, raising=False)
    missing = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={"token": "token", "accepted_terms": False, "device_id": "oauth-error-device-123456"},
    )
    assert missing.status_code == 503

    class BadResponse:
        status_code = 401
        text = "invalid"

    class FakeHttpClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, *_args, **_kwargs):
            return BadResponse()

    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_URL", "https://supabase.example", raising=False
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False
    )
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeHttpClient)
    invalid = await client.post(
        "/api/v1/auth/oauth/supabase",
        json={
            "token": "bad-token",
            "accepted_terms": False,
            "device_id": "oauth-error-device-123456",
        },
    )
    assert invalid.status_code == 401
