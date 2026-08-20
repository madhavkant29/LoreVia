from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import BetaReadFeedbackItem
from app.models.book import Book, Chapter, NovelScene
from app.utils.books.chapter_versions import snapshot_chapter_version
from app.utils.books.writer_workspace import normalize_writer_workspace


def list_revision_rounds(book: Book) -> list[dict[str, Any]]:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    return list(workspace.get("revision_rounds") or [])


async def _current_revision_summary(
    db: AsyncSession, *, book: Book, chapters: list[Chapter]
) -> dict[str, int]:
    scene_count = int(
        (await db.execute(select(func.count(NovelScene.id)).where(NovelScene.book_id == book.id)))
        .scalar_one()
        or 0
    )
    feedback_items = list(
        (
            await db.execute(
                select(BetaReadFeedbackItem).where(BetaReadFeedbackItem.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    board_items = list(
        normalize_writer_workspace(book.writer_workspace).get("revision_board", {}).get("items", [])
    )
    open_items = [item for item in board_items if item.get("status") not in {"resolved", "dismissed"}]
    high_count = sum(
        1
        for item in open_items
        if str((item.get("finding_snapshot") or {}).get("severity") or "").lower()
        in {"high", "critical"}
    )
    return {
        "chapter_count": len(chapters),
        "word_count": sum(int(chapter.word_count or 0) for chapter in chapters),
        "scene_count": scene_count,
        "open_finding_count": len(open_items),
        "high_severity_count": high_count,
        "open_beta_feedback_count": sum(
            1
            for item in feedback_items
            if str((item.metadata_json or {}).get("author_status") or "open") == "open"
        ),
    }


async def create_revision_round(
    db: AsyncSession,
    *,
    book: Book,
    label: str,
    note: str | None,
) -> dict[str, Any]:
    cleaned_label = " ".join(label.split()).strip()
    if not cleaned_label:
        raise HTTPException(400, "Revision round label is required.")
    chapters = list(
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    )
    if not chapters:
        raise HTTPException(409, "Add manuscript chapters before capturing a revision round.")
    round_id = str(uuid.uuid4())
    chapter_manifests = []
    for chapter in chapters:
        version = await snapshot_chapter_version(
            db,
            book,
            chapter,
            note=f"Revision round: {cleaned_label}",
            snapshot_kind="revision_round",
        )
        chapter_manifests.append(
            {
                "number": int(chapter.number),
                "title": str(chapter.title or f"Chapter {chapter.number}"),
                "version_id": str(version.id) if version is not None else None,
                "content_version": int(chapter.content_version or 1),
                "word_count": int(chapter.word_count or 0),
            }
        )
    revision_round = {
        "id": round_id,
        "label": cleaned_label,
        "note": str(note or "").strip() or None,
        "created_at": datetime.now(UTC).isoformat(),
        "chapters": chapter_manifests,
        "summary": await _current_revision_summary(db, book=book, chapters=chapters),
    }
    workspace = normalize_writer_workspace(book.writer_workspace)
    workspace["revision_rounds"] = [*(workspace.get("revision_rounds") or []), revision_round][-20:]
    book.writer_workspace = workspace
    await db.commit()
    await db.refresh(book)
    return revision_round


async def compare_revision_rounds(
    db: AsyncSession,
    *,
    book: Book,
    base_round_id: str,
    target_round_id: str | None,
) -> dict[str, Any]:
    rounds = {item["id"]: item for item in list_revision_rounds(book)}
    base = rounds.get(base_round_id)
    if base is None:
        raise HTTPException(404, "Base revision round not found.")
    if target_round_id:
        target = rounds.get(target_round_id)
        if target is None:
            raise HTTPException(404, "Target revision round not found.")
    else:
        chapters = list(
            (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc())
                )
            )
            .scalars()
            .all()
        )
        target = {
            "chapters": [
                {
                    "number": int(chapter.number),
                    "content_version": int(chapter.content_version or 1),
                    "word_count": int(chapter.word_count or 0),
                }
                for chapter in chapters
            ],
            "summary": await _current_revision_summary(db, book=book, chapters=chapters),
        }
    base_chapters = {int(item["number"]): item for item in base.get("chapters") or []}
    target_chapters = {int(item["number"]): item for item in target.get("chapters") or []}
    shared = set(base_chapters) & set(target_chapters)
    base_summary = base.get("summary") or {}
    target_summary = target.get("summary") or {}
    return {
        "base_round_id": base_round_id,
        "target_round_id": target_round_id,
        "changed_chapters": sorted(
            number
            for number in shared
            if int(base_chapters[number].get("content_version") or 0)
            != int(target_chapters[number].get("content_version") or 0)
            or int(base_chapters[number].get("word_count") or 0)
            != int(target_chapters[number].get("word_count") or 0)
        ),
        "added_chapters": sorted(set(target_chapters) - set(base_chapters)),
        "removed_chapters": sorted(set(base_chapters) - set(target_chapters)),
        "chapter_delta": int(target_summary.get("chapter_count") or 0) - int(base_summary.get("chapter_count") or 0),
        "word_count_delta": int(target_summary.get("word_count") or 0) - int(base_summary.get("word_count") or 0),
        "scene_count_delta": int(target_summary.get("scene_count") or 0) - int(base_summary.get("scene_count") or 0),
        "open_finding_delta": int(target_summary.get("open_finding_count") or 0) - int(base_summary.get("open_finding_count") or 0),
        "open_beta_feedback_delta": int(target_summary.get("open_beta_feedback_count") or 0) - int(base_summary.get("open_beta_feedback_count") or 0),
    }
