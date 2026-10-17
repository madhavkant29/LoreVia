from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book
from app.schemas.books import ManuscriptImportJobOut, ManuscriptImportResult
from app.services.editor_project_service import auto_reprocess_enabled
from app.services.manuscript_import_job_service import (
    create_manuscript_import_job,
    should_queue_manuscript_import,
)
from app.services.manuscript_import_service import persist_manuscript_import
from app.services.upload_preview_service import (
    accept_upload_structure_plan,
    load_or_build_upload_preview,
)
from app.utils.books.chapter_titles import normalize_chapter_title
from app.utils.books.continuity import as_bool
from app.utils.books.imports import (
    next_chapter_number,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    parse_screenplay_upload,
)
from app.utils.books.manuscript import clean_manuscript_html
from app.utils.books.normalization import (
    normalize_book_work_type,
    resolve_upload_format_and_work_type,
    story_unit_name,
)
from app.utils.upload_security_utils import read_upload_bounded, validate_document_upload_bytes


async def execute_manuscript_import_request(
    db: AsyncSession,
    *,
    book: Book,
    current_user: Any,
    files: list[UploadFile] | None,
    text: str | None,
    html: str | None,
    title: str | None,
    work_type: str | None,
    chapter_number: int | None,
    replace_existing: str,
    expected_content_version: int | None,
    chunk_long_documents: str,
    split_into_chapters: str,
    structure_plan: str | None = None,
) -> tuple[ManuscriptImportResult | ManuscriptImportJobOut, bool]:
    """Stage a durable large import or parse and persist a small import."""
    if not text and not files:
        raise HTTPException(400, "Provide text or one or more files")

    manuscript_files = [upload for upload in (files or []) if upload.filename]
    if structure_plan is not None and len(manuscript_files) != 1:
        raise HTTPException(400, "An edited outline requires exactly one manuscript file.")
    if should_queue_manuscript_import(manuscript_files):
        queued = await create_manuscript_import_job(
            db,
            book=book,
            current_user=current_user,
            files=manuscript_files,
            text=text,
            html=html,
            title=title,
            work_type=work_type,
            chapter_number=chapter_number,
            replace_existing=replace_existing,
            expected_content_version=expected_content_version,
            chunk_long_documents=chunk_long_documents,
            split_into_chapters=split_into_chapters,
            structure_plan=structure_plan,
        )
        return queued, True

    import_jobs: list[dict[str, object]] = []
    structure_batches: list[dict[str, Any]] = []
    screenplay_batches: list[dict[str, object]] = []
    normalized_title = normalize_chapter_title(title) if title is not None else None
    next_number = await next_chapter_number(db, book.id)
    replace_flag = as_bool(replace_existing)
    chunk_flag = as_bool(chunk_long_documents)
    split_flag = as_bool(split_into_chapters)
    preserve_exact_structure = bool(book.preserve_chapter_numbers or book.preserve_source_chapters)
    resolved_book_work_type = normalize_book_work_type(work_type, default=book.work_type or "novel")
    resolved_import_format: str | None = None
    first_pdf_raw_for_cover: bytes | None = None
    cleaned_html = clean_manuscript_html(html) if html else None
    total_file_size = 0

    if text and text.strip():
        if resolved_book_work_type == "screenplay":
            screenplay_payload = await parse_screenplay_upload(
                "inline.fountain",
                text.encode("utf-8"),
            )
            new_jobs = normalize_imported_chapters(
                screenplay_payload["chapters"],
                chapter_number=chapter_number,
                start_number=chapter_number or next_number,
                replace_existing=replace_flag,
                chunk_long_documents=False,
                preserve_exact_structure=False,
            )
            import_jobs.extend(new_jobs)
            screenplay_batches.append(
                {
                    "parsed_scenes": screenplay_payload["scenes"],
                    "starting_number": min(int(cast(Any, job["number"])) for job in new_jobs),
                    "scene_numbers": {int(cast(Any, job["number"])) for job in new_jobs},
                }
            )
        else:
            import_jobs.extend(
                normalize_imported_chapters(
                    [
                        {
                            "title": normalized_title
                            or f"{story_unit_name(book)} {chapter_number or next_number}",
                            "text": text,
                            "html": cleaned_html,
                            "number": chapter_number or next_number,
                        }
                    ],
                    chapter_number=chapter_number,
                    start_number=chapter_number or next_number,
                    replace_existing=replace_flag,
                    chunk_long_documents=chunk_flag,
                    preserve_exact_structure=preserve_exact_structure,
                )
            )

    if len(manuscript_files) > settings.MANUSCRIPT_IMPORT_MAX_FILES:
        raise HTTPException(
            413,
            f"Manuscript import accepts at most {settings.MANUSCRIPT_IMPORT_MAX_FILES} files at once.",
        )

    for upload in manuscript_files:
        raw = await read_upload_bounded(
            upload,
            settings.MANUSCRIPT_IMPORT_MAX_BYTES,
            "Manuscript file",
        )
        if not raw:
            continue
        total_file_size += len(raw)
        if total_file_size > settings.MANUSCRIPT_IMPORT_MAX_TOTAL_BYTES:
            raise HTTPException(413, "Manuscript import exceeds the maximum aggregate upload size.")
        format_name, upload_work_type = resolve_upload_format_and_work_type(
            str(upload.filename),
            work_type if work_type is not None else book.work_type,
        )
        validate_document_upload_bytes(str(upload.filename), raw, format_name)
        resolved_import_format = resolved_import_format or format_name
        if format_name == "pdf" and first_pdf_raw_for_cover is None:
            first_pdf_raw_for_cover = raw
        accepted_plan = None
        if structure_plan is not None:
            preview = await load_or_build_upload_preview(
                user_id=current_user.id, raw=raw,
                format_name=format_name, work_type=upload_work_type,
            )
            accepted_plan = accept_upload_structure_plan(
                preview=preview, raw=raw, submitted=structure_plan,
            )
        parsed_payload = await parse_book_upload_for_ingestion(
            format_name=format_name,
            work_type=upload_work_type,
            raw=raw,
            preserve_chapter_numbers=bool(book.preserve_chapter_numbers),
            preserve_source_chapters=bool(book.preserve_source_chapters),
            filename=str(upload.filename),
            proposed_plan=accepted_plan,
        )
        screenplay_payload = (
            parsed_payload.get("screenplay_payload") if upload_work_type == "screenplay" else None
        )
        parsed = list(cast(list[dict[str, object]], parsed_payload["chapters"]))
        if upload_work_type != "screenplay" and not split_flag:
            merged_text = "\n\n".join(
                str(chapter.get("text") or "").strip() for chapter in parsed if chapter.get("text")
            )
            merged_html_parts = [
                str(chapter.get("html") or "").strip() for chapter in parsed if chapter.get("html")
            ]
            parsed = [
                {
                    "title": normalized_title or str(upload.filename).rsplit(".", 1)[0],
                    "text": merged_text,
                    "html": (
                        clean_manuscript_html("\n".join(merged_html_parts))
                        if merged_html_parts
                        else None
                    ),
                    "images": [
                        image for chapter in parsed for image in list(chapter.get("images") or [])
                    ],
                    "number": 1,
                }
            ]
        base_number = chapter_number if replace_flag and chapter_number else next_number
        new_jobs = normalize_imported_chapters(
            parsed,
            chapter_number=chapter_number,
            start_number=base_number,
            replace_existing=replace_flag and len(parsed) == 1,
            chunk_long_documents=False if upload_work_type == "screenplay" else chunk_flag,
            preserve_exact_structure=preserve_exact_structure or bool(parsed_payload.get("structure_plan")),
        )
        import_jobs.extend(new_jobs)
        if upload_work_type != "screenplay" and split_flag and not replace_flag:
            structure_batches.append({
                "scope": str(uuid.uuid4()),
                "plan": parsed_payload["structure_plan"],
                "jobs": new_jobs,
            })
        if upload_work_type == "screenplay" and screenplay_payload is not None:
            screenplay_batches.append(
                {
                    "parsed_scenes": screenplay_payload["scenes"],
                    "starting_number": min(int(cast(Any, job["number"])) for job in new_jobs),
                    "scene_numbers": {int(cast(Any, job["number"])) for job in new_jobs},
                }
            )
            resolved_book_work_type = "screenplay"
        next_number = max(
            next_number,
            max(
                (int(cast(Any, job["number"])) for job in import_jobs),
                default=next_number,
            )
            + 1,
        )

    if not import_jobs:
        raise HTTPException(400, "No importable manuscript content was found")

    result = await persist_manuscript_import(
        db,
        book=book,
        current_user=current_user,
        import_jobs=import_jobs,
        screenplay_batches=screenplay_batches,
        replace_existing=replace_flag,
        chapter_number=chapter_number,
        expected_content_version=expected_content_version,
        should_auto_reprocess=auto_reprocess_enabled(book),
        resolved_book_work_type=resolved_book_work_type,
        resolved_import_format=resolved_import_format,
        first_pdf_raw_for_cover=first_pdf_raw_for_cover,
        total_file_size=total_file_size,
        files_were_uploaded=bool(manuscript_files),
        structure_batches=structure_batches,
    )
    return result, False
