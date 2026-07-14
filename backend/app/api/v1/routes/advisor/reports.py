from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_continuity_checker
from app.api.v1.routes.advisor.editing import editorial_review
from app.api.v1.routes.advisor.suggestions import advisor_suggestions
from app.core.database import get_db
from app.models.book import Book
from app.schemas.advisor import EditorialReviewRequest
from app.utils.advisor_utils import build_continuity_report_markdown, build_continuity_report_pdf
from app.utils.export_utils import export_filename_base

router = APIRouter()


@router.get("/{book_id}/advisor/continuity-report")
async def continuity_report(
    book_id: uuid.UUID,
    text: str = Query(...),
    chapter_num: int | None = Query(None),
    format: str = Query("pdf", pattern="^(pdf|md)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    if not text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    review_payload = await editorial_review(
        book_id=book_id,
        body=EditorialReviewRequest(text=text, chapter_num=chapter_num),
        db=db,
        current_user=current_user,
        _=_,
    )
    suggestions_payload = await advisor_suggestions(
        book_id=book_id, db=db, current_user=current_user
    )
    open_threads = [
        item
        for item in suggestions_payload.get("suggestions", [])
        if item.get("type")
        in {"dropped_thread", "future_direction", "unresolved_clue", "arc_opportunity"}
    ][:8]

    markdown = build_continuity_report_markdown(
        title=book.title,
        chapter_num=chapter_num,
        review=review_payload["review"],
        retrieved_passages=review_payload["retrieved_passages"],
        open_threads=open_threads,
    )
    filename_base = export_filename_base(book.title)

    if format == "md":
        return Response(
            content=markdown.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-continuity-report.md"'
            },
        )

    raw = build_continuity_report_pdf(markdown, title=book.title, chapter_num=chapter_num)
    return Response(
        content=raw,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_base}-continuity-report.pdf"'
        },
    )
