import uuid
from typing import Any, cast

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_search, rate_limit_summary
from app.core.config import is_local_mode, settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_chapter_summary, key_search_results
from app.core.security import decode_token
from app.core.storage import download_book
from app.engine.search.semantic import build_search_result, find_context_for_tap, semantic_search
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import Character, CharacterState
from app.models.intelligence import BookChunk, ChapterSummary, CharacterRelationship, QuoteEntry
from app.schemas.reader import SaveQuoteBody
from app.services.chapter_recovery_service import resolve_reader_chapter_payload
from app.services.summary_service import get_or_generate_summary
from app.utils.beta_read_utils import list_chapter_beta_feedback
from app.utils.billing_utils import require_author_access, summary_mode_allowed
from app.utils.book_utils import (
    collaboration_allows_chapter,
    collaboration_can_copy_manuscript,
    get_book_with_collaboration_access,
)
from app.utils.character_utils import (
    append_unique_summary,
    backfill_character_first_chapters_for_chapter_text,
    relationship_summary_for_character,
    serialize_reader_character,
)
from app.utils.public_utils import ensure_public_mode_enabled
from app.utils.reader_utils import (
    build_chapter_list_payload,
    build_summary_collection_payload,
    chapter_analysis_status,
    chapter_intelligence_available,
    normalize_summary_response,
    queue_analysis_if_missing,
    read_chapter_set,
    require_summary_access,
    summary_visible_chapter_set,
)
from app.utils.sparse_utils import apply_sparse_fields, apply_sparse_includes, include_requested
from app.utils.tag_utils import ENTITY_TYPE_CHAPTER, get_custom_tags_for_entity

router = APIRouter()

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


