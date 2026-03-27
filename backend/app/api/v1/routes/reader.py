"""
Reader routes — the core intelligence surface.
Smart tap, summaries, relationship graph, memory recall, progress.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_chapter_summary, key_relationship_graph, key_memory_recall, key_search_results
from app.core.config import settings
from app.core.storage import get_presigned_url
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread
from app.models.progress import ReadingProgress, ReadingSession
from app.engine.search.semantic import find_context_for_tap, semantic_search
from app.engine.analysis.recall import generate_recall
from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_search, rate_limit_summary
from datetime import datetime, timezone
import uuid

router = APIRouter()


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

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

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
        data = {"content": summary.content, "key_events": summary.key_events,
                "char_changes": summary.char_changes, "clues": summary.clues}
        await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
        return data

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
    await cache_set(cache_key, results, settings.REDIS_TTL_SEARCH)
    return results


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
        p.current_chapter = current_chapter
        p.scroll_pct = scroll_pct
        p.last_read = datetime.now(timezone.utc)
    else:
        db.add(ReadingProgress(user_id=current_user.id, book_id=book_id,
                                current_chapter=current_chapter, scroll_pct=scroll_pct))
    await db.commit()

    # Trigger lazy processing ahead
    from app.workers.tasks.extraction_tasks import process_chapter_task
    book = await db.get(Book, book_id)
    total = book.total_chapters or 1
    for n in range(current_chapter + 1, min(current_chapter + 4, total + 1)):
        process_chapter_task.apply_async(
            args=[str(book_id), n, "", ""],  # text fetched from S3 in consumer
            countdown=n * 3, queue="extraction",
        )
    return {"ok": True}
