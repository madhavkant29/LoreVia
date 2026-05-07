import pytest

from app.utils.auth_utils import hash_device_id, normalize_device_id, password_is_valid


def test_normalize_device_id_accepts_uuid_style_ids():
    assert normalize_device_id("550e8400-e29b-41d4-a716-446655440000") == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.parametrize("device_id", ["short-id", "bad spaces here", "symbols!*invalid"])
def test_normalize_device_id_rejects_invalid_ids(device_id: str):
    with pytest.raises(ValueError):
        normalize_device_id(device_id)


def test_hash_device_id_is_stable():
    device_id = "550e8400-e29b-41d4-a716-446655440000"
    assert hash_device_id(device_id) == hash_device_id(device_id)


def test_password_is_valid_accepts_strong_password():
    assert password_is_valid("StrongPass123!@", "reader@example.com") is True


def test_password_is_valid_rejects_email_pattern():
    assert password_is_valid("reader123!AA", "reader@example.com") is False
