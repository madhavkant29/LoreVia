import asyncio
import uuid
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.v1.routes.books import character_exports
from app.core import storage
from app.core.database import get_db
from app.core.redis import mark_book_cache_dirty
from app.models.book import Chapter, VaultNoteSource
from app.schemas.books import (
    NovelPrefaceBody,
    NovelSettingsBody,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_can_edit,
    collaboration_can_export,
    get_book_with_collaboration_access,
)
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
    load_novel_cover_image,
    load_novel_export_chapters,
)
from app.utils.books.scene_metadata import strip_scene_metadata_from_manuscript_text
from app.utils.books.scene_records import list_novel_scenes
from app.utils.books.vault_storage import (
    list_vault_notes,
)
from app.utils.books.writer_workspace import (
    build_writer_workspace_payload,
)
from app.utils.export_utils import (
    export_filename_base,
    manuscript_docx,
    manuscript_epub_compiled,
    manuscript_pdf_compiled,
    manuscript_vault_zip,
    normalize_export_font_family,
    novel_docx,
    novel_epub_compiled,
    novel_pdf_compiled,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS

router = APIRouter()
router.include_router(character_exports.router)


# ─── Manuscript export ──────────────────────────────────────────────────────


@router.get("/{book_id}/manuscript/export")
async def export_manuscript(
    book_id: uuid.UUID,
    format: str = Query("docx", pattern="^(pdf|docx|epub|vault)$"),
    preset: str = Query(
        "standard_manuscript", pattern="^(standard_manuscript|trade_paperback|kdp_paperback)$"
    ),
    include_scene_metadata: bool = Query(True),
    include_toc: bool = Query(False),
    font_family: str = Query("serif", pattern="^(serif|sans|mono|italian-old-style|eb-garamond)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    selected_font = normalize_export_font_family(font_family)
    include_toc_enabled = include_toc is True
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_export(collaborator):
        raise HTTPException(403, "This share cannot export the manuscript.")
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    if collaborator is not None:
        chapter_rows = [
            row for row in chapter_rows if collaboration_allows_chapter(collaborator, int(row[0]))
        ]
    if not chapter_rows:
        raise HTTPException(404, "No chapters available to export")

    chapters: list[dict] = []
    for number, chapter_title, s3_key in chapter_rows:
        chapter_text = ""
        chapter_html = None
        if s3_key:
            try:
                stored = deserialize_manuscript_content(
                    await asyncio.to_thread(storage.download_book, s3_key)
                )
                chapter_text = str(stored.get("text") or "")
                chapter_html = str(stored.get("html") or "") or None
            except STORAGE_IO_EXCEPTIONS:
                chapter_text = ""
                chapter_html = None
        if not include_scene_metadata:
            chapter_text = strip_scene_metadata_from_manuscript_text(chapter_text)
            chapter_html = None
        chapters.append(
            {"number": number, "title": chapter_title, "text": chapter_text, "html": chapter_html}
        )

    workspace = build_writer_workspace_payload(book)
    front_matter = workspace.get("manuscript_front_matter") if isinstance(workspace, dict) else None
    index_format: str = (
        (workspace.get("index_format") or "arabic") if isinstance(workspace, dict) else "arabic"
    )
    manuscript_scenes = [
        scene
        for scene in await list_novel_scenes(db, book=book, collaborator=collaborator)
        if scene.get("source") == "manual" and scene.get("status") != "archived"
    ]

    filename_base = export_filename_base(book.title)
    if format == "pdf":
        raw = manuscript_pdf_compiled(
            title=book.title or "LoreVia Manuscript",
            chapters=chapters,
            scenes=[],
            preset=preset,
            front_matter=cast(dict | None, front_matter),
            font_family=selected_font,
            include_toc=include_toc_enabled,
            index_format=index_format,
        )
        return Response(
            content=raw,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-manuscript.pdf"'
            },
        )
    if format == "epub":
        raw = manuscript_epub_compiled(
            title=book.title or "LoreVia Manuscript",
            chapters=chapters,
            scenes=[],
            preset=preset,
            front_matter=cast(dict | None, front_matter),
            font_family=selected_font,
            include_toc=include_toc_enabled,
            index_format=index_format,
        )
        return Response(
            content=raw,
            media_type="application/epub+zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-manuscript.epub"'
            },
        )
    if format == "vault":
        notes = await list_vault_notes(
            db,
            book=book,
            user_id=current_user.id,
            source=VaultNoteSource.USER_NOTES.value,
        )
        raw = manuscript_vault_zip(
            title=book.title or "LoreVia Manuscript",
            chapters=chapters,
            scenes=manuscript_scenes,
            notes=notes,
            front_matter=cast(dict | None, front_matter),
            font_family=selected_font,
            index_format=index_format,
        )
        return Response(
            content=raw,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-manuscript-vault.zip"'
            },
        )

    raw = manuscript_docx(
        title=book.title or "LoreVia Manuscript",
        chapters=chapters,
        scenes=[],
        preset=preset,
        front_matter=cast(dict | None, front_matter),
        font_family=selected_font,
        include_toc=include_toc_enabled,
        index_format=index_format,
    )
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}-manuscript.docx"'},
    )


