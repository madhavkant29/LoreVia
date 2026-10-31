from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
    total_chapters: int | None = Field(default=None, ge=0)


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
    evidence_excerpt: str | None = None
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
    audit_failure_category: str | None = None
    audit_groups_total: int = 0
    audit_groups_completed: int = 0


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


class AdvisorSuggestionScanProgress(BaseModel):
    completed: int = Field(ge=0)
    total: int = Field(ge=0)


class AdvisorSuggestionJobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "complete", "failed"]
    result: AdvisorSuggestionsResponse | None = None
    progress: AdvisorSuggestionScanProgress | None = None
    error: str | None = None


class EditorialReviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PASSAGE_CHARS)
    chapter_num: int | None = Field(default=None, ge=1)


class VoiceConsistencyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PASSAGE_CHARS)
    chapter_num: int | None = Field(default=None, ge=1)
    character_id: uuid.UUID | None = None
    scene_context: str | None = Field(default=None, max_length=500)
    voice_mode: Literal["dialogue", "first_person_narration"] = "dialogue"


class VoiceChapterReviewRequest(BaseModel):
    chapter_number: int = Field(ge=1)
    retry_paused: bool = False


class VoiceChapterReviewJobResponse(BaseModel):
    job_id: uuid.UUID
    status: Literal["queued", "running", "paused", "complete", "failed"]
    chapter_number: int
    progress: dict[str, int]
    next_resume_at: str | None = None
    result: dict | None = None
    error: str | None = None


class VoiceReviewDecisionRequest(BaseModel):
    decision: Literal["intentional", "incorrect", "resolved"]
    note: str | None = Field(default=None, max_length=500)


class VoiceReviewDecisionResponse(BaseModel):
    finding_key: str
    decision: Literal["intentional", "incorrect", "resolved"]
    note: str | None = None


BetaReaderScope = Literal["passage", "chapter", "chapter_range", "full_book"]
BetaReaderCheck = Literal["repetition", "voice", "reader_feedback"]


class BetaReaderAnalysisRequest(BaseModel):
    scope: BetaReaderScope
    text: str | None = Field(default=None, max_length=MAX_PASSAGE_CHARS)
    chapter_number: int | None = Field(default=None, ge=1)
    chapter_start: int | None = Field(default=None, ge=1)
    chapter_end: int | None = Field(default=None, ge=1)
    character_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    checks: list[BetaReaderCheck] = Field(
        default_factory=lambda: ["repetition", "voice", "reader_feedback"],
        min_length=1,
        max_length=3,
    )

    @field_validator("checks")
    @classmethod
    def validate_checks(cls, value: list[BetaReaderCheck]) -> list[BetaReaderCheck]:
        if len(set(value)) != len(value):
            raise ValueError("Checks must be unique.")
        return value

    @field_validator("character_ids")
    @classmethod
    def validate_character_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_scope_fields(self) -> BetaReaderAnalysisRequest:
        cleaned_text = (self.text or "").strip()
        if self.scope == "passage":
            if not cleaned_text:
                raise ValueError("Passage text is required for passage scope.")
            if self.chapter_start is not None or self.chapter_end is not None:
                raise ValueError("Passage scope does not accept a chapter range.")
            self.text = cleaned_text
        elif self.scope == "chapter":
            if self.chapter_number is None:
                raise ValueError("Chapter number is required for chapter scope.")
            if cleaned_text or self.chapter_start is not None or self.chapter_end is not None:
                raise ValueError("Chapter scope accepts only chapter_number.")
        elif self.scope == "chapter_range":
            if self.chapter_start is None or self.chapter_end is None:
                raise ValueError("Chapter start and end are required for chapter-range scope.")
            if self.chapter_start > self.chapter_end:
                raise ValueError("Chapter start cannot be greater than chapter end.")
            if cleaned_text or self.chapter_number is not None:
                raise ValueError("Chapter-range scope accepts only chapter_start and chapter_end.")
        elif cleaned_text or any(
            value is not None
            for value in (self.chapter_number, self.chapter_start, self.chapter_end)
        ):
            raise ValueError("Full-book scope does not accept passage or chapter fields.")
        return self


class BetaReaderProgressOut(BaseModel):
    stage: str = Field(max_length=80)
    completed: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    message: str = Field(max_length=500)


class BetaReaderEvidenceOut(BaseModel):
    chapter_number: int | None = None
    excerpt: str = Field(min_length=1, max_length=240)


