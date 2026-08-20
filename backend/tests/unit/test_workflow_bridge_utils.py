import uuid

from fastapi import HTTPException
import pytest

from app.utils.books import workflow_bridge


@pytest.mark.asyncio
async def test_workflow_import_jobs_reject_empty_manuscripts(monkeypatch):
    async def parse_empty(filename, raw, split_into_chapters):
        return [{"number": 1, "title": "Empty", "text": "   "}]

    monkeypatch.setattr(workflow_bridge, "parse_import_upload", parse_empty)

    with pytest.raises(HTTPException) as exc_info:
        await workflow_bridge.build_workflow_import_jobs("empty.docx", b"docx")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_workflow_import_jobs_use_the_same_normalized_sequence_as_apply(monkeypatch):
    async def parse_chapters(filename, raw, split_into_chapters):
        return [
            {"number": 8, "title": " First  Chapter ", "text": "  Draft text  "},
            {"number": 9, "title": "Empty", "text": ""},
        ]

    monkeypatch.setattr(workflow_bridge, "parse_import_upload", parse_chapters)

    jobs = await workflow_bridge.build_workflow_import_jobs("draft.docx", b"docx")

    assert len(jobs) == 1
    assert jobs[0]["number"] == 1
    assert jobs[0]["title"] == "First Chapter"
    assert jobs[0]["text"] == "Draft text"


def test_workflow_preview_token_is_bound_to_user_book_and_file():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    token = workflow_bridge.build_workflow_preview_token(
        user_id=user_id,
        book_id=book_id,
        format_name="docx",
        raw=b"reviewed file",
        book_state_digest="state-v1",
    )

    workflow_bridge.verify_workflow_preview_token(
        token,
        user_id=user_id,
        book_id=book_id,
        format_name="docx",
        raw=b"reviewed file",
        book_state_digest="state-v1",
    )

    for changed in (
        {"user_id": uuid.uuid4(), "book_id": book_id, "format_name": "docx", "raw": b"reviewed file", "book_state_digest": "state-v1"},
        {"user_id": user_id, "book_id": uuid.uuid4(), "format_name": "docx", "raw": b"reviewed file", "book_state_digest": "state-v1"},
        {"user_id": user_id, "book_id": book_id, "format_name": "scrivener", "raw": b"reviewed file", "book_state_digest": "state-v1"},
        {"user_id": user_id, "book_id": book_id, "format_name": "docx", "raw": b"different file", "book_state_digest": "state-v1"},
        {"user_id": user_id, "book_id": book_id, "format_name": "docx", "raw": b"reviewed file", "book_state_digest": "state-v2"},
    ):
        with pytest.raises(HTTPException) as exc_info:
            workflow_bridge.verify_workflow_preview_token(token, **changed)
        assert exc_info.value.status_code == 409


def test_workflow_book_state_digest_changes_with_manuscript_state():
    chapter = type(
        "ChapterState",
        (),
        {
            "id": uuid.uuid4(),
            "number": 1,
            "title": "Opening",
            "content_version": 2,
            "word_count": 120,
            "s3_key": "books/chapter-1-v2.txt",
        },
    )()
    original = workflow_bridge.workflow_book_state_digest([chapter])

    chapter.content_version = 3

    assert workflow_bridge.workflow_book_state_digest([chapter]) != original
