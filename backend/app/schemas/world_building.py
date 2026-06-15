from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorldBuildingDocumentOut(BaseModel):
    id: str
    book_id: str
    title: str
    source_name: str | None = None
    word_count: int | None = None
    is_active: bool = True
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorldBuildingDocumentDetailOut(WorldBuildingDocumentOut):
    text: str
    html: str | None = None


class WorldBuildingDocumentUpdateBody(BaseModel):
    title: str | None = None
    text: str
    html: str | None = None


class WorldElementOut(BaseModel):
    id: str
    book_id: str
    series_id: str | None = None
    world_document_id: str | None = None
    source_scope: str = "story"
    element_type: str
    name: str
    description: str | None = None
    parent_element_id: str | None = None
    dependencies: list[dict] | list[str] = Field(default_factory=list)
    usage_count: int = 0
    gap_score: float | None = None
    integration_score: float | None = None
    suggestions: list[dict] = Field(default_factory=list)
    edited_by_author: bool = False
    is_series_canonical: bool = False
    created_at: datetime
    updated_at: datetime
    chapter_number: int | None = None
    chapter_title: str | None = None
    world_document_title: str | None = None
    canonical_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    confidence: float | None = None
    provenance: list[dict] = Field(default_factory=list)
    claims: list[dict] = Field(default_factory=list)
    chapter_numbers: list[int] = Field(default_factory=list)
    chapter_count: int = 0
    summary_mentions: int = 0
    presence_score: float | None = None
    narrative_modes: list[str] = Field(default_factory=list)
    source_excerpt: str | None = None
    character_id: str | None = None
    author_override: bool = False
    quality_flags: list[str] = Field(default_factory=list)
    grounding_passage_count: int = 0
    confidence_band: str | None = None


class WorldGapItemOut(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    description: str
    suggested_fix: str
    world_evidence: str | None = None
    story_evidence: str | None = None
    world_document_id: str | None = None
    world_document_title: str | None = None
    story_chapter_number: int | None = None
    story_chapter_title: str | None = None
    character_name: str | None = None
    priority: int = 5
    entity_type: str | None = None
    canonical_name: str | None = None
    confidence: float = 0.0
    provenance: dict = Field(default_factory=dict)


class WorldGapGroupOut(BaseModel):
    key: str
    label: str
    description: str | None = None
    items: list[WorldGapItemOut] = Field(default_factory=list)


class GapAnalysisRequest(BaseModel):
    mode: str | None = None
    query: str | None = None
    auto_create_notes: bool = False


class GapAnalysisResponse(BaseModel):
    mode: str
    generated_at: datetime | None = None
    gap_categories: dict[str, list[dict]]
    gap_groups: list[WorldGapGroupOut] = Field(default_factory=list)
    priority_gaps: list[WorldGapItemOut] = Field(default_factory=list)
    consistency_flags: list[dict] = Field(default_factory=list)
    world_elements: list[WorldElementOut] = Field(default_factory=list)
    world_documents: list[WorldBuildingDocumentOut] = Field(default_factory=list)


class IntegrationAnalysisResponse(BaseModel):
    mode: str
    generated_at: datetime | None = None
    integration_opportunities: list[dict] = Field(default_factory=list)
    consistency_flags: list[dict] = Field(default_factory=list)
    world_elements: list[WorldElementOut] = Field(default_factory=list)
    world_documents: list[WorldBuildingDocumentOut] = Field(default_factory=list)
    dependency_graph: list[dict] = Field(default_factory=list)


class WorldQueryRequest(BaseModel):
    query: str
    mode: str | None = None


class WorldQueryResponse(BaseModel):
    mode: str
    answer: str
    citations: list[dict]
    suggestions: list[dict]
    logic_alerts: list[dict] = Field(default_factory=list)
    simulation_steps: list[str] = Field(default_factory=list)


class SuggestionAcceptance(BaseModel):
    suggestion_id: str
    mark_implemented: bool = True


class CanonOverrideBody(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    notes: str | None = None


class CanonOverrideOut(BaseModel):
    id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class WorldNoteBody(BaseModel):
    world_element_id: str | None = None
    world_document_id: str | None = None
    note_type: str = "general_world"
    chapter_number: int | None = None
    title: str | None = None
    body: str
    priority: str = "medium"
    status: str = "open"
    linked_gap_id: str | None = None
    linked_integration_id: str | None = None
    context_label: str | None = None
    suggested_fix: str | None = None


class WorldNoteStatusBody(BaseModel):
    status: str


class WorldNoteOut(BaseModel):
    id: str
    book_id: str
    world_element_id: str | None = None
    world_document_id: str | None = None
    note_type: str
    chapter_number: int | None = None
    title: str | None = None
    body: str
    priority: str
    status: str
    linked_gap_id: str | None = None
    linked_integration_id: str | None = None
    context_label: str | None = None
    suggested_fix: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    addressed_at: datetime | None = None


class WikiEntryOut(BaseModel):
    id: str
    book_id: str
    entry_type: str
    name: str
    description: str | None = None
    first_mention: int | None = None
    related_char_ids: list[str] | None = None
    created_at: datetime


class WikiGenerationResponse(BaseModel):
    generated_count: int
    updated_names: list[str] = Field(default_factory=list)
    entries: list[WikiEntryOut] = Field(default_factory=list)


class WorldBuildingBootstrapOut(BaseModel):
    documents: list[WorldBuildingDocumentOut] = Field(default_factory=list)
    selected_document: WorldBuildingDocumentDetailOut | None = None
    notes: list[WorldNoteOut] = Field(default_factory=list)
    canon_overrides: list[CanonOverrideOut] = Field(default_factory=list)
    elements: list[WorldElementOut] = Field(default_factory=list)
    wiki: list[WikiEntryOut] = Field(default_factory=list)
    stats: dict | None = None
    gap_analysis: GapAnalysisResponse | None = None
