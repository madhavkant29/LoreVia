"""
Reader routes — the core intelligence surface.
Smart tap, summaries, relationship graph, memory recall, progress.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_chapter_summary, key_relationship_graph, key_memory_recall, key_search_results
from app.core.config import effective_tier, settings
from app.core.storage import download_book, get_presigned_url
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import BookChunk, ChapterSummary, CharacterRelationship, PlotThread, QuoteEntry
from app.models.progress import ReadingProgress, ReadingSession
from app.engine.search.semantic import find_context_for_tap, semantic_search
from app.engine.analysis.recall import generate_recall
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.profile_builder import build_description
from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_search, rate_limit_summary
from datetime import datetime, timezone
import json
import uuid

router = APIRouter()


class SaveQuoteBody(BaseModel):
    quote_text: str
    chapter_number: int | None = None
    character_name: str | None = None
    note: str | None = None


@router.get("/{book_id}/chapter/{chapter_num}")
async def get_chapter(
    book_id: uuid.UUID,
    chapter_num: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Returns chapter text URL + all characters introduced up to this chapter."""
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    await consolidate_characters(db, book_id, up_to_chapter=chapter_num)

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    if not await _chapter_intelligence_available(db, book, current_user, chapter_num):
        raise HTTPException(402, "Chapter intelligence is unavailable on the Starter plan beyond your processed reading capacity. You can still open the chapter, but summaries and advanced tools stop here.")

    chars = (await db.execute(
        select(Character)
        .where(Character.book_id == book_id, Character.first_chapter <= chapter_num)
        .order_by(Character.first_chapter)
    )).scalars().all()

    char_data = []
    for char in chars:
        state = (await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == char.id, CharacterState.at_chapter <= chapter_num)
            .order_by(CharacterState.at_chapter.desc()).limit(1)
        )).scalar()

        char_data.append({
            "id": str(char.id),
            "name": char.name,
            "aliases": char.aliases or [],
            "role": char.role,
            "first_chapter": char.first_chapter,
            "trait_state": state.trait_snapshot if state else char.trait_state,
            "description": build_description(state.trait_snapshot if state else (char.trait_state or {}), char.archetype),
            "personality_tags": char.personality_tags or [],
            "motivations": char.motivations or [],
        })

    return {
        "chapter_number": chapter_num,
        "chapter_title": chapter.title,
        "text_url": get_presigned_url(chapter.s3_key) if chapter.s3_key else None,
        "text_content": download_book(chapter.s3_key).decode("utf-8", errors="ignore") if chapter.s3_key and not get_presigned_url(chapter.s3_key) else None,
        "characters": char_data,
    }


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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await consolidate_characters(db, book_id, up_to_chapter=chapter)

    # 1. Exact character name match
    char = (await db.execute(
        select(Character).where(Character.book_id == book_id, Character.name.ilike(f"%{q}%"), Character.first_chapter <= chapter)
    )).scalar()

    if char:
        state = (await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == char.id, CharacterState.at_chapter <= chapter)
            .order_by(CharacterState.at_chapter.desc()).limit(1)
        )).scalar()

        rels = (await db.execute(
            select(CharacterRelationship).where(
                (CharacterRelationship.character_a_id == char.id) | (CharacterRelationship.character_b_id == char.id),
                CharacterRelationship.from_chapter <= chapter,
                (CharacterRelationship.to_chapter == None) | (CharacterRelationship.to_chapter >= chapter),
            )
        )).scalars().all()

        return {
            "type": "character",
            "character": {
                "id": str(char.id),
                "name": char.name,
                "aliases": char.aliases or [],
                "role": char.role,
                "trait_state": state.trait_snapshot if state else char.trait_state,
                "description": build_description(state.trait_snapshot if state else (char.trait_state or {}), char.archetype),
                "personality_tags": char.personality_tags or [],
                "motivations": char.motivations or [],
                "fears": char.fears or [],
                "arc_note": state.arc_note if state else None,
                "first_chapter": char.first_chapter,
            },
            "relationships": [
                {
                    "with": str(r.character_b_id if r.character_a_id == char.id else r.character_a_id),
                    "type": r.rel_type,
                    "sentiment": r.sentiment,
                    "description": r.description,
                }
                for r in rels
            ],
        }

    # 2. Semantic search fallback
    results = await find_context_for_tap(db, book_id, q, chapter)
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(
                BookChunk.book_id == book_id,
                Chapter.number <= chapter,
                BookChunk.text.ilike(f"%{lowered}%"),
            )
            .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
        )).all()

        results = [
            {
                "text": row[0][:300] + ("..." if len(row[0]) > 300 else ""),
                "chunk_index": row[1],
                "chapter_num": row[2],
                "chapter_title": row[3],
                "relevance": 0.5,
            }
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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    _require_summary_access(book, current_user, chapter_num)

    if mode not in ("short", "detailed", "key_points"):
        raise HTTPException(400, "Invalid mode")

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    # Try Redis cache
    cached = await cache_get(key_chapter_summary(str(chapter.id), mode))
    if cached:
        return cached

    # Try DB
    summary = (await db.execute(
        select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id, ChapterSummary.mode == mode)
    )).scalar()

    if summary:
        data = _normalize_summary_response(summary.content, summary.key_events, summary.char_changes, summary.clues)
        await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
        return data

    await _queue_analysis_if_missing(db, chapter)

    return {
        "content": "Summary is being prepared. Please retry in a few moments.",
        "key_events": [],
        "char_changes": [],
        "clues": [],
        "pending": True,
    }

    # Generate on demand (fallback — normally pre-generated by worker)
    from app.engine.analysis.summariser import generate_summary
    from app.core.storage import download_book
    try:
        raw = download_book(chapter.s3_key)
        chapter_text = raw.decode("utf-8", errors="ignore")
    except Exception:
        raise HTTPException(503, "Chapter text not available yet")

    data = await generate_summary(chapter_text, mode, chapter.title or "")
    row = ChapterSummary(chapter_id=chapter.id, mode=mode, content=data["content"],
                          key_events=data.get("key_events"), char_changes=data.get("char_changes"),
                          clues=data.get("clues"))
    db.add(row)
    await db.commit()
    await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
    return data


