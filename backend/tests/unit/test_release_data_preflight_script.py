from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.release_data_preflight_service import (
    DuplicateSummary,
    ReleaseDataPreflight,
)
from scripts import check_release_data_preflight


@pytest.mark.asyncio
async def test_release_data_preflight_script_emits_redacted_aggregate_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = ReleaseDataPreflight(
        transaction_read_only=True,
        duplicate_checks={
            "book_chunks.chapter_id_chunk_index": DuplicateSummary(0, 0),
        },
        required_constraints_present=(),
        required_constraints_missing=("uq_book_chunks_chapter_id_chunk_index",),
        chapter_number_duplicate_groups=2,
        safe_for_constraint_rollout=True,
    )
    audit = AsyncMock(return_value=result)
    dispose = AsyncMock()
    script_engine = SimpleNamespace(dispose=dispose)
    monkeypatch.setattr(check_release_data_preflight, "audit_release_data_from_engine", audit)
    monkeypatch.setattr(check_release_data_preflight, "engine", script_engine)
    monkeypatch.setattr(
        check_release_data_preflight.settings,
        "DATABASE_URL",
        "postgresql+psycopg://audit-user:super-secret@db.example/lorevia",
    )

    exit_code = await check_release_data_preflight.main()

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["database_target"] == "postgresql+psycopg://db.example/lorevia"
    assert report["chapter_number_duplicate_groups"] == 2
    assert "super-secret" not in json.dumps(report)
    audit.assert_awaited_once_with(script_engine)
    dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_release_data_preflight_script_returns_two_for_blocking_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = ReleaseDataPreflight(
        transaction_read_only=True,
        duplicate_checks={
            "reading_progress.user_id_book_id": DuplicateSummary(1, 1),
        },
        required_constraints_present=(),
        required_constraints_missing=("uq_reading_progress_user_id_book_id",),
        chapter_number_duplicate_groups=0,
        safe_for_constraint_rollout=False,
    )
    monkeypatch.setattr(
        check_release_data_preflight,
        "audit_release_data_from_engine",
        AsyncMock(return_value=result),
    )
    monkeypatch.setattr(
        check_release_data_preflight,
        "engine",
        SimpleNamespace(dispose=AsyncMock()),
    )

    assert await check_release_data_preflight.main() == 2
