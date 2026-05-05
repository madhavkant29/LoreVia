from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    author: str | None
    genre: str | None
    format: str
    work_type: str
    status: str
    mode: str
    source_kind: str
    preserve_chapter_numbers: bool = False
    cover_url: str | None = None
    cover_processed_url: str | None = None
    cover_edge_colors: dict[str, str] | None = None
    cover_processed_at: datetime | None = None
    cover_crop_bounds: dict[str, int] | None = None
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
    processing: "BookProcessingOut | None" = None


class SeriesOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    books: list[BookOut]


class SeriesBibleEpisodeOut(BaseModel):
    book_id: str
    title: str
    episode_number: int | None = None
    format: str
    work_type: str
    total_scenes: int = 0
    total_dialogue_lines: int = 0
    total_words: int = 0
    status: str


class SeriesBibleCharacterOut(BaseModel):
    name: str
    normalized_name: str
    episode_count: int
    total_mentions: int = 0
    first_episode: int | None = None
    last_episode: int | None = None
    episodes: list[SeriesBibleEpisodeOut] = Field(default_factory=list)


class SeriesBibleRelationshipOut(BaseModel):
    characters: list[str]
    relationship_type: str
    episode_count: int
    episodes: list[SeriesBibleEpisodeOut] = Field(default_factory=list)
    note: str | None = None


class SeriesBiblePlotThreadOut(BaseModel):
    title: str
    status: str
    episode_count: int
    episodes: list[SeriesBibleEpisodeOut] = Field(default_factory=list)
    note: str | None = None


class SeriesBibleCanonEntryOut(BaseModel):
    name: str
    entry_type: str
    episode_count: int
    episodes: list[SeriesBibleEpisodeOut] = Field(default_factory=list)
    description: str | None = None


class SeriesBibleOut(BaseModel):
    series_id: str
    name: str
    description: str | None = None
    work_type: str
    episode_count: int
    episodes: list[SeriesBibleEpisodeOut]
    recurring_characters: list[SeriesBibleCharacterOut]
    recurring_relationships: list[SeriesBibleRelationshipOut]
    unresolved_plot_threads: list[SeriesBiblePlotThreadOut]
    canon_entries: list[SeriesBibleCanonEntryOut]
    continuity_risks: list[str]


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


class CharacterMergeBody(BaseModel):
    primary_id: uuid.UUID
    secondary_id: uuid.UUID


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


class MajorEventOut(BaseModel):
    chapter_number: int
    chapter_title: str | None = None
    event_title: str
    description: str
    importance: int
    involved_characters: list[str] | None = None
    involved_character_names: list[str] | None = None
    event_type: str | None = None


class CharacterEventOut(BaseModel):
    character_id: str
    character_name: str
    chapter_number: int
    event_title: str
    description: str
    impact_score: int
    role: str | None = None
    accomplishments: list[str] = []
    growth_direction: str = "neutral"
    growth_magnitude: int = 0
    is_major: bool = False


class BookEventsOut(BaseModel):
    major_events: list[MajorEventOut]
    character_events: list[CharacterEventOut]


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
    snapshot_kind: str = "manual"
    created_at: datetime


class ChapterVersionDetailOut(ChapterVersionOut):
    text: str
    html: str | None = None


class WordCountGoalsOut(BaseModel):
    chapter_target: int | None = None
    book_target: int | None = None
    session_target: int | None = None


class CorkboardCardOut(BaseModel):
    id: str
    title: str
    description: str = ""
    status: str = "planned"
    lane: str = "ideas"
    chapter_number: int | None = None
    template_id: str | None = None


class WritingTemplateOut(BaseModel):
    id: str
    kind: str
    title: str
    description: str
    content: str


class PublishingPresetOut(BaseModel):
    active_preset: str = "standard_manuscript"
    trim_size: str = "6x9"
    include_title_page: bool = True
    mirror_margins: bool = True


class ManuscriptFrontMatterOut(BaseModel):
    author_name: str = ""
    pen_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    contact_address: str = ""
    title: str = ""
    subtitle: str = ""
    header_last_name: str = ""
    header_title: str = ""
    approximate_word_count_override: int | None = None
    dedication: str = ""
    acknowledgments: str = ""
    epigraph: str = ""
    prologue: str = ""
    include_dedication: bool = False
    include_acknowledgments: bool = False
    include_epigraph: bool = False
    include_prologue: bool = False


class BookProcessingOut(BaseModel):
    status: str | None = None
    stage: str | None = None
    progress_pct: float | None = None
    chapters_completed: int | None = None
    chapters_total: int | None = None
    eta_seconds: int | None = None
    queue_wait_ms: int | None = None
    last_chapter_number: int | None = None
    last_chapter_title: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None
    parser_diagnostics: dict[str, Any] | None = None


class WriterWorkspaceOut(BaseModel):
    word_count_goals: WordCountGoalsOut
    corkboard_cards: list[CorkboardCardOut]
    templates: list[WritingTemplateOut]
    publishing: PublishingPresetOut
    manuscript_front_matter: ManuscriptFrontMatterOut
    processing: BookProcessingOut | None = None


class WordCountGoalsBody(BaseModel):
    chapter_target: int | None = None
    book_target: int | None = None
    session_target: int | None = None


class CorkboardCardBody(BaseModel):
    id: str | None = None
    title: str
    description: str = ""
    status: str = "planned"
    lane: str = "ideas"
    chapter_number: int | None = None
    template_id: str | None = None