@router.get("/{book_id}/relationships")
async def get_relationships(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await consolidate_characters(db, book_id, up_to_chapter=chapter)

    cached = await cache_get(key_relationship_graph(str(book_id), chapter))
    if cached:
        return cached

    chars = (await db.execute(
        select(Character).where(Character.book_id == book_id, Character.first_chapter <= chapter)
    )).scalars().all()

    rels = (await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
            (CharacterRelationship.to_chapter == None) | (CharacterRelationship.to_chapter >= chapter),
        )
    )).scalars().all()

    graph = {
        "nodes": [{"id": str(c.id), "name": c.name, "role": c.role, "first_chapter": c.first_chapter} for c in chars],
        "edges": [{"source": str(r.character_a_id), "target": str(r.character_b_id),
                   "type": r.rel_type, "sentiment": r.sentiment, "description": r.description} for r in rels],
    }
    if graph["nodes"] or graph["edges"]:
        await cache_set(key_relationship_graph(str(book_id), chapter), graph, settings.REDIS_TTL_GRAPH)
    return graph


@router.get("/{book_id}/search")
async def search(
    book_id: uuid.UUID,
    q: str = Query(...),
    chapter: int = Query(..., description="Max chapter to search — spoiler gate"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    cache_key = key_search_results(str(book_id), q, chapter)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    results = await semantic_search(db, book_id, q, chapter)
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(
                BookChunk.book_id == book_id,
                Chapter.number <= chapter,
                BookChunk.text.ilike(f"%{lowered}%"),
            )
            .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
        )).all()

        results = [
            {
                "text": row[0][:300] + ("..." if len(row[0]) > 300 else ""),
                "chunk_index": row[1],
                "chapter_num": row[2],
                "chapter_title": row[3],
                "relevance": 0.5,
            }
            for row in lexical_rows
        ]
    if not results:
        terms = [term for term in q.strip().split() if len(term) >= 3]
        if terms:
            token_filters = [BookChunk.text.ilike(f"%{term}%") for term in terms]
            token_rows = (await db.execute(
                select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
                .join(Chapter, Chapter.id == BookChunk.chapter_id)
                .where(
                    BookChunk.book_id == book_id,
                    Chapter.number <= chapter,
                    or_(*token_filters),
                )
                .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
            )).all()

            results = [
                {
                    "text": row[0][:300] + ("..." if len(row[0]) > 300 else ""),
                    "chunk_index": row[1],
                    "chapter_num": row[2],
                    "chapter_title": row[3],
                    "relevance": 0.35,
                }
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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()
    read_upto = progress.current_chapter if progress else 0
    read_set = set(progress.chapters_read or []) if progress else set()

    chapters = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number)
    )).scalars().all()
    intelligence_map = await _chapter_intelligence_map(db, book, current_user)

    return {
        "read_upto": read_upto,
        "current_chapter": read_upto,
        "chapters": [
            {
                "number": chapter.number,
                "title": chapter.title,
                "processed": chapter.processed,
                "intelligence_available": intelligence_map.get(chapter.number, True),
                "read": chapter.number in read_set,
            }
            for chapter in chapters
        ],
    }


