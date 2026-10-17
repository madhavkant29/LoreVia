from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_api, rate_limit_support
from app.core.config import settings
from app.core.database import get_db
from app.schemas.support import (
    SupportAnswerOut,
    SupportChatRequest,
    SupportConfigOut,
    SupportIncidentCreateBody,
    SupportIncidentOut,
)
from app.services.support_retrieval_service import (
    answer_support_question_ai,
    load_support_corpus,
    support_guide_summaries,
)
from app.services.support_service import (
    create_user_support_incident,
    get_user_support_incident,
)

router = APIRouter(dependencies=[Depends(rate_limit_api)])


@router.get("/config", response_model=SupportConfigOut)
async def get_support_config(current_user=Depends(get_current_user)):
    _ = current_user
    corpus_version, _articles = load_support_corpus()
    return SupportConfigOut(
        assistant_enabled=settings.SUPPORT_ASSISTANT_ENABLED,
        corpus_version=corpus_version,
    )


@router.get("/guides")
async def list_support_guides(current_user=Depends(get_current_user)):
    _ = current_user
    return {"guides": support_guide_summaries()}


@router.post("/chat-stream", dependencies=[Depends(rate_limit_support)])
async def support_chat_stream(
    body: SupportChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    answer = await answer_support_question_ai(
        db,
        message=body.message,
        context=body.context,
        current_user=current_user,
        recent_messages=body.recent_messages,
    )

    async def events():
        yield f"event: stage\ndata: {json.dumps({'stage': 'searching_support_guides'})}\n\n"
        yield f"event: answer\ndata: {answer.model_dump_json()}\n\n"
        yield f"event: done\ndata: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post(
    "/chat",
    response_model=SupportAnswerOut,
    dependencies=[Depends(rate_limit_support)],
)
async def support_chat(
    body: SupportChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await answer_support_question_ai(
        db,
        message=body.message,
        context=body.context,
        current_user=current_user,
        recent_messages=body.recent_messages,
    )


@router.post(
    "/incidents",
    response_model=SupportIncidentOut,
    dependencies=[Depends(rate_limit_support)],
)
async def create_support_incident(
    body: SupportIncidentCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await create_user_support_incident(db, current_user=current_user, body=body)


@router.get("/incidents/{incident_id}", response_model=SupportIncidentOut)
async def get_support_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await get_user_support_incident(
        db,
        current_user=current_user,
        incident_id=incident_id,
    )
