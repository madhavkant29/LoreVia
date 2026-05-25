from __future__ import annotations

from typing import Any

from app.utils.billing_utils import ARCHITECT_TIER, normalize_tier, user_access_tier

PRIORITY_QUEUE_SUFFIX = "_priority"


def queue_for_access_tier(base_queue: str, access_tier: str | None) -> str:
    tier = normalize_tier(access_tier)
    if tier == ARCHITECT_TIER:
        return f"{base_queue}{PRIORITY_QUEUE_SUFFIX}"
    return base_queue


def queue_for_user(user: Any, base_queue: str) -> str:
    return queue_for_access_tier(base_queue, user_access_tier(user))
