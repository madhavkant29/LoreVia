import asyncio
import json
import logging
import mimetypes
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

# ─── Upload limits ────────────────────────────────────────────────────────────
MAX_BOOK_UPLOAD_BYTES = 100 * 1024 * 1024   # 100 MB
MAX_COVER_UPLOAD_BYTES = 5 * 1024 * 1024    # 5 MB

_COVER_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
}

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None


def _book_cache_access_key(current_user_id: uuid.UUID, collaborator: Any | None) -> str:
    if collaborator is None:
        return f"owner:{current_user_id}"
    permissions = collaborator.permissions if isinstance(collaborator.permissions, dict) else {}
    permissions_key = json.dumps(permissions, sort_keys=True, default=str)
    return "||".join(
        [
            f"user:{current_user_id}",
            f"role:{collaborator.role}",
            f"scope:{json.dumps(collaborator.scope, sort_keys=True, default=str)}",
            f"permissions:{permissions_key}",
        ]
    )


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


async def _read_upload_bounded(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    parts: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break

        total += len(chunk)

        if total > max_bytes:
            raise HTTPException(
                413,
                f"{label} exceeds the maximum allowed size ({max_bytes // 1024 // 1024} MB).",
            )

        parts.append(chunk)

    await upload.seek(0)
    return b"".join(parts)


def _validate_cover_magic(raw: bytes) -> tuple[str, str]:
    for magic, (suffix, mime) in _COVER_MAGIC.items():
        if raw[:len(magic)] == magic:
            if mime == "image/webp" and raw[8:12] != b"WEBP":
                continue
            return suffix, mime
    raise HTTPException(400, "Cover image must be a JPEG, PNG, GIF, or WebP file.")


from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import (
    rate_limit_manuscript_import,
    rate_limit_public_publish,
    rate_limit_public_unpublish,
    rate_limit_upload,
)
from app.api.deps.subscription import check_upload_limit
from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import (
    get_book_cache_version,
    get_book_overview_cache,
    get_writer_workspace_cache,
    mark_book_cache_dirty,
    mark_user_dashboard_cache_dirty,
    set_book_overview_cache,
    set_writer_workspace_cache,
)
from app.core.security import create_asset_token, decode_token
from app.engine.character.consolidator import consolidate_characters
from app.utils.sparse_utils import include_requested, parse_csv_param
from app.models.book import (
    Book,
    BookCollaborator,
    BookNote,
    Chapter,
    VaultNoteSource,
    Series,
    SeriesBook,
)
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterRelationshipCandidate,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, QuoteEntry
from app.models.progress import ReadingProgress
from app.schemas.books import (
    BookForumMetadataBody,
    BookOverviewOut,
    BookEventsOut,
    BookModeBody,
    BookNoteBody,
    BookNoteOut,
    BookOut,
    BookProcessingOut,
    ChapterConsistencyReport,
    ChapterVersionOut,
    CharacterCreateBody,
    CharacterCandidateAttachBody,
    CharacterEventOut,
    CharacterMergeBody,
    RelationshipCandidateAcceptBody,
    RelationshipCandidateAttachBody,
    CharacterPartitionBody,
    CharacterShareOut,
    CharacterUpdateBody,
    CorkboardCardOut,
    EmotionalArcOverviewOut,
    EntityTagSetOut,
    EntityTagUpdateBody,
    MajorEventOut,
    ManuscriptImportResult,
    ManuscriptBootstrapOut,
    PermanentBookDeletionBody,
    PermanentBookDeletionOut,
    VaultGraphOut,
    VaultNoteLinkListOut,
    VaultPreviewOut,
    VaultNoteBody,
    VaultNoteOut,
    VaultNoteSaveOut,
    PreWritingCheckOut,
    PrivateUserStats,
    PublicUserStats,
    ReadabilityMetricsOut,
    ReadabilityRequestBody,
    RelationshipCreateBody,
    RelationshipUpdateBody,
    ReaderBootstrapOut,
    RevisionIntelligenceOut,
    SeriesBibleOut,
    SeriesBody,
    SeriesBookStatusBody,
    SeriesCreateBody,
    SeriesMembershipBody,
    SeriesOut,
    StoryHealthOut,
    UserStatsOut,
    WriterWorkspaceBody,
    WriterWorkspaceOut,
)
from app.schemas.public import PublicBookCreateOut, PublicBookShareBody
from app.schemas.character import CharacterReviewOut
from app.services.privacy_service import queue_book_permanent_deletion
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.billing_utils import calculate_upload_usage_summary, require_author_access
from app.services.pipeline_state_service import (
    build_writer_workspace_response,
    build_writer_workspace_update,
    enqueue_processing_state_repair_if_needed,
    retry_book_processing,
)
from app.utils.book_utils import (
    _append_recent_revision_edit,
    as_bool,
    book_out,
    build_book_out_list,
    build_character_card_payload,
    build_emotional_arc_payload,
    build_manuscript_workspace_tree,
    build_vault_graph,
    build_prewriting_check,
    build_revision_intelligence_payload,
    build_single_series_out,
    build_series_bible_payload,
    build_series_out_list,
    build_story_health_payload,
    build_writer_workspace_payload,
    clean_manuscript_html,
    collaboration_allows_chapter,
    collaboration_can_comment,
    collaboration_can_edit,
    collaboration_can_export,
    collaboration_has_resource,
    compute_words_read_for_books,
    delete_book_note,
    delete_vault_note,
    deserialize_manuscript_content,
    ensure_book_cover,
    estimate_readability,
    export_vault_notes_zip,
    extract_novel_scene_candidates,
    get_book_with_collaboration_access,
    get_owned_book,
    get_owned_series,
    import_vault_notes_zip,
    list_book_notes,
    list_chapter_consistency_reports,
    list_manuscript_annotations,
    list_chapter_versions,
    list_novel_scenes,
    list_vault_note_relations,
    list_vault_notes,
    list_vault_bible_notes,
    list_user_notes,
    load_vault_note_overrides,
    next_chapter_number,
    normalize_chapter_title,
    normalize_book_work_type,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    parse_screenplay_upload,
    refresh_screenplay_scene_rows,
    require_book_owner_access,
    replace_chapter_novel_scenes,
    resolve_owned_series_ids,
    resolve_upload_format_and_work_type,
    save_book_note,
    save_vault_note,
    snapshot_chapter_version,
    story_unit_name,
    strip_scene_metadata_from_manuscript_text,
    sync_chapter_content_from_novel_scenes,
    touch_public_book_updated_at,
)
from app.utils.db_utils import run_read_with_retry

from app.utils.character_utils import (
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_VISIBILITY_VISIBLE,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_DUPLICATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_REJECTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED,
    append_unique_summary,
    append_character_review_audit_entry,
    apply_graph_visibility_override,
    apply_manual_character_description,
    attach_character_candidate,
    build_manual_character,
    build_character_review_payload,
    clean_optional_text,
    clean_string_list,
    demote_character_to_review_candidate,
    dedupe_preserve_order,
    is_displayable_character,
    is_cast_visible_character,
    list_character_review_data,
    mark_character_curated,
    mark_character_candidates_merged,
    merge_characters,
    partition_character,
    promote_character_candidate,
    reject_character_as_noise,
    refresh_character_duplicate_suggestions,
    relationship_summary_for_character,
    serialize_book_character,
    set_character_review_state,
)
from app.utils.public_utils import (
    CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
    CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
    MODERATION_STATUS_UNDER_REVIEW,
    PUBLIC_DEMO_SOURCE_KIND,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_PUBLISHED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
    add_moderation_action,
    enforce_daily_public_publish_limit,
    ensure_content_source_allowed_for_user,
    ensure_public_mode_enabled,
    get_public_share_status,
    hash_text,
    normalize_public_slug,
)
from app.utils.reader_utils import (
    build_chapter_list_payload,
    build_reading_progress_payload,
    build_summary_collection_payload,
    chapter_intelligence_map,
)
from app.utils.storage_utils import delete_storage_key_best_effort
from app.utils.relationship_utils import (
    canonical_relationship_pair_ids,
    repair_relationship_timelines,
    upsert_relationship_timeline_state,
)
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
from app.utils.llm_usage_utils import summarize_llm_usage_for_user
from app.utils.ingestion_utils import build_analysis_chapter_state
from app.utils.notification_utils import (
    build_upload_processing_notification,
)
from app.utils.queue_utils import queue_for_user
from app.utils.tag_utils import (
    ENTITY_TYPE_CHARACTER,
    ENTITY_TYPE_NOTE,
    can_manage_tag_target,
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
    replace_custom_tags_for_entity,
    resolve_tag_target,
)
from app.utils.user_utils import (
    add_daily_word_progress,
    build_writing_activity_entry,
    build_writing_dashboard_stats,
)
from app.utils.upload_security_utils import validate_document_upload_bytes
from app.workers.consumers.extraction_consumer import _process_chapter
from app.workers.tasks.analysis_tasks import analyse_chapter_task
from app.workers.tasks.extraction_tasks import process_book_task
from scripts.repair_character_bible_book import apply_repair_plan, build_repair_plan

router = APIRouter()
log = logging.getLogger("lorevia.books")


# ─── Book mode & metadata ────────────────────────────────────────────────────

@router.put("/{book_id}/mode", response_model=BookOut)
async def update_book_mode(
    book_id: uuid.UUID,
    body: BookModeBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    require_book_owner_access(book, current_user, collaborator)
    require_author_access(current_user)
    mode = (body.mode or "").strip().lower()
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    book.mode = mode
    if mode == "author" and not book.source_kind:
        book.source_kind = "single_upload"
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return await book_out(db, book, current_user.id, collaborator)


@router.put("/{book_id}/forum-metadata", response_model=BookOut)
async def update_book_forum_metadata(
    book_id: uuid.UUID,
    body: BookForumMetadataBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    normalized_title = _clean_text(body.title)
    normalized_genre = _clean_text(body.genre)
    normalized_description = _clean_text(body.description)
    if not normalized_title or not normalized_genre or not normalized_description:
        raise HTTPException(400, "Novel discussions require a title, genre, and description.")
    book.title = normalized_title
    book.genre = normalized_genre
    book.public_description = normalized_description
    touch_public_book_updated_at(book)
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(book.id)
    await mark_user_dashboard_cache_dirty(current_user.id)
    return await book_out(db, book, current_user.id)


# ─── Book listing & stats ────────────────────────────────────────────────────

@router.get("/", response_model=list[BookOut])
async def list_books(
    include_hidden: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    current_user_id = current_user.id
    current_user_email = str(current_user.email).strip().lower()

    async def load_book_list() -> list[BookOut]:
        stmt = (
            select(Book)
            .options(noload(Book.vault_note_series_links))
            .where(Book.user_id == current_user_id)
        )
        if not include_hidden:
            stmt = stmt.where(Book.hidden_at.is_(None))
        result = await db.execute(stmt.order_by(Book.created_at.desc()))
        books = list(result.scalars().all())
        shared_rows = (
            await db.execute(
                select(Book, BookCollaborator)
                .options(noload(Book.vault_note_series_links))
                .join(BookCollaborator, BookCollaborator.book_id == Book.id)
                .where(
                    BookCollaborator.email == current_user_email,
                    BookCollaborator.invite_status == "active",
                    Book.user_id != current_user_id,
                )
                .order_by(BookCollaborator.invited_at.desc())
            )
        ).all()
        if not include_hidden:
            shared_rows = [row for row in shared_rows if row[0].hidden_at is None]

        shared_books = [book for book, _ in shared_rows]
        repair_seen_book_ids: set[uuid.UUID] = set()
        for candidate in [*books, *shared_books]:
            if candidate.id in repair_seen_book_ids:
                continue
            repair_seen_book_ids.add(candidate.id)
            await enqueue_processing_state_repair_if_needed(candidate)

        owned_payloads = await build_book_out_list(db, books=books, user_id=current_user_id)
        shared_payloads = await build_book_out_list(
            db,
            books=shared_books,
            user_id=current_user_id,
            collaborators_by_book_id={book.id: collaborator for book, collaborator in shared_rows},
        )
        return owned_payloads + shared_payloads

    return await run_read_with_retry(db, load_book_list)


@router.get("/stats", response_model=UserStatsOut)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    books_result = await db.execute(select(Book).where(Book.user_id == current_user.id).order_by(Book.created_at.desc()))
    books = list(books_result.scalars().all())

    progress_rows_result = await db.execute(select(ReadingProgress).where(ReadingProgress.user_id == current_user.id))
    progress_rows = list(progress_rows_result.scalars().all())
    progress_by_book = {progress.book_id: progress for progress in progress_rows}

    total_books_read = 0
    total_words_read = 0
    total_chapters_tracked = 0

    words_read_by_book = await compute_words_read_for_books(db, books=books, progress_rows=progress_rows)
    for book in books:
        total_chapters_tracked += book.total_chapters or 0
        progress = progress_by_book.get(book.id)
        read_chapters = sorted(set(progress.chapters_read or [])) if progress and progress.chapters_read else []
        if book.total_chapters and len(read_chapters) >= book.total_chapters:
            total_books_read += 1
        total_words_read += words_read_by_book.get(book.id, 0)

    total_token_consumption = int(sum(book.total_tokens or 0 for book in books))
    saved_quotes = int(
        (await db.execute(select(func.count(QuoteEntry.id)).where(QuoteEntry.user_id == current_user.id))).scalar() or 0
    )
    writing_stats = await build_writing_dashboard_stats(db, current_user)
    upload_usage = await calculate_upload_usage_summary(db, current_user)
    llm_usage = await summarize_llm_usage_for_user(db, current_user.id)

    return UserStatsOut(
        public=PublicUserStats(total_books_read=total_books_read, total_words_read=total_words_read),
        private=PrivateUserStats(
            total_uploads=upload_usage.total_uploads,
            manuscript_uploads=upload_usage.manuscript_uploads,
            worldbuilding_uploads=upload_usage.worldbuilding_uploads,
            upload_limit=upload_usage.upload_limit,
            uploads_remaining=upload_usage.uploads_remaining,
            upload_limit_unlimited=upload_usage.upload_limit_unlimited,
            total_token_consumption=total_token_consumption,
            llm_request_count=llm_usage.request_count,
            llm_prompt_tokens=llm_usage.prompt_tokens,
            llm_completion_tokens=llm_usage.completion_tokens,
            llm_total_tokens=llm_usage.total_tokens,
            total_chapters_tracked=total_chapters_tracked,
            saved_quotes=saved_quotes,
        ),
        writing=writing_stats,
    )


@router.get("/quotes")
async def list_saved_quotes(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    require_author_access(current_user)
    rows = (await db.execute(
        select(QuoteEntry, Book.title, Chapter.title)
        .join(Book, Book.id == QuoteEntry.book_id)
        .outerjoin(Chapter, and_(Chapter.book_id == QuoteEntry.book_id, Chapter.number == QuoteEntry.chapter_number))
        .where(QuoteEntry.user_id == current_user.id)
        .order_by(QuoteEntry.created_at.desc())
    )).all()
    return [
        {
            "id": str(quote.id),
            "book_id": str(quote.book_id),
            "book_title": book_title,
            "chapter_number": quote.chapter_number,
            "chapter_title": chapter_title,
            "character_name": quote.character_name,
            "quote_text": quote.quote_text,
            "note": quote.note,
            "created_at": quote.created_at,
        }
        for quote, book_title, chapter_title in rows
    ]


@router.get("/notes", response_model=list[BookNoteOut])
async def list_saved_notes(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    return await list_user_notes(db, current_user.id)


# ─── Book detail & overview ──────────────────────────────────────────────────

@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book, collaborator = await get_book_with_collaboration_access(
        db, book_id, current_user,
        options=(
            selectinload(Book.characters),
            selectinload(Book.chapters),
            selectinload(Book.plot_threads),
        ),
    )
    await enqueue_processing_state_repair_if_needed(book)
    return await book_out(db, book, current_user.id, collaborator)


@router.post("/{book_id}/processing/retry", response_model=BookProcessingOut)
async def retry_book_processing_endpoint(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, _collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    processing = await retry_book_processing(db, book)
    if processing is None:
        raise HTTPException(409, "Processing retry is not available for this book.")
    return processing


@router.get("/{book_id}/overview", response_model=BookOverviewOut)
async def get_book_overview(
    book_id: uuid.UUID,
    include: str | None = Query(None, description="Comma-separated sub-objects: book, progress, chapter_list, summary_collection"),
    fields: str | None = Query(None, description="Comma-separated fields for the book sub-object"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(
        db, book_id, current_user,
    )
    await enqueue_processing_state_repair_if_needed(book)
    use_cache = parse_csv_param(include) is None
    if use_cache:
        cache_version = await get_book_cache_version(str(book.id))
        access_key = _book_cache_access_key(current_user.id, collaborator)
        cached = await get_book_overview_cache(str(book.id), str(current_user.id), access_key, cache_version)
        if cached is not None:
            return BookOverviewOut(**cached)

    progress = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.book_id == book.id,
                ReadingProgress.user_id == current_user.id,
            )
        )
    ).scalars().first()
    intelligence_map = await chapter_intelligence_map(db, book, current_user) if include_requested(include, "chapter_list", "summary_collection") else {}

    book_payload = await book_out(db, book, current_user.id, collaborator, progress=progress)
    progress_payload = await build_reading_progress_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
        progress=progress,
    ) if include_requested(include, "progress") else None
    chapter_list_payload = await build_chapter_list_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
        progress=progress,
        intelligence_map=intelligence_map,
    ) if include_requested(include, "chapter_list") else None
    summary_collection_payload = await build_summary_collection_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
        progress=progress,
        intelligence_map=intelligence_map,
    ) if include_requested(include, "summary_collection") else None

    payload = BookOverviewOut(
        book=book_payload,
        progress=progress_payload,
        chapter_list=chapter_list_payload,
        summary_collection=summary_collection_payload,
    )
    if use_cache:
        await set_book_overview_cache(
            str(book.id),
            str(current_user.id),
            access_key,
            cache_version,
            payload.model_dump(mode="json"),
        )
    return payload


# ─── Analysis & intelligence endpoints ───────────────────────────────────────

@router.get("/{book_id}/pre-writing-check", response_model=PreWritingCheckOut)
async def get_prewriting_check(
    book_id: uuid.UUID,
    upcoming_chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "reader_confusion_report"):
        raise HTTPException(403, "This share does not include the reader confusion report.")
    if collaborator is None:
        require_author_access(current_user)
    next_chapter = upcoming_chapter or ((book.total_chapters or 0) + 1)
    return await build_prewriting_check(db, book, next_chapter)


@router.get("/{book_id}/story-health", response_model=StoryHealthOut)
async def get_story_health(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "reader_confusion_report"):
        raise HTTPException(403, "This share does not include the reader confusion report.")
    if collaborator is None:
        require_author_access(current_user)
    return await build_story_health_payload(db, book)


@router.get("/{book_id}/revision-intelligence", response_model=RevisionIntelligenceOut)
async def get_revision_intelligence(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_has_resource(collaborator, "continuity_report"):
        raise HTTPException(403, "This share does not include revision intelligence.")
    if collaborator is None:
        require_author_access(current_user)
    return RevisionIntelligenceOut(**(await build_revision_intelligence_payload(db, book)))


@router.get("/{book_id}/chapter-reports", response_model=list[ChapterConsistencyReport])
async def get_book_chapter_reports(
    book_id: uuid.UUID,
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "continuity_report"):
        raise HTTPException(403, "This share does not include the continuity report.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_chapter_consistency_reports(db, book, limit)


@router.get("/{book_id}/chapter-versions", response_model=list[ChapterVersionOut])
async def get_book_chapter_versions(
    book_id: uuid.UUID,
    chapter_number: int = Query(..., ge=1),
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot access that chapter history.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_chapter_versions(db, book, chapter_number, limit)


# ─── Writer workspace ────────────────────────────────────────────────────────

@router.get("/{book_id}/writer-workspace", response_model=WriterWorkspaceOut)
async def get_writer_workspace(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    await enqueue_processing_state_repair_if_needed(book)
    cache_version = await get_book_cache_version(str(book.id))
    access_key = _book_cache_access_key(current_user.id, collaborator)
    cached = await get_writer_workspace_cache(str(book.id), str(current_user.id), access_key, cache_version)
    if cached is not None:
        return WriterWorkspaceOut(**cached)
    payload = build_writer_workspace_response(book)
    await set_writer_workspace_cache(
        str(book.id),
        str(current_user.id),
        access_key,
        cache_version,
        payload.model_dump(mode="json"),
    )
    return payload


@router.put("/{book_id}/writer-workspace", response_model=WriterWorkspaceOut)
async def update_writer_workspace(
    book_id: uuid.UUID,
    body: WriterWorkspaceBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    next_payload = build_writer_workspace_update(book, body.model_dump(exclude_none=True))
    book.writer_workspace = next_payload
    if body.reprocess is not None and body.reprocess.auto_reprocess_enabled is not None:
        from app.services.editor_project_service import update_reprocess_metadata

        update_reprocess_metadata(book, auto_reprocess_enabled=body.reprocess.auto_reprocess_enabled)
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return build_writer_workspace_response(book)


# ─── Emotional arc ───────────────────────────────────────────────────────────

@router.get("/{book_id}/emotional-arc", response_model=EmotionalArcOverviewOut)
async def get_emotional_arc(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(
        db, book_id, current_user.id,
        options=(selectinload(Book.characters),),
    )
    require_author_access(current_user)
    book_characters = getattr(book, "characters", None)
    if book_characters is None:
        result = await db.execute(
            select(Character)
            .where(Character.book_id == book_id)
            .order_by(Character.mention_count.desc().nullslast(), Character.name)
        )
        book_characters = result.scalars().all()
    characters = sorted(
        book_characters or [],
        key=lambda c: (c.mention_count or 0, c.name or ""),
        reverse=True,
    )
    return EmotionalArcOverviewOut(**build_emotional_arc_payload(characters))


# ─── Book lifecycle ──────────────────────────────────────────────────────────

@router.get("/{book_id}/reader-bootstrap", response_model=ReaderBootstrapOut)
async def get_reader_bootstrap(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    overview = await get_book_overview(book_id, None, None, db, current_user)
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
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

    if book.workspace_shell == "reader":
        notes = await list_book_notes(db, book, collaborator=collaborator)
        if collaborator is None:
            try:
                saved_quotes = await list_saved_quotes(db, current_user)
            except HTTPException:
                saved_quotes = []

    if author_bootstrap:
        stats = await get_user_stats(db, current_user)
        characters = await _bootstrap_characters(db, book)
        chapter_reports = await list_chapter_consistency_reports(db, book, 6)
        prewriting_check = await build_prewriting_check(db, book, (book.total_chapters or 0) + 1)
        story_health = await build_story_health_payload(db, book)
        writer_workspace = build_writer_workspace_response(book)
        revision_intelligence = RevisionIntelligenceOut(**(await build_revision_intelligence_payload(db, book)))

    return ReaderBootstrapOut(
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
    emotional_arc = await get_emotional_arc(book_id, db, current_user) if collaborator is None else None
    workspace_tree = await build_manuscript_workspace_tree(
        db,
        book=book,
        user_id=current_user.id,
        collaborator=collaborator,
    )
    annotations = (
        await list_manuscript_annotations(
            db,
            book=book,
            actor=current_user,
            collaborator=collaborator,
            chapter_number=annotation_chapter_number,
        )
        if annotation_chapter_number is not None
        else []
    )
    notes = await list_book_notes(db, book, collaborator=collaborator)
    vault_notes = (
        await list_vault_notes(
            db,
            book=book,
            user_id=current_user.id,
            source=VaultNoteSource.USER_NOTES.value,
        )
        if collaborator is None
        else []
    )
    chapter_versions = (
        await list_chapter_versions(db, book, active_chapter_number, 12)
        if active_chapter_number is not None
        else []
    )
    prewriting_check = await build_prewriting_check(db, book, chapter_number)

    return ManuscriptBootstrapOut(
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


@router.put("/{book_id}/archive", response_model=BookOut)
async def archive_book(
    book_id: uuid.UUID,
    archived: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    book.archived_at = datetime.now(UTC) if archived else None
    if archived:
        book.hidden_at = None
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.put("/{book_id}/hide", response_model=BookOut)
async def hide_book(
    book_id: uuid.UUID,
    hidden: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    book.hidden_at = datetime.now(UTC) if hidden else None
    if hidden:
        book.archived_at = None
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.delete("/{book_id}", response_model=BookOut)
async def delete_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    book.hidden_at = datetime.now(UTC)
    book.archived_at = None
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.delete("/{book_id}/permanent", response_model=PermanentBookDeletionOut)
async def permanently_delete_book(
    book_id: uuid.UUID,
    body: PermanentBookDeletionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    request = await queue_book_permanent_deletion(db, book, body.confirmation_text, current_user)
    return PermanentBookDeletionOut(book_id=book_id, deletion_request_id=request.id, status=request.status)


# ─── Cover management ─────────────────────────────────────────────────────────

@router.put("/{book_id}/cover", response_model=BookOut)
async def update_book_cover(
    book_id: uuid.UUID,
    cover_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    previous_cover_s3_key = book.cover_s3_key
    raw = await _read_upload_bounded(cover_file, MAX_COVER_UPLOAD_BYTES, "Cover image")
    if not raw:
        raise HTTPException(400, "Cover file is empty")
    suffix, content_type = _validate_cover_magic(raw)
    next_cover_s3_key = await asyncio.to_thread(
        storage.upload_binary,
        f"covers/{current_user.id}/{uuid.uuid4()}.{suffix}",
        raw,
        content_type,
    )
    book.cover_s3_key = next_cover_s3_key
    await db.commit()
    await db.refresh(book)
    if previous_cover_s3_key and previous_cover_s3_key != next_cover_s3_key:
        await delete_storage_key_best_effort(previous_cover_s3_key, context="book_cover")
    await mark_book_cache_dirty(str(book.id))
    return await book_out(db, book, current_user.id)


@router.delete("/{book_id}/cover", response_model=BookOut)
async def remove_book_cover(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    previous_cover_s3_key = book.cover_s3_key
    book.cover_s3_key = None
    await db.commit()
    await db.refresh(book)
    if previous_cover_s3_key:
        await delete_storage_key_best_effort(previous_cover_s3_key, context="book_cover")
    await mark_book_cache_dirty(str(book.id))
    return await book_out(db, book, current_user.id)


# ─── Public asset endpoints (not router-decorated; used directly by router.py) ─

async def get_book_cover_public(book_id: uuid.UUID, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(book.user_id)
        or payload.get("res") != f"book-cover:{book.id}"
    ):
        raise HTTPException(401, "Invalid cover token")

    await ensure_book_cover(db, book)
    if not book.cover_s3_key:
        raise HTTPException(404, "Cover not found")

    raw = await asyncio.to_thread(storage.download_book, book.cover_s3_key)
    media_type = mimetypes.guess_type(book.cover_s3_key)[0] or "image/png"
    return Response(
        content=raw,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


async def get_book_character_card_public(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    character = await db.get(Character, character_id)
    if not book or not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(book.user_id)
        or payload.get("res") != f"character-card:{book.id}:{character.id}"
    ):
        raise HTTPException(401, "Invalid share token")

    return await build_character_card_payload(db, book, character)