@router.get("/{book_id}/summary-collection")
async def get_summary_collection(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()
    read_upto = progress.current_chapter if progress else 0
    read_set = set(progress.chapters_read or []) if progress else set()
    available_set = await _read_available_chapter_set(db, book, current_user, read_set)

    if not available_set:
        return {"read_upto": 0, "summaries": []}

    chapter_rows = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(available_set)))
        .order_by(Chapter.number)
    )).all()

    summary_rows = (await db.execute(
        select(ChapterSummary.chapter_id, ChapterSummary.content, ChapterSummary.key_events)
        .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(available_set)),
            ChapterSummary.mode == "short",
        )
    )).all()
    summary_by_chapter_id = {
        str(row[0]): {"content": row[1], "key_events": row[2] or []}
        for row in summary_rows
    }

    return {
        "read_upto": read_upto,
        "summaries": [
            {
                "chapter_number": row[0],
                "chapter_title": row[1],
                "read": True,
                "available": str(row[2]) in summary_by_chapter_id,
                "content": summary_by_chapter_id.get(str(row[2]), {}).get("content"),
                "key_events": summary_by_chapter_id.get(str(row[2]), {}).get("key_events", []),
            }
            for row in chapter_rows
        ],
    }


@router.get("/{book_id}/foreshadowing")
async def get_foreshadowing_highlights(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await _read_available_chapter_set(db, book, current_user, await _read_chapter_set(db, current_user.id, book_id))
    if not read_set:
        return {"items": []}

    rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.clues)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(read_set)),
            ChapterSummary.mode == "detailed",
        )
        .order_by(Chapter.number)
    )).all()

    items = []
    for number, title, clues in rows:
        for clue in clues or []:
            if isinstance(clue, dict) and clue.get("clue"):
                items.append({
                    "chapter_number": number,
                    "chapter_title": title,
                    "clue": clue.get("clue"),
                    "foreshadows": clue.get("foreshadows"),
                })
    return {"items": items}


