from __future__ import annotations

import hashlib
import re
from typing import Any


DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def password_is_valid(password: str, email: str) -> bool:
    normalized_email = normalize_email(email)
    email_local = normalized_email.split("@")[0]
    checks = [
        len(password) >= 12,
        any(ch.islower() for ch in password),
        any(ch.isupper() for ch in password),
        any(ch.isdigit() for ch in password),
        any(not ch.isalnum() for ch in password),
        email_local not in password.lower(),
        not any(password[i] == password[i + 1] == password[i + 2] for i in range(max(0, len(password) - 2))),
    ]
    return all(checks)


def normalize_device_id(device_id: str) -> str:
    normalized = (device_id or "").strip()
    if not DEVICE_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid device identifier")
    return normalized


def hash_device_id(device_id: str) -> str:
    return hashlib.sha256(normalize_device_id(device_id).encode("utf-8")).hexdigest()


def current_token_version(user: Any) -> int:
    try:
        version = int(getattr(user, "token_version", 1) or 1)
    except (TypeError, ValueError):
        return 1
    return max(version, 1)


def next_token_version(user: Any) -> int:
    return current_token_version(user) + 1
