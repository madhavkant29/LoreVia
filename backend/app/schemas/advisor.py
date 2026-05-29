from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Maximum characters accepted for any single LLM input field.
# Prevents cost-amplification: a bad actor sending 100k-char messages
# would otherwise burn ~$1 k/day in OpenAI credits per account.
MAX_MESSAGE_CHARS = 8_000
MAX_PASSAGE_CHARS = 12_000
MIN_WHATS_THE_WORD_DESCRIPTION_WORDS = 5


def _word_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", value))


class AdvisorMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=MAX_MESSAGE_CHARS)


class AdvisorRequest(BaseModel):
    messages: list[AdvisorMessage] = Field(..., max_length=20)
    total_chapters: int = Field(default=9999, ge=1, le=9999)


class AdvisorAsyncAccepted(BaseModel):
    task_id: str
    status: Literal["queued"]
    cached: bool = False


class AdvisorTaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "complete", "failed"]
    result: dict | None = None
    error: str | None = None


class SuggestionDismiss(BaseModel):
    suggestion_id: str
    intentional: bool = False


class AdvisorSuggestionOut(BaseModel):
    id: str
    type: str
    severity: str
    title: str
    description: str
    chapter_ref: int | None = None
    action_label: str
    ask_prompt: str
    source: str | None = None


class AdvisorScanMeta(BaseModel):
    character_count: int = 0
    state_count: int = 0
    open_thread_count: int = 0
    clue_count: int = 0
    relationship_count: int = 0
    world_element_count: int = 0
    heuristic_count: int = 0
    fallback_applied: bool = False
    proactive_audit_applied: bool = False
    scan_basis: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    audit_summary: str | None = None


class AdvisorSuggestionsResponse(BaseModel):
    suggestions: list[AdvisorSuggestionOut] = Field(default_factory=list)
    total: int
    book_title: str
    meta: AdvisorScanMeta
    cached: bool = False


class AdvisorSuggestionScanResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    cached: bool = False


class AdvisorSuggestionJobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "complete", "failed"]
    result: AdvisorSuggestionsResponse | None = None
    error: str | None = None


class EditorialReviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PASSAGE_CHARS)
    chapter_num: int | None = Field(default=None, ge=1)


class VoiceConsistencyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PASSAGE_CHARS)
    chapter_num: int | None = Field(default=None, ge=1)
    character_id: uuid.UUID | None = None


class ProseTightenRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4_000)
    chapter_num: int | None = Field(default=None, ge=1)


class InlineContinuityRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PASSAGE_CHARS)
    chapter_num: int | None = Field(default=None, ge=1)


class WhatsTheWordRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=600)
    previous_word: str | None = Field(default=None, max_length=80)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if _word_count(cleaned) < MIN_WHATS_THE_WORD_DESCRIPTION_WORDS:
            raise ValueError(f"Please describe it in at least {MIN_WHATS_THE_WORD_DESCRIPTION_WORDS} words.")
        return cleaned

    @field_validator("previous_word")
    @classmethod
    def validate_previous_word(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None


class WhatsTheWordResponse(BaseModel):
    word: str
    gloss: str


class ProseTightenResponse(BaseModel):
    tightened_text: str
    rationale: list[str] = Field(default_factory=list)
    changed: bool = True


class InlineContinuityIssueOut(BaseModel):
    severity: str
    title: str
    snippet: str
    explanation: str
    suggestion: str


class InlineContinuityResponse(BaseModel):
    issues: list[InlineContinuityIssueOut] = Field(default_factory=list)
    memory_bank: list[str] = Field(default_factory=list)
    overall_verdict: str


class SynopsisResponse(BaseModel):
    spoiler_level: str
    synopsis: str
    focus_points: list[str] = Field(default_factory=list)
    coverage_chapters: list[int] = Field(default_factory=list)
    cached: bool = False
