"""
Grounded intelligence routes: contextual Q&A + character chat.
"""
import uuid
from typing import Any, TypedDict, cast

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_chat
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_grounded_answer
from app.engine.intelligence.character_chat import chat_as_character
from app.engine.search.semantic import semantic_search
from app.models.book import Book, SeriesBook
from app.models.character import Character
from app.models.intelligence import WikiEntry
from app.schemas.intelligence import ChatRequest, GroundedAnswerOut, QARequest
from app.utils.intelligence_utils import build_grounded_qa_context

router = APIRouter()


class CrossBookMatch(TypedDict, total=False):
    left_book_id: str
    left_name: str
    right_book_id: str
    right_name: str
    similarity: float
    entry_type: str | None


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


@router.post("/{book_id}/qa", response_model=GroundedAnswerOut)
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
        cached_payload = cast(dict[str, Any], cached)
        return GroundedAnswerOut(
            answer=str(cached_payload["answer"]),
            citations=list(cached_payload.get("citations") or []),
            cached=True,
        )

    context_blocks, citations = await build_grounded_qa_context(
        db=db,
        book=book,
        user_id=current_user.id,
        question=body.question,
        current_chapter=body.current_chapter,
    )

    system = (
        f'You answer questions about "{book.title}" using only the provided material.\n'
        f'The reader has completed up to chapter {body.current_chapter}.\n'
        "If earlier books in the same series are provided as prior-volume context, you may use them to answer questions about past lore.\n"
        "Rules:\n"
        "- Answer only from text and summaries provided.\n"
        "- Do not predict future events or speculate.\n"
        "- If the answer is not grounded in the provided material, say so plainly.\n"
        "- Keep the response concise but useful.\n"
        "- Prefer 1-3 short sentences.\n"
        "- When grounded, mention the most relevant chapter number directly in the answer.\n"
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
        answer = (response.choices[0].message.content or "").strip()
        payload = {"answer": answer, "citations": citations}
        await cache_set(cache_key, payload, settings.REDIS_TTL_SUMMARY)
        return GroundedAnswerOut(answer=answer, citations=citations)
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

    serialized_messages = [message.model_dump() for message in body.messages]
    last_user_message = next((msg["content"] for msg in reversed(serialized_messages) if msg.get("role") == "user"), "")
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
        messages=serialized_messages,
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
        comparison_books = list(series_book_rows) or [book]

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

    character_matches: list[CrossBookMatch] = []
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

    wiki_matches: list[CrossBookMatch] = []
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
