from datetime import UTC, datetime

from app.services.processing_pause_service import (
    parse_processing_blocker,
    parse_processing_resume_at,
)


def test_parse_processing_blocker_preserves_structured_limit_details():
    blocker = parse_processing_blocker(
        '{"kind":"llm_tokens","auto_resume":true,"next_resume_at":"2026-09-01T12:00:00+00:00"}'
    )

    assert blocker == {
        "kind": "llm_tokens",
        "auto_resume": True,
        "next_resume_at": "2026-09-01T12:00:00+00:00",
    }


def test_parse_processing_blocker_falls_back_for_plain_text_and_non_object_json():
    assert parse_processing_blocker("provider unavailable") == {"detail": "provider unavailable"}
    assert parse_processing_blocker('["unexpected"]') == {"detail": '["unexpected"]'}
    assert parse_processing_blocker(None) == {}


def test_parse_processing_resume_at_normalizes_naive_time_to_utc():
    assert parse_processing_resume_at("2026-09-01T12:00:00") == datetime(
        2026, 9, 1, 12, 0, tzinfo=UTC
    )
    assert parse_processing_resume_at("2026-09-01T17:30:00+05:30") == datetime.fromisoformat(
        "2026-09-01T17:30:00+05:30"
    )


def test_parse_processing_resume_at_rejects_missing_or_invalid_values():
    assert parse_processing_resume_at(None) is None
    assert parse_processing_resume_at(123) is None
    assert parse_processing_resume_at("not-a-time") is None
