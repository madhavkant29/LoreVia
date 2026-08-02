import uuid

import pytest

from app.services.auth_service import (
    DeviceTrialLimitError,
    authenticate_user,
    build_device_trial,
    ensure_device_trial_available,
    link_device_to_user_if_allowed,
    register_user,
)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._value


class _FakeSession:
    def __init__(self, *values):
        self._values = list(values)
        self.added = []

    async def execute(self, _query):
        value = self._values.pop(0) if self._values else None
        return _FakeResult(value)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None

    async def refresh(self, value):
        if value.id is None:
            value.id = uuid.uuid4()


@pytest.mark.asyncio
async def test_ensure_device_trial_available_rejects_reused_device():
    with pytest.raises(DeviceTrialLimitError):
        await ensure_device_trial_available(
            _FakeSession(2),
            "550e8400-e29b-41d4-a716-446655440000",
        )


@pytest.mark.asyncio
async def test_ensure_device_trial_available_allows_new_device():
    await ensure_device_trial_available(
        _FakeSession(1),
        "550e8400-e29b-41d4-a716-446655440000",
    )


@pytest.mark.asyncio
async def test_ensure_device_trial_available_skips_in_debug_mode(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.settings.DEBUG", True, raising=False)

    await ensure_device_trial_available(
        _FakeSession(999),
        "550e8400-e29b-41d4-a716-446655440000",
    )


@pytest.mark.asyncio
async def test_link_device_to_user_if_allowed_adds_new_link():
    user_id = uuid.uuid4()
    session = _FakeSession(None, 1)

    await link_device_to_user_if_allowed(
        session,
        user_id,
        "550e8400-e29b-41d4-a716-446655440000",
    )

    assert len(session.added) == 1
    assert session.added[0].user_id == user_id


@pytest.mark.asyncio
async def test_link_device_to_user_if_allowed_skips_existing_link():
    session = _FakeSession("existing-link-id")

    await link_device_to_user_if_allowed(
        session,
        uuid.uuid4(),
        "550e8400-e29b-41d4-a716-446655440000",
    )

    assert session.added == []


@pytest.mark.asyncio
async def test_link_device_to_user_if_allowed_rejects_new_third_account():
    with pytest.raises(DeviceTrialLimitError):
        await link_device_to_user_if_allowed(
            _FakeSession(None, 2),
            uuid.uuid4(),
            "550e8400-e29b-41d4-a716-446655440000",
        )


def test_build_device_trial_hashes_device_id():
    trial = build_device_trial(
        user_id=uuid.uuid4(),
        device_id="550e8400-e29b-41d4-a716-446655440000",
    )

    assert trial.device_id_hash
    assert trial.device_id_hash != "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_register_user_hashes_password_stores_session_and_returns_tokens(monkeypatch):
    session = _FakeSession()
    stored = []
    monkeypatch.setattr("app.services.auth_service.hash_password", lambda value: f"hash:{value}")
    monkeypatch.setattr("app.services.auth_service.current_token_version", lambda _user: 7)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, version: f"access:{user_id}:{version}",
    )
    monkeypatch.setattr(
        "app.services.auth_service.create_refresh_token",
        lambda user_id, version, sid: f"refresh:{user_id}:{version}:{sid}",
    )

    async def store(user_id, session_id, ttl):
        stored.append((user_id, session_id, ttl))

    monkeypatch.setattr("app.services.auth_service.store_refresh_session", store)
    user, access, refresh = await register_user(session, "writer@example.test", "SafePass123!")

    assert user.email == "writer@example.test" and user.password_hash == "hash:SafePass123!"
    assert access == f"access:{user.id}:7"
    assert refresh.startswith(f"refresh:{user.id}:7:")
    assert stored[0][0] == str(user.id)
    assert stored[0][2] > 0


@pytest.mark.asyncio
async def test_authenticate_user_accepts_valid_password_and_rejects_other_cases(monkeypatch):
    user = type("UserRow", (), {"password_hash": "stored"})()
    monkeypatch.setattr(
        "app.services.auth_service.verify_password",
        lambda password, hashed: password == "correct" and hashed == "stored",
    )
    assert await authenticate_user(_FakeSession(user), "writer@example.test", "correct") is user
    assert await authenticate_user(_FakeSession(user), "writer@example.test", "wrong") is None
    assert await authenticate_user(_FakeSession(None), "missing@example.test", "correct") is None


@pytest.mark.asyncio
async def test_non_strict_device_link_silently_skips_account_limit():
    session = _FakeSession(None, 99)
    await link_device_to_user_if_allowed(
        session,
        uuid.uuid4(),
        "550e8400-e29b-41d4-a716-446655440000",
        strict=False,
    )
    assert session.added == []
