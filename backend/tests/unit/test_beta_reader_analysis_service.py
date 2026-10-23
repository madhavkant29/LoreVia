import uuid
from types import SimpleNamespace

import pytest

from app.schemas.advisor import BetaReaderAnalysisRequest
from app.services import beta_reader_analysis_service
from app.utils.advisor_beta_reader_report_utils import bound_beta_reader_report


@pytest.mark.asyncio
async def test_reader_feedback_synthesis_reuses_shared_openai_client(monkeypatch):
    class Client:
        closed = False

        async def close(self):
            self.closed = True

    client = Client()
    calls = []

    async def complete(**kwargs):
        assert kwargs["client"] is client
        assert client.closed is False
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"overall_impression":"Clear"}'))]
        )

    monkeypatch.setattr(beta_reader_analysis_service, "get_openai_client", lambda: client)
    monkeypatch.setattr(beta_reader_analysis_service, "create_tracked_chat_completion", complete)

    for _ in range(2):
        result = await beta_reader_analysis_service._reader_feedback_synthesis(
            db=SimpleNamespace(),
            book=SimpleNamespace(id=uuid.uuid4(), title="The Silver Gate"),
            user_id=uuid.uuid4(),
            chapter_texts={1: "The silver gate opened."},
            overused_terms=[],
            voices=[],
            progress=None,
        )
        assert result["overall_impression"] == "Clear"

    assert len(calls) == 2
    assert client.closed is False


@pytest.mark.asyncio
async def test_reader_feedback_synthesis_preserves_shared_client_after_provider_error(monkeypatch):
    class Client:
        closed = False

        async def close(self):
            self.closed = True

    client = Client()

    async def fail(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(beta_reader_analysis_service, "get_openai_client", lambda: client)
    monkeypatch.setattr(beta_reader_analysis_service, "create_tracked_chat_completion", fail)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await beta_reader_analysis_service._reader_feedback_synthesis(
            db=SimpleNamespace(),
            book=SimpleNamespace(id=uuid.uuid4(), title="The Silver Gate"),
            user_id=uuid.uuid4(),
            chapter_texts={1: "The silver gate opened."},
            overused_terms=[],
            voices=[],
            progress=None,
        )

    assert client.closed is False


def _stored_report() -> dict:
    return {
        "report_id": "report-1",
        "scope": "passage",
        "request_hash": "request-hash",
        "source_fingerprint": "source-fingerprint",
        "created_at": "2026-08-30T00:00:00Z",
        "is_stale": False,
        "checks": ["repetition"],
        "coverage": {
            "requested_chapters": [],
            "analyzed_chapters": [],
            "missing_chapters": [],
            "word_count": 10,
            "character_count": 0,
        },
        "overall_impression": "Deterministic pass complete.",
        "strengths": [],
        "reader_questions": [],
        "prioritized_revisions": [],
        "overused_terms": [],
        "character_voices": [],
        "findings": [],
        "revision_candidates": [],
        "warnings": [],
    }


@pytest.mark.asyncio
async def test_build_report_keeps_deterministic_results_when_reader_synthesis_fails(
    monkeypatch,
):
    async def prepare_run(*args, **kwargs):
        return {
            "chapters": [],
            "request_hash": "request-hash",
            "source_fingerprint": "source-fingerprint",
            "cached": None,
        }

    async def character_context(*args, **kwargs):
        return [], [], []

    async def reader_feedback(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(beta_reader_analysis_service, "prepare_beta_reader_run", prepare_run)
    monkeypatch.setattr(beta_reader_analysis_service, "_character_context", character_context)
    monkeypatch.setattr(beta_reader_analysis_service, "_reader_feedback_synthesis", reader_feedback)

    progress_events: list[dict] = []

    async def progress(payload: dict):
        progress_events.append(payload)

    report = await beta_reader_analysis_service.build_beta_reader_report(
        SimpleNamespace(),
        book=SimpleNamespace(id=uuid.uuid4(), title="The Silver Gate"),
        collaborator=None,
        user_id=uuid.uuid4(),
        body=BetaReaderAnalysisRequest(
            scope="passage",
            text="Quietly quietly quietly quietly quietly, the silver gate opened.",
            checks=["repetition", "reader_feedback"],
        ),
        progress=progress,
    )

    assert any(item["term"] == "quietly" for item in report["overused_terms"])
    assert any("synthesis was unavailable" in warning for warning in report["warnings"])
    assert progress_events[0]["stage"] == "analysis"


@pytest.mark.asyncio
async def test_build_report_fails_when_reader_feedback_is_the_only_requested_check(
    monkeypatch,
):
    async def prepare_run(*args, **kwargs):
        return {
            "chapters": [],
            "request_hash": "request-hash",
            "source_fingerprint": "source-fingerprint",
            "cached": None,
        }

    async def character_context(*args, **kwargs):
        return [], [], []

    async def reader_feedback(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(beta_reader_analysis_service, "prepare_beta_reader_run", prepare_run)
    monkeypatch.setattr(beta_reader_analysis_service, "_character_context", character_context)
    monkeypatch.setattr(beta_reader_analysis_service, "_reader_feedback_synthesis", reader_feedback)

    with pytest.raises(RuntimeError, match="model unavailable"):
        await beta_reader_analysis_service.build_beta_reader_report(
            SimpleNamespace(),
            book=SimpleNamespace(id=uuid.uuid4(), title="The Silver Gate"),
            collaborator=None,
            user_id=uuid.uuid4(),
            body=BetaReaderAnalysisRequest(
                scope="passage",
                text="A complete passage for a reader reaction.",
                checks=["reader_feedback"],
            ),
        )


@pytest.mark.asyncio
async def test_persist_report_merges_against_locked_latest_workspace_state():
    fresh_book = SimpleNamespace(
        writer_workspace={
            "word_count_goals": {
                "chapter_target": 2500,
                "book_target": 92000,
                "session_target": 1000,
            },
            "novel_preface": "A concurrent workspace edit",
        }
    )

    class Result:
        def scalar_one(self):
            return fresh_book

    class Database:
        committed = False

        async def execute(self, statement):
            return Result()

        async def commit(self):
            self.committed = True

    db = Database()
    report = _stored_report()
    persisted = await beta_reader_analysis_service.persist_beta_reader_report(
        db,
        book_id=uuid.uuid4(),
        report=report,
    )

    assert persisted == report
    assert db.committed is True
    assert fresh_book.writer_workspace["word_count_goals"]["book_target"] == 92000
    assert fresh_book.writer_workspace["novel_preface"] == "A concurrent workspace edit"
    assert fresh_book.writer_workspace["ai_beta_reader"]["reports"][0] == (
        bound_beta_reader_report(report)
    )
