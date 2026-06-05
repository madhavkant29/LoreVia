import asyncio
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core import storage
from app.core.database import get_db
from app.models.book import Book, Chapter, VaultNoteSource
from app.models.character import Character
from app.schemas.books import (
    VaultPreviewOut,
    VaultNoteBody,
    VaultNoteOut,
    VaultNoteSaveOut,
)
from app.utils.billing_utils import require_author_access
from app.utils.book_utils import (
    build_character_card_payload,
    build_writer_workspace_payload,
    collaboration_allows_chapter,
    collaboration_can_edit,
    collaboration_can_export,
    collaboration_has_resource,
    deserialize_manuscript_content,
    get_book_with_collaboration_access,
    get_owned_book,
    list_novel_scenes,
    list_vault_notes,
    list_vault_bible_notes,
    load_vault_note_overrides,
    save_vault_note,
    strip_scene_metadata_from_manuscript_text,
)
from app.utils.character_utils import is_displayable_character
from app.utils.export_utils import (
    build_character_bible_vault_context,
    character_bible_docx,
    character_bible_markdown,
    character_bible_vault_folder,
    character_bible_vault_preview,
    character_bible_pdf,
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
    export_filename_base,
    manuscript_docx,
    manuscript_epub_compiled,
    manuscript_vault_zip,
    manuscript_pdf_compiled,
)

router = APIRouter()


# ─── Manuscript export ──────────────────────────────────────────────────────

@router.get("/{book_id}/manuscript/export")
async def export_manuscript(
    book_id: uuid.UUID,
    format: str = Query("docx", pattern="^(pdf|docx|epub|vault)$"),
    preset: str = Query("standard_manuscript", pattern="^(standard_manuscript|trade_paperback|kdp_paperback)$"),
    include_scene_metadata: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_export(collaborator):
        raise HTTPException(403, "This share cannot export the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    if collaborator is not None:
        chapter_rows = [
            row
            for row in chapter_rows
            if collaboration_allows_chapter(collaborator, int(row[0]))
        ]
    if not chapter_rows:
        raise HTTPException(404, "No chapters available to export")

    chapters: list[dict] = []
    for number, chapter_title, s3_key in chapter_rows:
        chapter_text = ""
        chapter_html = None
        if s3_key:
            try:
                stored = deserialize_manuscript_content(await asyncio.to_thread(storage.download_book, s3_key))
                chapter_text = str(stored.get("text") or "")
                chapter_html = str(stored.get("html") or "") or None
            except Exception:
                chapter_text = ""
                chapter_html = None
        if not include_scene_metadata:
            chapter_text = strip_scene_metadata_from_manuscript_text(chapter_text)
            chapter_html = None
        chapters.append({"number": number, "title": chapter_title, "text": chapter_text, "html": chapter_html})

    workspace = build_writer_workspace_payload(book)
    front_matter = workspace.get("manuscript_front_matter") if isinstance(workspace, dict) else None
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
        )
        return Response(
            content=raw,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-manuscript.pdf\""},
        )
    if format == "epub":
        raw = manuscript_epub_compiled(
            title=book.title or "LoreVia Manuscript",
            chapters=chapters,
            scenes=[],
            preset=preset,
            front_matter=cast(dict | None, front_matter),
        )
        return Response(
            content=raw,
            media_type="application/epub+zip",
            headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-manuscript.epub\""},
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
        )
        return Response(
            content=raw,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-manuscript-vault.zip\""},
        )

    raw = manuscript_docx(
        title=book.title or "LoreVia Manuscript",
        chapters=chapters,
        scenes=[],
        preset=preset,
        front_matter=cast(dict | None, front_matter),
    )
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-manuscript.docx\""},
    )


# ─── Character card export ──────────────────────────────────────────────────

@router.get("/{book_id}/characters/{character_id}/export")
async def export_character_card(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    format: str = Query("pdf", pattern="^(md|pdf|docx)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_has_resource(collaborator, "character_bible"):
        raise HTTPException(403, "This share does not include the story bible.")
    if collaborator and not collaboration_can_export(collaborator):
        raise HTTPException(403, "This share cannot export story bible assets.")
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")

    payload = await build_character_card_payload(db, book, character)
    markdown, filename_base = character_card_markdown(payload)

    if format == "md":
        return Response(content=markdown, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-character-card.md\""})
    if format == "pdf":
        raw = character_card_pdf(payload)
        return Response(content=raw, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-character-card.pdf\""})
    raw = character_card_docx(payload)
    return Response(content=raw,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-character-card.docx\""})