@router.get("/{book_id}/timeline")
async def get_timeline(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await _read_available_chapter_set(db, book, current_user, await _read_chapter_set(db, current_user.id, book_id))
    if not read_set:
        return {"events": []}

    summary_rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.key_events)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(read_set)),
            ChapterSummary.mode == "short",
        )
        .order_by(Chapter.number)
    )).all()
    character_rows = (await db.execute(
        select(Character.name, Character.first_chapter)
        .where(Character.book_id == book_id, Character.first_chapter.in_(sorted(read_set)))
        .order_by(Character.first_chapter, Character.name)
    )).all()
    thread_rows = (await db.execute(
        select(PlotThread.title, PlotThread.introduced_at, PlotThread.resolved_at, PlotThread.status)
        .where(PlotThread.book_id == book_id)
        .order_by(PlotThread.introduced_at, PlotThread.importance.desc())
    )).all()

    events = []
    for chapter_num, chapter_title, key_events in summary_rows:
        for event in key_events or []:
            if isinstance(event, dict) and event.get("event"):
                events.append({
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title,
                    "kind": "event",
                    "title": event.get("event"),
                    "detail": None,
                })
    for name, first_chapter in character_rows:
        events.append({
            "chapter_number": first_chapter,
            "chapter_title": None,
            "kind": "character_entry",
            "title": name,
            "detail": "Character enters the story",
        })
    for title, introduced_at, resolved_at, status in thread_rows:
        if introduced_at and introduced_at in read_set:
            events.append({
                "chapter_number": introduced_at,
                "chapter_title": None,
                "kind": "thread_start",
                "title": title,
                "detail": status,
            })
        if resolved_at and resolved_at in read_set:
            events.append({
                "chapter_number": resolved_at,
                "chapter_title": None,
                "kind": "thread_end",
                "title": title,
                "detail": "Resolved",
            })

    events.sort(key=lambda item: (item["chapter_number"], item["kind"], item["title"]))
    return {"events": events}


@router.get("/{book_id}/thematic-search")
async def thematic_search(
    book_id: uuid.UUID,
    q: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await _read_available_chapter_set(db, book, current_user, await _read_chapter_set(db, current_user.id, book_id))
    if not read_set:
        return {"results": []}

    terms = [term for term in q.lower().split() if len(term) >= 3]
    rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events, ChapterSummary.clues)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(read_set)),
            ChapterSummary.mode.in_(["short", "detailed"]),
        )
        .order_by(Chapter.number)
    )).all()

    results = []
    for chapter_num, chapter_title, content, key_events, clues in rows:
        haystacks = [content or ""]
        haystacks.extend(event.get("event", "") for event in (key_events or []) if isinstance(event, dict))
        haystacks.extend(clue.get("clue", "") for clue in (clues or []) if isinstance(clue, dict))
        haystack_text = " ".join(haystacks).lower()
        score = sum(1 for term in terms if term in haystack_text)
        if score:
            results.append({
                "chapter_number": chapter_num,
                "chapter_title": chapter_title,
                "score": score,
                "summary": content,
            })
    results.sort(key=lambda item: (-item["score"], item["chapter_number"]))
    return {"results": results[:20]}


