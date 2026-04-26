import asyncio
import uuid
from datetime import UTC, datetime

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


async def _read_upload_bounded(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    """Read an UploadFile in chunks, raising 413 if the size cap is exceeded."""
    parts = []
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
from app.api.deps.subscription import check_upload_limit
from app.core.database import get_db
from app.core.security import create_asset_token, decode_token
from app.core.storage import download_book, upload_binary, upload_book_bytes
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.profile_builder import build_description
from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.character import Character
from app.models.intelligence import CharacterRelationship, PlotThread, QuoteEntry
from app.models.progress import ReadingProgress
from app.schemas.books import (
    BookModeBody,
    BookNoteBody,
    BookNoteOut,
    BookOut,
    ChapterConsistencyReport,
    ChapterVersionOut,
    CharacterShareOut,
    CharacterUpdateBody,
    ManuscriptImportResult,
    PreWritingCheckOut,
    PrivateUserStats,
    PublicUserStats,
    RelationshipUpdateBody,
    SeriesBody,
    SeriesBookStatusBody,
    SeriesCreateBody,
    SeriesMembershipBody,
    SeriesOut,
    UserStatsOut,
)
from app.utils.book_utils import (
    as_bool,
    book_out,
    build_chapter_consistency_report,
    build_character_card_payload,
    build_prewriting_check,
    clean_manuscript_html,
    compute_words_read_for_book,
    delete_book_note,
    deserialize_manuscript_content,
    ensure_book_cover,
    get_owned_book,
    get_owned_series,
    list_book_notes,
    list_chapter_consistency_reports,
    list_chapter_versions,
    list_user_notes,
    next_chapter_number,
    normalize_imported_chapters,
    parse_import_upload,
    resolve_owned_series_ids,
    save_book_note,
    snapshot_chapter_version,
)

# ── Utils imports ──────────────────────────────────────────────────────────────
from app.utils.character_utils import (
    append_unique_summary,
    apply_manual_character_description,
    character_status,
    clean_optional_text,
    clean_string_list,
    dedupe_preserve_order,
    is_displayable_character,
    merge_description_with_relationships,
    relationship_summary_for_character,
)
from app.engine.character.entity_filters import is_gag_character
from app.utils.export_utils import (
    character_bible_docx,
    character_bible_markdown,
    character_bible_pdf,
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
    manuscript_docx,
    manuscript_pdf,
)
from app.utils.notification_utils import (
    build_chapter_report_notification,
    build_continuity_risk_notifications,
)
from app.workers.consumers.analysis_consumer import analyse_chapter
from app.workers.consumers.extraction_consumer import _process_chapter
from app.workers.tasks.extraction_tasks import process_book_task

router = APIRouter()


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=202)
async def upload_book_endpoint(
    file: UploadFile = File(...),
    cover_file: UploadFile | None = File(None),
    title: str = Form(...),
    genre: str | None = Form(None),
    author: str | None = Form(None),
    series_ids: list[str] = Form(default=[]),
    visibility: str = Form("private"),
    description: str | None = Form(None),
    mode: str = Form("reader"),
    auto_extract_cover: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(check_upload_limit),
):
    title = bleach.clean(title, tags=[], strip=True) if title else ""
    if author:
        author = bleach.clean(author, tags=[], strip=True)
    if genre:
        genre = bleach.clean(genre, tags=[], strip=True)
    if description:
        description = bleach.clean(description, tags=[], strip=True)
    if not file.filename:
        raise HTTPException(400, "No file")
    if visibility not in {"private", "public"}:
        raise HTTPException(400, "Invalid visibility")
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    if not title.strip():
        raise HTTPException(400, "Title is required")

    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        fmt = "pdf"
    elif filename.endswith(".epub"):
        fmt = "epub"
    else:
        raise HTTPException(400, "Only PDF and EPUB files are supported")

    # Validate series ownership BEFORE expensive file operations
    selected_series = await resolve_owned_series_ids(db, current_user.id, series_ids)

    is_public = visibility == "public"
    # Stream-read with a hard size cap to prevent OOM DoS.
    raw = await _read_upload_bounded(file, MAX_BOOK_UPLOAD_BYTES, "Book file")
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    s3_key = upload_book_bytes(raw, str(current_user.id), file.filename)
    cover_s3_key = None
    if not as_bool(auto_extract_cover) and cover_file is not None and cover_file.filename:
        cover_raw = await _read_upload_bounded(cover_file, MAX_COVER_UPLOAD_BYTES, "Cover image")
        if cover_raw:
            # Validate magic bytes — never trust client-supplied MIME or extension.
            suffix, content_type = _validate_cover_magic(cover_raw)
            cover_s3_key = upload_binary(
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
        s3_key=s3_key,
        cover_s3_key=cover_s3_key,
        status="pending",
        is_public=is_public,
        public_description=description,
        mode=mode,
        source_kind="single_upload",
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

    process_book_task.apply_async(args=[str(book.id)], queue="extraction")
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
    book.mode = mode
    if mode == "author" and not book.source_kind:
        book.source_kind = "single_upload"
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.post("/{book_id}/manuscript/import", response_model=ManuscriptImportResult)
async def import_manuscript_content(
    book_id: uuid.UUID,
    files: list[UploadFile] | None = File(None),
    text: str | None = Form(None),
    html: str | None = Form(None),
    title: str | None = Form(None),
    chapter_number: int | None = Form(None),
    replace_existing: str = Form("false"),
    chunk_long_documents: str = Form("false"),
    split_into_chapters: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    if not text and not files:
        raise HTTPException(400, "Provide text or one or more files")

    import_jobs: list[dict] = []
    normalized_title = bleach.clean((title or "").strip(), tags=[], strip=True) or None
    next_number = await next_chapter_number(db, book.id)
    replace_flag = as_bool(replace_existing)
    chunk_flag = as_bool(chunk_long_documents)
    split_flag = as_bool(split_into_chapters)

    cleaned_html = clean_manuscript_html(html) if html else None

    if text and text.strip():
        import_jobs.extend(
            normalize_imported_chapters(
                [{
                    "title": normalized_title or f"Chapter {chapter_number or next_number}",
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
        parsed = await parse_import_upload(upload.filename, raw, split_flag)
        base_number = chapter_number if replace_flag and chapter_number else next_number
        import_jobs.extend(
            normalize_imported_chapters(
                parsed,
                chapter_number=chapter_number,
                start_number=base_number,
                replace_existing=replace_flag and len(parsed) == 1,
                chunk_long_documents=chunk_flag,
            )
        )
        next_number = max(next_number, max((job["number"] for job in import_jobs), default=next_number) + 1)

    if not import_jobs:
        raise HTTPException(400, "No importable manuscript content was found")

    imported_numbers: list[int] = []
    for job in import_jobs:
        if replace_flag:
            existing = (
                await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == job["number"]))
            ).scalar()
            if existing is not None:
                await snapshot_chapter_version(
                    db,
                    book,
                    existing,
                    note=f"Snapshot before replacing Chapter {job['number']}",
                )
                await db.delete(existing)
                await db.flush()
        await _process_chapter(
            db,
            book,
            {
                "number": job["number"],
                "title": job.get("title"),
                "text": job.get("text", ""),
                "html": job.get("html"),
                "images": [],
            },
        )
        imported_numbers.append(job["number"])

    total_chapters = await db.scalar(select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id)) or 0
    book.total_chapters = total_chapters
    book.mode = "author"
    book.source_kind = "chapter_wise" if len(import_jobs) == 1 and not files else "batch_upload"
    await db.commit()
    await db.refresh(book)

    chapter_reports: list[ChapterConsistencyReport] = []
    for number in imported_numbers:
        chapter = (
            await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == number))
        ).scalar()
        if chapter is not None:
            chapter_payload = deserialize_manuscript_content(await asyncio.to_thread(download_book, chapter.s3_key)) if chapter.s3_key else {"text": ""}
            chapter_text = str(chapter_payload.get("text") or "")
            await db.execute(
                delete(PlotThread).where(
                    PlotThread.book_id == book.id,
                    PlotThread.introduced_at == number,
                )
            )
            await db.commit()
            await analyse_chapter(str(chapter.id), chapter_text, chapter.title or "")
            chapter_reports.append(await build_chapter_consistency_report(db, book, number))

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

    series_name = bleach.clean((body.series_name or "").strip(), tags=[], strip=True)
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
    rows = (
        await db.execute(
            select(Series)
            .where(Series.user_id == current_user.id)
            .order_by(Series.created_at.desc(), Series.name)
        )
    ).scalars().all()
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
        books = []
        for membership, book in memberships:
            enriched = await book_out(db, book, current_user.id)
            enriched.marked_complete_in_series = membership.marked_complete
            books.append(enriched)
        output.append(SeriesOut(id=series.id, name=series.name, description=series.description, created_at=series.created_at, books=books))
    return output


@router.post("/series", response_model=SeriesOut, status_code=201)
async def create_series(
    body: SeriesCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    name = bleach.clean(body.name.strip(), tags=[], strip=True)
    description = bleach.clean((body.description or "").strip(), tags=[], strip=True) or None
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
    books = result.scalars().all()
    return [await book_out(db, book, current_user.id) for book in books]


@router.get("/stats", response_model=UserStatsOut)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    books = (
        await db.execute(select(Book).where(Book.user_id == current_user.id).order_by(Book.created_at.desc()))
    ).scalars().all()

    progress_rows = (
        await db.execute(select(ReadingProgress).where(ReadingProgress.user_id == current_user.id))
    ).scalars().all()
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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    return await book_out(db, book, current_user.id)


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


@router.get("/{book_id}/pre-writing-check", response_model=PreWritingCheckOut)
async def get_prewriting_check(
    book_id: uuid.UUID,
    upcoming_chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    next_chapter = upcoming_chapter or ((book.total_chapters or 0) + 1)
    return await build_prewriting_check(db, book, next_chapter)


@router.get("/{book_id}/chapter-reports", response_model=list[ChapterConsistencyReport])
async def get_book_chapter_reports(
    book_id: uuid.UUID,
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
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


@router.get("/{book_id}/manuscript/export")
async def export_manuscript(
    book_id: uuid.UUID,
    format: str = Query("docx", pattern="^(pdf|docx)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
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
                stored = deserialize_manuscript_content(await asyncio.to_thread(download_book, s3_key))
                chapter_text = str(stored.get("text") or "")
                chapter_html = str(stored.get("html") or "") or None
            except Exception:
                chapter_text = ""
                chapter_html = None
        chapters.append({"number": number, "title": chapter_title, "text": chapter_text, "html": chapter_html})

    filename_base = "".join(ch for ch in (book.title or "lorevia") if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "-") or "lorevia"
    if format == "pdf":
        raw = manuscript_pdf(title=book.title or "LoreVia Manuscript", chapters=chapters)
        return Response(
            content=raw,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}-manuscript.pdf"'},
        )

    raw = manuscript_docx(title=book.title or "LoreVia Manuscript", chapters=chapters)
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
    raw = await asyncio.to_thread(download_book, book.cover_s3_key)
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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await consolidate_characters(db, book_id)
    result = await db.execute(select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name))
    characters = [char for char in result.scalars().all() if is_displayable_character(char)]
    rel_result = await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    relationships = rel_result.scalars().all()
    # Plot threads data available if needed later

    char_by_id = {char.id: char for char in characters}
    rel_summaries: dict[str, list[str]] = {}
    rel_keys: dict[str, set[str]] = {}

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

    return [
        {
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
            "motivations": char.motivations or [],
            "fears": char.fears or [],
            "archetype": char.archetype,
            "arc_summary": char.arc_summary,
            "growth_events": char.growth_events or [],
            "relationship_summaries": dedupe_preserve_order(rel_summaries.get(str(char.id), [])),
            "character_type": (
                "gag" if is_gag_character(
                    personality_tags=char.personality_tags or [],
                    archetype=char.archetype,
                    arc_summary=char.arc_summary,
                    mention_count=char.mention_count or 0,
                    role=char.role,
                    growth_events=char.growth_events or [],
                ) else "complex"
            ),
        }
        for char in characters
    ]


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
        cleaned_name = bleach.clean(body.name, tags=[], strip=True).strip()
        if not cleaned_name:
            raise HTTPException(400, "Character name cannot be empty")
        character.name = cleaned_name
    if body.aliases is not None:
        character.aliases = clean_string_list(body.aliases)
    if body.role is not None:
        role = bleach.clean(body.role, tags=[], strip=True).strip().lower() or None
        if role not in {None, "mc", "sc", "background"}:
            raise HTTPException(400, "Invalid role")
        character.role = role
    if body.description is not None:
        apply_manual_character_description(character, body.description)
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

    return {
        "id": str(character.id),
        "book_id": str(character.book_id),
        "name": character.name,
        "aliases": character.aliases or [],
        "role": character.role,
        "first_chapter": character.first_chapter,
        "last_seen_chapter": character.last_seen_chapter,
        "mention_count": character.mention_count or 0,
        "status": character_status(character),
        "trait_state": character.trait_state or {},
        "description": build_description(character.trait_state or {}, character.archetype),
        "personality_tags": character.personality_tags or [],
        "motivations": character.motivations or [],
        "fears": character.fears or [],
        "archetype": character.archetype,
        "arc_summary": character.arc_summary,
        "growth_events": character.growth_events or [],
        "relationship_summaries": [],
    }


@router.put("/{book_id}/relationships/{relationship_id}")
async def update_book_relationship(
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    body: RelationshipUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    relationship = await db.get(CharacterRelationship, relationship_id)
    if not relationship or relationship.book_id != book.id:
        raise HTTPException(404, "Relationship not found")
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    rel_type = bleach.clean(body.rel_type or "", tags=[], strip=True).strip().lower().replace(" ", "_")
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

    relationship.rel_type = rel_type
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
    format: str = Query("md", pattern="^(md|pdf|docx)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    await consolidate_characters(db, book_id)
    result = await db.execute(
        select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name)
    )
    characters = [char for char in result.scalars().all() if is_displayable_character(char)]

    rel_result = await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    relationships = rel_result.scalars().all()

    plot_result = await db.execute(select(PlotThread).where(PlotThread.book_id == book_id))
    plot_threads = plot_result.scalars().all()

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

    markdown, filename_base = character_bible_markdown(
        book=book,
        characters=characters,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )
    title = f"{book.title} — Character Bible" if book.title else "LoreVia — Character Bible"

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
