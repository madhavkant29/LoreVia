from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    author: str | None
    genre: str | None
    format: str
    status: str
    mode: str
    source_kind: str
    cover_url: str | None = None
    total_chapters: int | None
    total_tokens: int | None
    is_truncated: bool
    primary_series_id: uuid.UUID | None = None
    series_name: str | None
    series_order: int | None
    is_public: bool
    public_description: str | None
    copyright_warning: bool
    archived_at: datetime | None
    hidden_at: datetime | None
    created_at: datetime
    progress_pct: float | None = None
    chapters_read_count: int | None = None
    chapters_left: int | None = None
    marked_complete_in_series: bool | None = None


class SeriesOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    books: list[BookOut]


class SeriesBody(BaseModel):
    series_name: str | None = None
    series_order: int | None = None


class SeriesCreateBody(BaseModel):
    name: str
    description: str | None = None


class SeriesMembershipBody(BaseModel):
    position: int | None = None


class SeriesBookStatusBody(BaseModel):
    marked_complete: bool = True


class BookModeBody(BaseModel):
    mode: str


class CharacterUpdateBody(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    role: str | None = None
    description: str | None = None
    arc_summary: str | None = None
    personality_tags: list[str] | None = None
    motivations: list[str] | None = None
    fears: list[str] | None = None


class RelationshipUpdateBody(BaseModel):
    rel_type: str
    sentiment: float | None = None
    description: str | None = None
    from_chapter: int | None = None
    to_chapter: int | None = None


class CharacterShareOut(BaseModel):
    share_url: str
    expires_in_minutes: int


class ChapterReportCharacter(BaseModel):
    id: str
    name: str
    role: str | None = None
    first_chapter: int | None = None
    arc_summary: str | None = None


class ChapterConsistencyReport(BaseModel):
    chapter_number: int
    chapter_title: str | None = None
    summary: str
    new_characters: list[ChapterReportCharacter]
    relationship_changes: list[str]
    plot_threads_opened: list[str]
    plot_threads_resolved: list[str]
    continuity_flags: list[str]


class ManuscriptImportResult(BaseModel):
    book_id: str
    imported_chapters: list[int]
    total_chapters: int
    mode: str
    source_kind: str
    chapter_reports: list[ChapterConsistencyReport] = []


class PreWritingCharacterOut(BaseModel):
    id: str
    name: str
    role: str | None = None
    last_seen_chapter: int | None = None
    arc_summary: str | None = None


class PreWritingThreadOut(BaseModel):
    id: str
    title: str
    status: str
    introduced_at: int | None = None
    note: str | None = None


class PreWritingEventOut(BaseModel):
    chapter_number: int
    chapter_title: str | None = None
    detail: str


class AuthorAlertOut(BaseModel):
    kind: str
    title: str
    body: str
    chapter_ref: int | None = None


class PreWritingCheckOut(BaseModel):
    upcoming_chapter: int
    active_characters: list[PreWritingCharacterOut]
    unresolved_threads: list[PreWritingThreadOut]
    recent_events: list[PreWritingEventOut]
    alerts: list[AuthorAlertOut]


class ChapterVersionOut(BaseModel):
    id: str
    chapter_number: int
    title: str | None = None
    word_count: int | None = None
    note: str | None = None
    created_at: datetime


class BookNoteBody(BaseModel):
    note_id: str | None = None
    chapter_number: int | None = None
    title: str | None = None
    body: str


class BookNoteOut(BaseModel):
    id: str
    book_id: str
    book_title: str
    chapter_number: int | None = None
    chapter_title: str | None = None
    title: str | None = None
    body: str
    created_at: datetime
    updated_at: datetime


class PublicUserStats(BaseModel):
    total_books_read: int
    total_words_read: int


class PrivateUserStats(BaseModel):
    total_uploads: int
    total_token_consumption: int
    total_chapters_tracked: int
    saved_quotes: int


class UserStatsOut(BaseModel):
    public: PublicUserStats
    private: PrivateUserStats


# Screenplay-specific schemas

class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    book_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    number: int
    heading: str
    location: str | None = None
    time_of_day: str | None = None
    interior: bool = False
    exterior: bool = False
    scene_number: str | None = None
    description: str | None = None
    word_count: int | None = None
    page_number: int | None = None
    created_at: datetime
    dialogue: list[DialogueOut] = []


class DialogueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    scene_id: uuid.UUID
    character_name: str
    character_extension: str | None = None
    dialogue_text: str
    parenthetical: str | None = None
    line_number: int
    word_count: int | None = None
    created_at: datetime


class ScreenplayImportResult(BaseModel):
    book_id: str
    imported_scenes: list[int]
    total_scenes: int
    total_dialogue_lines: int
    mode: str
    source_kind: str


class SceneAnalysis(BaseModel):
    scene_number: int
    scene_heading: str
    characters_present: list[str]
    dialogue_count: int
    action_lines: int
    estimated_duration_minutes: float | None = None


class ScreenplayStats(BaseModel):
    total_scenes: int
    total_dialogue_lines: int
    total_words: int
    estimated_pages: int | None = None
    character_dialogue_counts: dict[str, int]
    scene_types: dict[str, int]  # INT/EXT breakdown