@router.get("/{book_id}/relationship-evolution")
async def get_relationship_evolution(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    rels = (await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
        ).order_by(CharacterRelationship.from_chapter, CharacterRelationship.character_a_id, CharacterRelationship.character_b_id)
    )).scalars().all()

    chars = (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    name_by_id = {char.id: char.name for char in chars}

    grouped: dict[tuple[str, str], list[dict]] = {}
    for rel in rels:
        a_name = name_by_id.get(rel.character_a_id)
        b_name = name_by_id.get(rel.character_b_id)
        if not a_name or not b_name:
            continue
        key = tuple(sorted([a_name, b_name]))
        grouped.setdefault(key, []).append({
            "chapter": rel.from_chapter,
            "type": rel.rel_type,
            "description": rel.description,
            "sentiment": rel.sentiment,
        })

    return {
        "pairs": [
            {
                "characters": list(key),
                "events": value,
            }
            for key, value in grouped.items()
        ]
    }


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
    quote_text = " ".join((body.quote_text or "").split())
    if not quote_text:
        raise HTTPException(400, "Quote text is required")

    quote = QuoteEntry(
        user_id=current_user.id,
        book_id=book_id,
        chapter_number=body.chapter_number,
        character_name=body.character_name,
        quote_text=quote_text,
        note=body.note,
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return {"id": str(quote.id), "saved": True}


@router.get("/{book_id}/plot-threads")
async def get_plot_threads(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    threads = (await db.execute(
        select(PlotThread).where(
            PlotThread.book_id == book_id,
            PlotThread.introduced_at <= chapter,
        ).order_by(PlotThread.importance.desc())
    )).scalars().all()

    return [{"id": str(t.id), "title": t.title, "type": t.thread_type, "status": t.status,
             "description": t.description, "introduced_at": t.introduced_at,
             "resolved_at": t.resolved_at, "importance": t.importance} for t in threads]


@router.get("/{book_id}/recall")
async def memory_recall(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    cache_key = key_memory_recall(str(current_user.id), str(book_id))
    cached = await cache_get(cache_key)
    if cached:
        return {"recall": cached, "cached": True}

    # Get reading progress
    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
        )
    )).scalar()
    if not progress:
        return {"recall": None}

    last_chapter = progress.current_chapter

    # Get most recent summary as context
    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == last_chapter)
    )).scalar()

    recent_summary = ""
    if chapter:
        summ = (await db.execute(
            select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id, ChapterSummary.mode == "short")
        )).scalar()
        if summ:
            recent_summary = summ.content

    # Active characters
    chars = (await db.execute(
        select(Character.name).where(Character.book_id == book_id, Character.first_chapter <= last_chapter).limit(8)
    )).scalars().all()

    # Open threads
    open_threads = (await db.execute(
        select(PlotThread.title).where(
            PlotThread.book_id == book_id,
            PlotThread.status.in_(["ongoing", "introduced"]),
            PlotThread.introduced_at <= last_chapter,
        ).limit(3)
    )).scalars().all()

    recall_text = await generate_recall(
        title=book.title,
        last_chapter=last_chapter,
        recent_summary=recent_summary,
        active_characters=list(chars),
        open_threads=list(open_threads),
    )

    await cache_set(cache_key, recall_text, settings.REDIS_TTL_RECALL)
    return {"recall": recall_text, "last_chapter": last_chapter}


@router.get("/{book_id}/progress")
async def get_progress(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    p = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()
    return p or {"current_chapter": 1, "scroll_pct": 0.0}


@router.put("/{book_id}/progress")
async def update_progress(
    book_id: uuid.UUID,
    current_chapter: int,
    scroll_pct: float,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    p = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()
    if p:
        read_set = set(p.chapters_read or [])
        read_set.add(current_chapter)
        p.current_chapter = current_chapter
        p.scroll_pct = scroll_pct
        p.chapters_read = sorted(read_set)
        p.last_read = datetime.now(timezone.utc)
    else:
        db.add(ReadingProgress(user_id=current_user.id, book_id=book_id,
                                current_chapter=current_chapter, scroll_pct=scroll_pct, chapters_read=[current_chapter]))
    await db.commit()

    # Trigger lazy processing ahead
    from app.workers.tasks.extraction_tasks import process_chapter_task
    book = await db.get(Book, book_id)
    total = book.total_chapters or 1
    for n in range(current_chapter + 1, min(current_chapter + 4, total + 1)):
        next_chapter = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book_id, Chapter.number == n)
            )
        ).scalar()
        if next_chapter and next_chapter.processed:
            continue
        if not await _chapter_intelligence_available(db, book, current_user, n):
            continue
        process_chapter_task.apply_async(
            args=[str(book_id), n, "", ""],  # text fetched from S3 in consumer
            countdown=n * 3, queue="extraction",
        )
    current_row = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == current_chapter)
        )
    ).scalar()
    if current_row and await _chapter_intelligence_available(db, book, current_user, current_chapter):
        await _queue_analysis_if_missing(db, current_row)
    return {"ok": True}