class WritingTemplateBody(BaseModel):
    id: str
    kind: str
    title: str
    description: str
    content: str


class PublishingPresetBody(BaseModel):
    active_preset: str = "standard_manuscript"
    trim_size: str = "6x9"
    include_title_page: bool = True
    mirror_margins: bool = True


class ManuscriptFrontMatterBody(BaseModel):
    author_name: str | None = None
    pen_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_address: str | None = None
    title: str | None = None
    subtitle: str | None = None
    header_last_name: str | None = None
    header_title: str | None = None
    approximate_word_count_override: int | None = None
    dedication: str | None = None
    acknowledgments: str | None = None
    epigraph: str | None = None
    prologue: str | None = None
    include_dedication: bool | None = None
    include_acknowledgments: bool | None = None
    include_epigraph: bool | None = None
    include_prologue: bool | None = None


class WriterWorkspaceBody(BaseModel):
    word_count_goals: WordCountGoalsBody | None = None
    corkboard_cards: list[CorkboardCardBody] | None = None
    templates: list[WritingTemplateBody] | None = None
    publishing: PublishingPresetBody | None = None
    manuscript_front_matter: ManuscriptFrontMatterBody | None = None


class ReadabilityMetricsOut(BaseModel):
    words: int
    sentences: int
    paragraphs: int
    average_sentence_length: float
    reading_ease: float
    grade_level: float
    label: str


class ReadabilityRequestBody(BaseModel):
    text: str


class EmotionalArcPointOut(BaseModel):
    chapter_number: int
    label: str
    sentiment: float
    impact_score: int
    growth_direction: str = "neutral"


class EmotionalArcCharacterOut(BaseModel):
    character_id: str
    character_name: str
    role: str | None = None
    arc_summary: str | None = None
    trajectory_score: float
    points: list[EmotionalArcPointOut]


class EmotionalArcOverviewOut(BaseModel):
    focus_character_count: int
    latest_turning_points: list[str]
    characters: list[EmotionalArcCharacterOut]


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


class ObsidianPreviewFileOut(BaseModel):
    path: str
    content: str


class ObsidianPreviewOut(BaseModel):
    root_folder: str
    files: list[ObsidianPreviewFileOut]


class ObsidianVaultNoteBody(BaseModel):
    path: str
    content: str


class ObsidianNoteLinkBody(BaseModel):
    source_path: str
    target_path: str
    link_type: str = "reference"
    target_label: str | None = None


class ObsidianVaultNoteOut(BaseModel):
    id: str
    book_id: str
    path: str
    source: str
    content: str
    created_at: datetime
    updated_at: datetime


class ObsidianVaultNoteSaveOut(BaseModel):
    path: str
    source: str
    content: str
    persisted: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ObsidianNoteTagOut(BaseModel):
    id: str
    book_id: str
    note_id: str
    note_path: str
    tag_name: str
    created_at: datetime


class ObsidianNoteLinkOut(BaseModel):
    id: str
    book_id: str
    source_note_id: str
    source_note_path: str
    target_note_id: str
    target_note_path: str
    link_type: str
    target_label: str | None = None
    created_at: datetime


class ObsidianNoteSeriesLinkOut(BaseModel):
    id: str
    series_id: str
    source_book_id: str
    target_book_id: str
    source_note_id: str
    source_note_path: str
    target_note_id: str
    target_note_path: str
    link_type: str
    created_at: datetime


class ObsidianNoteLinkListOut(BaseModel):
    links: list[ObsidianNoteLinkOut]
    backlinks: list[ObsidianNoteLinkOut]
    tags: list[ObsidianNoteTagOut]
    series_links: list[ObsidianNoteSeriesLinkOut]


class NovelSceneBody(BaseModel):
    title: str
    description: str | None = None
    body: str
    html_body: str | None = None
    chapter_number: int | None = None
    status: str | None = None
    sort_order: int | None = None


class NovelSceneOut(BaseModel):
    id: str
    book_id: str
    chapter_id: str | None = None
    chapter_number: int | None = None
    title: str
    description: str | None = None
    body: str
    html_body: str | None = None
    path: str
    status: str
    sort_order: int
    source: str
    origin_chapter_number: int | None = None
    created_at: datetime
    updated_at: datetime


class NovelSceneInsertBody(BaseModel):
    chapter_number: int
    position: Literal["start", "end"] = "end"


class WorkspaceChapterNodeOut(BaseModel):
    chapter_number: int
    title: str | None = None
    scene_count: int = 0


class WorkspaceSceneGroupOut(BaseModel):
    id: str
    label: str
    chapter_number: int | None = None
    collapsed_by_default: bool = False
    scenes: list[NovelSceneOut] = Field(default_factory=list)


class ManuscriptWorkspaceTreeOut(BaseModel):
    chapters: list[WorkspaceChapterNodeOut] = Field(default_factory=list)
    scene_groups: list[WorkspaceSceneGroupOut] = Field(default_factory=list)
    note_paths: list[str] = Field(default_factory=list)


class ObsidianGraphNodeOut(BaseModel):
    id: str
    path: str
    title: str
    folder: str
    link_count: int = 0


class ObsidianGraphEdgeOut(BaseModel):
    source: str
    target: str
    label: str | None = None


class ObsidianGraphOut(BaseModel):
    nodes: list[ObsidianGraphNodeOut]
    edges: list[ObsidianGraphEdgeOut]


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
