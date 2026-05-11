import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
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
from app.api.deps.rate_limit import rate_limit_manuscript_import, rate_limit_upload
from app.api.deps.subscription import check_upload_limit
from app.core.database import get_db
from app.core.security import create_asset_token, decode_token
from app.core import storage
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.profile_builder import build_description
from app.models.book import Book, BookCollaborator, Chapter, ObsidianVaultNoteSource, Series, SeriesBook
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, QuoteEntry
from app.models.progress import ReadingProgress
from app.schemas.books import (
    BookEventsOut,
    BookModeBody,
    BookNoteBody,
    BookNoteOut,
    BookOut,
    ChapterConsistencyReport,
    ChapterVersionOut,
    CharacterEventOut,
    CharacterMergeBody,
    CharacterPartitionBody,
    CharacterShareOut,
    CharacterUpdateBody,
    CorkboardCardOut,
    EmotionalArcOverviewOut,
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
from app.utils.billing_utils import require_author_access
from app.utils.book_utils import (
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
    collaboration_has_resource,
    compute_words_read_for_book,
    delete_book_note,
    delete_obsidian_note,
    deserialize_manuscript_content,
    ensure_book_cover,
    estimate_readability,
    export_obsidian_notes_zip,
    extract_novel_scene_candidates,
    get_owned_book,
    get_book_with_collaboration_access,
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
    normalize_book_work_type,
    normalize_imported_chapters,
    normalize_writer_workspace,
    parse_import_upload,
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
)

# ── Utils imports ──────────────────────────────────────────────────────────────
from app.utils.character_utils import (
    append_unique_summary,
    apply_manual_character_description,
    build_character_arc_tracker,
    character_status,
    clean_optional_text,
    clean_string_list,
    dedupe_preserve_order,
    is_displayable_character,
    merge_characters,
    merge_description_with_relationships,
    partition_character,
    relationship_summary_for_character,
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
    manuscript_docx,
    manuscript_epub_compiled,
    manuscript_obsidian_vault_zip,
    manuscript_pdf_compiled,
)
from app.utils.notification_utils import (
    build_chapter_report_notification,
    build_continuity_risk_notifications,
    build_upload_processing_notification,
)
from app.utils.queue_utils import queue_for_user
from app.utils.user_utils import add_daily_word_progress
from app.workers.consumers.analysis_consumer import analyse_chapter
from app.workers.consumers.extraction_consumer import _process_chapter
from app.workers.tasks.extraction_tasks import process_book_task

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


def _serialize_book_character(
    char: Character,
    *,
    rel_summaries: dict[str, list[str]],
    states: list[CharacterState],
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
    voice_profile: CharacterVoiceProfile | None,
    total_chapters: int | None,
) -> dict[str, Any]:
    return {
        "id": str(char.id),
        "book_id": str(char.book_id),
        "name": char.name,
        "aliases": char.aliases or [],
        "role": char.role,
        "first_chapter": char.first_chapter,
        "last_seen_chapter": char.last_seen_chapter,
        "mention_count": char.mention_count or 0,
        "status": character_status(char),
        "trait_state": char.trait_state or {},
        "description": merge_description_with_relationships(
            build_description(char.trait_state or {}, char.archetype),
            dedupe_preserve_order(rel_summaries.get(str(char.id), [])),
        ),
        "personality_tags": char.personality_tags or [],
        "goal": char.goal,
        "motivations": char.motivations or [],
        "fears": char.fears or [],
        "lie_they_believe": char.lie_they_believe,
        "backstory_wound": char.backstory_wound,
        "arc_type": char.arc_type,
        "archetype": char.archetype,
        "arc_summary": char.arc_summary,
        "growth_events": char.growth_events or [],
        "relationship_summaries": dedupe_preserve_order(rel_summaries.get(str(char.id), [])),
        "character_type": char.character_type,
        "character_type_score": char.character_type_score,
        "subtype_scores": char.subtype_scores or {},
        "arc_tracker": build_character_arc_tracker(
            char,
            states=states,
            relationships=relationships,
            counterpart_names=counterpart_names,
            voice_profile=voice_profile,
            total_chapters=total_chapters,
        ),
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
    _=Depends(check_upload_limit),
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
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    if mode == "author":
        require_author_access(current_user)
    if not title.strip():
        raise HTTPException(400, "Title is required")

    fmt, resolved_work_type = resolve_upload_format_and_work_type(file.filename, work_type)

    # Validate series ownership BEFORE expensive file operations
    selected_series = await resolve_owned_series_ids(db, current_user.id, series_ids)

    is_public = visibility == "public"
    # Stream-read with a hard size cap to prevent OOM DoS.
    raw = await _read_upload_bounded(file, MAX_BOOK_UPLOAD_BYTES, "Book file")
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    s3_key = storage.upload_book_bytes(raw, str(current_user.id), file.filename)
    cover_s3_key = None
    cover_raw = None
    if not as_bool(auto_extract_cover) and cover_file is not None and cover_file.filename:
        cover_raw = await _read_upload_bounded(cover_file, MAX_COVER_UPLOAD_BYTES, "Cover image")
        if cover_raw:
            # Validate magic bytes — never trust client-supplied MIME or extension.
            suffix, content_type = _validate_cover_magic(cover_raw)
            cover_s3_key = storage.upload_binary(
                f"covers/{current_user.id}/{uuid.uuid4()}.{suffix}",
                cover_raw,
                content_type,
            )
    book = Book(
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
    book = await get_owned_book(db, book_id, current_user.id)
    mode = (body.mode or "").strip().lower()
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    if mode == "author":
        require_author_access(current_user)
    book.mode = mode
    if mode == "author" and not book.source_kind:
        book.source_kind = "single_upload"
    await db.commit()
    await db.refresh(book)
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
    normalized_title = _clean_optional_text(title)
    next_number = await next_chapter_number(db, book.id)
    replace_flag = as_bool(replace_existing)
    chunk_flag = as_bool(chunk_long_documents)
    split_flag = as_bool(split_into_chapters)
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
                )
            )

    MAX_MANUSCRIPT_BYTES = 20 * 1024 * 1024  # 20 MB per file
    for upload in files or []:
        if not upload.filename:
            continue
        raw = await _read_upload_bounded(upload, MAX_MANUSCRIPT_BYTES, "Manuscript file")
        if not raw:
            continue
        total_file_size += len(raw)
        fmt, upload_work_type = resolve_upload_format_and_work_type(
            upload.filename,
            work_type if work_type is not None else book.work_type,
        )
        resolved_import_format = resolved_import_format or fmt
        if upload_work_type == "screenplay":
            screenplay_payload = await parse_screenplay_upload(upload.filename, raw)
            parsed = screenplay_payload["chapters"]
        else:
            parsed = await parse_import_upload(upload.filename, raw, split_flag)
        base_number = chapter_number if replace_flag and chapter_number else next_number
        new_jobs = normalize_imported_chapters(
            parsed,
            chapter_number=chapter_number,
            start_number=base_number,
            replace_existing=replace_flag and len(parsed) == 1,
            chunk_long_documents=False if upload_work_type == "screenplay" else chunk_flag,
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
        if replace_flag:
            existing = (
                await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == job_number))
            ).scalar()
            if existing is not None:
                previous_word_count = int(existing.word_count or 0)
                await snapshot_chapter_version(
                    db,
                    book,
                    existing,
                    note=f"Snapshot before replacing Chapter {job_number}",
                    snapshot_kind="pre_replace",
                )
                await db.delete(existing)
                await db.flush()
        daily_words_added += max(next_word_count - previous_word_count, 0)
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
            },
        )
        if resolved_book_work_type != "screenplay":
            extracted_scenes = extract_novel_scene_candidates(
                text=next_text,
                chapter_number=job_number,
                source="extracted",
            )
            await replace_chapter_novel_scenes(
                db,
                book=book,
                chapter_number=job_number,
                scenes=extracted_scenes,
            )
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

    return ManuscriptImportResult(
        book_id=str(book.id),
        imported_chapters=sorted(set(imported_numbers)),
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

    total_uploads = len(books)
    total_token_consumption = int(sum(book.total_tokens or 0 for book in books))
    saved_quotes = int(
        (await db.execute(select(func.count(QuoteEntry.id)).where(QuoteEntry.user_id == current_user.id))).scalar() or 0
    )

    return UserStatsOut(
        public=PublicUserStats(total_books_read=total_books_read, total_words_read=total_words_read),
        private=PrivateUserStats(
            total_uploads=total_uploads,
            total_token_consumption=total_token_consumption,
            total_chapters_tracked=total_chapters_tracked,
            saved_quotes=saved_quotes,
        ),
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


@router.get("/{book_id}/notes", response_model=list[BookNoteOut])
async def get_book_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_book_notes(db, book)


@router.post("/{book_id}/notes", response_model=BookNoteOut)
async def upsert_book_note(
    book_id: uuid.UUID,
    body: BookNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
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
    book = await get_owned_book(db, book_id, current_user.id)
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
    archive_bytes = await _read_upload_bounded(file, 25 * 1024 * 1024, "ZIP file")
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
    book = await get_owned_book(db, book_id, current_user.id)
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
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_chapter_versions(db, book, chapter_number, limit)


@router.get("/{book_id}/writer-workspace", response_model=WriterWorkspaceOut)
async def get_writer_workspace(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return WriterWorkspaceOut(**build_writer_workspace_payload(book))


@router.put("/{book_id}/writer-workspace", response_model=WriterWorkspaceOut)
async def update_writer_workspace(
    book_id: uuid.UUID,
    body: WriterWorkspaceBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    next_payload = normalize_writer_workspace(
        {
            **build_writer_workspace_payload(book),
            **body.model_dump(exclude_none=True),
        }
    )
    book.writer_workspace = next_payload
    await db.commit()
    await db.refresh(book)
    return WriterWorkspaceOut(**build_writer_workspace_payload(book))


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
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
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
        for scene in await list_novel_scenes(db, book=book)
        if scene.get("source") == "manual" and scene.get("status") != "archived"
    ]

    filename_base = "".join(ch for ch in (book.title or "lorevia") if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "-") or "lorevia"
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


@router.get("/{book_id}/characters")
async def get_book_characters(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "character_bible"):
        raise HTTPException(403, "This share does not include the character bible.")
    await consolidate_characters(db, book_id)
    result = await db.execute(select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name))
    characters = [char for char in result.scalars().all() if is_displayable_character(char)]
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

    return [
        _serialize_book_character(
            char,
            rel_summaries=rel_summaries,
            states=states_by_character.get(char.id, []),
            relationships=relationships_by_character.get(char.id, []),
            counterpart_names=counterpart_names,
            voice_profile=voice_profiles_by_character.get(char.id),
            total_chapters=book.total_chapters,
        )
        for char in characters
    ]


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

    return _serialize_book_character(
        character,
        rel_summaries={},
        states=list(states),
        relationships=list(relationships),
        counterpart_names=counterpart_names,
        voice_profile=voice_profile,
        total_chapters=book.total_chapters,
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
    await db.commit()
    return {"deleted": str(character_id)}


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

    rel_type = _clean_text(body.rel_type).strip().lower().replace(" ", "_")
    if not rel_type:
        raise HTTPException(400, "Relationship type is required")
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")
    if body.from_chapter is not None and body.from_chapter < 1:
        raise HTTPException(400, "from_chapter must be at least 1")
    if body.to_chapter is not None and body.to_chapter < 1:
        raise HTTPException(400, "to_chapter must be at least 1")
    if body.from_chapter is not None and body.to_chapter is not None and body.to_chapter < body.from_chapter:
        raise HTTPException(400, "to_chapter cannot be earlier than from_chapter")

    cast(Any, relationship).rel_type = rel_type
    relationship.sentiment = body.sentiment
    relationship.description = clean_optional_text(body.description)
    if body.from_chapter is not None:
        relationship.from_chapter = body.from_chapter
    relationship.to_chapter = body.to_chapter

    await db.commit()
    await db.refresh(relationship)

    return {
        "id": str(relationship.id),
        "rel_type": relationship.rel_type,
        "sentiment": relationship.sentiment,
        "description": relationship.description,
        "from_chapter": relationship.from_chapter,
        "to_chapter": relationship.to_chapter,
    }


@router.post("/{book_id}/characters/{character_id}/share", response_model=CharacterShareOut)
async def share_book_character(
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
    book = await get_owned_book(db, book_id, current_user.id)
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
    require_author_access(current_user)
    context = await build_character_bible_obsidian_context(db, book_id)
    book = context.get("book")
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

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
    require_author_access(current_user)
    context = await build_character_bible_obsidian_context(db, book_id)
    book = context.get("book")
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

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