class BetaReaderOverusedTermOut(BaseModel):
    id: str = Field(max_length=100)
    term: str = Field(min_length=1, max_length=240)
    kind: Literal["word", "phrase"]
    count: int = Field(ge=0)
    rate_per_1000: float = Field(ge=0)
    narration_count: int = Field(default=0, ge=0)
    dialogue_count: int = Field(default=0, ge=0)
    burst_detected: bool = False
    chapter_counts: dict[str, int] = Field(default_factory=dict)
    evidence: list[BetaReaderEvidenceOut] = Field(default_factory=list, max_length=3)


class BetaReaderVoiceOut(BaseModel):
    id: str = Field(max_length=100)
    character_id: str = Field(max_length=100)
    character_name: str = Field(min_length=1, max_length=160)
    distinctness_score: int | None = Field(default=None, ge=0, le=100)
    confidence: Literal["high", "medium", "low", "insufficient"]
    sample_dialogue_count: int = Field(default=0, ge=0)
    sample_word_count: int = Field(default=0, ge=0)
    closest_character_id: str | None = Field(default=None, max_length=100)
    closest_character_name: str | None = Field(default=None, max_length=160)
    similarity_score: int | None = Field(default=None, ge=0, le=100)
    signals: dict[str, int] = Field(default_factory=dict)
    shared_signals: list[str] = Field(default_factory=list, max_length=9)
    shared_phrases: list[str] = Field(default_factory=list, max_length=6)


class BetaReaderFindingOut(BaseModel):
    id: str = Field(max_length=100)
    category: str = Field(min_length=1, max_length=64)
    severity: Literal["high", "medium", "low"]
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    chapter_number: int | None = None
    evidence: list[BetaReaderEvidenceOut] = Field(default_factory=list, max_length=3)
    recommendation: str = Field(min_length=1, max_length=800)
    reader_question: str | None = Field(default=None, max_length=500)


class BetaReaderRevisionCandidateOut(BaseModel):
    id: str = Field(max_length=100)
    source_item_id: str = Field(max_length=100)
    category: str = Field(min_length=1, max_length=64)
    severity: Literal["high", "medium", "low"]
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    recommendation: str = Field(min_length=1, max_length=800)
    chapter_number: int | None = None
    evidence: list[BetaReaderEvidenceOut] = Field(default_factory=list, max_length=3)


class BetaReaderCoverageOut(BaseModel):
    requested_chapters: list[int] = Field(default_factory=list)
    analyzed_chapters: list[int] = Field(default_factory=list)
    missing_chapters: list[int] = Field(default_factory=list)
    word_count: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)


class BetaReaderReportOut(BaseModel):
    report_id: str = Field(max_length=100)
    scope: BetaReaderScope
    request_hash: str = Field(max_length=128)
    source_fingerprint: str = Field(max_length=128)
    created_at: str = Field(max_length=64)
    is_stale: bool = False
    checks: list[BetaReaderCheck] = Field(default_factory=list, max_length=3)
    coverage: BetaReaderCoverageOut = Field(default_factory=BetaReaderCoverageOut)
    overall_impression: str = Field(min_length=1, max_length=1200)
    reader_vibe: str = Field(default="", max_length=1200)
    story_understanding: str = Field(default="", max_length=1200)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    reader_questions: list[str] = Field(default_factory=list, max_length=8)
    prioritized_revisions: list[str] = Field(default_factory=list, max_length=8)
    overused_terms: list[BetaReaderOverusedTermOut] = Field(default_factory=list, max_length=30)
    character_voices: list[BetaReaderVoiceOut] = Field(default_factory=list, max_length=20)
    findings: list[BetaReaderFindingOut] = Field(default_factory=list, max_length=20)
    revision_candidates: list[BetaReaderRevisionCandidateOut] = Field(
        default_factory=list, max_length=20
    )
    warnings: list[str] = Field(default_factory=list, max_length=30)


class BetaReaderRunOut(BaseModel):
    status: Literal["queued", "complete"]
    task_id: str | None = None
    cached: bool = False
    report: BetaReaderReportOut | None = None


class BetaReaderJobOut(BaseModel):
    task_id: str
    status: Literal["queued", "running", "complete", "failed"]
    progress: BetaReaderProgressOut | None = None
    report: BetaReaderReportOut | None = None
    error: str | None = None


class BetaReaderReportsOut(BaseModel):
    reports: list[BetaReaderReportOut] = Field(default_factory=list)


class BetaReaderRevisionTaskOut(BaseModel):
    task_id: str
    candidate_id: str
    created: bool


class FirstImpressionOut(BaseModel):
    status: Literal["not_started", "queued", "running", "complete", "failed"]
    task_id: str | None = None
    progress: BetaReaderProgressOut | None = None
    report: BetaReaderReportOut | None = None
    error: str | None = None
    can_retry: bool = False


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
            raise ValueError(
                f"Please describe it in at least {MIN_WHATS_THE_WORD_DESCRIPTION_WORDS} words."
            )
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
