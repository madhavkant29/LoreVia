from __future__ import annotations

import asyncio
import re
import uuid

from sqlalchemy import delete, func, or_, select

from app.core.storage import upload_text
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterState,
)
from app.models.intelligence import CharacterRelationship
from app.services.extraction_chapter_content_service import _count_words, _sync_chapter_media
from app.utils.books.manuscript import serialize_manuscript_content
from app.utils.books.normalization import normalize_chapter_kind
from app.utils.characters.constants import (
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_CANDIDATE_SUPPRESSED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED,
)
from app.utils.ingestion_utils import (
    build_analysis_chapter_state,
    build_chapter_storage_key,
    build_source_integrity_state,
)


async def stage_chapter_for_extraction(
    db, book: Book, ch_data: dict, chapter_number: int, *, rebuild_existing_chapter: bool = False
) -> Chapter:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar()

    s3_key = chapter.s3_key if chapter is not None else ""
    if chapter is None and rebuild_existing_chapter:
        raise RuntimeError("rebuild_chapter_missing")
    if ch_data.get("_lorevia_persist_rich_content") and not rebuild_existing_chapter:
        storage_key = s3_key or build_chapter_storage_key(book.id, chapter_number)
        payload = serialize_manuscript_content(
            str(ch_data.get("text") or ""),
            ch_data.get("html") if isinstance(ch_data.get("html"), str) else None,
        )
        s3_key = await asyncio.to_thread(upload_text, storage_key, payload)

    if chapter is None:
        chapter = Chapter(
            book_id=book.id,
            number=chapter_number,
            content_version=int(ch_data.get("content_version") or 1),
            title=ch_data.get("title"),
            description=ch_data.get("description"),
            chapter_kind=normalize_chapter_kind(
                ch_data.get("chapter_kind") or ch_data.get("section_type")
            ),
            s3_key=s3_key,
            word_count=_count_words(ch_data.get("text", "")),
            processed=False,
        )
        db.add(chapter)
        await db.flush()
        await _sync_chapter_media(db, book, chapter, ch_data)
    else:
        chapter_changed = False
        if not rebuild_existing_chapter:
            if ch_data.get("title") and chapter.title != ch_data["title"]:
                chapter.title = ch_data["title"]
                chapter_changed = True
            if ch_data.get("description") and chapter.description != ch_data["description"]:
                chapter.description = ch_data["description"]
                chapter_changed = True
            next_chapter_kind = normalize_chapter_kind(
                ch_data.get("chapter_kind") or ch_data.get("section_type")
            )
            if next_chapter_kind != chapter.chapter_kind:
                chapter.chapter_kind = next_chapter_kind
                chapter_changed = True
            next_word_count = _count_words(ch_data.get("text", ""))
            if next_word_count and chapter.word_count != next_word_count:
                chapter.word_count = next_word_count
                chapter_changed = True
            next_content_version = ch_data.get("content_version")
            if next_content_version is not None and int(chapter.content_version or 1) != int(
                next_content_version
            ):
                chapter.content_version = int(next_content_version)
                chapter_changed = True
            if s3_key and chapter.s3_key != s3_key:
                chapter.s3_key = s3_key
                chapter_changed = True
        if chapter.processed:
            chapter.processed = False
            chapter_changed = True
        if chapter_changed:
            await db.flush()
        if not rebuild_existing_chapter:
            await _sync_chapter_media(db, book, chapter, ch_data)

    stored_media_count = len(ch_data.get("images") or [])
    if rebuild_existing_chapter:
        stored_media_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(ChapterMedia)
                    .where(ChapterMedia.chapter_id == chapter.id)
                )
            ).scalar()
            or 0
        )
    chapter.analysis_state = build_analysis_chapter_state(
        chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
        status="pending",
        source_integrity=build_source_integrity_state(
            text_present=bool(str(ch_data.get("text") or "").strip()),
            media_marker_count=len(
                re.findall(r"\[\[IMAGE:[^\]]+\]\]", str(ch_data.get("text") or ""))
            ),
            stored_media_count=stored_media_count,
            recovery_status="ok",
        ),
    )
    await db.flush()

    return chapter


async def replace_chapter_extraction_records(
    db,
    *,
    book_id,
    chapter_number: int,
    replace_generated_intelligence: bool = False,
) -> set[uuid.UUID]:
    """Clear replaceable rows only after new provider output is available."""
    previous_character_ids = set(
        (
            await db.scalars(
                select(CharacterMention.matched_character_id).where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.chapter_number == chapter_number,
                    CharacterMention.matched_character_id.is_not(None),
                )
            )
        ).all()
    )
    await db.execute(
        delete(CharacterMention).where(
            CharacterMention.book_id == book_id,
            CharacterMention.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterCandidate).where(
            CharacterCandidate.book_id == book_id,
            CharacterCandidate.chapter_number == chapter_number,
            CharacterCandidate.status.in_(
                (CHARACTER_CANDIDATE_PENDING, CHARACTER_CANDIDATE_SUPPRESSED)
            ),
            CharacterCandidate.rejection_reason.is_distinct_from("author_marked_place"),
            or_(
                CharacterCandidate.source_batch_key.is_(None),
                ~CharacterCandidate.source_batch_key.like("manual-demote:%"),
            ),
        )
    )
    await db.execute(
        delete(CharacterRelationshipCandidate).where(
            CharacterRelationshipCandidate.book_id == book_id,
            CharacterRelationshipCandidate.chapter_number == chapter_number,
            CharacterRelationshipCandidate.status.in_(
                (
                    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
                    CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED,
                )
            ),
            func.array_position(
                CharacterRelationshipCandidate.reason_codes, "author_attached_endpoint"
            ).is_(None),
        )
    )
    if not replace_generated_intelligence:
        return previous_character_ids
    await db.execute(
        delete(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter == chapter_number,
            CharacterRelationship.edited_by_author.is_(False),
        )
    )
    await db.execute(
        delete(CharacterState).where(
            CharacterState.character_id.in_(
                select(Character.id).where(Character.book_id == book_id)
            ),
            CharacterState.at_chapter == chapter_number,
        )
    )
    return previous_character_ids
