"""
Grounded intelligence routes: contextual Q&A + character chat.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_chat
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_grounded_answer
from app.engine.intelligence.character_chat import chat_as_character
from app.engine.search.semantic import semantic_search
from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character
from app.models.intelligence import BookChunk, ChapterSummary, CharacterRelationship, PlotThread, WikiEntry

router = APIRouter()


class QARequest(BaseModel):
    question: str
    current_chapter: int


class ChatRequest(BaseModel):
    messages: list[dict]
    current_chapter: int
    context_summary: str = ""


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


@router.post("/{book_id}/qa")
async def qa_endpoint(
    book_id: uuid.UUID,
    body: QARequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_chat),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    cache_key = key_grounded_answer(str(book_id), body.current_chapter, body.question)
    cached = await cache_get(cache_key)
    if cached:
        return {"answer": cached["answer"], "cached": True}

    summary_rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.content)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number <= body.current_chapter,
            ChapterSummary.mode == "short",
        )
        .order_by(Chapter.number.desc())
        .limit(4)
    )).all()
    chunk_rows = (await db.execute(
        select(BookChunk.text, Chapter.number, Chapter.title)
        .join(Chapter, Chapter.id == BookChunk.chapter_id)
        .where(
            BookChunk.book_id == book_id,
            Chapter.number <= body.current_chapter,
        )
        .limit(4)
    )).all()

    context_blocks = []
    for chapter_num, chapter_title, content in reversed(summary_rows):
        context_blocks.append(f"Chapter {chapter_num}: {chapter_title or 'Untitled'}\nSummary: {(content or '')[:500]}")
    for text, chapter_num, chapter_title in chunk_rows[:2]:
        context_blocks.append(f"Passage from Chapter {chapter_num}: {chapter_title or 'Untitled'}\n{text[:420]}")

    series_context = await _build_prior_series_context(db, book, current_user.id)
    if series_context:
        context_blocks = series_context + context_blocks

    system = (
        f'You answer questions about "{book.title}" using only the provided material.\n'
        f'The reader has completed up to chapter {body.current_chapter}.\n'
        "If earlier books in the same series are provided as prior-volume context, you may use them to answer questions about past lore.\n"
        "Rules:\n"
        "- Answer only from text and summaries provided.\n"
        "- Do not predict future events or speculate.\n"
        "- If the answer is not grounded in the provided material, say so plainly.\n"
        "- Keep the response concise but useful.\n"
    )

    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
            temperature=0.2,
            max_tokens=220,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Question: {body.question}\n\nContext:\n\n" + "\n\n".join(context_blocks)},
            ],
        )
        answer = response.choices[0].message.content.strip()
        await cache_set(cache_key, {"answer": answer}, settings.REDIS_TTL_SUMMARY)
        return {"answer": answer}
    finally:
        await client.close()


@router.post("/{book_id}/predict")
async def predict_endpoint(
    book_id: uuid.UUID,
    body: QARequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_chat),
):
    return await qa_endpoint(book_id, body, db, current_user, _)


@router.post("/{book_id}/chat/{character_id}")
async def character_chat(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_chat),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    char = await db.get(Character, character_id)
    if not char or char.book_id != book_id:
        raise HTTPException(404)

    last_user_message = next((msg["content"] for msg in reversed(body.messages) if msg.get("role") == "user"), "")
    semantic_hits = await semantic_search(
        db,
        book_id,
        last_user_message or char.name,
        body.current_chapter,
        limit=2,
    )
    search_context = "\n\n".join(hit["text"][:280] for hit in semantic_hits)

    reply = await chat_as_character(
        character=char,
        book_title=book.title,
        current_chapter=body.current_chapter,
        context_summary=body.context_summary,
        search_context=search_context,
        messages=body.messages,
    )
    grounded_hint = None
    if semantic_hits:
        grounded_hint = f"Grounded in chapter {semantic_hits[0]['chapter_num']} evidence."
    return {"reply": reply, "character": char.name, "grounded_hint": grounded_hint}


@router.get("/{book_id}/cross-book-intelligence")
async def cross_book_intelligence(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    comparison_books = [book]
    if book.primary_series_id:
        series_book_rows = (
            await db.execute(
                select(Book)
                .join(SeriesBook, SeriesBook.book_id == Book.id)
                .where(
                    SeriesBook.series_id == book.primary_series_id,
                    Book.user_id == current_user.id,
                )
            )
        ).scalars().all()
        comparison_books = series_book_rows or [book]

    book_ids = [item.id for item in comparison_books]
    characters = (
        await db.execute(
            select(Character).where(
                Character.book_id.in_(book_ids),
                Character.embedding.is_not(None),
            )
        )
    ).scalars().all()
    wikis = (
        await db.execute(
            select(WikiEntry).where(
                WikiEntry.book_id.in_(book_ids),
                WikiEntry.embedding.is_not(None),
            )
        )
    ).scalars().all()

    character_matches = []
    for idx, left in enumerate(characters):
        for right in characters[idx + 1:]:
            if left.book_id == right.book_id:
                continue
            similarity = _cosine_similarity(left.embedding, right.embedding)
            if similarity < 0.9:
                continue
            character_matches.append({
                "left_book_id": str(left.book_id),
                "left_name": left.name,
                "right_book_id": str(right.book_id),
                "right_name": right.name,
                "similarity": round(similarity, 3),
            })

    wiki_matches = []
    for idx, left in enumerate(wikis):
        for right in wikis[idx + 1:]:
            if left.book_id == right.book_id:
                continue
            similarity = _cosine_similarity(left.embedding, right.embedding)
            if similarity < 0.9:
                continue
            wiki_matches.append({
                "left_book_id": str(left.book_id),
                "left_name": left.name,
                "right_book_id": str(right.book_id),
                "right_name": right.name,
                "similarity": round(similarity, 3),
                "entry_type": left.entry_type or right.entry_type,
            })

    character_matches.sort(key=lambda item: item["similarity"], reverse=True)
    wiki_matches.sort(key=lambda item: item["similarity"], reverse=True)
    return {
        "series_name": book.series_name,
        "comparison_book_ids": [str(item.id) for item in comparison_books],
        "character_matches": character_matches[:20],
        "wiki_matches": wiki_matches[:20],
    }


def _cosine_similarity(left, right) -> float:
    if left is None or right is None:
        return 0.0
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_mag = sum(a * a for a in left) ** 0.5
    right_mag = sum(b * b for b in right) ** 0.5
    if left_mag == 0 or right_mag == 0:
        return 0.0
    similarity = dot / (left_mag * right_mag)
    # Convert to regular Python float to avoid JSON serialization issues
    return float(similarity)


async def _build_prior_series_context(db: AsyncSession, book: Book, user_id: uuid.UUID) -> list[str]:
    if not book.primary_series_id:
        return []

    series_rows = (
        await db.execute(
            select(Book, SeriesBook.position)
            .join(SeriesBook, SeriesBook.book_id == Book.id)
            .where(
                SeriesBook.series_id == book.primary_series_id,
                Book.user_id == user_id,
            )
            .order_by(SeriesBook.position.is_(None), SeriesBook.position, Book.created_at)
        )
    ).all()
    if not series_rows:
        return []

    ordered_books = [row[0] for row in series_rows]
    try:
        current_index = next(index for index, item in enumerate(ordered_books) if item.id == book.id)
    except StopIteration:
        return []

    previous_books = ordered_books[:current_index]
    if not previous_books:
        return []

    context_blocks: list[str] = []
    for prior_book in previous_books[-3:]:
        snapshot = await _book_series_snapshot(db, prior_book.id, prior_book.title)
        if snapshot:
            context_blocks.append(snapshot)
    return context_blocks


async def _book_series_snapshot(db: AsyncSession, book_id: uuid.UUID, title: str) -> str | None:
    summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "short",
            )
            .order_by(Chapter.number.desc())
            .limit(3)
        )
    ).all()
    character_rows = (
        await db.execute(
            select(Character.name, Character.role, Character.arc_summary)
            .where(Character.book_id == book_id)
            .order_by(Character.first_chapter, Character.name)
            .limit(8)
        )
    ).all()
    relationship_rows = (
        await db.execute(
            select(CharacterRelationship.rel_type, CharacterRelationship.description)
            .where(CharacterRelationship.book_id == book_id)
            .order_by(CharacterRelationship.from_chapter.desc())
            .limit(6)
        )
    ).all()
    thread_rows = (
        await db.execute(
            select(PlotThread.title, PlotThread.description, PlotThread.status)
            .where(PlotThread.book_id == book_id)
            .order_by(PlotThread.importance.desc(), PlotThread.created_at.desc())
            .limit(5)
        )
    ).all()

    blocks: list[str] = [f"Previous volume context: {title}"]

    if summary_rows:
        summary_lines = []
        for chapter_num, chapter_title, content, key_events in reversed(summary_rows):
            summary_lines.append(
                f"Chapter {chapter_num} ({chapter_title or 'Untitled'}): {(content or '')[:320]}"
            )
            event_line = _flatten_key_events(key_events)
            if event_line:
                summary_lines.append(f"Key events: {event_line}")
        blocks.append("Story so far:\n" + "\n".join(summary_lines[:6]))

    if character_rows:
        cast = [
            f"{name}{f' ({role})' if role else ''}: {(arc_summary or 'role in progress')[:140]}"
            for name, role, arc_summary in character_rows
            if name
        ]
        if cast:
            blocks.append("Core cast:\n" + "\n".join(cast[:6]))

    if relationship_rows:
        relationship_lines = []
        for rel_type, description in relationship_rows:
            fallback = (rel_type or "connection").replace("_", " ")
            text = (description or fallback).strip()
            if text:
                relationship_lines.append(text[:180])
        if relationship_lines:
            blocks.append("Known relationships:\n" + "\n".join(relationship_lines[:4]))

    if thread_rows:
        thread_lines = []
        for thread_title, description, status in thread_rows:
            thread_lines.append(
                f"{thread_title} [{status or 'unknown'}]: {(description or 'No detail yet.')[:180]}"
            )
        if thread_lines:
            blocks.append("Major plot threads:\n" + "\n".join(thread_lines[:4]))

    if len(blocks) == 1:
        return None
    return "\n\n".join(blocks)


def _flatten_key_events(key_events: object) -> str:
    if isinstance(key_events, list):
        items = [str(item).strip() for item in key_events if str(item).strip()]
        return "; ".join(items[:4])
    if isinstance(key_events, dict):
        flattened: list[str] = []
        for value in key_events.values():
            if isinstance(value, list):
                flattened.extend(str(item).strip() for item in value if str(item).strip())
            elif value:
                flattened.append(str(value).strip())
        return "; ".join(flattened[:4])
    return ""