@router.put("/{book_id}/progress/chapter-status")
async def update_chapter_read_status(
    book_id: uuid.UUID,
    chapter: int,
    read: bool,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()

    if progress is None:
        chapters_read = [chapter] if read else []
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=book_id,
            current_chapter=max(chapter, 1),
            scroll_pct=0.0,
            chapters_read=chapters_read,
        )
        db.add(progress)
    else:
        read_set = set(progress.chapters_read or [])
        if read:
            read_set.add(chapter)
            progress.current_chapter = max(progress.current_chapter, chapter)
        else:
            read_set.discard(chapter)
        progress.chapters_read = sorted(read_set)
        progress.last_read = datetime.now(timezone.utc)

    await db.commit()
    if read:
        chapter_row = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter)
            )
        ).scalar()
        if chapter_row and await _chapter_intelligence_available(db, book, current_user, chapter):
            await _queue_analysis_if_missing(db, chapter_row)
    return {"ok": True, "chapter": chapter, "read": read}


def _normalize_summary_response(content, key_events, char_changes, clues):
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = _strip_json_fence(stripped)
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and "summary" in parsed:
                return {
                    "content": parsed.get("summary", content),
                    "key_events": parsed.get("key_events") or key_events or [],
                    "char_changes": parsed.get("char_changes") or char_changes or [],
                    "clues": parsed.get("clues") or clues or [],
                }
        except Exception:
            pass

    return {
        "content": content,
        "key_events": key_events or [],
        "char_changes": char_changes or [],
        "clues": clues or [],
    }


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()


def _require_summary_access(book: Book, current_user, chapter_num: int | None = None) -> None:
    if effective_tier(current_user.tier) in ("pro", "power", "admin"):
        return
    if chapter_num is not None and book.is_truncated:
        detail = "This book has reached the Starter plan reading capacity. Upgrade to Pro to unlock more summaries and intelligence views."
        detail = f"Chapter {chapter_num} summary is unavailable because this book has reached the Starter plan reading capacity. Upgrade to Pro to continue."
        raise HTTPException(402, detail)


async def _read_chapter_set(db: AsyncSession, user_id: uuid.UUID, book_id: uuid.UUID) -> set[int]:
    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == user_id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()
    return set(progress.chapters_read or []) if progress else set()


async def _read_available_chapter_set(
    db: AsyncSession,
    book: Book,
    current_user,
    read_set: set[int],
) -> set[int]:
    availability = await _chapter_intelligence_map(db, book, current_user)
    return {chapter for chapter in read_set if availability.get(chapter, False)}


async def _queue_analysis_if_missing(db: AsyncSession, chapter: Chapter) -> None:
    summary_exists = await _chapter_has_any_summary(db, chapter.id)
    if summary_exists:
        return
    from app.workers.tasks.analysis_tasks import analyse_chapter_task

    try:
        chapter_text = download_book(chapter.s3_key).decode("utf-8", errors="ignore")
    except Exception:
        return

    analyse_chapter_task.apply_async(
        args=[str(chapter.id), chapter_text, chapter.title or ""],
        queue="analysis",
    )


async def _chapter_has_any_summary(db: AsyncSession, chapter_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(ChapterSummary.id).where(ChapterSummary.chapter_id == chapter_id).limit(1)
        )
    ).first()
    return row is not None


async def _chapter_intelligence_available(db: AsyncSession, book: Book, current_user, chapter_num: int) -> bool:
    availability = await _chapter_intelligence_map(db, book, current_user)
    return availability.get(chapter_num, False)


async def _chapter_intelligence_map(db: AsyncSession, book: Book, current_user) -> dict[int, bool]:
    if effective_tier(current_user.tier) in ("pro", "power", "admin"):
        rows = (await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )).all()
        return {number: True for (number,) in rows}
    if not book.is_truncated:
        rows = (await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )).all()
        return {number: True for (number,) in rows}
    rows = (await db.execute(
        select(Chapter.number, Chapter.token_count)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.number)
    )).all()
    running_total = 0
    availability: dict[int, bool] = {}
    for number, token_count in rows:
        running_total += token_count or 0
        availability[number] = running_total <= (book.total_tokens or 0)
    return availability
