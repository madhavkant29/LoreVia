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


class CrossBookMatchOut(BaseModel):
    left_book_id: str
    left_name: str
    right_book_id: str
    right_name: str
    similarity: float
    entry_type: str | None = None


class CrossBookIntelligenceOut(BaseModel):
    series_name: str | None = None
    comparison_book_ids: list[str]
    character_matches: list[CrossBookMatchOut]
    wiki_matches: list[CrossBookMatchOut]
    cached: bool = False
