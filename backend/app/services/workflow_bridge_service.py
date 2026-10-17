from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.schemas.books import ManuscriptImportResult
from app.services.editor_project_service import auto_reprocess_enabled
from app.services.manuscript_import_service import persist_manuscript_import
from app.utils.books.workflow_bridge import build_workflow_import_jobs


async def apply_workflow_bridge_import(
    db: AsyncSession,
    *,
    book: Book,
    current_user: Any,
    filename: str,
    raw: bytes,
    format_name: str,
) -> ManuscriptImportResult:
    import_jobs = await build_workflow_import_jobs(filename, raw)
    return await persist_manuscript_import(
        db,
        book=book,
        current_user=current_user,
        import_jobs=import_jobs,
        screenplay_batches=[],
        replace_existing=True,
        chapter_number=None,
        expected_content_version=None,
        should_auto_reprocess=auto_reprocess_enabled(book),
        resolved_book_work_type=book.work_type or "novel",
        resolved_import_format=format_name,
        first_pdf_raw_for_cover=None,
        total_file_size=len(raw),
        files_were_uploaded=True,
    )
