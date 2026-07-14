import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import VaultNoteSource
from app.models.character import Character
from app.schemas.books import (
    VaultNoteBody,
    VaultNoteOut,
    VaultNoteSaveOut,
    VaultPreviewOut,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.character_cards import build_character_card_payload
from app.utils.books.collaboration_access import (
    collaboration_can_export,
    collaboration_has_resource,
    get_book_with_collaboration_access,
)
from app.utils.books.notes import get_owned_book
from app.utils.books.vault import list_vault_bible_notes, load_vault_note_overrides
from app.utils.books.vault_storage import save_vault_note
from app.utils.characters.governance import is_displayable_character
from app.utils.export_utils import (
    build_character_bible_vault_context,
    character_bible_docx,
    character_bible_markdown,
    character_bible_pdf,
    character_bible_vault_folder,
    character_bible_vault_preview,
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
    normalize_export_font_family,
)

router = APIRouter()


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
        return Response(
            content=markdown,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-character-card.md"'
            },
        )
    if format == "pdf":
        raw = character_card_pdf(payload)
        return Response(
            content=raw,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-character-card.pdf"'
            },
        )
    raw = character_card_docx(payload)
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_base}-character-card.docx"'
        },
    )


@router.get("/{book_id}/export/character-bible")
async def export_character_bible(
    book_id: uuid.UUID,
    format: str = Query("md", pattern="^(md|pdf|docx|vault_folder)$"),
    font_family: str = Query("serif", pattern="^(serif|sans|mono|italian-old-style|eb-garamond)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    selected_font = normalize_export_font_family(font_family)
    context = await build_character_bible_vault_context(db, book_id)
    book = context.get("book")
    if not book:
        raise HTTPException(404)
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
            font_family=selected_font,
        )
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-character-bible.zip"'
            },
        )

    markdown, filename_base = character_bible_markdown(
        book=book,
        characters=characters,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )

    if format == "md":
        return Response(
            content=markdown,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-character-bible.md"'
            },
        )
    if format == "pdf":
        raw = character_bible_pdf(markdown=markdown, title=title, font_family=selected_font)
        return Response(
            content=raw,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}-character-bible.pdf"'
            },
        )
    raw = character_bible_docx(markdown=markdown, title=title, font_family=selected_font)
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_base}-character-bible.docx"'
        },
    )


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
