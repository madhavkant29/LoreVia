import asyncio
import json
import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# ─── Upload limits ────────────────────────────────────────────────────────────
# Hard cap on book uploads. file.read() without a limit causes OOM DoS.
MAX_BOOK_UPLOAD_BYTES = 100 * 1024 * 1024   # 100 MB
MAX_COVER_UPLOAD_BYTES = 5 * 1024 * 1024    # 5 MB

# Magic-byte signatures for allowed cover image formats.
# We inspect actual bytes rather than trusting the client-supplied MIME type
# or filename extension — both are fully attacker-controlled.
_COVER_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),   # bytes [8:12] must be b"WEBP"
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


async def _read_upload_bounded(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    """Read an UploadFile in chunks, raising 413 if the size cap is exceeded."""
    parts: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(1024 * 1024)  # 1MB chunks
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
    """Return (extension, mime_type) by inspecting magic bytes.

    Raises HTTP 400 if the bytes do not match a permitted image format.
    Prevents SVG/HTML/script files from being stored as cover images.
    """
    for magic, (suffix, mime) in _COVER_MAGIC.items():
        if raw[:len(magic)] == magic:
            # Extra check for WebP: bytes[8:12] must equal b"WEBP"
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
from app.models.book import (
    Book,
    BookCollaborator,
    BookNote,
    Chapter,
    ObsidianVaultNoteSource,
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
    ObsidianGraphOut,
    ObsidianNoteLinkListOut,
    ObsidianPreviewOut,
    ObsidianVaultNoteBody,
    ObsidianVaultNoteOut,
    ObsidianVaultNoteSaveOut,
    PreWritingCheckOut,
    PrivateUserStats,
    PublicUserStats,
    ReadabilityMetricsOut,
    ReadabilityRequestBody,
    RelationshipCreateBody,
    RelationshipUpdateBody,
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
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.billing_utils import calculate_upload_usage_summary, require_author_access
from app.services.pipeline_state_service import (
    build_writer_workspace_response,
    build_writer_workspace_update,
    requeue_stalled_book_processing_if_needed,
)
from app.utils.book_utils import (
    _append_recent_revision_edit,
    as_bool,
    book_out,
    build_chapter_consistency_report,
    build_character_card_payload,
    build_emotional_arc_payload,
    build_obsidian_graph,
    build_prewriting_check,
    build_revision_intelligence_payload,
    build_series_bible_payload,
    build_story_health_payload,
    build_writer_workspace_payload,
    clean_manuscript_html,
    collaboration_allows_chapter,
    collaboration_can_comment,
    collaboration_can_edit,
    collaboration_can_export,
    collaboration_has_resource,
    compute_words_read_for_book,
    delete_book_note,
    delete_obsidian_note,
    deserialize_manuscript_content,
    ensure_book_cover,
    estimate_readability,
    export_obsidian_notes_zip,
    extract_novel_scene_candidates,
    get_book_with_collaboration_access,
    get_owned_book,
    get_owned_series,
    import_obsidian_notes_zip,
    list_book_notes,
    list_chapter_consistency_reports,
    list_chapter_versions,
    list_novel_scenes,
    list_obsidian_note_relations,
    list_obsidian_notes,
    list_obsidian_vault_notes,
    list_user_notes,
    load_obsidian_vault_overrides,
    next_chapter_number,
    normalize_chapter_title,
    normalize_book_work_type,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    parse_screenplay_upload,
    refresh_screenplay_scene_rows,
    replace_chapter_novel_scenes,
    resolve_owned_series_ids,
    resolve_upload_format_and_work_type,
    save_book_note,
    save_obsidian_vault_note,
    snapshot_chapter_version,
    story_unit_name,
    strip_scene_metadata_from_manuscript_text,
    sync_chapter_content_from_novel_scenes,
)

# ── Utils imports ──────────────────────────────────────────────────────────────
from app.utils.character_utils import (
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
    list_character_review_data,
    mark_character_curated,
    mark_character_candidates_merged,
    merge_characters,
    partition_character,
    promote_character_candidate,
    refresh_character_duplicate_suggestions,
    relationship_summary_for_character,
    serialize_book_character,
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
)
from app.utils.export_utils import (
    build_character_bible_obsidian_context,
    character_bible_docx,
    character_bible_markdown,
    character_bible_obsidian_folder,
    character_bible_obsidian_preview,
    character_bible_pdf,
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
    export_filename_base,
    manuscript_docx,
    manuscript_epub_compiled,
    manuscript_obsidian_vault_zip,
    manuscript_pdf_compiled,
)
from app.utils.llm_usage_utils import summarize_llm_usage_for_user
from app.utils.notification_utils import (
    build_chapter_report_notification,
    build_continuity_risk_notifications,
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
from app.workers.consumers.analysis_consumer import analyse_chapter
from app.workers.consumers.extraction_consumer import _process_chapter
from app.workers.tasks.extraction_tasks import process_book_task
from scripts.repair_character_bible_book import apply_repair_plan, build_repair_plan

router = APIRouter()
log = logging.getLogger("lorevia.books")


def _normalize_book_major_event(
    *,
    chapter_number: int,
    chapter_title: str | None,
    event: dict,
    character_names_by_id: dict[str, str],
) -> dict:
    involved_ids = [str(item).strip() for item in (event.get("involved_characters") or []) if str(item).strip()]
    involved_names = [character_names_by_id.get(item, item) for item in involved_ids]
    return {
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "event_title": str(event.get("event_title") or event.get("event") or "").strip(),
        "description": str(event.get("description") or event.get("impact") or "").strip(),
        "importance": int(event.get("importance") or 5),
        "involved_characters": involved_ids or None,
        "involved_character_names": involved_names or None,
        "event_type": event.get("event_type"),
    }


def _normalize_relationship_type(value: str) -> str:
    rel_type = _clean_text(value).strip().lower().replace(" ", "_")
    if not rel_type:
        raise HTTPException(400, "Relationship type is required")
    return rel_type


def _validate_relationship_window(from_chapter: int | None, to_chapter: int | None) -> None:
    if from_chapter is not None and from_chapter < 1:
        raise HTTPException(400, "from_chapter must be at least 1")
    if to_chapter is not None and to_chapter < 1:
        raise HTTPException(400, "to_chapter must be at least 1")
    if from_chapter is not None and to_chapter is not None and to_chapter < from_chapter:
        raise HTTPException(400, "to_chapter cannot be earlier than from_chapter")


def _serialize_relationship_record(relationship: CharacterRelationship) -> dict[str, Any]:
    return {
        "id": str(relationship.id),
        "character_a_id": str(relationship.character_a_id),
        "character_b_id": str(relationship.character_b_id),
        "rel_type": relationship.rel_type,
        "sentiment": relationship.sentiment,
        "description": relationship.description,
        "from_chapter": relationship.from_chapter,
        "to_chapter": relationship.to_chapter,
    }


def _normalize_book_character_event(*, character: Character, event: dict) -> dict:
    return {
        "character_id": str(character.id),
        "character_name": character.name,
        "chapter_number": int(event.get("chapter_number") or character.first_chapter),
        "event_title": str(event.get("event_title") or event.get("event") or "").strip(),
        "description": str(event.get("description") or event.get("impact") or "").strip(),
        "impact_score": int(event.get("impact_score") or event.get("importance") or 5),
        "role": event.get("role") or character.role,
        "accomplishments": [str(item).strip() for item in (event.get("accomplishments") or []) if str(item).strip()],
        "growth_direction": str(event.get("growth_direction") or "neutral"),
        "growth_magnitude": int(event.get("growth_magnitude") or event.get("impact_score") or 0),
        "is_major": bool(event.get("is_major", False)),
    }


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=202)
async def upload_book_endpoint(
    file: UploadFile = File(...),
    cover_file: UploadFile | None = File(None),
    title: str = Form(...),
    genre: str | None = Form(None),
    author: str | None = Form(None),
    work_type: str | None = Form(None),
    series_ids: list[str] = Form(default=[]),
    visibility: str = Form("private"),
    description: str | None = Form(None),
    mode: str = Form("reader"),
    auto_extract_cover: str = Form("true"),
    preserve_chapter_numbers: str = Form("false"),
    preserve_source_chapters: str = Form("false"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    __=Depends(rate_limit_upload),
):
    title = _clean_text(title) if title else ""
    if author:
        author = _clean_text(author)
    if genre:
        genre = _clean_text(genre)
    if description:
        description = _clean_text(description)
    if not file.filename:
        raise HTTPException(400, "No file")
    if visibility not in {"private", "public"}:
        raise HTTPException(400, "Invalid visibility")
    if visibility == "public":
        raise HTTPException(
            400,
            "Main upload flow only supports private manuscripts. Use the explicit public-sharing route after upload.",
        )
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    if mode == "author":
        require_author_access(current_user)
    if not title.strip():
        raise HTTPException(400, "Title is required")

    fmt, resolved_work_type = resolve_upload_format_and_work_type(file.filename, work_type)

    # Validate series ownership BEFORE expensive file operations
    selected_series = await resolve_owned_series_ids(db, current_user.id, series_ids)
    await check_upload_limit(db, current_user, requested_uploads=1)

    is_public = False
    # Stream-read with a hard size cap to prevent OOM DoS.
    raw = await _read_upload_bounded(file, settings.BOOK_UPLOAD_MAX_BYTES, "Book file")
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    validate_document_upload_bytes(file.filename, raw, fmt)
    book_id = uuid.uuid4()
    cover_raw = None
    if not as_bool(auto_extract_cover) and cover_file is not None and cover_file.filename:
        cover_raw = await _read_upload_bounded(cover_file, settings.COVER_UPLOAD_MAX_BYTES, "Cover image")
        if cover_raw:
            # Validate magic bytes — never trust client-supplied MIME or extension.
            _validate_cover_magic(cover_raw)
    s3_key = storage.upload_book_bytes(raw, str(current_user.id), file.filename)
    cover_s3_key = None
    if cover_raw:
        suffix, content_type = _validate_cover_magic(cover_raw)
        cover_s3_key = storage.upload_binary(
            f"covers/{current_user.id}/{uuid.uuid4()}.{suffix}",
            cover_raw,
            content_type,
        )
    book = Book(
        id=book_id,
        user_id=current_user.id,
        title=title,
        genre=genre,
        author=author,
        format=fmt,
        work_type=resolved_work_type,
        s3_key=s3_key,
        cover_s3_key=cover_s3_key,
        status="pending",
        is_public=is_public,
        public_description=description,
        mode=mode,
        source_kind="single_upload",
        preserve_chapter_numbers=as_bool(preserve_chapter_numbers),
        preserve_source_chapters=as_bool(preserve_source_chapters),
    )
    db.add(book)
    await db.flush()
    for index, series in enumerate(selected_series):
        membership = SeriesBook(series_id=series.id, book_id=book.id)
        db.add(membership)
        if index == 0:
            book.primary_series_id = series.id
            book.series_name = series.name
            book.series_order = None

    await db.commit()
    await db.refresh(book)

    # Send processing notification
    notification = build_upload_processing_notification(book, mode, len(raw))
    db.add(notification)
    await db.commit()

    process_book_task.apply_async(args=[str(book.id)], queue=queue_for_user(current_user, "extraction"))
    return {"book_id": str(book.id), "status": "processing",
            "copyright_warning": False, "visibility": visibility, "mode": mode}


@router.put("/{book_id}/mode", response_model=BookOut)
async def update_book_mode(
    book_id: uuid.UUID,
    body: BookModeBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    mode = (body.mode or "").strip().lower()
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
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
    normalized_title = _clean_text(body.title)
    normalized_genre = _clean_text(body.genre)
    normalized_description = _clean_text(body.description)
    if not normalized_title or not normalized_genre or not normalized_description:
        raise HTTPException(400, "Novel discussions require a title, genre, and description.")
    book.title = normalized_title
    book.genre = normalized_genre
    book.public_description = normalized_description
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(book.id)
    await mark_user_dashboard_cache_dirty(current_user.id)
    return await book_out(db, book, current_user.id)


@router.get("/{book_id}/events", response_model=BookEventsOut)
async def get_book_events(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id, ChapterSummary.mode == "detailed")
            .order_by(Chapter.number)
        )
    ).all()
    characters_result = await db.execute(select(Character).where(Character.book_id == book.id).order_by(Character.name))
    characters = list(characters_result.scalars().all())
    character_names_by_id = {str(character.id): character.name for character in characters}

    major_events: list[dict] = []
    for chapter_number, chapter_title, key_events in chapter_rows:
        for event in key_events or []:
            if isinstance(event, dict):
                major_events.append(
                    _normalize_book_major_event(
                        chapter_number=chapter_number,
                        chapter_title=chapter_title,
                        event=event,
                        character_names_by_id=character_names_by_id,
                    )
                )

    character_events: list[dict] = []
    for character in characters:
        for event in character.growth_events or []:
            if isinstance(event, dict):
                character_events.append(_normalize_book_character_event(character=character, event=event))

    major_events.sort(key=lambda item: (item["chapter_number"], item["event_title"].lower()))
    character_events.sort(key=lambda item: (item["chapter_number"], item["character_name"].lower(), item["event_title"].lower()))
    return BookEventsOut(
        major_events=[MajorEventOut(**item) for item in major_events],
        character_events=[CharacterEventOut(**item) for item in character_events],
    )


@router.get("/{book_id}/events/reader", response_model=BookEventsOut)
async def get_reader_safe_book_events(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    progress_result = await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book.id)
    )
    progress = progress_result.scalar()
    max_visible_chapter = chapter or (progress.current_chapter if progress else 1)
    payload = await get_book_events(book_id=book_id, db=db, current_user=current_user)
    return BookEventsOut(
        major_events=[event for event in payload.major_events if event.chapter_number <= max_visible_chapter],
        character_events=[event for event in payload.character_events if event.chapter_number <= max_visible_chapter],
    )


@router.post("/{book_id}/manuscript/import", response_model=ManuscriptImportResult)
async def import_manuscript_content(
    book_id: uuid.UUID,
    files: list[UploadFile] | None = File(None),
    text: str | None = Form(None),
    html: str | None = Form(None),
    title: str | None = Form(None),
    work_type: str | None = Form(None),
    chapter_number: int | None = Form(None),
    replace_existing: str = Form("false"),
    expected_content_version: int | None = Form(None),
    chunk_long_documents: str = Form("false"),
    split_into_chapters: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_manuscript_import),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if not text and not files:
        raise HTTPException(400, "Provide text or one or more files")

    import_jobs: list[dict[str, object]] = []
    screenplay_batches: list[dict[str, object]] = []
    daily_words_added = 0
    imported_content_versions: dict[int, int] = {}
    normalized_title = normalize_chapter_title(title) if title is not None else None
    next_number = await next_chapter_number(db, book.id)
    replace_flag = as_bool(replace_existing)
    chunk_flag = as_bool(chunk_long_documents)
    split_flag = as_bool(split_into_chapters)
    preserve_exact_structure = bool(book.preserve_chapter_numbers or book.preserve_source_chapters)
    resolved_book_work_type = normalize_book_work_type(work_type, default=book.work_type or "novel")
    resolved_import_format: str | None = None

    cleaned_html = clean_manuscript_html(html) if html else None
    
    # Track total file size for notification
    total_file_size = 0

    if text and text.strip():
        if resolved_book_work_type == "screenplay":
            screenplay_payload = await parse_screenplay_upload("inline.fountain", text.encode("utf-8"))
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
                    [{
                        "title": normalized_title or f"{story_unit_name(book)} {chapter_number or next_number}",
                        "text": text,
                        "html": cleaned_html,
                        "number": chapter_number or next_number,
                    }],
                    chapter_number=chapter_number,
                    start_number=chapter_number or next_number,
                    replace_existing=replace_flag,
                    chunk_long_documents=chunk_flag,
                    preserve_exact_structure=preserve_exact_structure,
                )
            )

    for upload in files or []:
        if not upload.filename:
            continue
        raw = await _read_upload_bounded(upload, settings.MANUSCRIPT_IMPORT_MAX_BYTES, "Manuscript file")
        if not raw:
            continue
        total_file_size += len(raw)
        fmt, upload_work_type = resolve_upload_format_and_work_type(
            upload.filename,
            work_type if work_type is not None else book.work_type,
        )
        validate_document_upload_bytes(upload.filename, raw, fmt)
        resolved_import_format = resolved_import_format or fmt
        parsed_payload = await parse_book_upload_for_ingestion(
            format_name=fmt,
            work_type=upload_work_type,
            raw=raw,
            preserve_chapter_numbers=bool(book.preserve_chapter_numbers),
            preserve_source_chapters=bool(book.preserve_source_chapters),
        )
        screenplay_payload = parsed_payload.get("screenplay_payload") if upload_work_type == "screenplay" else None
        parsed = list(cast(list[dict[str, object]], parsed_payload["chapters"]))
        if upload_work_type != "screenplay" and not split_flag:
            merged_text = "\n\n".join(str(chapter.get("text") or "").strip() for chapter in parsed if chapter.get("text"))
            merged_html_parts = [str(chapter.get("html") or "").strip() for chapter in parsed if chapter.get("html")]
            parsed = [{
                "title": normalized_title or (upload.filename.rsplit(".", 1)[0] if "." in upload.filename else upload.filename),
                "text": merged_text,
                "html": clean_manuscript_html("\n".join(part for part in merged_html_parts if part)) if merged_html_parts else None,
                "number": 1,
            }]
        base_number = chapter_number if replace_flag and chapter_number else next_number
        new_jobs = normalize_imported_chapters(
            parsed,
            chapter_number=chapter_number,
            start_number=base_number,
            replace_existing=replace_flag and len(parsed) == 1,
            chunk_long_documents=False if upload_work_type == "screenplay" else chunk_flag,
            preserve_exact_structure=preserve_exact_structure,
        )
        import_jobs.extend(new_jobs)
        if upload_work_type == "screenplay":
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
            max((int(cast(Any, job["number"])) for job in import_jobs), default=next_number) + 1,
        )

    if not import_jobs:
        raise HTTPException(400, "No importable manuscript content was found")

    imported_numbers: list[int] = []
    for job in import_jobs:
        job_number = int(cast(Any, job["number"]))
        next_text = str(job.get("text") or "")
        next_word_count = len(next_text.split()) if next_text.strip() else 0
        previous_word_count = 0
        previous_text = ""
        source_version_id: str | None = None
        if replace_flag:
            existing = (
                await db.execute(
                    select(Chapter)
                    .where(Chapter.book_id == book.id, Chapter.number == job_number)
                    .with_for_update()
                )
            ).scalar()
            if existing is not None:
                current_content_version = int(existing.content_version or 1)
                if expected_content_version is not None and len(import_jobs) == 1 and job_number == (chapter_number or job_number):
                    if current_content_version != expected_content_version:
                        raise HTTPException(
                            409,
                            {
                                "message": "Chapter content changed elsewhere. Reload the latest version or save again to intentionally overwrite it.",
                                "chapter_number": job_number,
                                "current_content_version": current_content_version,
                            },
                        )
                previous_word_count = int(existing.word_count or 0)
                if existing.s3_key:
                    existing_payload = deserialize_manuscript_content(await asyncio.to_thread(storage.download_book, existing.s3_key))
                    previous_text = str(existing_payload.get("text") or "")
                snapshot = await snapshot_chapter_version(
                    db,
                    book,
                    existing,
                    note=f"Snapshot before replacing Chapter {job_number}",
                    snapshot_kind="pre_replace",
                )
                source_version_id = str(snapshot.id) if snapshot is not None else None
                job["content_version"] = current_content_version + 1
                await db.delete(existing)
                await db.flush()
            else:
                job["content_version"] = 1
        else:
            job["content_version"] = 1
        words_added = max(next_word_count - previous_word_count, 0)
        daily_words_added += words_added
        writing_activity = build_writing_activity_entry(
            current_user,
            book,
            words_added,
            chapter_number=job_number,
            title=str(job.get("title") or ""),
        )
        if writing_activity is not None:
            db.add(writing_activity)
        await _process_chapter(
            db,
            book,
            {
                "number": job_number,
                "title": job.get("title"),
                "text": next_text,
                "html": job.get("html"),
                "description": job.get("description"),
                "images": [],
                "content_version": int(job.get("content_version") or 1),
            },
        )
        if resolved_book_work_type != "screenplay":
            extracted_scenes = extract_novel_scene_candidates(
                text=next_text,
                chapter_number=job_number,
                source="chapter_sync",
            )
            await replace_chapter_novel_scenes(
                db,
                book=book,
                chapter_number=job_number,
                scenes=extracted_scenes,
            )
            await sync_chapter_content_from_novel_scenes(
                db,
                book=book,
                chapter_number=job_number,
                increment_content_version=False,
            )
        _append_recent_revision_edit(
            book,
            kind="chapter",
            chapter_number=job_number,
            before_text=previous_text,
            after_text=next_text,
            source_version_id=source_version_id,
        )
        imported_content_versions[job_number] = int(job.get("content_version") or 1)
        imported_numbers.append(job_number)

    for batch in screenplay_batches:
        await refresh_screenplay_scene_rows(
            db,
            book=book,
            parsed_scenes=cast(list[Any], batch["parsed_scenes"]),
            starting_number=int(cast(Any, batch["starting_number"])),
            replace_scene_numbers=cast(set[int], batch["scene_numbers"]),
        )

    total_chapters = await db.scalar(select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id)) or 0
    book.total_chapters = total_chapters
    book.mode = "author"
    book.work_type = resolved_book_work_type
    if resolved_import_format:
        book.format = resolved_import_format
    book.source_kind = "chapter_wise" if len(import_jobs) == 1 and not files else "batch_upload"
    if daily_words_added > 0:
        add_daily_word_progress(current_user, daily_words_added)
    await db.commit()
    if daily_words_added > 0:
        await mark_user_dashboard_cache_dirty(str(current_user.id))
    await db.refresh(book)

    # Send processing notification for manuscript import
    if total_file_size > 0:
        notification = build_upload_processing_notification(book, "author", total_file_size)
        db.add(notification)
        await db.commit()

    # For author mode, mark all chapters as read
    if book.mode == "author" and total_chapters > 0:
        progress = (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == current_user.id,
                    ReadingProgress.book_id == book.id
                )
            )
        ).scalar()
        
        chapters_read = list(range(1, total_chapters + 1))
        if progress is None:
            progress = ReadingProgress(
                user_id=current_user.id,
                book_id=book.id,
                current_chapter=total_chapters,
                scroll_pct=1.0,
                chapters_read=chapters_read,
            )
            db.add(progress)
        else:
            progress.current_chapter = total_chapters
            progress.scroll_pct = 1.0
            progress.chapters_read = chapters_read
        await db.commit()

    chapter_reports: list[ChapterConsistencyReport] = []
    for number in imported_numbers:
        chapter = (
            await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == number))
        ).scalar()
        if chapter is not None:
            chapter_payload = deserialize_manuscript_content(await asyncio.to_thread(storage.download_book, chapter.s3_key)) if chapter.s3_key else {"text": ""}
            chapter_text = str(chapter_payload.get("text") or "")
            await db.execute(
                delete(PlotThread).where(
                    PlotThread.book_id == book.id,
                    PlotThread.introduced_at == number,
                )
            )
            await db.commit()
            try:
                await analyse_chapter(str(chapter.id), chapter_text, chapter.title or "")
                chapter_reports.append(await build_chapter_consistency_report(db, book, number))
            except Exception:
                log.warning(
                    "manuscript_import_analysis_failed book_id=%s chapter_number=%s",
                    book.id,
                    number,
                    exc_info=True,
                )

    if book.mode == "author" and len(chapter_reports) == 1:
        for report in chapter_reports:
            notification = build_chapter_report_notification(book, report)
            if notification is not None:
                db.add(notification)
            for risk_notification in build_continuity_risk_notifications(book, report):
                db.add(risk_notification)
        await db.commit()

    await invalidate_advisor_caches_for_book(db, book_id=book.id)

    return ManuscriptImportResult(
        book_id=str(book.id),
        imported_chapters=sorted(set(imported_numbers)),
        chapter_content_versions=imported_content_versions,
        total_chapters=book.total_chapters or total_chapters,
        mode=book.mode or "author",
        source_kind=book.source_kind or "chapter_wise",
        chapter_reports=chapter_reports,
    )


