from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QARequest(BaseModel):
    question: str
    current_chapter: int


class GroundedCitationOut(BaseModel):
    chapter_num: int
    chapter_title: str | None = None
    excerpt: str
    source_type: Literal["summary", "passage"]
    relevance: float | None = None


class GroundedAnswerOut(BaseModel):
    answer: str
    citations: list[GroundedCitationOut] = Field(default_factory=list)
    cached: bool = False
