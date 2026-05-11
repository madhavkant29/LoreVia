from pydantic import BaseModel


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


class TimelineResponseOut(BaseModel):
    chapters: list[TimelineChapterOut]
    events: list[TimelineEventOut]
    character_tracks: list[CharacterTimelineTrackOut]
    thread_tracks: list[PlotThreadTimelineTrackOut]
    relationship_markers: list[RelationshipTimelineMarkerOut]