@router.get("/media/{media_id}")
async def get_chapter_media_public(
    media_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    media = await db.get(ChapterMedia, media_id)
    if not media:
        raise HTTPException(404, "Chapter media not found")

    book = await db.get(Book, media.book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(book.user_id)
        or payload.get("res") != f"chapter-media:{media.id}"
    ):
        raise HTTPException(401, "Invalid chapter media token")

    try:
        raw = download_book(media.storage_key)
    except Exception:
        raise HTTPException(404, "Chapter media not found")

    return Response(content=raw, media_type=media.content_type or "application/octet-stream")


@router.get("/{book_id}/chapter/{chapter_num}")
async def get_chapter(
    book_id: uuid.UUID,
    chapter_num: int,
    include: str | None = Query(None, description="Comma-separated sub-objects: characters, media, tags, beta_feedback, text_content, html_content, text_url"),
    fields: str | None = Query(None, description="Comma-separated top-level fields to return"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Returns chapter text URL + all characters introduced up to this chapter."""
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter_num):
        raise HTTPException(403, "This share does not include that chapter.")
    
    # Validate book has chapters
    if book.total_chapters is None or book.total_chapters == 0:
        if book.is_editor_project:
            raise HTTPException(400, "This project has no chapters yet. Create your first chapter to get started.")
        raise HTTPException(400, "This book has no chapters yet. Please wait for processing to complete or import a manuscript.")
    
    # Validate chapter number is in valid range
    if chapter_num < 1:
        raise HTTPException(400, f"Invalid chapter number: {chapter_num}. Chapter numbers must be 1 or greater.")
    if chapter_num > book.total_chapters:
        raise HTTPException(404, f"Chapter {chapter_num} does not exist. This book has {book.total_chapters} chapter{'s' if book.total_chapters != 1 else ''}.")
    
    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    want_text = include_requested(include, "text_content", "html_content", "text_url")
    resolved_chapter = await resolve_reader_chapter_payload(
        db,
        book=book,
        chapter=chapter,
        chapter_num=chapter_num,
        current_user=current_user,
    )
    if resolved_chapter is None:
        raise HTTPException(404, "Chapter not found")

    if want_text:
        chapter_text_content = resolved_chapter["text_content"]
        if await backfill_character_first_chapters_for_chapter_text(
            db,
            book_id=book_id,
            chapter_number=chapter_num,
            chapter_text=chapter_text_content,
        ):
            await db.commit()

    chars_result = await db.execute(
        select(Character)
        .where(Character.book_id == book_id, Character.first_chapter <= chapter_num)
        .order_by(Character.first_chapter)
    )
    chars = chars_result.scalars().all()

    char_ids = [char.id for char in chars]
    states_by_character: dict[uuid.UUID, CharacterState] = {}
    if char_ids:
        states_result = await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id.in_(char_ids), CharacterState.at_chapter <= chapter_num)
            .order_by(CharacterState.character_id, desc(CharacterState.at_chapter))
        )
        states = states_result.scalars().all()
        for state in states:
            states_by_character.setdefault(state.character_id, state)

    char_data = []
    if include_requested(include, "characters"):
        for char in chars:
            char_state = states_by_character.get(char.id)
            trait_snapshot_raw = cast(dict[str, Any], char_state.trait_snapshot) if char_state else cast(dict[str, Any], char.trait_state or {})
            char_data.append(serialize_reader_character(char, trait_snapshot=dict(trait_snapshot_raw)))

    response = {
        "chapter_number": chapter_num,
        "chapter_title": resolved_chapter["chapter_title"],
        "content_version": resolved_chapter["content_version"],
        "total_chapters": book.total_chapters,
        "intelligence_available": await chapter_intelligence_available(db, book, current_user, chapter_num),
        "analysis_status": resolved_chapter["analysis_status"],
        "source_integrity": resolved_chapter["source_integrity"],
        "can_copy_manuscript": collaboration_can_copy_manuscript(book, collaborator),
    }
    if include_requested(include, "text_url"):
        response["text_url"] = resolved_chapter["text_url"]
    if include_requested(include, "text_content"):
        response["text_content"] = resolved_chapter["text_content"]
    if include_requested(include, "html_content"):
        response["html_content"] = resolved_chapter["html_content"]
    if include_requested(include, "media"):
        response["media"] = resolved_chapter["media"]
    if include_requested(include, "tags"):
        response["tags"] = (
            await get_custom_tags_for_entity(
                db,
                entity_type=ENTITY_TYPE_CHAPTER,
                entity_id=chapter.id,
                book_id=book.id,
            )
            if chapter is not None
            else []
        )
    if include_requested(include, "beta_feedback"):
        response["beta_feedback"] = await list_chapter_beta_feedback(
            db,
            book_id=book.id,
            chapter_number=chapter_num,
            current_user=current_user,
            collaborator=collaborator,
        )
    if include_requested(include, "characters"):
        response["characters"] = char_data

    if fields:
        return apply_sparse_fields(response, fields)
    return response


@router.get("/{book_id}/context")
async def smart_tap(
    book_id: uuid.UUID,
    q: str = Query(..., description="Tapped word or phrase"),
    chapter: int = Query(..., description="Current chapter number"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Smart Tap — the core real-time intelligence endpoint.
    Tap any word → get character context, wiki entry, or relevant passage.
    Always spoiler-gated to current chapter.
    """
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter):
        raise HTTPException(403, "This share does not include that chapter.")
    if collaborator is None:
        require_author_access(current_user)

    # Check if book has embeddings (processing complete)
    chunk_count = await db.scalar(
        select(func.count()).select_from(BookChunk).where(BookChunk.book_id == book_id)
    )
    if chunk_count == 0:
        # Book still processing, return empty results
        return {"type": "search", "results": []}

    char_rows = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book_id, Character.first_chapter <= chapter)
            .order_by(Character.first_chapter, Character.name)
        )
    ).scalars().all()
    needle = q.strip().casefold()
    char = next(
        (
            item
            for item in char_rows
            if needle
            and (
                needle == str(item.name or "").casefold()
                or needle in {str(alias or "").casefold() for alias in (item.aliases or [])}
                or needle in str(item.name or "").casefold()
                or any(needle in str(alias or "").casefold() for alias in (item.aliases or []))
            )
        ),
        None,
    )

    if char:
        states = (
            await db.execute(
                select(CharacterState)
                .where(CharacterState.character_id == char.id, CharacterState.at_chapter <= chapter)
                .order_by(CharacterState.at_chapter)
            )
        ).scalars().all()
        char_state_result = await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == char.id, CharacterState.at_chapter <= chapter)
            .order_by(CharacterState.at_chapter.desc()).limit(1)
        )
        char_state = char_state_result.scalar()
        trait_snapshot_raw = cast(dict[str, Any], char_state.trait_snapshot) if char_state else cast(dict[str, Any], char.trait_state or {})
        trait_snapshot = dict(trait_snapshot_raw)

        rels_result = await db.execute(
            select(CharacterRelationship).where(
                or_(
                    CharacterRelationship.character_a_id == char.id,
                    CharacterRelationship.character_b_id == char.id
                ),
                CharacterRelationship.from_chapter <= chapter,
                or_(
                    CharacterRelationship.to_chapter.is_(None),
                    CharacterRelationship.to_chapter >= chapter
                ),
            )
        )
        rels = rels_result.scalars().all()
        counterpart_ids = {
            rel.character_b_id if rel.character_a_id == char.id else rel.character_a_id
            for rel in rels
        }
        counterparts = (
            await db.execute(select(Character).where(Character.id.in_(counterpart_ids)))
        ).scalars().all() if counterpart_ids else []
        counterpart_names = {item.id: item.name for item in counterparts}
        rel_summaries: dict[str, list[str]] = {}
        rel_keys: dict[str, set[str]] = {}
        for rel in rels:
            counterpart_name = counterpart_names.get(
                rel.character_b_id if rel.character_a_id == char.id else rel.character_a_id
            )
            if not counterpart_name:
                continue
            summary = relationship_summary_for_character(rel, char.name, counterpart_name, char.name)
            if summary:
                label_signature = ":".join(
                    ",".join(str(item) for item in (getattr(rel, field, None) or []))
                    for field in ("shared_labels", "character_a_to_b_labels", "character_b_to_a_labels")
                )
                append_unique_summary(
                    rel_summaries,
                    rel_keys,
                    str(char.id),
                    f"{rel.rel_type}:{rel.from_chapter}:{rel.to_chapter}:{label_signature}:{counterpart_name}".lower(),
                    summary,
                )

        return {
            "type": "character",
            "character": {
                **serialize_reader_character(
                    char,
                    trait_snapshot=trait_snapshot,
                    relationship_summaries=rel_summaries.get(str(char.id), []),
                ),
                "arc_note": char_state.arc_note if char_state else None,
            },
            "relationships": [
                {
                    "with": str(r.character_b_id if r.character_a_id == char.id else r.character_a_id),
                    "type": r.rel_type,
                    "sentiment": r.sentiment,
                    "description": r.description,
                    "shared_labels": list(getattr(r, "shared_labels", None) or []),
                    "character_a_to_b_labels": list(getattr(r, "character_a_to_b_labels", None) or []),
                    "character_b_to_a_labels": list(getattr(r, "character_b_to_a_labels", None) or []),
                    "label_evidence": dict(getattr(r, "label_evidence", None) or {}),
                }
                for r in rels
            ],
            "states": [
                {
                    "at_chapter": state.at_chapter,
                    "trait_state": state.trait_snapshot,
                    "arc_note": state.arc_note,
                    "prompt_delta": state.prompt_delta,
                }
                for state in states
            ],
        }

    results = await find_context_for_tap(db, book_id, q, chapter)
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(BookChunk.book_id == book_id, Chapter.number <= chapter, BookChunk.text.ilike(f"%{lowered}%"))
            .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
        )).all()
        results = [
            build_search_result(text=row[0], chunk_index=row[1], chapter_num=row[2], chapter_title=row[3], relevance=0.5)
            for row in lexical_rows
        ]
    return {"type": "search", "results": results}


