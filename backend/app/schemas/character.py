import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TraitOut(BaseModel):
    value: str
    confidence: float  # 0.0–1.0
    type: str  # objective | subjective | abstract


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
        user_curated: bool = False
        protected_from_repair: bool = False
        canonical_confidence: float | None = None
        grounding_coverage: float | None = None
        cluster_size: int = 0
        cluster_mention_count: int = 0
        resolver_status: str | None = None
        review_note: str | None = None
        visibility_state: str | None = None
        approval_state: str | None = None
        approval_source: str | None = None
        approval_reason_codes: list[str] = Field(default_factory=list)
        dossier_summary: dict | None = None
        trust_tier: str | None = None
        trust_reasons: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    name: str
    aliases: list[str] | None
    alias_records: list[dict] = Field(default_factory=list)
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
    visibility_state: str | None = None
    approval_state: str | None = None
    approval_source: str | None = None
    approval_reason_codes: list[str] = Field(default_factory=list)
    approval_updated_at: datetime | None = None
    is_manual: bool = False
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
    shared_labels: list[str] | None = None
    character_a_to_b_labels: list[str] | None = None
    character_b_to_a_labels: list[str] | None = None
    label_evidence: dict | None = None


class CharacterCandidateOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    scene_id: uuid.UUID | None = None
    chapter_number: int
    raw_name: str
    proposed_name: str
    display_name: str | None = None
    normalized_name: str
    aliases: list[str] = Field(default_factory=list)
    matched_character_id: uuid.UUID | None = None
    status: str
    confidence: int
    reason_codes: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    mention_count: int | None = None
    chapter_count: int | None = None
    evidence_windows: list[dict] = Field(default_factory=list)
    entity_type: str | None = None
    adjudication_status: str | None = None
    character_score: int | None = None
    rejection_reason: str | None = None
    cluster_names: list[str] = Field(default_factory=list)
    cluster_size: int = 0
    cluster_mention_count: int = 0
    resolver_status: str | None = None
    resolver_reasons: list[str] = Field(default_factory=list)
    canonical_confidence: float | None = None
    grounding_coverage: float | None = None
    dossier_summary: dict = Field(default_factory=dict)
    snippets: list[str] = Field(default_factory=list)
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
    shared_cluster_keys: list[str] = Field(default_factory=list)
    shared_chapters: list[int] = Field(default_factory=list)
    embedding_similarity: float | None = None
    primary_is_protected: bool = False
    secondary_is_protected: bool = False
    primary_is_manual: bool = False
    secondary_is_manual: bool = False
    primary_is_curated: bool = False
    secondary_is_curated: bool = False
    status: str
    dismissal_reason: str | None = None
    auto_dismissed: bool = False
    created_at: datetime
    updated_at: datetime


class CharacterAliasBody(BaseModel):
    alias_text: str = Field(..., min_length=1)
    alias_kind: str = "user_confirmed"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CharacterAliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    character_id: uuid.UUID
    alias_text: str
    normalized_alias: str
    alias_kind: str
    source: str
    confidence: float
    created_at: datetime


class CharacterRelationshipCandidateOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    chapter_number: int
    raw_character_a: str
    raw_character_b: str
    matched_character_a_id: uuid.UUID | None = None
    matched_character_b_id: uuid.UUID | None = None
    rel_type: str | None = None
    sentiment: float | None = None
    description: str | None = None
    shared_labels: list[str] | None = None
    character_a_to_b_labels: list[str] | None = None
    character_b_to_a_labels: list[str] | None = None
    label_evidence: dict | None = None
    status: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    source_batch_key: str | None = None
    created_at: datetime
    updated_at: datetime


class CharacterDecisionEventOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    character_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    action: str
    visibility_state: str | None = None
    approval_state: str | None = None
    approval_source: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    created_at: datetime


class CharacterReviewCountsOut(BaseModel):
    pending_candidates: int = 0
    pending_duplicate_suggestions: int = 0
    pending_relationship_candidates: int = 0


class CharacterReviewOut(BaseModel):
    candidates: list[CharacterCandidateOut] = Field(default_factory=list)
    duplicate_suggestions: list[CharacterDuplicateSuggestionOut] = Field(default_factory=list)
    relationship_candidates: list[CharacterRelationshipCandidateOut] = Field(default_factory=list)
    shadow_characters: list[CharacterOut] = Field(default_factory=list)
    decision_events: list[CharacterDecisionEventOut] = Field(default_factory=list)
    auto_actions_summary: dict[str, int] = Field(default_factory=dict)
    counts: CharacterReviewCountsOut = Field(default_factory=CharacterReviewCountsOut)
