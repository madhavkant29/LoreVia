from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.book import Book, BookCollaborator, Chapter
from app.utils.advisor_beta_reader_report_utils import normalize_ai_beta_reader_state
from app.utils.books import revision_decisions, writer_workspace
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_is_chapter_restricted,
)


async def create_beta_reader_revision_task(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    report_id: str,
    candidate_id: str,
    collaborator: BookCollaborator | None = None,
) -> tuple[str, bool]:
    book = (
        await db.execute(select(Book).where(Book.id == book_id).with_for_update())
    ).scalar_one_or_none()
    if book is None:
        raise HTTPException(404, "Book not found.")

    workspace = writer_workspace.normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    state = normalize_ai_beta_reader_state(workspace.get("ai_beta_reader"))
    report = next((item for item in state["reports"] if item["report_id"] == report_id), None)
    if report is None:
        raise HTTPException(404, "AI beta reader report not found.")
    requested_chapters = report["coverage"]["requested_chapters"]
    if collaboration_is_chapter_restricted(collaborator) and (
        not requested_chapters
        or any(
            not collaboration_allows_chapter(collaborator, number) for number in requested_chapters
        )
    ):
        raise HTTPException(403, "This report includes chapters outside the collaboration scope.")
    candidate = next(
        (
            item
            for item in report.get("revision_candidates") or []
            if item.get("id") == candidate_id
        ),
        None,
    )
    if candidate is None:
        raise HTTPException(404, "Revision candidate not found.")

    finding_id = f"ai-beta-reader:{candidate_id}"
    board = writer_workspace._normalize_revision_board(workspace.get("revision_board"))
    existing = next((item for item in board["items"] if item.get("item_id") == finding_id), None)
    if existing and existing.get("task_id"):
        return str(existing["task_id"]), False

    chapter_numbers = {
        int(evidence["chapter_number"])
        for evidence in candidate.get("evidence") or []
        if isinstance(evidence, dict) and evidence.get("chapter_number")
    }
    if candidate.get("chapter_number"):
        chapter_numbers.add(int(candidate["chapter_number"]))
    versions = (
        dict(
            (
                await db.execute(
                    select(Chapter.number, Chapter.content_version).where(
                        Chapter.book_id == book_id,
                        Chapter.number.in_(chapter_numbers),
                    )
                )
            ).all()
        )
        if chapter_numbers
        else {}
    )
    evidence = [
        {
            "chapter_ref": item.get("chapter_number"),
            "excerpt": item.get("excerpt"),
            "source_content_version": versions.get(item.get("chapter_number"), 1),
        }
        for item in candidate.get("evidence") or []
        if isinstance(item, dict)
    ]
    finding: dict[str, Any] = {
        "id": finding_id,
        "category": candidate["category"],
        "severity": candidate["severity"],
        "title": candidate["title"],
        "description": candidate["description"],
        "recommendation": candidate["recommendation"],
        "chapter_ref": candidate.get("chapter_number"),
        "source_label": "AI Beta Reader",
        "evidence": evidence,
    }
    revision_decisions.apply_revision_finding_decision(
        book,
        finding=finding,
        decision="accepted",
        action="added_to_revision_plan",
        reason=None,
    )
    updated_workspace = writer_workspace.normalize_writer_workspace(book.writer_workspace)
    updated_board = writer_workspace._normalize_revision_board(
        updated_workspace.get("revision_board")
    )
    task_id = f"ai-beta-reader-task:{candidate_id}"
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for item in updated_board["items"]:
        if item.get("item_id") == finding_id:
            item["task_id"] = task_id
            item["updated_at"] = now
            break
    updated_workspace["revision_board"] = updated_board
    book.writer_workspace = updated_workspace
    await db.commit()
    await mark_book_cache_dirty(str(book_id))
    return task_id, True
