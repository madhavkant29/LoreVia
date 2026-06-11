from typing import Any

from pydantic import BaseModel, Field


class SaveQuoteBody(BaseModel):
    quote_text: str
    chapter_number: int | None = None
    character_name: str | None = None
    note: str | None = None


class PlotThreadOut(BaseModel):
    id: str
    title: str
    type: str | None = None
    status: str
    description: str | None = None
    introduced_at: int | None = None
    resolved_at: int | None = None
    first_mentioned: int | None = None
    last_mentioned: int | None = None
    mention_count: int = 0
    importance: int
    note: str | None = None
    character_ids: list[str] = []
    related_characters: list[str] = []
    risk: str | None = None
    suggested_action: str | None = None
    tags: list[str] = Field(default_factory=list)


class UpdatePlotThreadBody(BaseModel):
    note: str | None = None
    status: str | None = None


class TimelineEventOut(BaseModel):
    chapter_number: int
    chapter_title: str | None = None
    kind: str
    title: str
    detail: str | None = None


class TimelineChapterOut(BaseModel):
    number: int
    title: str | None = None


class CharacterTimelineTrackOut(BaseModel):
    id: str
    name: str
    role: str | None = None
    start_chapter: int
    end_chapter: int
    detail: str | None = None


class PlotThreadTimelineTrackOut(BaseModel):
    id: str
    title: str
    status: str
    start_chapter: int
    end_chapter: int
    note: str | None = None
    detail: str | None = None


class RelationshipTimelineMarkerOut(BaseModel):
    id: str
    title: str
    chapter_number: int
    detail: str | None = None
    type: str | None = None
    shared_labels: list[str] = Field(default_factory=list)
    character_a_to_b_labels: list[str] = Field(default_factory=list)
    character_b_to_a_labels: list[str] = Field(default_factory=list)


class TimelineResponseOut(BaseModel):
    chapters: list[TimelineChapterOut]
    events: list[TimelineEventOut]
    character_tracks: list[CharacterTimelineTrackOut]
    thread_tracks: list[PlotThreadTimelineTrackOut]
    relationship_markers: list[RelationshipTimelineMarkerOut]


class ChapterAnalysisStatusOut(BaseModel):
    status: str
    generated_modes: list[str] = Field(default_factory=list)
    attempt_count: int = 0
    last_error: str | None = None
    updated_at: Any | None = None


class ChapterListItemOut(BaseModel):
    number: int
    title: str | None = None
    chapter_kind: str = "chapter"
    word_count: int | None = None
    processed: bool
    intelligence_available: bool = True
    read: bool
    analysis_status: ChapterAnalysisStatusOut | None = None
    tags: list[str] = Field(default_factory=list)


class ChapterListResponseOut(BaseModel):
    read_upto: int
    current_chapter: int
    chapters: list[ChapterListItemOut] = Field(default_factory=list)


class ReadingProgressOut(BaseModel):
    current_chapter: int
    scroll_pct: float
    chapters_read_count: int
    percent_complete: float
    chapters_left: int


class SummaryKeyEventOut(BaseModel):
    event: str
    importance: int = 0


class SummaryCollectionItemOut(BaseModel):
    chapter_number: int
    chapter_title: str | None = None
    chapter_kind: str = "chapter"
    read: bool
    available: bool
    status: str = "pending"
    content: str | None = None
    key_events: list[SummaryKeyEventOut] = Field(default_factory=list)


class SummaryCollectionResponseOut(BaseModel):
    read_upto: int
    summaries: list[SummaryCollectionItemOut] = Field(default_factory=list)
