"""Classify voice-review pauses before persisting their retry schedule."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.services.voice_chapter_review_service import voice_chapter_pause


def test_configuration_failure_is_not_scheduled_as_capacity_retry():
    for kind in ("llm_attribution", "llm_configuration"):
        assert voice_chapter_pause(HTTPException(503, detail={"kind": kind}), 0) is None


def test_future_quota_refresh_is_scheduled():
    refresh = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    pause = voice_chapter_pause(
        HTTPException(
            429,
            detail={"kind": "llm_tokens", "auto_resume": True, "next_resume_at": refresh},
        ),
        0,
    )
    assert pause is not None and pause[1] == refresh


def test_stale_quota_refresh_uses_bounded_backoff_then_manual_pause():
    stale = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    exc = HTTPException(
        429, detail={"kind": "llm_budget", "auto_resume": True, "next_resume_at": stale}
    )
    pause = voice_chapter_pause(exc, 0)
    assert pause is not None and pause[1] is not None
    assert datetime.fromisoformat(pause[1]) > datetime.now(UTC)
    assert voice_chapter_pause(exc, 3) == (
        "AI allowance is unavailable. Retry after your plan window refreshes.",
        None,
    )


def test_malformed_quota_refresh_does_not_crash_or_auto_retry():
    pause = voice_chapter_pause(
        HTTPException(
            429,
            detail={"kind": "llm_tokens", "auto_resume": True, "next_resume_at": "tomorrow"},
        ),
        0,
    )
    assert pause is not None and pause[1] is None
