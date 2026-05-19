from types import SimpleNamespace

from app.services.pipeline_state_service import (
    build_writer_workspace_response,
    build_writer_workspace_update,
)


def test_build_writer_workspace_response_preserves_processing_pipeline_fields():
    book = SimpleNamespace(
        title="Atlas",
        author="M. Author",
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "chapter_complete",
                "chapters_completed": 2,
                "chapters_total": 4,
                "is_fully_ready": False,
                "retry_actions": ["retry_analysis"],
                "pipeline": {
                    "extraction": {"status": "succeeded", "completed_chapters": 4, "total_chapters": 4},
                    "analysis": {"status": "running", "completed_chapters": 2, "total_chapters": 4},
                },
            }
        },
    )

    payload = build_writer_workspace_response(book)

    assert payload.processing is not None
    assert payload.processing.pipeline is not None
    assert payload.processing.pipeline.extraction is not None
    assert payload.processing.pipeline.extraction.status == "succeeded"
    assert payload.processing.pipeline.analysis is not None
    assert payload.processing.pipeline.analysis.status == "running"
    assert payload.processing.retry_actions == ["retry_analysis"]


def test_build_writer_workspace_update_merges_existing_workspace_with_updates():
    book = SimpleNamespace(
        title="Atlas",
        author="M. Author",
        writer_workspace={
            "goal_calendar": [{"id": "g1", "title": "Draft", "due_date": "2026-05-20", "completed": False}],
            "processing": {"status": "processing", "stage": "queued"},
        },
    )

    updated = build_writer_workspace_update(
        book,
        {
            "goal_calendar": [],
            "processing": {"status": "ready", "stage": "complete", "is_fully_ready": True},
        },
    )

    assert updated["goal_calendar"] == []
    assert updated["processing"]["status"] == "ready"
    assert updated["processing"]["is_fully_ready"] is True
