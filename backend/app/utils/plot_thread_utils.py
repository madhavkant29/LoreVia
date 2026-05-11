from __future__ import annotations

import re
from typing import Any

PLOT_THREAD_STATUS_ALIASES = {
    "ongoing": "developing",
    "in_progress": "developing",
    "active": "developing",
    "open": "developing",
    "done": "resolved",
    "complete": "resolved",
    "completed": "resolved",
    "closed": "resolved",
    "cancelled": "abandoned",
    "canceled": "abandoned",
    "intentionally_abandoned": "abandoned",
}

PLOT_THREAD_STATUSES = {
    "introduced",
    "developing",
    "paused",
    "resolved",
    "contradicted",
    "forgotten",
    "possibly_abandoned",
    "abandoned",
    "unknown",
}

PLOT_THREAD_OPEN_STATUSES = {
    "introduced",
    "developing",
    "paused",
    "forgotten",
    "possibly_abandoned",
    "unknown",
}

PLOT_THREAD_EXTRACTABLE_STATUSES = {
    "introduced",
    "developing",
    "paused",
    "resolved",
    "contradicted",
    "abandoned",
    "unknown",
}

PLOT_THREAD_TYPE_ALIASES = {
    "relationship tension": "relationship_tension",
    "relationship_tension": "relationship_tension",
    "open question": "open_question",
    "mcguffin": "object",
    "artifact": "object",
}

PLOT_THREAD_TYPES = {
    "promise",
    "mystery",
    "conflict",
    "prophecy",
    "goal",
    "object",
    "clue",
    "relationship_tension",
    "open_question",
    "subplot",
    "political",
    "romance",
    "main",
}


