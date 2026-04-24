from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Maximum characters accepted for any single LLM input field.
# Prevents cost-amplification: a bad actor sending 100k-char messages
# would otherwise burn ~$1 k/day in OpenAI credits per account.
MAX_MESSAGE_CHARS = 8_000
MAX_PASSAGE_CHARS = 12_000


class AdvisorMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=MAX_MESSAGE_CHARS)


class AdvisorRequest(BaseModel):
    messages: list[AdvisorMessage] = Field(..., max_length=20)
    total_chapters: int = Field(default=9999, ge=1, le=9999)


class SuggestionDismiss(BaseModel):
    suggestion_id: str
    intentional: bool = False


class EditorialReviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PASSAGE_CHARS)
    chapter_num: int | None = Field(default=None, ge=1)


class VoiceConsistencyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PASSAGE_CHARS)
    chapter_num: int | None = Field(default=None, ge=1)
