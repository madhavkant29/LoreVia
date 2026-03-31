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
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import BookChunk, ChapterSummary

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

    system = (
        f'You answer questions about "{book.title}" using only the provided material.\n'
        f'The reader has completed up to chapter {body.current_chapter}.\n'
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

    reply = await chat_as_character(
        character=char,
        book_title=book.title,
        current_chapter=body.current_chapter,
        context_summary=body.context_summary,
        messages=body.messages,
    )
    return {"reply": reply, "character": char.name}