# ─── Character bible export ─────────────────────────────────────────────────

@router.get("/{book_id}/export/character-bible")
async def export_character_bible(
    book_id: uuid.UUID,
    format: str = Query("md", pattern="^(md|pdf|docx|vault_folder)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    context = await build_character_bible_vault_context(db, book_id)
    book = context.get("book")
    if not book:
        raise HTTPException(404)
    collaborator = None
    if book.user_id != current_user.id:
        _, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
        if not collaboration_has_resource(collaborator, "character_bible"):
            raise HTTPException(403, "This share does not include the story bible.")
        if not collaboration_can_export(collaborator):
            raise HTTPException(403, "This share cannot export story bible assets.")
    else:
        require_author_access(current_user)

    characters = [char for char in context["characters"] if is_displayable_character(char)]
    relationships = context["relationships"]
    plot_threads = context["plot_threads"]
    wiki_entries = context["wiki_entries"]
    chapter_rows = context["chapter_rows"]
    chapter_events = context["chapter_events"]
    rel_summaries = context["rel_summaries"]
    thread_summaries = context["thread_summaries"]

    title = f"{book.title} - Character Bible" if book.title else "LoreVia - Character Bible"

    if format == "vault_folder":
        overrides = await load_vault_note_overrides(db, book, current_user.id)
        zip_data, filename_base = character_bible_vault_folder(
            book=book,
            characters=characters,
            relationships=relationships,
            plot_threads=plot_threads,
            wiki_entries=wiki_entries,
            chapter_rows=chapter_rows,
            chapter_events=chapter_events,
            rel_summaries=rel_summaries,
            thread_summaries=thread_summaries,
            overrides=overrides,
        )
        return Response(content=zip_data, media_type="application/zip",
                        headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-character-bible.zip\""})

    markdown, filename_base = character_bible_markdown(
        book=book,
        characters=characters,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )

    if format == "md":
        return Response(content=markdown, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-character-bible.md\""})
    if format == "pdf":
        raw = character_bible_pdf(markdown=markdown, title=title)
        return Response(content=raw, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-character-bible.pdf\""})
    raw = character_bible_docx(markdown=markdown, title=title)
    return Response(content=raw,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename=\"{filename_base}-character-bible.docx\""})


@router.get("/{book_id}/export/character-bible/preview", response_model=VaultPreviewOut)
async def preview_character_bible_vault(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    context = await build_character_bible_vault_context(db, book_id)
    book = context.get("book")
    if not book:
        raise HTTPException(404)
    collaborator = None
    if book.user_id != current_user.id:
        _, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
        if not collaboration_has_resource(collaborator, "character_bible"):
            raise HTTPException(403, "This share does not include the story bible.")
    else:
        require_author_access(current_user)

    characters = [char for char in context["characters"] if is_displayable_character(char)]
    overrides = await load_vault_note_overrides(db, book, current_user.id)
    return character_bible_vault_preview(
        book=book,
        characters=characters,
        relationships=context["relationships"],
        plot_threads=context["plot_threads"],
        wiki_entries=context["wiki_entries"],
        chapter_rows=context["chapter_rows"],
        chapter_events=context["chapter_events"],
        rel_summaries=context["rel_summaries"],
        thread_summaries=context["thread_summaries"],
        overrides=overrides,
    )


@router.get("/{book_id}/export/character-bible/notes", response_model=list[VaultNoteOut])
async def list_character_bible_vault_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_vault_bible_notes(db, book, current_user.id)


@router.put("/{book_id}/export/character-bible/notes", response_model=VaultNoteSaveOut)
async def save_character_bible_vault_note(
    book_id: uuid.UUID,
    body: VaultNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await save_vault_note(
        db,
        book=book,
        user_id=current_user.id,
        path=body.path,
        content=body.content,
        source=VaultNoteSource.CHARACTER_BIBLE.value,
    )