def normalize_plot_thread_title(value: object | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def plot_thread_lookup_key(value: object | None) -> str:
    normalized = normalize_plot_thread_title(value).casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_plot_thread_status(value: object | None, *, default: str = "unknown") -> str:
    raw = re.sub(r"[^a-z_]+", "_", str(value or "").strip().casefold()).strip("_")
    if not raw:
        return default
    raw = PLOT_THREAD_STATUS_ALIASES.get(raw, raw)
    return raw if raw in PLOT_THREAD_STATUSES else default


def normalize_plot_thread_type(value: object | None) -> str | None:
    raw = re.sub(r"[^a-z_]+", "_", str(value or "").strip().casefold()).strip("_")
    if not raw:
        return None
    raw = PLOT_THREAD_TYPE_ALIASES.get(raw, raw)
    return raw if raw in PLOT_THREAD_TYPES else raw


def normalize_related_characters(values: object | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values or []:
        cleaned = normalize_plot_thread_title(item)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def is_plot_thread_closed(status: str) -> bool:
    return normalize_plot_thread_status(status) in {"resolved", "abandoned"}


def is_plot_thread_open(status: str) -> bool:
    return normalize_plot_thread_status(status) in PLOT_THREAD_OPEN_STATUSES


def derive_plot_thread_status(
    base_status: object | None,
    *,
    introduced_at: int | None,
    last_mentioned_at: int | None,
    resolved_at: int | None,
    current_chapter: int | None,
) -> str:
    status = normalize_plot_thread_status(base_status)
    if status == "resolved":
        return "resolved"
    if status == "abandoned":
        return "abandoned"
    if status == "contradicted":
        return "contradicted"
    if current_chapter is None or last_mentioned_at is None:
        return status

    gap = current_chapter - last_mentioned_at
    if gap >= 12 and status in {"introduced", "developing", "paused", "unknown"}:
        return "forgotten"
    if gap >= 6 and status in {"introduced", "developing", "paused", "unknown"}:
        return "possibly_abandoned"
    if status == "unknown" and introduced_at is not None and current_chapter - introduced_at <= 1:
        return "introduced"
    return status


def derive_plot_thread_risk(
    *,
    title: str,
    status: str,
    importance: int | None,
    introduced_at: int | None,
    last_mentioned_at: int | None,
    current_chapter: int | None,
) -> str | None:
    resolved_status = derive_plot_thread_status(
        status,
        introduced_at=introduced_at,
        last_mentioned_at=last_mentioned_at,
        resolved_at=None,
        current_chapter=current_chapter,
    )
    if resolved_status == "resolved":
        return None
    weight = int(importance or 5)
    if resolved_status == "contradicted":
        return "This thread appears to conflict with earlier setup and may read like a continuity break."
    if resolved_status == "forgotten":
        return "Readers are likely to read this as forgotten unless it is revived or intentionally closed out."
    if resolved_status == "possibly_abandoned":
        return "Reader expectation may still be active because this thread has been quiet for several chapters."
    if resolved_status == "paused":
        return "The thread is resting off-page; readers may need a reminder before it matters again."
    if introduced_at is not None and current_chapter is not None and current_chapter - introduced_at >= 4 and weight >= 7:
        return "Reader may strongly expect closure because this thread has stayed active for a long stretch."
    if resolved_status in {"introduced", "developing", "unknown"}:
        return f"'{title}' is still open, so readers may expect resolution or reinforcement."
    return None


def derive_plot_thread_suggested_action(
    *,
    status: str,
    current_chapter: int | None,
    last_mentioned_at: int | None,
) -> str | None:
    resolved_status = derive_plot_thread_status(
        status,
        introduced_at=None,
        last_mentioned_at=last_mentioned_at,
        resolved_at=None,
        current_chapter=current_chapter,
    )
    if resolved_status == "resolved":
        return "Keep as resolved or link the payoff to a larger thread."
    if resolved_status == "contradicted":
        return "Reconcile the contradiction, explain it in-story, or split this into a new thread."
    if resolved_status == "forgotten":
        return "Resolve it, revive it with a reminder, or intentionally abandon it on the page."
    if resolved_status == "possibly_abandoned":
        return "Resolve, remind, or intentionally abandon before the thread goes cold."
    if resolved_status == "paused":
        return "Plant a reminder beat before the next escalation."
    if resolved_status in {"introduced", "developing", "unknown"}:
        return "Develop, resolve, or explicitly defer with a reminder beat."
    if resolved_status == "abandoned":
        return "Confirm the abandonment on-page if you want readers to stop expecting payoff."
    return None


def merge_plot_thread_status(existing_status: object | None, incoming_status: object | None) -> str:
    current = normalize_plot_thread_status(existing_status)
    incoming = normalize_plot_thread_status(incoming_status)
    if incoming == "unknown":
        return current
    if incoming == "resolved":
        return "resolved"
    if incoming == "contradicted":
        return "contradicted"
    if current == "resolved" and incoming in {"introduced", "developing", "paused"}:
        return "contradicted"
    if current == "abandoned" and incoming in {"introduced", "developing", "paused"}:
        return "contradicted"
    if incoming == "abandoned":
        return "abandoned"
    if current in {"contradicted", "resolved", "abandoned"}:
        return current
    if incoming == "paused":
        return "paused"
    if incoming == "developing":
        return "developing"
    if incoming == "introduced" and current == "unknown":
        return "introduced"
    return current


def build_plot_thread_payload(
    thread: Any,
    *,
    current_chapter: int | None,
) -> dict[str, Any]:
    title = normalize_plot_thread_title(getattr(thread, "title", ""))
    introduced_at = getattr(thread, "introduced_at", None)
    last_mentioned_at = getattr(thread, "last_mentioned_at", None) or introduced_at
    resolved_at = getattr(thread, "resolved_at", None)
    status = derive_plot_thread_status(
        getattr(thread, "status", None),
        introduced_at=introduced_at,
        last_mentioned_at=last_mentioned_at,
        resolved_at=resolved_at,
        current_chapter=current_chapter,
    )
    related_characters = normalize_related_characters(getattr(thread, "character_ids", None) or [])
    return {
        "id": str(getattr(thread, "id")),
        "title": title,
        "type": normalize_plot_thread_type(getattr(thread, "thread_type", None)),
        "status": status,
        "description": getattr(thread, "description", None),
        "introduced_at": introduced_at,
        "resolved_at": resolved_at,
        "first_mentioned": introduced_at,
        "last_mentioned": last_mentioned_at,
        "mention_count": int(getattr(thread, "mention_count", 0) or 0),
        "importance": int(getattr(thread, "importance", 5) or 5),
        "note": getattr(thread, "note", None),
        "character_ids": related_characters,
        "related_characters": related_characters,
        "risk": derive_plot_thread_risk(
            title=title,
            status=getattr(thread, "status", None),
            importance=getattr(thread, "importance", None),
            introduced_at=introduced_at,
            last_mentioned_at=last_mentioned_at,
            current_chapter=current_chapter,
        ),
        "suggested_action": derive_plot_thread_suggested_action(
            status=getattr(thread, "status", None),
            current_chapter=current_chapter,
            last_mentioned_at=last_mentioned_at,
        ),
    }
