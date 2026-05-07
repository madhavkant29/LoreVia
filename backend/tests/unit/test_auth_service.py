import uuid

import pytest

from app.services.auth_service import DeviceTrialLimitError, build_device_trial, ensure_device_trial_available


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeSession:
    def __init__(self, value):
        self._value = value

    async def execute(self, _query):
        return _FakeResult(self._value)


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


def test_build_device_trial_hashes_device_id():
    trial = build_device_trial(
        user_id=uuid.uuid4(),
        device_id="550e8400-e29b-41d4-a716-446655440000",
    )

    assert trial.device_id_hash
    assert trial.device_id_hash != "550e8400-e29b-41d4-a716-446655440000"