@router.get("/{book_id}/summary/{chapter_num}")
async def get_summary(
    book_id: uuid.UUID,
    chapter_num: int,
    mode: str = Query("short", description="short | detailed | key_points"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_summary),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter_num):
        raise HTTPException(403, "This share does not include that chapter.")
    if collaborator is None:
        require_author_access(current_user)

    if mode not in ("short", "detailed", "key_points"):
        raise HTTPException(400, "Invalid mode")
    if not summary_mode_allowed(current_user, mode):
        raise HTTPException(403, "Upgrade to Author to unlock detailed and key-point summaries.")
    
    # Validate book has chapters
    if book.total_chapters is None or book.total_chapters == 0:
        raise HTTPException(400, "This book has no chapters yet.")
    
    # Validate chapter number is in valid range
    if chapter_num < 1 or chapter_num > book.total_chapters:
        raise HTTPException(404, f"Chapter {chapter_num} does not exist.")
    
    await require_summary_access(db, book, current_user, chapter_num)

    read_set = await read_chapter_set(db, current_user.id, book_id)
    if chapter_num not in read_set and not is_local_mode():
        raise HTTPException(403, "Read the chapter first to unlock its summary.")

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    data = await get_or_generate_summary(db, book_id, chapter_num, mode)
    if not data:
        await queue_analysis_if_missing(db, chapter, current_user)
        raise HTTPException(503, "Chapter text not available yet")
    if data.get("status") != "ready":
        await queue_analysis_if_missing(db, chapter, current_user)
        return {
            "status": data.get("status") or "pending",
            "content": None,
            "diagnostics": data.get("diagnostics") or {"analysis_status": chapter_analysis_status(chapter)},
        }

    data = normalize_summary_response(data["content"], data.get("key_events"), data.get("char_changes"), data.get("clues"))
    await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
    return {"status": "ready", **data, "diagnostics": {"analysis_status": chapter_analysis_status(chapter)}}


