"""
Phase 3 intelligence routes: predictions + character chat.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.character import Character
from app.models.book import Book
from app.engine.intelligence.predictor import predict
from app.engine.intelligence.character_chat import chat_as_character
from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_chat
from app.api.deps.subscription import require_power
from pydantic import BaseModel
import uuid

router = APIRouter()


class PredictRequest(BaseModel):
    question: str
    current_chapter: int


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user"/"assistant", "content": "..."}]
    current_chapter: int
    context_summary: str = ""


@router.post("/{book_id}/predict")
async def predict_endpoint(
    book_id: uuid.UUID,
    body: PredictRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_power),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    theories = await predict(db, book_id, body.question, body.current_chapter)
    return {"theories": theories}


@router.post("/{book_id}/chat/{character_id}")
async def character_chat(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_chat),
    __=Depends(require_power),
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
