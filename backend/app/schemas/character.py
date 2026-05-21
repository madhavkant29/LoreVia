import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TraitOut(BaseModel):
    value: str
    confidence: float   # 0.0–1.0
    type: str           # objective | subjective | abstract


class CharacterOut(BaseModel):
    class CharacterAnalysisOut(BaseModel):
        persistence_reason: str | None = None
        evidence_count: int | None = None
        summary_quality: str | None = None
        needs_review: bool = False
        rejected_duplicate_candidates: list[str] = Field(default_factory=list)
        quality_flags: list[str] = Field(default_factory=list)
        grounding_passage_count: int = 0
        confidence_band: str | None = None

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    name: str
    aliases: list[str] | None
    role: str | None
    first_chapter: int
    trait_state: dict | None
    hair: str | None
    eyes: str | None
    build: str | None
    age_descriptor: str | None
    distinguishing: str | None
    personality_tags: list[str] | None
    motivations: list[str] | None
    fears: list[str] | None
    archetype: str | None
    arc_summary: str | None
    last_seen_chapter: int | None = None
    mention_count: int | None = None
    growth_events: list[dict] | None = None
    character_type: str | None = None
    character_type_score: int | None = None
    subtype_scores: dict | None = None
    analysis_metadata: CharacterAnalysisOut | None = None
    created_at: datetime


class CharacterStateOut(BaseModel):
    character_id: uuid.UUID
    at_chapter: int
    trait_state: dict | None
    arc_note: str | None
    prompt_delta: str | None


class RelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    character_a_id: uuid.UUID
    character_b_id: uuid.UUID
    rel_type: str
    sentiment: float | None
    description: str | None
    from_chapter: int
    to_chapter: int | None


class CharacterCandidateOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    chapter_number: int
    raw_name: str
    proposed_name: str
    normalized_name: str
    aliases: list[str] = Field(default_factory=list)
    matched_character_id: uuid.UUID | None = None
    status: str
    confidence: int
    reason_codes: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    source_batch_key: str | None = None
    created_at: datetime
    updated_at: datetime


class CharacterDuplicateSuggestionOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    primary_character_id: uuid.UUID
    secondary_character_id: uuid.UUID
    confidence: int
    reasons: list[str] = Field(default_factory=list)
    shared_evidence: dict = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime


class CharacterReviewCountsOut(BaseModel):
    pending_candidates: int = 0
    pending_duplicate_suggestions: int = 0


class CharacterReviewOut(BaseModel):
    candidates: list[CharacterCandidateOut] = Field(default_factory=list)
    duplicate_suggestions: list[CharacterDuplicateSuggestionOut] = Field(default_factory=list)
    counts: CharacterReviewCountsOut = Field(default_factory=CharacterReviewCountsOut)
