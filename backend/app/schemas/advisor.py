from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AdvisorMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AdvisorRequest(BaseModel):
    messages: list[AdvisorMessage]
    total_chapters: int = 9999


class SuggestionDismiss(BaseModel):
    suggestion_id: str
    intentional: bool = False


class EditorialReviewRequest(BaseModel):
    text: str
    chapter_num: int | None = None


class VoiceConsistencyRequest(BaseModel):
    text: str
    chapter_num: int | None = None