@router.get("/{book_id}/novel/export")
async def export_novel(
    book_id: uuid.UUID,
    format: str = Query("pdf", pattern="^(pdf|docx|epub)$"),
    preset: str = Query(
        "standard_novel", pattern="^(standard_novel|trade_novel|large_print|ebook_optimized)$"
    ),
    include_images: bool = Query(False),
    image_placement: str = Query("end", pattern="^(end|inline|plates)$"),
    include_image_captions: bool = Query(False),
    preview_chapters: int | None = Query(None, ge=1, le=10),
    font_family: str = Query("serif", pattern="^(serif|sans|mono|italian-old-style|eb-garamond)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    selected_font = normalize_export_font_family(font_family)
    include_images_enabled = include_images is True
    include_captions_enabled = include_image_captions is True
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_export(collaborator):
        raise HTTPException(403, "This share cannot export the novel.")

    chapters = await load_novel_export_chapters(
        db,
        book=book,
        collaborator=collaborator,
        include_images=include_images_enabled,
    )
    preview_limit = preview_chapters if isinstance(preview_chapters, int) else None
    if preview_limit is not None:
        chapters = chapters[:preview_limit]
    workspace = build_writer_workspace_payload(book)
    front_matter = workspace.get("manuscript_front_matter") if isinstance(workspace, dict) else None
    preface = str(workspace.get("novel_preface") or "") if isinstance(workspace, dict) else ""
    novel_front_matter = (
        workspace.get("novel_front_matter") if isinstance(workspace, dict) else None
    )
    epub_metadata = workspace.get("novel_epub_metadata") if isinstance(workspace, dict) else None
    index_format: str = (
        (workspace.get("index_format") or "arabic") if isinstance(workspace, dict) else "arabic"
    )
    cover_image = await load_novel_cover_image(book)

    filename_base = export_filename_base(book.title)
    filename_suffix = "novel-preview" if preview_limit is not None else "novel"
    common_kwargs = {
        "title": book.title or "LoreVia Novel",
        "chapters": chapters,
        "preset": preset,
        "front_matter": cast(dict | None, front_matter),
        "preface": preface,
        "novel_front_matter": cast(dict | None, novel_front_matter),
        "epub_metadata": cast(dict | None, epub_metadata),
        "cover_image": cover_image,
        "font_family": selected_font,
        "include_images": include_images_enabled,
        "image_placement": image_placement,
        "include_image_captions": include_captions_enabled,
        "index_format": index_format,
    }
    if format == "pdf":
        raw = novel_pdf_compiled(**common_kwargs)
        return Response(
            content=raw,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-{filename_suffix}.pdf"'
            },
        )
    if format == "epub":
        raw = novel_epub_compiled(**common_kwargs)
        return Response(
            content=raw,
            media_type="application/epub+zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-{filename_suffix}.epub"'
            },
        )
    raw = novel_docx(**common_kwargs)
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_base}-{filename_suffix}.docx"'
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
