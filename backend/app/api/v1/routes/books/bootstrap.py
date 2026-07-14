import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Upload limits Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
MAX_BOOK_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_COVER_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

_COVER_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
}

BLEACH_EMPTY_TAGS: Any = frozenset()


from app.api.deps.auth import get_current_user
from app.api.v1.routes.books.core import get_user_stats, list_saved_quotes
from app.api.v1.routes.books.intelligence import get_emotional_arc
from app.core.database import get_db
from app.models.book import (
    VaultNoteSource,
)
from app.models.character import (
    Character,
)
from app.schemas.books import (
    BookNoteOut,
    ChapterConsistencyReport,
    ManuscriptBootstrapOut,
    PreWritingCheckOut,
    ReaderBootstrapOut,
    RevisionIntelligenceOut,
    StoryHealthOut,
    UserStatsOut,
    WriterWorkspaceOut,
)
from app.services.pipeline_state_service import (
    build_writer_workspace_response,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.chapter_versions import (
    list_chapter_versions,
)
from app.utils.books.collaboration_access import (
    collaboration_can_edit,
    get_book_with_collaboration_access,
)
from app.utils.books.consistency_reports import list_chapter_consistency_reports
from app.utils.books.notes import (
    list_book_notes,
    list_manuscript_annotations,
)
from app.utils.books.planning import build_prewriting_check
from app.utils.books.revision_service import (
    build_revision_intelligence_payload,
)
from app.utils.books.serialization import (
    book_out,
)
from app.utils.books.overview import build_book_overview_payload
from app.utils.books.story_health import build_story_health_payload
from app.utils.books.vault_storage import (
    list_vault_notes,
)
from app.utils.books.workspace_search import build_manuscript_workspace_tree
from app.utils.characters.governance import is_cast_visible_character, is_displayable_character
from app.utils.characters.serialization import serialize_book_character


async def _bootstrap_characters(db: AsyncSession, book: Any) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Character)
        .where(Character.book_id == book.id)
        .options(selectinload(Character.voice_profile), selectinload(Character.alias_records))
        .order_by(Character.first_chapter, Character.name)
    )
    all_characters = list(result.scalars().all())
    characters = (
        [char for char in all_characters if is_cast_visible_character(char)]
        if book.mode == "author"
        else [char for char in all_characters if is_displayable_character(char)]
    )
    counterpart_names = {char.id: char.name for char in characters}
    return [
        serialize_book_character(
            char,
            rel_summaries={},
            states=[],
            relationships=[],
            counterpart_names=counterpart_names,
            voice_profile=getattr(char, "voice_profile", None),
            total_chapters=book.total_chapters,
            tags=[],
            skip_arc_tracker=True,
            skip_analysis_metadata=False,
            skip_tags=True,
        )
        for char in characters
    ]


def _can_include_author_bootstrap(current_user: Any, collaborator: Any | None) -> bool:
    if collaborator is not None:
        return collaboration_can_edit(collaborator)
    try:
        require_author_access(current_user)
    except HTTPException:
        return False
    return True


router = APIRouter()


@router.get("/{book_id}/reader-bootstrap", response_model=ReaderBootstrapOut)
async def get_reader_bootstrap(
    book_id: uuid.UUID,
    profile: Literal["critical", "full"] = Query("full"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    overview = await build_book_overview_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )
    author_bootstrap = _can_include_author_bootstrap(current_user, collaborator)

    notes: list[BookNoteOut] = []
    saved_quotes: list[dict[str, Any]] = []
    stats: UserStatsOut | None = None
    characters: list[dict[str, Any]] = []
    chapter_reports: list[ChapterConsistencyReport] = []
    prewriting_check: PreWritingCheckOut | None = None
    story_health: StoryHealthOut | None = None
    writer_workspace: WriterWorkspaceOut | None = None
    revision_intelligence: RevisionIntelligenceOut | None = None

    if profile == "full" and book.mode == "reader":
        notes = await list_book_notes(db, book, collaborator=collaborator)
        if collaborator is None:
            try:
                saved_quotes = await list_saved_quotes(db, current_user)
            except HTTPException:
                saved_quotes = []

    if profile == "full" and author_bootstrap:
        stats = await get_user_stats(db, current_user)
        characters = await _bootstrap_characters(db, book)
        chapter_reports = await list_chapter_consistency_reports(db, book, 6)
        prewriting_check = await build_prewriting_check(db, book, (book.total_chapters or 0) + 1)
        story_health = await build_story_health_payload(db, book)
        writer_workspace = build_writer_workspace_response(book)
        revision_intelligence = RevisionIntelligenceOut(
            **(await build_revision_intelligence_payload(db, book))
        )

    return ReaderBootstrapOut(
        profile=profile,
        overview=overview,
        notes=notes,
        saved_quotes=saved_quotes,
        stats=stats,
        characters=characters,
        chapter_reports=chapter_reports,
        prewriting_check=prewriting_check,
        story_health=story_health,
        writer_workspace=writer_workspace,
        revision_intelligence=revision_intelligence,
    )


@router.get("/{book_id}/manuscript-bootstrap", response_model=ManuscriptBootstrapOut)
async def get_manuscript_bootstrap(
    book_id: uuid.UUID,
    active_chapter_number: int | None = Query(None, ge=1),
    annotation_chapter_number: int | None = Query(None, ge=1),
    profile: Literal["critical", "full"] = Query("full"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)

    chapter_number = active_chapter_number or ((book.total_chapters or 0) + 1)
    book_payload = await book_out(db, book, current_user.id, collaborator)
    characters = await _bootstrap_characters(db, book)
    writer_workspace = build_writer_workspace_response(book)
    workspace_tree = await build_manuscript_workspace_tree(
        db,
        book=book,
        user_id=current_user.id,
        collaborator=collaborator,
    )
    emotional_arc = (
        await get_emotional_arc(book_id, db, current_user)
        if profile == "full" and collaborator is None
        else None
    )
    annotations = (
        await list_manuscript_annotations(
            db,
            book=book,
            actor=current_user,
            collaborator=collaborator,
            chapter_number=annotation_chapter_number,
        )
        if profile == "full" and annotation_chapter_number is not None
        else []
    )
    notes = await list_book_notes(db, book, collaborator=collaborator) if profile == "full" else []
    vault_notes = (
        await list_vault_notes(
            db,
            book=book,
            user_id=current_user.id,
            source=VaultNoteSource.USER_NOTES.value,
        )
        if profile == "full" and collaborator is None
        else []
    )
    chapter_versions = (
        await list_chapter_versions(db, book, active_chapter_number, 12)
        if profile == "full" and active_chapter_number is not None
        else []
    )
    prewriting_check = (
        await build_prewriting_check(db, book, chapter_number) if profile == "full" else None
    )

    return ManuscriptBootstrapOut(
        profile=profile,
        book=book_payload,
        characters=characters,
        writer_workspace=writer_workspace,
        emotional_arc=emotional_arc,
        synopsis=None,
        workspace_tree=workspace_tree,
        annotations=annotations,
        notes=notes,
        vault_notes=vault_notes,
        chapter_versions=chapter_versions,
        prewriting_check=prewriting_check,
    )