@router.get("/{book_id}/search")
async def search(
    book_id: uuid.UUID,
    q: str = Query(...),
    chapter: int = Query(..., description="Max chapter to search — spoiler gate"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter):
        raise HTTPException(403, "This share does not include that chapter.")
    if collaborator is None:
        require_author_access(current_user)

    cache_key = key_search_results(f"{current_user.id}:{book_id}", q, chapter)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    results = await semantic_search(
        db,
        book_id,
        q,
        chapter,
        limit=settings.READER_SEARCH_RETURN_CHUNKS,
        candidate_limit=settings.READER_SEARCH_CANDIDATE_CHUNKS,
        similarity_threshold=settings.READER_SEARCH_SIMILARITY_THRESHOLD,
        usage_user_id=current_user.id,
        usage_feature="reader_search",
    )
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(BookChunk.book_id == book_id, Chapter.number <= chapter, BookChunk.text.ilike(f"%{lowered}%"))
            .limit(settings.READER_SEARCH_RETURN_CHUNKS)
        )).all()
        results = [
            build_search_result(text=row[0], chunk_index=row[1], chapter_num=row[2], chapter_title=row[3], relevance=0.5)
            for row in lexical_rows
        ]
    if not results:
        terms = [term for term in q.strip().split() if len(term) >= 3]
        if terms:
            token_filters = [BookChunk.text.ilike(f"%{term}%") for term in terms]
            token_rows = (await db.execute(
                select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
                .join(Chapter, Chapter.id == BookChunk.chapter_id)
                .where(BookChunk.book_id == book_id, Chapter.number <= chapter, or_(*token_filters))
                .limit(settings.READER_SEARCH_RETURN_CHUNKS)
            )).all()
            results = [
                build_search_result(text=row[0], chunk_index=row[1], chapter_num=row[2], chapter_title=row[3], relevance=0.35)
                for row in token_rows
            ]
    await cache_set(cache_key, results, settings.REDIS_TTL_SEARCH)
    return results


@router.get("/{book_id}/chapters")
async def get_chapter_list(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    return await build_chapter_list_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )


@router.get("/{book_id}/summary-collection")
async def get_summary_collection(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is None:
        require_author_access(current_user)
    return await build_summary_collection_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )


@router.get("/{book_id}/thematic-search")
async def thematic_search(
    book_id: uuid.UUID,
    q: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is None:
        require_author_access(current_user)

    read_set = await summary_visible_chapter_set(db, book, current_user, collaborator)
    if collaborator is not None:
        read_set = {chapter for chapter in read_set if collaboration_allows_chapter(collaborator, chapter)}
    if not read_set:
        return {"results": []}

    normalized_query = q.strip().lower()
    terms = [term for term in normalized_query.split() if len(term) >= 3]
    if not terms and normalized_query:
        terms = [normalized_query]
    rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events, ChapterSummary.clues)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)), ChapterSummary.mode.in_(["short", "detailed"]))
        .order_by(Chapter.number)
    )).all()

    results = []
    for chapter_num, chapter_title, content, key_events, clues in rows:
        haystacks = [content or ""]
        haystacks.extend(event.get("event", "") for event in (key_events or []) if isinstance(event, dict))
        haystacks.extend(clue.get("clue", "") for clue in (clues or []) if isinstance(clue, dict))
        haystack_text = " ".join(haystacks).lower()
        score = sum(1 for term in terms if term in haystack_text)
        if not score and normalized_query and normalized_query in haystack_text:
            score = 1
        if score:
            results.append({"chapter_number": chapter_num, "chapter_title": chapter_title,
                             "score": score, "summary": content})
    if not results:
        chapter_rows = (await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)))
            .order_by(Chapter.number)
        )).all()
        for chapter_num, chapter_title, s3_key in chapter_rows:
            if not s3_key:
                continue
            try:
                chapter_text = download_book(s3_key).decode("utf-8", errors="ignore")
            except Exception:
                continue
            normalized_text = chapter_text.lower()
            score = sum(1 for term in terms if term in normalized_text)
            if not score and normalized_query and normalized_query in normalized_text:
                score = 1
            if not score:
                continue
            results.append({"chapter_number": chapter_num, "chapter_title": chapter_title,
                             "score": score, "summary": chapter_text[:320] + ("..." if len(chapter_text) > 320 else "")})
    results.sort(key=lambda item: (-item["score"], item["chapter_number"]))
    return {"results": results[:20]}


@router.post("/{book_id}/quotes")
async def save_quote(
    book_id: uuid.UUID,
    body: SaveQuoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)
    quote_text = _clean_text(body.quote_text)
    if not quote_text:
        raise HTTPException(400, "Quote text is required")
    character_name = _clean_text(body.character_name) or None
    note_text = _clean_text(body.note) or None

    quote = QuoteEntry(user_id=current_user.id, book_id=book_id, chapter_number=body.chapter_number,
                       character_name=character_name, quote_text=quote_text, note=note_text)
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return {"id": str(quote.id), "saved": True}