@router.put("/{book_id}/series", response_model=BookOut)
async def update_book_series(
    book_id: uuid.UUID,
    body: SeriesBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")

    series_name = _clean_text(body.series_name)
    if body.series_order is not None and body.series_order < 1:
        raise HTTPException(400, "Series order must be at least 1")

    if not series_name:
        if book.primary_series_id:
            membership = (
                await db.execute(
                    select(SeriesBook).where(
                        SeriesBook.book_id == book.id,
                        SeriesBook.series_id == book.primary_series_id,
                    )
                )
            ).scalar()
            if membership:
                await db.delete(membership)
        book.primary_series_id = None
        book.series_name = None
        book.series_order = None
        await db.commit()
        await db.refresh(book)
        return await book_out(db, book, current_user.id)

    series = (
        await db.execute(
            select(Series).where(Series.user_id == current_user.id, Series.name == series_name)
        )
    ).scalar()
    if not series:
        series = Series(user_id=current_user.id, name=series_name)
        db.add(series)
        await db.flush()

    membership = (
        await db.execute(
            select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id)
        )
    ).scalar()
    if not membership:
        membership = SeriesBook(series_id=series.id, book_id=book.id)
        db.add(membership)
    membership.position = body.series_order
    book.primary_series_id = series.id
    book.series_name = series.name
    book.series_order = body.series_order
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.get("/series", response_model=list[SeriesOut])
async def list_series(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows_result = await db.execute(
        select(Series)
        .where(Series.user_id == current_user.id)
        .order_by(Series.created_at.desc(), Series.name)
    )
    rows = list(rows_result.scalars().all())
    output: list[SeriesOut] = []
    for series in rows:
        memberships = (
            await db.execute(
                select(SeriesBook, Book)
                .join(Book, Book.id == SeriesBook.book_id)
                .where(SeriesBook.series_id == series.id, Book.user_id == current_user.id)
                .order_by(SeriesBook.position, Book.created_at)
            )
        ).all()
        books: list[BookOut] = []
        for membership, book in memberships:
            enriched = await book_out(db, book, current_user.id)
            enriched.marked_complete_in_series = membership.marked_complete
            books.append(enriched)
        output.append(SeriesOut(id=series.id, name=series.name, description=series.description, created_at=series.created_at, books=books))
    return output


@router.get("/series/{series_id}/bible", response_model=SeriesBibleOut)
async def get_series_bible(
    series_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    return await build_series_bible_payload(db, series=series)


@router.post("/series", response_model=SeriesOut, status_code=201)
async def create_series(
    body: SeriesCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    name = _clean_text(body.name)
    description = _clean_optional_text(body.description)
    if not name:
        raise HTTPException(400, "Series name is required")

    existing = (
        await db.execute(select(Series).where(Series.user_id == current_user.id, Series.name == name))
    ).scalar()
    if existing:
        raise HTTPException(400, "Series already exists")

    series = Series(user_id=current_user.id, name=name, description=description)
    db.add(series)
    await db.commit()
    await db.refresh(series)
    return SeriesOut(id=series.id, name=series.name, description=series.description, created_at=series.created_at, books=[])


@router.post("/series/{series_id}/books/{book_id}", response_model=SeriesOut)
async def add_book_to_series(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    body: SeriesMembershipBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    book = await get_owned_book(db, book_id, current_user.id)
    if body.position is not None and body.position < 1:
        raise HTTPException(400, "Position must be at least 1")

    membership = (
        await db.execute(select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id))
    ).scalar()
    if not membership:
        membership = SeriesBook(series_id=series.id, book_id=book.id)
        db.add(membership)
    membership.position = body.position
    book.primary_series_id = series.id
    book.series_name = series.name
    book.series_order = body.position
    await db.commit()
    return next(item for item in await list_series(db, current_user) if item.id == series.id)


@router.delete("/series/{series_id}/books/{book_id}", response_model=SeriesOut)
async def remove_book_from_series(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    book = await get_owned_book(db, book_id, current_user.id)
    membership = (
        await db.execute(select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id))
    ).scalar()
    if not membership:
        raise HTTPException(404, "Series membership not found")

    await db.delete(membership)
    if book.primary_series_id == series.id:
        book.primary_series_id = None
        book.series_name = None
        book.series_order = None
    await db.commit()
    return next(item for item in await list_series(db, current_user) if item.id == series.id)


@router.put("/series/{series_id}/books/{book_id}/status", response_model=BookOut)
async def set_series_book_status(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    body: SeriesBookStatusBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    book = await get_owned_book(db, book_id, current_user.id)
    membership = (
        await db.execute(select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id))
    ).scalar()
    if not membership:
        raise HTTPException(404, "Series membership not found")

    membership.marked_complete = body.marked_complete
    progress = (
        await db.execute(select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book.id))
    ).scalar()
    total = book.total_chapters or 0
    if body.marked_complete and total > 0:
        chapters_read = list(range(1, total + 1))
        if progress is None:
            progress = ReadingProgress(
                user_id=current_user.id, book_id=book.id,
                current_chapter=total, scroll_pct=1.0, chapters_read=chapters_read,
            )
            db.add(progress)
        else:
            progress.current_chapter = total
            progress.scroll_pct = 1.0
            progress.chapters_read = chapters_read
            progress.last_read = datetime.now(UTC)
    await db.commit()
    enriched = await book_out(db, book, current_user.id)
    enriched.marked_complete_in_series = membership.marked_complete
    return enriched


@router.get("", response_model=list[BookOut])
async def list_books(
    include_hidden: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    stmt = select(Book).where(Book.user_id == current_user.id)
    if not include_hidden:
        stmt = stmt.where(Book.hidden_at.is_(None))
    result = await db.execute(stmt.order_by(Book.created_at.desc()))
    books = list(result.scalars().all())
    shared_rows = (
        await db.execute(
            select(Book, BookCollaborator)
            .join(BookCollaborator, BookCollaborator.book_id == Book.id)
            .where(
                BookCollaborator.email == str(current_user.email).strip().lower(),
                BookCollaborator.invite_status == "active",
                Book.user_id != current_user.id,
            )
            .order_by(BookCollaborator.invited_at.desc())
        )
    ).all()
    if not include_hidden:
        shared_rows = [row for row in shared_rows if row[0].hidden_at is None]

    owned_payloads = [await book_out(db, book, current_user.id) for book in books]
    shared_payloads = [await book_out(db, book, current_user.id, collaborator) for book, collaborator in shared_rows]
    return owned_payloads + shared_payloads


@router.get("/stats", response_model=UserStatsOut)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    books_result = await db.execute(select(Book).where(Book.user_id == current_user.id).order_by(Book.created_at.desc()))
    books = list(books_result.scalars().all())

    progress_rows_result = await db.execute(select(ReadingProgress).where(ReadingProgress.user_id == current_user.id))
    progress_rows = list(progress_rows_result.scalars().all())
    progress_by_book = {progress.book_id: progress for progress in progress_rows}

    total_books_read = 0
    total_words_read = 0
    total_chapters_tracked = 0

    for book in books:
        total_chapters_tracked += book.total_chapters or 0
        progress = progress_by_book.get(book.id)
        read_chapters = sorted(set(progress.chapters_read or [])) if progress and progress.chapters_read else []
        if book.total_chapters and len(read_chapters) >= book.total_chapters:
            total_books_read += 1
        total_words_read += await compute_words_read_for_book(db, book, progress)

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
    return await list_user_notes(db, current_user.id)


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    return await book_out(db, book, current_user.id, collaborator)


@router.get("/{book_id}/overview", response_model=BookOverviewOut)
async def get_book_overview(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    cache_version = await get_book_cache_version(str(book.id))
    access_key = _book_cache_access_key(current_user.id, collaborator)
    cached = await get_book_overview_cache(str(book.id), str(current_user.id), access_key, cache_version)
    if cached is not None:
        return BookOverviewOut(**cached)
    book_payload = await book_out(db, book, current_user.id, collaborator)
    progress_payload = await build_reading_progress_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )
    chapter_list_payload = await build_chapter_list_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )
    summary_collection_payload = await build_summary_collection_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )
    payload = BookOverviewOut(
        book=book_payload,
        progress=progress_payload,
        chapter_list=chapter_list_payload,
        summary_collection=summary_collection_payload,
    )
    await set_book_overview_cache(
        str(book.id),
        str(current_user.id),
        access_key,
        cache_version,
        payload.model_dump(mode="json"),
    )
    return payload


@router.get("/{book_id}/notes", response_model=list[BookNoteOut])
async def get_book_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot view or leave comments.")
    return await list_book_notes(db, book, collaborator=collaborator)


@router.put("/{book_id}/revision-tags", response_model=EntityTagSetOut)
async def update_revision_tags(
    book_id: uuid.UUID,
    body: EntityTagUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    resolved_type, resolved_entity_id, target_chapter_number = await resolve_tag_target(
        db,
        book=book,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        chapter_number=body.chapter_number,
    )
    target_owner_user_id = None
    if resolved_type == ENTITY_TYPE_NOTE:
        note = await db.get(BookNote, resolved_entity_id)
        target_owner_user_id = note.user_id if note is not None else None
    if not can_manage_tag_target(
        collaborator=collaborator,
        public_entity_type=body.entity_type,
        target_chapter_number=target_chapter_number,
        target_owner_user_id=target_owner_user_id,
        current_user_id=current_user.id,
    ):
        raise HTTPException(403, "This share cannot manage tags for that item.")

    tags = await replace_custom_tags_for_entity(
        db,
        book_id=book.id,
        entity_type=resolved_type,
        entity_id=resolved_entity_id,
        created_by_user_id=current_user.id,
        tags=body.tags,
    )
    await db.commit()
    return EntityTagSetOut(
        entity_type=body.entity_type,
        entity_id=str(resolved_entity_id),
        chapter_number=target_chapter_number,
        tags=tags,
    )


@router.post("/{book_id}/notes", response_model=BookNoteOut)
async def upsert_book_note(
    book_id: uuid.UUID,
    body: BookNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot leave comments.")
    if collaborator and body.chapter_number is not None and not collaboration_allows_chapter(collaborator, body.chapter_number):
        raise HTTPException(403, "This share cannot comment on that chapter.")
    return await save_book_note(
        db,
        book=book,
        user_id=current_user.id,
        note_id=body.note_id,
        chapter_number=body.chapter_number,
        title=body.title,
        body=body.body,
    )


@router.delete("/{book_id}/notes/{note_id}", status_code=204)
async def remove_book_note(
    book_id: uuid.UUID,
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot remove comments.")
    await delete_book_note(db, book=book, user_id=current_user.id, note_id=note_id)
    return Response(status_code=204)


@router.get("/{book_id}/notes/obsidian", response_model=list[ObsidianVaultNoteOut])
async def list_book_obsidian_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_obsidian_notes(
        db,
        book=book,
        user_id=current_user.id,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )


@router.put("/{book_id}/notes/obsidian", response_model=ObsidianVaultNoteSaveOut)
async def save_book_obsidian_note(
    book_id: uuid.UUID,
    body: ObsidianVaultNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await save_obsidian_vault_note(
        db,
        book=book,
        user_id=current_user.id,
        path=body.path,
        content=body.content,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )


@router.delete("/{book_id}/notes/obsidian/{path:path}", status_code=204)
async def delete_book_obsidian_note(
    book_id: uuid.UUID,
    path: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    await delete_obsidian_note(
        db,
        book=book,
        user_id=current_user.id,
        path=path,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )
    return Response(status_code=204)


@router.post("/{book_id}/notes/obsidian/import", response_model=list[ObsidianVaultNoteSaveOut])
async def import_book_obsidian_notes(
    book_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_manuscript_import),
):
    book = await get_owned_book(db, book_id, current_user.id)
    archive_bytes = await _read_upload_bounded(file, settings.OBSIDIAN_IMPORT_MAX_BYTES, "ZIP file")
    return await import_obsidian_notes_zip(
        db,
        book=book,
        user_id=current_user.id,
        archive_bytes=archive_bytes,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )


@router.get("/{book_id}/notes/obsidian/export")
async def export_book_obsidian_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    notes = await list_obsidian_notes(
        db,
        book=book,
        user_id=current_user.id,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )
    zip_data = export_obsidian_notes_zip(notes=notes)
    safe_title = _clean_text(book.title or "notes").strip() or "notes"
    filename = f"{safe_title.replace(' ', '-')}-obsidian-notes.zip"
    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{book_id}/notes/obsidian/graph", response_model=ObsidianGraphOut)
async def get_book_obsidian_graph(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    notes = await list_obsidian_notes(
        db,
        book=book,
        user_id=current_user.id,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )
    return build_obsidian_graph(notes)


@router.get("/{book_id}/notes/obsidian/relations", response_model=ObsidianNoteLinkListOut)
async def get_book_obsidian_note_relations(
    book_id: uuid.UUID,
    path: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_obsidian_note_relations(
        db,
        book=book,
        user_id=current_user.id,
        path=path,
    )


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
    await requeue_stalled_book_processing_if_needed(db, book=book)
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
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return build_writer_workspace_response(book)


@router.post("/{book_id}/manuscript/readability", response_model=ReadabilityMetricsOut)
async def manuscript_readability(
    book_id: uuid.UUID,
    body: ReadabilityRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    _ = book
    return ReadabilityMetricsOut(**estimate_readability(body.text))


@router.get("/{book_id}/emotional-arc", response_model=EmotionalArcOverviewOut)
async def get_emotional_arc(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    characters = (
        await db.execute(select(Character).where(Character.book_id == book.id).order_by(Character.mention_count.desc(), Character.name))
    ).scalars().all()
    return EmotionalArcOverviewOut(**build_emotional_arc_payload(list(characters)))


@router.get("/{book_id}/manuscript/export")
async def export_manuscript(
    book_id: uuid.UUID,
    format: str = Query("docx", pattern="^(pdf|docx|epub|obsidian)$"),
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
            headers={"Content-Disposition": f'attachment; filename="{filename_base}-manuscript.pdf"'},
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
            headers={"Content-Disposition": f'attachment; filename="{filename_base}-manuscript.epub"'},
        )
    if format == "obsidian":
        notes = await list_obsidian_notes(
            db,
            book=book,
            user_id=current_user.id,
            source=ObsidianVaultNoteSource.USER_NOTES.value,
        )
        raw = manuscript_obsidian_vault_zip(
            title=book.title or "LoreVia Manuscript",
            chapters=chapters,
            scenes=manuscript_scenes,
            notes=notes,
            front_matter=cast(dict | None, front_matter),
        )
        return Response(
            content=raw,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}-manuscript-vault.zip"'},
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
        headers={"Content-Disposition": f'attachment; filename="{filename_base}-manuscript.docx"'},
    )


async def get_book_cover_public(book_id: uuid.UUID, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
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

    import mimetypes
    raw = await asyncio.to_thread(storage.download_book, book.cover_s3_key)
    media_type = mimetypes.guess_type(book.cover_s3_key)[0] or "image/png"
    return Response(content=raw, media_type=media_type)


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


@router.post(
    "/{book_id}/publish",
    response_model=PublicBookCreateOut,
    dependencies=[Depends(rate_limit_public_publish)],
)
async def publish_book_publicly(
    book_id: uuid.UUID,
    body: PublicBookShareBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id or book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(404, "Book not found")
    if getattr(current_user, "email_verified_at", None) is None and current_user.tier != "admin":
        raise HTTPException(403, "Verify your email before publishing a public book.")

    moderation_status = str(getattr(book, "moderation_status", "") or "").strip().lower()
    if moderation_status in {MODERATION_STATUS_HIDDEN, MODERATION_STATUS_REMOVED, MODERATION_STATUS_UNDER_REVIEW}:
        raise HTTPException(409, "This book is not eligible for public publishing right now.")
    if getattr(book, "takedown_at", None) is not None:
        raise HTTPException(409, "This book is under takedown and cannot be republished.")
    if not (body.rights_confirmation or body.confirm_public_share):
        raise HTTPException(400, "Public publishing requires explicit rights confirmation.")
    if not body.public_slug:
        raise HTTPException(400, "Public publishing requires a public URL slug.")

    content_source_type = ensure_content_source_allowed_for_user(current_user, body.content_source_type)
    await enforce_daily_public_publish_limit(db, user=current_user)

    normalized_slug = normalize_public_slug(body.public_slug)
    existing_slug = (
        await db.execute(
            select(Book.id).where(
                Book.public_slug == normalized_slug,
                Book.id != book.id,
            )
        )
    ).scalar_one_or_none()
    if existing_slug is not None:
        raise HTTPException(409, "That public URL is already in use.")

    previous_status = str(getattr(book, "public_status", "") or "") or None
    now = datetime.now(UTC)
    source_kind = (
        PUBLIC_DEMO_SOURCE_KIND
        if content_source_type in {CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN, CONTENT_SOURCE_TYPE_ADMIN_SEEDED}
        else USER_PUBLIC_SHARE_SOURCE_KIND
    )

    book.public_slug = normalized_slug
    book.public_description = _clean_optional_text(body.description)
    book.rights_confirmation = True
    book.rights_confirmation_at = now
    book.rights_confirmation_ip_hash = hash_text(request.client.host if request.client else None)
    book.rights_confirmation_user_agent = request.headers.get("user-agent")
    book.content_source_type = content_source_type
    book.source_kind = source_kind
    book.public_visibility = "public"
    book.public_status = PUBLIC_STATUS_PUBLISHED
    book.moderation_status = "clean"
    book.moderation_reason = None
    book.takedown_reason = None
    book.takedown_at = None
    book.takedown_by_user_id = None
    book.published_at = book.published_at or now
    book.public_upload_counted_at = now
    book.is_public = True
    book.public_share_status = PUBLIC_SHARE_STATUS_APPROVED
    book.public_share_requested_at = now
    book.public_share_approved_at = now
    book.public_share_approved_by_user_id = current_user.id if current_user.tier == "admin" else None
    await add_moderation_action(
        db,
        action_type="book_published",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.public_status,
        reason="Creator published book publicly with rights confirmation.",
        metadata={
            "public_slug": normalized_slug,
            "content_source_type": content_source_type,
        },
    )
    await db.commit()
    return PublicBookCreateOut(
        book_id=str(book.id),
        status=book.status,
        visibility="public",
        public_kind=source_kind,
        approval_status=book.public_status,
        public_slug=book.public_slug,
        message="Public book is now live.",
    )


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


@router.post(
    "/{book_id}/unpublish",
    response_model=PublicBookCreateOut,
    dependencies=[Depends(rate_limit_public_unpublish)],
)
async def unpublish_book_publicly(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    previous_status = str(getattr(book, "public_status", "") or "") or None
    book.is_public = False
    book.public_status = PUBLIC_STATUS_HIDDEN
    book.public_visibility = "private"
    await add_moderation_action(
        db,
        action_type="book_unpublished",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.public_status,
        reason="Creator unpublished book from public view.",
    )
    await db.commit()
    return PublicBookCreateOut(
        book_id=str(book.id),
        status=book.status,
        visibility="private",
        public_kind=book.source_kind or USER_PUBLIC_SHARE_SOURCE_KIND,
        approval_status=book.public_status,
        public_slug=book.public_slug,
        message="Book removed from public view.",
    )


@router.get("/{book_id}/characters")
async def get_book_characters(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "character_bible"):
        raise HTTPException(403, "This share does not include the character bible.")
    result = await db.execute(select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name))
    all_characters = list(result.scalars().all())
    characters = all_characters if book.mode == "author" else [char for char in all_characters if is_displayable_character(char)]
    rel_result = await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    relationships = list(rel_result.scalars().all())
    char_by_id = {char.id: char for char in characters}
    character_ids = list(char_by_id.keys())
    rel_summaries: dict[str, list[str]] = {}
    rel_keys: dict[str, set[str]] = {}
    states_by_character: dict[uuid.UUID, list[CharacterState]] = {char_id: [] for char_id in character_ids}
    voice_profiles_by_character: dict[uuid.UUID, CharacterVoiceProfile] = {}

    for rel in relationships:
        a = char_by_id.get(rel.character_a_id)
        b = char_by_id.get(rel.character_b_id)
        if not a or not b:
            continue
        summary_a = relationship_summary_for_character(rel, a.name, b.name, a.name)
        summary_b = relationship_summary_for_character(rel, a.name, b.name, b.name)
        if summary_a:
            append_unique_summary(rel_summaries, rel_keys, str(a.id), f"{rel.rel_type}:{b.name}".lower(), summary_a)
        if summary_b:
            append_unique_summary(rel_summaries, rel_keys, str(b.id), f"{rel.rel_type}:{a.name}".lower(), summary_b)
    if character_ids:
        state_rows = (
            await db.execute(
                select(CharacterState)
                .where(CharacterState.character_id.in_(character_ids))
                .order_by(CharacterState.character_id, CharacterState.at_chapter)
            )
        ).scalars().all()
        for state in state_rows:
            states_by_character.setdefault(state.character_id, []).append(state)

        voice_profiles = (
            await db.execute(select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book_id))
        ).scalars().all()
        voice_profiles_by_character = {profile.character_id: profile for profile in voice_profiles}

    counterpart_names = {char.id: char.name for char in characters}
    relationships_by_character: dict[uuid.UUID, list[CharacterRelationship]] = {char_id: [] for char_id in character_ids}
    for rel in relationships:
        if rel.character_a_id in relationships_by_character:
            relationships_by_character[rel.character_a_id].append(rel)
        if rel.character_b_id in relationships_by_character:
            relationships_by_character[rel.character_b_id].append(rel)
    tags_by_character = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_CHARACTER,
        entity_ids=character_ids,
        book_id=book.id,
    )

    return [
        serialize_book_character(
            char,
            rel_summaries=rel_summaries,
            states=states_by_character.get(char.id, []),
            relationships=relationships_by_character.get(char.id, []),
            counterpart_names=counterpart_names,
            voice_profile=voice_profiles_by_character.get(char.id),
            total_chapters=book.total_chapters,
            tags=tags_by_character.get(char.id, []),
        )
        for char in characters
    ]


@router.get("/{book_id}/character-review", response_model=CharacterReviewOut)
async def get_book_character_review(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character review is only available in author mode")
    return await list_character_review_data(db, book_id=book.id)


@router.get("/{book_id}/character-review/reprocess")
async def preview_book_character_reprocess(
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool = Query(True),
    allow_demote_obvious_noise: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character reprocessing is only available in author mode")
    plan = await build_repair_plan(
        book.id,
        allow_merge_safe_pairs=allow_merge_safe_pairs,
        allow_demote_obvious_noise=allow_demote_obvious_noise,
    )
    return asdict(plan)


@router.post("/{book_id}/character-review/reprocess")
async def apply_book_character_reprocess(
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool = Query(True),
    allow_demote_obvious_noise: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character reprocessing is only available in author mode")
    return await apply_repair_plan(
        book.id,
        allow_merge_safe_pairs=allow_merge_safe_pairs,
        allow_demote_obvious_noise=allow_demote_obvious_noise,
    )


@router.post("/{book_id}/characters", status_code=201)
async def create_book_character(
    book_id: uuid.UUID,
    body: CharacterCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character editing is only available in author mode")

    role = _clean_text(body.role).strip().lower() if body.role is not None else None
    if role not in {None, "mc", "sc", "background"}:
        raise HTTPException(400, "Invalid role")

    try:
        character = build_manual_character(
            book_id=book.id,
            name=body.name,
            first_chapter=body.first_chapter,
            aliases=body.aliases,
            role=role,
            description=body.description,
            goal=body.goal,
            lie_they_believe=body.lie_they_believe,
            backstory_wound=body.backstory_wound,
            arc_type=body.arc_type,
            arc_summary=body.arc_summary,
            personality_tags=body.personality_tags,
            motivations=body.motivations,
            fears=body.fears,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    db.add(character)
    await db.flush()
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await db.refresh(character)
    return serialize_book_character(
        character,
        rel_summaries={},
        states=[],
        relationships=[],
        counterpart_names={},
        voice_profile=None,
        total_chapters=book.total_chapters,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_CHARACTER,
            entity_id=character.id,
            book_id=book.id,
        ),
    )


@router.post("/{book_id}/characters/merge")
async def merge_book_characters(
    book_id: uuid.UUID,
    body: CharacterMergeBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    primary = await db.get(Character, body.primary_id)
    secondary = await db.get(Character, body.secondary_id)
    if not primary or not secondary or primary.book_id != book.id or secondary.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if primary.id == secondary.id:
        return {"merged": str(primary.id)}

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    await mark_character_candidates_merged(
        db,
        book_id=book.id,
        primary_character_id=merged.id,
        secondary_character_id=secondary.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await db.refresh(merged)
    return {"merged": str(merged.id)}


@router.post("/{book_id}/characters/{character_id}/partition")
async def partition_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterPartitionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character partition is only available in author mode")

    try:
        created = await partition_character(
            db,
            source=character,
            partitions=[{"name": item.name, "aliases": item.aliases} for item in body.partitions],
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {
        "replaced": str(character_id),
        "created": [str(item.id) for item in created],
    }


@router.put("/{book_id}/characters/{character_id}")
async def update_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character editing is only available in author mode")

    if body.name is not None:
        cleaned_name = _clean_text(body.name).strip()
        if not cleaned_name:
            raise HTTPException(400, "Character name cannot be empty")
        cast(Any, character).name = cleaned_name
    if body.aliases is not None:
        character.aliases = clean_string_list(body.aliases)
    if body.role is not None:
        role = _clean_text(body.role).strip().lower() or None
        if role not in {None, "mc", "sc", "background"}:
            raise HTTPException(400, "Invalid role")
        cast(Any, character).role = role
    if body.description is not None:
        apply_manual_character_description(character, body.description)
    if body.goal is not None:
        character.goal = clean_optional_text(body.goal)
    if body.lie_they_believe is not None:
        character.lie_they_believe = clean_optional_text(body.lie_they_believe)
    if body.backstory_wound is not None:
        character.backstory_wound = clean_optional_text(body.backstory_wound)
    if body.arc_type is not None:
        character.arc_type = clean_optional_text(body.arc_type)
    if body.arc_summary is not None:
        character.arc_summary = clean_optional_text(body.arc_summary)
    if body.personality_tags is not None:
        character.personality_tags = clean_string_list(body.personality_tags)
    if body.motivations is not None:
        character.motivations = clean_string_list(body.motivations)
    if body.fears is not None:
        character.fears = clean_string_list(body.fears)
    if body.graph_visibility is not None:
        try:
            apply_graph_visibility_override(character, body.graph_visibility)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    mark_character_curated(
        character,
        protected_from_repair=body.protected_from_repair
        if body.protected_from_repair is not None
        else None,
        review_note=body.review_note if body.review_note is not None else None,
    )

    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await db.refresh(character)
    states = (
        await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == character.id)
            .order_by(CharacterState.at_chapter)
        )
    ).scalars().all()
    relationships = (
        await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == book.id,
                (CharacterRelationship.character_a_id == character.id) | (CharacterRelationship.character_b_id == character.id),
            )
        )
    ).scalars().all()
    counterpart_ids = {
        rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        for rel in relationships
    }
    counterparts = (
        await db.execute(select(Character).where(Character.id.in_(counterpart_ids)))
    ).scalars().all() if counterpart_ids else []
    counterpart_names = {item.id: item.name for item in counterparts}
    voice_profile = (
        await db.execute(
            select(CharacterVoiceProfile).where(CharacterVoiceProfile.character_id == character.id)
        )
    ).scalar_one_or_none()

    return serialize_book_character(
        character,
        rel_summaries={},
        states=list(states),
        relationships=list(relationships),
        counterpart_names=counterpart_names,
        voice_profile=voice_profile,
        total_chapters=book.total_chapters,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_CHARACTER,
            entity_id=character.id,
            book_id=book.id,
        ),
    )


@router.delete("/{book_id}/characters/{character_id}")
async def delete_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character correction is only available in author mode")

    await db.delete(character)
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"deleted": str(character_id)}


@router.post("/{book_id}/characters/{character_id}/demote")
async def demote_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character review is only available in author mode")

    candidate = await demote_character_to_review_candidate(
        db,
        character=character,
        reason_codes=["author_requested_review"],
        review_note=(character.analysis_metadata or {}).get("review_note"),
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"demoted": str(character_id), "candidate_id": str(candidate.id)}


@router.post("/{book_id}/character-review/{candidate_id}/promote")
async def promote_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    if candidate.status != CHARACTER_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending candidates can be promoted")

    character = await promote_character_candidate(db, candidate=candidate)
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"promoted": str(character.id), "candidate_id": str(candidate.id)}


@router.post("/{book_id}/character-review/{candidate_id}/attach")
async def attach_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: CharacterCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    character = await db.get(Character, body.character_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if candidate.status != CHARACTER_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending candidates can be attached")

    await attach_character_candidate(db, candidate=candidate, character=character)
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"attached": str(character.id), "candidate_id": str(candidate.id)}


@router.post("/{book_id}/character-review/{candidate_id}/reject")
async def reject_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    candidate.status = "rejected"
    await db.commit()
    return {"rejected": str(candidate.id)}


@router.post("/{book_id}/relationship-review/{candidate_id}/attach-a")
async def attach_relationship_candidate_a(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    character = await db.get(Character, body.character_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if candidate.status != CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending relationship candidates can be updated")
    candidate.matched_character_a_id = character.id
    append_character_review_audit_entry(
        character,
        action="relationship_candidate_attached_a",
        details={"relationship_candidate_id": str(candidate.id)},
    )
    await db.commit()
    return {"attached_a": str(character.id), "relationship_candidate_id": str(candidate.id)}


@router.post("/{book_id}/relationship-review/{candidate_id}/attach-b")
async def attach_relationship_candidate_b(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    character = await db.get(Character, body.character_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if candidate.status != CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending relationship candidates can be updated")
    candidate.matched_character_b_id = character.id
    append_character_review_audit_entry(
        character,
        action="relationship_candidate_attached_b",
        details={"relationship_candidate_id": str(candidate.id)},
    )
    await db.commit()
    return {"attached_b": str(character.id), "relationship_candidate_id": str(candidate.id)}


@router.post("/{book_id}/relationship-review/{candidate_id}/accept")
async def accept_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAcceptBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Relationship review is only available in author mode")
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    if candidate.status != CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending relationship candidates can be accepted")

    relationship_a = await db.get(Character, body.character_a_id)
    relationship_b = await db.get(Character, body.character_b_id)
    if not relationship_a or relationship_a.book_id != book.id or not relationship_b or relationship_b.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if relationship_a.id == relationship_b.id:
        raise HTTPException(400, "Choose two different characters")

    rel_type = _normalize_relationship_type(body.rel_type or candidate.rel_type or "connection")
    from_chapter = body.from_chapter or int(candidate.chapter_number or 1)
    _validate_relationship_window(from_chapter, body.to_chapter)
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")

    relationship = CharacterRelationship(
        book_id=book.id,
        character_a_id=relationship_a.id,
        character_b_id=relationship_b.id,
        rel_type=rel_type,
        sentiment=body.sentiment if body.sentiment is not None else candidate.sentiment,
        description=clean_optional_text(body.description) if body.description is not None else clean_optional_text(candidate.description),
        from_chapter=from_chapter,
        to_chapter=body.to_chapter,
    )
    db.add(relationship)
    candidate.matched_character_a_id = relationship_a.id
    candidate.matched_character_b_id = relationship_b.id
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED
    append_character_review_audit_entry(
        relationship_a,
        action="relationship_candidate_accepted",
        details={"relationship_candidate_id": str(candidate.id), "side": "a"},
    )
    append_character_review_audit_entry(
        relationship_b,
        action="relationship_candidate_accepted",
        details={"relationship_candidate_id": str(candidate.id), "side": "b"},
    )
    await db.commit()
    await db.refresh(relationship)
    return _serialize_relationship_record(relationship)


@router.post("/{book_id}/relationship-review/{candidate_id}/resolve")
async def resolve_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED
    await db.commit()
    return {"resolved": str(candidate.id)}


@router.post("/{book_id}/relationship-review/{candidate_id}/reject")
async def reject_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_REJECTED
    await db.commit()
    return {"rejected": str(candidate.id)}


@router.post("/{book_id}/duplicate-suggestions/{suggestion_id}/accept")
async def accept_character_duplicate_suggestion(
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suggestion = await db.get(CharacterDuplicateSuggestion, suggestion_id)
    if not suggestion or suggestion.book_id != book.id:
        raise HTTPException(404, "Duplicate suggestion not found")

    primary = await db.get(Character, suggestion.primary_character_id)
    secondary = await db.get(Character, suggestion.secondary_character_id)
    if not primary or not secondary or primary.book_id != book.id or secondary.book_id != book.id:
        raise HTTPException(404, "Character not found")

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    suggestion.status = "accepted"
    await mark_character_candidates_merged(
        db,
        book_id=book.id,
        primary_character_id=merged.id,
        secondary_character_id=secondary.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"merged": str(merged.id), "suggestion_id": str(suggestion.id)}


@router.post("/{book_id}/duplicate-suggestions/{suggestion_id}/dismiss")
async def dismiss_character_duplicate_suggestion(
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suggestion = await db.get(CharacterDuplicateSuggestion, suggestion_id)
    if not suggestion or suggestion.book_id != book.id:
        raise HTTPException(404, "Duplicate suggestion not found")
    suggestion.status = "dismissed"
    await db.commit()
    return {"dismissed": str(suggestion.id)}


@router.post("/{book_id}/relationships", status_code=201)
async def create_book_relationship(
    book_id: uuid.UUID,
    body: RelationshipCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    relationship_a = await db.get(Character, body.character_a_id)
    relationship_b = await db.get(Character, body.character_b_id)
    if not relationship_a or relationship_a.book_id != book.id or not relationship_b or relationship_b.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if relationship_a.id == relationship_b.id:
        raise HTTPException(400, "Choose two different characters")

    rel_type = _normalize_relationship_type(body.rel_type)
    _validate_relationship_window(body.from_chapter, body.to_chapter)
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")

    relationship = CharacterRelationship(
        book_id=book.id,
        character_a_id=relationship_a.id,
        character_b_id=relationship_b.id,
        rel_type=rel_type,
        sentiment=body.sentiment,
        description=clean_optional_text(body.description),
        from_chapter=body.from_chapter,
        to_chapter=body.to_chapter,
    )
    db.add(relationship)
    await db.commit()
    await db.refresh(relationship)
    return _serialize_relationship_record(relationship)


@router.put("/{book_id}/relationships/{relationship_id}")
async def update_book_relationship(
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    body: RelationshipUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    relationship = await db.get(CharacterRelationship, relationship_id)
    if not relationship or relationship.book_id != book.id:
        raise HTTPException(404, "Relationship not found")
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    rel_type = _normalize_relationship_type(body.rel_type)
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")
    _validate_relationship_window(body.from_chapter, body.to_chapter)

    cast(Any, relationship).rel_type = rel_type
    relationship.sentiment = body.sentiment
    relationship.description = clean_optional_text(body.description)
    if body.from_chapter is not None:
        relationship.from_chapter = body.from_chapter
    relationship.to_chapter = body.to_chapter

    await db.commit()
    await db.refresh(relationship)

    return _serialize_relationship_record(relationship)


@router.delete("/{book_id}/relationships/{relationship_id}")
async def delete_book_relationship(
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    relationship = await db.get(CharacterRelationship, relationship_id)
    if not relationship or relationship.book_id != book.id:
        raise HTTPException(404, "Relationship not found")
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    await db.delete(relationship)
    await db.commit()
    return {"deleted": str(relationship_id)}


@router.post("/{book_id}/characters/{character_id}/share", response_model=CharacterShareOut)
async def share_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")

    token = create_asset_token(str(current_user.id), f"character-card:{book.id}:{character.id}", expires_minutes=7 * 24 * 60)
    return CharacterShareOut(share_url=f"/share/character/{book.id}/{character.id}?token={token}", expires_in_minutes=7 * 24 * 60)


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
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-card.md"'})
    if format == "pdf":
        raw = character_card_pdf(payload)
        return Response(content=raw, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-card.pdf"'})
    raw = character_card_docx(payload)
    return Response(content=raw,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-card.docx"'})


@router.get("/{book_id}/export/character-bible")
async def export_character_bible(
    book_id: uuid.UUID,
    format: str = Query("md", pattern="^(md|pdf|docx|obsidian_folder)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    context = await build_character_bible_obsidian_context(db, book_id)
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

    if format == "obsidian_folder":
        overrides = await load_obsidian_vault_overrides(db, book, current_user.id)
        zip_data, filename_base = character_bible_obsidian_folder(
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
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.zip"'})

    markdown, filename_base = character_bible_markdown(
        book=book,
        characters=characters,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )

    if format == "md":
        return Response(content=markdown, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.md"'})
    if format == "pdf":
        raw = character_bible_pdf(markdown=markdown, title=title)
        return Response(content=raw, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.pdf"'})
    raw = character_bible_docx(markdown=markdown, title=title)
    return Response(content=raw,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.docx"'})

    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    await consolidate_characters(db, book_id)
    result = await db.execute(
        select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name)
    )
    characters = [char for char in result.scalars().all() if is_displayable_character(char)]

    rel_result = await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    relationships = list(rel_result.scalars().all())

    plot_result = await db.execute(select(PlotThread).where(PlotThread.book_id == book_id))
    plot_threads = list(plot_result.scalars().all())

    char_by_id = {char.id: char for char in characters}
    rel_summaries: dict[str, list[str]] = {}
    rel_keys: dict[str, set[str]] = {}
    thread_summaries: dict[str, list[str]] = {}
    for rel in relationships:
        a = char_by_id.get(rel.character_a_id)
        b = char_by_id.get(rel.character_b_id)
        if not a or not b:
            continue
        summary_a = relationship_summary_for_character(rel, a.name, b.name, a.name)
        summary_b = relationship_summary_for_character(rel, a.name, b.name, b.name)
        if summary_a:
            append_unique_summary(rel_summaries, rel_keys, str(a.id), f"{rel.rel_type}:{b.name}".lower(), summary_a)
        if summary_b:
            append_unique_summary(rel_summaries, rel_keys, str(b.id), f"{rel.rel_type}:{a.name}".lower(), summary_b)

    for thread in plot_threads:
        for raw_name in thread.character_ids or []:
            owner = next((char for char in characters if char.name == raw_name), None)
            if owner is None:
                continue
            thread_summaries.setdefault(str(owner.id), []).append(
                f"{thread.title} [{thread.status}]"
                + (f" — note: {thread.note}" if thread.note else "")
            )

    title = f"{book.title} — Character Bible" if book.title else "LoreVia — Character Bible"

    if format == "obsidian_folder":
        zip_data, filename_base = character_bible_obsidian_folder(
            book=book,
            characters=characters,
            rel_summaries=rel_summaries,
            thread_summaries=thread_summaries,
        )
        return Response(content=zip_data, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.zip"'})

    markdown, filename_base = character_bible_markdown(
        book=book,
        characters=characters,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )

    if format == "md":
        return Response(content=markdown, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.md"'})
    if format == "pdf":
        raw = character_bible_pdf(markdown=markdown, title=title)
        return Response(content=raw, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.pdf"'})
    raw = character_bible_docx(markdown=markdown, title=title)
    return Response(content=raw,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{filename_base}-character-bible.docx"'})


@router.get("/{book_id}/export/character-bible/preview", response_model=ObsidianPreviewOut)
async def preview_character_bible_obsidian(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    context = await build_character_bible_obsidian_context(db, book_id)
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
    overrides = await load_obsidian_vault_overrides(db, book, current_user.id)
    return character_bible_obsidian_preview(
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


@router.get("/{book_id}/export/character-bible/notes", response_model=list[ObsidianVaultNoteOut])
async def list_character_bible_obsidian_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_obsidian_vault_notes(db, book, current_user.id)


@router.put("/{book_id}/export/character-bible/notes", response_model=ObsidianVaultNoteSaveOut)
async def save_character_bible_obsidian_note(
    book_id: uuid.UUID,
    body: ObsidianVaultNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await save_obsidian_vault_note(
        db,
        book=book,
        user_id=current_user.id,
        path=body.path,
        content=body.content,
        source=ObsidianVaultNoteSource.CHARACTER_BIBLE.value,
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
