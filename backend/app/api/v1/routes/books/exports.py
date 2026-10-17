import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Response as FastAPIResponse
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.v1.routes.books import character_exports
from app.core import storage
from app.core.database import get_db
from app.core.redis import mark_book_cache_dirty
from app.schemas.books import (
    ManuscriptExportJobOut,
    ManuscriptExportPreparationOut,
    ManuscriptExportRequest,
    NovelPrefaceBody,
    NovelSettingsBody,
)
from app.services.manuscript_export_service import (
    generate_manuscript_export_artifact,
    get_manuscript_export_job,
    manuscript_export_job_out,
    prepare_manuscript_export,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_can_edit,
    get_book_with_collaboration_access,
)
from app.utils.books.writer_workspace import (
    build_writer_workspace_payload,
)

router = APIRouter()
router.include_router(character_exports.router)


# ─── Manuscript export ──────────────────────────────────────────────────────


@router.get("/{book_id}/manuscript/export")
async def export_manuscript(
    book_id: uuid.UUID,
    format: Annotated[str, Query(pattern="^(pdf|docx|epub|vault)$")] = "docx",
    preset: Annotated[
        str,
        Query(pattern="^(standard_manuscript|trade_paperback|kdp_paperback)$"),
    ] = "standard_manuscript",
    include_scene_metadata: Annotated[bool, Query()] = True,
    include_toc: Annotated[bool, Query()] = False,
    font_family: Annotated[
        str,
        Query(pattern="^(serif|sans|mono|italian-old-style|eb-garamond)$"),
    ] = "serif",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    export_request = ManuscriptExportRequest(
        export_kind="manuscript",
        format=format,
        preset=preset,
        include_scene_metadata=include_scene_metadata is True,
        include_toc=include_toc is True,
        font_family=font_family,
    )
    preparation = await prepare_manuscript_export(
        db,
        book_id=book_id,
        current_user=current_user,
        request=export_request,
    )
    if preparation.delivery == "job" and preparation.job is not None:
        return FastAPIResponse(
            content=preparation.model_dump_json(),
            status_code=202,
            media_type="application/json",
            headers={
                "Location": f"/api/v1/books/{book_id}/exports/{preparation.job.id}",
                "Retry-After": "2",
            },
        )
    artifact = await generate_manuscript_export_artifact(
        db,
        book_id=book_id,
        current_user=current_user,
        request=export_request,
    )
    try:
        return FastAPIResponse(
            content=artifact.stream.read(),
            media_type=artifact.media_type,
            headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
        )
    finally:
        artifact.stream.close()


@router.get("/{book_id}/novel/export")
async def export_novel(
    book_id: uuid.UUID,
    format: Annotated[str, Query(pattern="^(pdf|docx|epub)$")] = "pdf",
    preset: Annotated[
        str,
        Query(pattern="^(standard_novel|trade_novel|large_print|ebook_optimized)$"),
    ] = "standard_novel",
    include_images: Annotated[bool, Query()] = False,
    image_placement: Annotated[str, Query(pattern="^(end|inline|plates)$")] = "end",
    include_image_captions: Annotated[bool, Query()] = False,
    preview_chapters: Annotated[int | None, Query(ge=1, le=10)] = None,
    font_family: Annotated[
        str,
        Query(pattern="^(serif|sans|mono|italian-old-style|eb-garamond)$"),
    ] = "serif",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    export_request = ManuscriptExportRequest(
        export_kind="novel",
        format=format,
        preset=preset,
        include_images=include_images is True,
        image_placement=image_placement,
        include_image_captions=include_image_captions is True,
        preview_chapters=preview_chapters,
        font_family=font_family,
    )
    preparation = await prepare_manuscript_export(
        db,
        book_id=book_id,
        current_user=current_user,
        request=export_request,
    )
    if preparation.delivery == "job" and preparation.job is not None:
        return FastAPIResponse(
            content=preparation.model_dump_json(),
            status_code=202,
            media_type="application/json",
            headers={
                "Location": f"/api/v1/books/{book_id}/exports/{preparation.job.id}",
                "Retry-After": "2",
            },
        )
    artifact = await generate_manuscript_export_artifact(
        db,
        book_id=book_id,
        current_user=current_user,
        request=export_request,
    )
    try:
        return FastAPIResponse(
            content=artifact.stream.read(),
            media_type=artifact.media_type,
            headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
        )
    finally:
        artifact.stream.close()


@router.post(
    "/{book_id}/exports/prepare",
    response_model=ManuscriptExportPreparationOut,
)
async def prepare_export(
    book_id: uuid.UUID,
    body: ManuscriptExportRequest,
    response: FastAPIResponse,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await prepare_manuscript_export(
        db,
        book_id=book_id,
        current_user=current_user,
        request=body,
    )
    if result.delivery == "job":
        response.status_code = 202
    return result


@router.get(
    "/{book_id}/exports/{job_id}",
    response_model=ManuscriptExportJobOut,
)
async def export_job_status(
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_book_with_collaboration_access(db, book_id, current_user)
    job = await get_manuscript_export_job(
        db,
        job_id=job_id,
        book_id=book_id,
        user_id=current_user.id,
    )
    return manuscript_export_job_out(job)


@router.get("/{book_id}/exports/{job_id}/download")
async def download_export_job_artifact(
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_book_with_collaboration_access(db, book_id, current_user)
    job = await get_manuscript_export_job(
        db,
        job_id=job_id,
        book_id=book_id,
        user_id=current_user.id,
    )
    if job.status == "expired":
        raise HTTPException(410, "This export has expired")
    if job.status != "completed" or not job.artifact_storage_key:
        raise HTTPException(409, "This export is not ready to download")
    return StreamingResponse(
        storage.iter_object_chunks(job.artifact_storage_key),
        media_type=job.artifact_media_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{job.artifact_filename or "export.bin"}"',
            **(
                {"Content-Length": str(job.artifact_size_bytes)}
                if job.artifact_size_bytes is not None
                else {}
            ),
        },
    )


@router.put("/{book_id}/novel/preface")
async def save_novel_preface(
    book_id: uuid.UUID,
    body: NovelPrefaceBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    workspace = build_writer_workspace_payload(book)
    workspace["novel_preface"] = str(body.preface or "").strip()
    book.writer_workspace = workspace
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return {"preface": workspace["novel_preface"]}


@router.put("/{book_id}/novel/settings")
async def save_novel_settings(
    book_id: uuid.UUID,
    body: NovelSettingsBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    workspace = build_writer_workspace_payload(book)
    front_matter = body.front_matter
    epub_metadata = body.epub_metadata
    workspace["novel_preface"] = str(body.preface or "").strip()
    workspace["novel_front_matter"] = {
        "dedication": str(front_matter.dedication or "").strip(),
        "acknowledgements": str(front_matter.acknowledgements or "").strip(),
        "copyright_page": str(front_matter.copyright_page or "").strip(),
        "about_author": str(front_matter.about_author or "").strip(),
        "series_book_list": str(front_matter.series_book_list or "").strip(),
    }
    workspace["novel_epub_metadata"] = {
        "publisher": str(epub_metadata.publisher or "").strip(),
        "language": str(epub_metadata.language or "en").strip() or "en",
        "isbn": str(epub_metadata.isbn or "").strip(),
        "description": str(epub_metadata.description or "").strip(),
        "series_name": str(epub_metadata.series_name or "").strip(),
        "series_number": str(epub_metadata.series_number or "").strip(),
    }
    book.writer_workspace = workspace
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return {
        "preface": workspace["novel_preface"],
        "front_matter": workspace["novel_front_matter"],
        "epub_metadata": workspace["novel_epub_metadata"],
    }
