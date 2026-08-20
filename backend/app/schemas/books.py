from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.beta_reads import BetaReadAssignmentOut
from app.schemas.reader import (
    ChapterListResponseOut,
    ReadingProgressOut,
    SummaryCollectionResponseOut,
)


class CollaborationScope(BaseModel):
    chapter_start: int | None = Field(None, ge=1)
    chapter_end: int | None = Field(None, ge=1)
    character_bible: bool = False
    continuity_report: bool = False
    reader_confusion_report: bool = False


class CollaborationPermissions(BaseModel):
    can_edit_manuscript: bool = False
    can_view_story_bible: bool = False
    can_run_ai_scans: bool = False
    can_export: bool = False
    can_comment: bool = False
    can_view_selected_chapters_only: bool = True


CollaborationRoleLiteral = Literal[
    "viewer",
    "commenter",
    "editor",
    "beta_reader",
    "developmental_editor",
    "coauthor",
    "reader_only",
    "co_writer",
]
BookAccessClassLiteral = Literal["owner", "author_collaborator", "reader_collaborator"]
WorkspaceShellLiteral = Literal["author", "reader"]
TagTargetLiteral = Literal[
    "chapter",
    "scene",
    "character",
    "note",
    "comment",
    "plot_thread",
    "world_note",
]


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
    workspace_shell: WorkspaceShellLiteral = "reader"
    access_class: BookAccessClassLiteral = "owner"
    can_switch_workspace_mode: bool = True
    source_kind: str
    preserve_chapter_numbers: bool = False
    preserve_source_chapters: bool = False
    cover_url: str | None = None
    total_chapters: int | None
    total_tokens: int | None
    total_words: int = 0
    is_truncated: bool
    primary_series_id: uuid.UUID | None = None
    series_name: str | None
    series_order: int | None
    is_public: bool
    public_status: str = "draft"
    public_slug: str | None = None
    published_at: datetime | None = None
    public_updated_at: datetime | None = None
    public_visibility: str = "private"
    rights_confirmation: bool = False
    rights_confirmation_at: datetime | None = None
    content_source_type: str = "user_original"
    moderation_status: str = "clean"
    moderation_reason: str | None = None
    takedown_reason: str | None = None
    takedown_at: datetime | None = None
    public_upload_counted_at: datetime | None = None
    source_title: str | None = None
    source_author: str | None = None
    source_public_domain_note: str | None = None
    source_url: str | None = None
    public_description: str | None
    public_share_status: str | None = None
    public_share_requested_at: datetime | None = None
    public_share_approved_at: datetime | None = None
    copyright_warning: bool
    is_editor_project: bool = False
    archived_at: datetime | None
    hidden_at: datetime | None
    created_at: datetime
    progress_pct: float | None = None
    chapters_read_count: int | None = None
    chapters_left: int | None = None
    marked_complete_in_series: bool | None = None
    processing: BookProcessingOut | None = None
    collaboration_role: str | None = None
    collaboration_scope: CollaborationScope | None = None
    collaboration_permissions: CollaborationPermissions | None = None


class BookOverviewOut(BaseModel):
    book: BookOut
    progress: ReadingProgressOut | None = None
    chapter_list: ChapterListResponseOut | None = None
    summary_collection: SummaryCollectionResponseOut | None = None


class VisibilitySummaryItemOut(BaseModel):
    state: str
    label: str
    count: int | None = None
    detail: str | None = None


class BookVisibilitySummaryOut(BaseModel):
    book_id: uuid.UUID
    access_class: BookAccessClassLiteral
    workspace_shell: WorkspaceShellLiteral
    badges: list[str] = Field(default_factory=list)
    private_status: VisibilitySummaryItemOut
    collaborators: VisibilitySummaryItemOut
    beta_readers: VisibilitySummaryItemOut
    public_publishing: VisibilitySummaryItemOut
    public_discussion: VisibilitySummaryItemOut
    rights: VisibilitySummaryItemOut
    moderation: VisibilitySummaryItemOut
    public_url: str | None = None


class ReaderBootstrapOut(BaseModel):
    profile: Literal["critical", "full"] = "full"
    overview: BookOverviewOut
    notes: list[BookNoteOut] = Field(default_factory=list)
    saved_quotes: list[dict[str, Any]] = Field(default_factory=list)
    stats: UserStatsOut | None = None
    characters: list[dict[str, Any]] = Field(default_factory=list)
    chapter_reports: list[ChapterConsistencyReport] = Field(default_factory=list)
    prewriting_check: PreWritingCheckOut | None = None
    story_health: StoryHealthOut | None = None
    writer_workspace: WriterWorkspaceOut | None = None
    revision_intelligence: RevisionIntelligenceOut | None = None


class ManuscriptBootstrapOut(BaseModel):
    profile: Literal["critical", "full"] = "full"
    book: BookOut
    characters: list[dict[str, Any]] = Field(default_factory=list)
    writer_workspace: WriterWorkspaceOut | None = None
    emotional_arc: EmotionalArcOverviewOut | None = None
    synopsis: dict[str, Any] | None = None
    workspace_tree: ManuscriptWorkspaceTreeOut | None = None
    annotations: list[ManuscriptAnnotationOut] = Field(default_factory=list)
    notes: list[BookNoteOut] = Field(default_factory=list)
    vault_notes: list[VaultNoteOut] = Field(default_factory=list)
    chapter_versions: list[ChapterVersionOut] = Field(default_factory=list)
    prewriting_check: PreWritingCheckOut | None = None


class BookForumMetadataBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    genre: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=5000)


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


class PermanentBookDeletionBody(BaseModel):
    confirmation_text: str


class PermanentBookDeletionOut(BaseModel):
    ok: bool = True
    book_id: uuid.UUID
    deletion_request_id: uuid.UUID
    status: str


class CharacterCreateBody(BaseModel):
    name: str
    first_chapter: int = Field(default=1, ge=1)
    aliases: list[str] | None = None
    role: str | None = None
    description: str | None = None
    goal: str | None = None
    lie_they_believe: str | None = None
    backstory_wound: str | None = None
    arc_type: str | None = None
    arc_summary: str | None = None
    personality_tags: list[str] | None = None
    motivations: list[str] | None = None
    fears: list[str] | None = None


class CharacterUpdateBody(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    role: str | None = None
    description: str | None = None
    goal: str | None = None
    lie_they_believe: str | None = None
    backstory_wound: str | None = None
    arc_type: str | None = None
    arc_summary: str | None = None
    personality_tags: list[str] | None = None
    motivations: list[str] | None = None
    fears: list[str] | None = None
    graph_visibility: str | None = None
    protected_from_repair: bool | None = None
    review_note: str | None = None


class RelationshipCreateBody(BaseModel):
    character_a_id: uuid.UUID
    character_b_id: uuid.UUID
    rel_type: str
    sentiment: float | None = None
    description: str | None = None
    from_chapter: int = Field(default=1, ge=1)
    to_chapter: int | None = Field(default=None, ge=1)
    shared_labels: list[str] = Field(default_factory=list)
    character_a_to_b_labels: list[str] = Field(default_factory=list)
    character_b_to_a_labels: list[str] = Field(default_factory=list)
    label_evidence: dict | None = None


class RelationshipUpdateBody(BaseModel):
    rel_type: str
    sentiment: float | None = None
    description: str | None = None
    from_chapter: int | None = None
    to_chapter: int | None = None
    shared_labels: list[str] | None = None
    character_a_to_b_labels: list[str] | None = None
    character_b_to_a_labels: list[str] | None = None
    label_evidence: dict | None = None


class CharacterShareOut(BaseModel):
    share_url: str
    expires_in_minutes: int


class BookCollaboratorCreateBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    display_name: str | None = Field(None, max_length=120)
    role: CollaborationRoleLiteral
    scope: CollaborationScope = Field(default_factory=CollaborationScope)
    permissions: CollaborationPermissions | None = None


class BookCollaboratorUpdateBody(BaseModel):
    display_name: str | None = Field(None, max_length=120)
    role: CollaborationRoleLiteral | None = None
    scope: CollaborationScope | None = None
    permissions: CollaborationPermissions | None = None
    invite_status: Literal["active", "revoked"] | None = None


class BookCollaboratorOut(BaseModel):
    id: str
    book_id: str
    email: str
    display_name: str | None = None
    role: str
    scope: CollaborationScope
    permissions: CollaborationPermissions
    invite_status: str
    invited_at: datetime
    updated_at: datetime


class ChapterBetaFeedbackOut(BaseModel):
    id: str
    assignment_id: str
    collaborator_id: str | None = None
    reader_user_id: str | None = None
    reader_email: str
    reader_display_name: str
    task_label: str
    kind: str
    chapter_number: int | None = None
    anchor_text: str | None = None
    body: str | None = None
    author_status: str = "open"
    created_at: datetime
    updated_at: datetime


class CollaboratorActivityItemOut(BaseModel):
    id: str
    kind: str
    title: str
    body: str | None = None
    chapter_number: int | None = None
    chapter_title: str | None = None
    assignment_id: str | None = None
    feedback_item_id: str | None = None
    annotation_id: str | None = None
    created_at: datetime


class CollaboratorActivityOut(BaseModel):
    collaborator: BookCollaboratorOut
    assignments: list[BetaReadAssignmentOut] = Field(default_factory=list)
    items: list[CollaboratorActivityItemOut] = Field(default_factory=list)
    chapter_comment_count: int = 0
    annotation_count: int = 0
    latest_activity_at: datetime | None = None


class CharacterMergeBody(BaseModel):
    primary_id: uuid.UUID
    secondary_id: uuid.UUID


class CharacterPartitionTargetBody(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)


class CharacterPartitionBody(BaseModel):
    partitions: list[CharacterPartitionTargetBody]


class CharacterCandidateAttachBody(BaseModel):
    character_id: uuid.UUID


class RelationshipCandidateAttachBody(BaseModel):
    character_id: uuid.UUID


class RelationshipCandidateAcceptBody(BaseModel):
    character_a_id: uuid.UUID
    character_b_id: uuid.UUID
    rel_type: str | None = None
    sentiment: float | None = None
    description: str | None = None
    from_chapter: int | None = Field(default=None, ge=1)
    to_chapter: int | None = Field(default=None, ge=1)
    shared_labels: list[str] | None = None
    character_a_to_b_labels: list[str] | None = None
    character_b_to_a_labels: list[str] | None = None
    label_evidence: dict | None = None


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


class StoryHealthMetricOut(BaseModel):
    label: str
    score: int
    detail: str


class StoryHealthOut(BaseModel):
    score: int
    status: str
    summary: str
    metrics: list[StoryHealthMetricOut]


class ManuscriptImportResult(BaseModel):
    status: str = "imported"
    book_id: str
    imported_chapters: list[int]
    chapters_created: int = 0
    analysis_dispatched: int = 0
    analysis_tasks: list[dict[str, Any]] = Field(default_factory=list)
    chapter_content_versions: dict[int, int] = Field(default_factory=dict)
    total_chapters: int
    mode: str
    source_kind: str
    chapter_reports: list[ChapterConsistencyReport] = Field(default_factory=list)


class EmptyProjectBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    author: str | None = Field(None, max_length=255)
    genre: str | None = Field(None, max_length=100)
    work_type: str | None = None
    series_ids: list[str] | None = Field(default_factory=list)


class EmptyProjectOut(BaseModel):
    book_id: str
    status: str
    mode: str
    is_editor_project: bool = True


class ManuscriptReprocessOut(BaseModel):
    book_id: str
    status: str
    chapters_queued: int = 0
    total_words: int = 0
    upload_charge_consumed: bool = False
    charge_kind: Literal["manual_reprocess"] | None = None
    processed_words_reserved: int = 0
    processed_words_remaining: int | None = None


class ManuscriptReprocessBody(BaseModel):
    confirm_upload_charge: bool = False
    confirm_processing_words: bool = False


class ReprocessMetadataOut(BaseModel):
    auto_reprocess_enabled: bool = True
    pending_chapters: list[int] = Field(default_factory=list)
    last_mode_changed_at: str | None = None
    last_manual_chapter_started_at: str | None = None
    last_manual_chapter_number: int | None = None


class ReprocessMetadataBody(BaseModel):
    auto_reprocess_enabled: bool | None = None
    pending_chapters: list[int] | None = None
    last_mode_changed_at: str | None = None
    last_manual_chapter_started_at: str | None = None
    last_manual_chapter_number: int | None = None


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
    restore_status: str | None = None
    restore_error: str | None = None
    restore_task_id: str | None = None
    restore_started_at: datetime | None = None
    restore_completed_at: datetime | None = None
    created_at: datetime


class ChapterVersionDetailOut(ChapterVersionOut):
    text: str
    html: str | None = None


class ChapterVersionRestoreStatusOut(BaseModel):
    id: str
    chapter_number: int
    restore_status: str | None = None
    restore_error: str | None = None
    restore_task_id: str | None = None
    restore_started_at: datetime | None = None
    restore_completed_at: datetime | None = None


class SceneVersionOut(BaseModel):
    id: str
    scene_id: str | None = None
    chapter_number: int | None = None
    scene_title: str
    scene_path: str | None = None
    word_count: int | None = None
    note: str | None = None
    snapshot_kind: str = "manual"
    created_at: datetime


class SceneVersionDetailOut(SceneVersionOut):
    description: str | None = None
    body: str
    html_body: str | None = None


class SceneVersionRestoreOut(BaseModel):
    scene: NovelSceneOut
    versions: list[SceneVersionOut] = Field(default_factory=list)


class WordCountGoalsOut(BaseModel):
    chapter_target: int | None = None
    book_target: int | None = None
    session_target: int | None = None


class GoalCalendarItemOut(BaseModel):
    id: str
    title: str
    due_date: str
    quota_value: int | None = None
    quota_unit: str | None = None
    completed: bool = False


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


class EditorPreferencesOut(BaseModel):
    font_family: str = "Times New Roman"
    font_size: int = 12
    line_height: float = 1.8
    manuscript_width: str = "standard"
    show_page_guides: bool = True
    focus_mode: bool = False
    default_scene_separator: str = "asterisks"


class ReadingThemesOut(BaseModel):
    active_theme: str = "light"
    allow_dark_mode: bool = True


class TypewriterModeOut(BaseModel):
    enabled: bool = False
    center_offset_px: int = 160


class ManuscriptLayoutOut(BaseModel):
    margins: str = "standard"
    page_size: str = "letter"
    orientation: str = "portrait"
    show_headers: bool = True
    show_footers: bool = True
    page_numbering: bool = True
    different_first_page: bool = True


class WorkspaceStructureNodeOut(BaseModel):
    id: str
    label: str
    kind: str
    chapter_number: int | None = None
    scene_id: str | None = None
    children: list[WorkspaceStructureNodeOut] = Field(default_factory=list)


class WorkspaceBreadcrumbOut(BaseModel):
    id: str
    label: str
    kind: str


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


class NovelFrontMatterOut(BaseModel):
    dedication: str = ""
    acknowledgements: str = ""
    copyright_page: str = ""
    about_author: str = ""
    series_book_list: str = ""


class NovelEpubMetadataOut(BaseModel):
    publisher: str = ""
    language: str = "en"
    isbn: str = ""
    description: str = ""
    series_name: str = ""
    series_number: str = ""


class RevisionBoardItemStateOut(BaseModel):
    item_id: str
    status: str = "pending"
    assigned_version_id: str | None = None
    task_id: str | None = None
    updated_at: str | None = None
    decision: str | None = None
    action: str | None = None
    reason: str | None = None
    source_content_versions: dict[int, int] = Field(default_factory=dict)
    finding_snapshot: dict[str, Any] | None = None


class RevisionBoardOut(BaseModel):
    items: list[RevisionBoardItemStateOut] = Field(default_factory=list)
    last_generated_at: str | None = None


class ActivationStateOut(BaseModel):
    completed_at: str | None = None
    completion_action: str | None = None
    completed_finding_id: str | None = None


class ProcessingPipelineStageOut(BaseModel):
    status: str | None = None
    completed_chapters: int | None = None
    total_chapters: int | None = None
    updated_at: datetime | None = None
    eta_seconds: int | None = None
    last_error: str | None = None
    failed_chapters: list[int] = Field(default_factory=list)


class ProcessingPipelineOut(BaseModel):
    extraction: ProcessingPipelineStageOut | None = None
    analysis: ProcessingPipelineStageOut | None = None


class BookProcessingOut(BaseModel):
    status: str | None = None
    stage: str | None = None
    current_step_label: str | None = None
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
    is_fully_ready: bool = False
    pipeline: ProcessingPipelineOut | None = None
    retry_actions: list[str] = Field(default_factory=list)
    retry_available: bool = False
    processing_run_id: str | None = None
    pause_reason: str | None = None
    resume_available: bool = False
    resume_blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_chapter_number: int | None = None
    next_resume_at: datetime | None = None


class WriterWorkspaceOut(BaseModel):
    word_count_goals: WordCountGoalsOut
    goal_calendar: list[GoalCalendarItemOut]
    corkboard_cards: list[CorkboardCardOut]
    templates: list[WritingTemplateOut]
    publishing: PublishingPresetOut
    manuscript_front_matter: ManuscriptFrontMatterOut
    novel_preface: str = ""
    novel_front_matter: NovelFrontMatterOut = Field(default_factory=NovelFrontMatterOut)
    novel_epub_metadata: NovelEpubMetadataOut = Field(default_factory=NovelEpubMetadataOut)
    revision_board: RevisionBoardOut
    activation: ActivationStateOut = Field(default_factory=ActivationStateOut)
    editor_preferences: EditorPreferencesOut = Field(default_factory=EditorPreferencesOut)
    reading_themes: ReadingThemesOut = Field(default_factory=ReadingThemesOut)
    typewriter_mode: TypewriterModeOut = Field(default_factory=TypewriterModeOut)
    manuscript_layout: ManuscriptLayoutOut = Field(default_factory=ManuscriptLayoutOut)
    structure_tree: list[WorkspaceStructureNodeOut] = Field(default_factory=list)
    revision_rounds: list[dict[str, Any]] = Field(default_factory=list)
    reprocess: ReprocessMetadataOut = Field(default_factory=ReprocessMetadataOut)
    processing: BookProcessingOut | None = None
    index_format: str = "arabic"


class WordCountGoalsBody(BaseModel):
    chapter_target: int | None = None
    book_target: int | None = None
    session_target: int | None = None


class GoalCalendarItemBody(BaseModel):
    id: str | None = None
    title: str
    due_date: str
    quota_value: int | None = None
    quota_unit: str | None = None
    completed: bool = False


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


class EditorPreferencesBody(BaseModel):
    font_family: str | None = None
    font_size: int | None = None
    line_height: float | None = None
    manuscript_width: str | None = None
    show_page_guides: bool | None = None
    focus_mode: bool | None = None
    default_scene_separator: str | None = None


class ReadingThemesBody(BaseModel):
    active_theme: str | None = None
    allow_dark_mode: bool | None = None


class TypewriterModeBody(BaseModel):
    enabled: bool | None = None
    center_offset_px: int | None = None


class ManuscriptLayoutBody(BaseModel):
    margins: str | None = None
    page_size: str | None = None
    orientation: str | None = None
    show_headers: bool | None = None
    show_footers: bool | None = None
    page_numbering: bool | None = None
    different_first_page: bool | None = None


class WorkspaceStructureNodeBody(BaseModel):
    id: str
    label: str
    kind: str
    chapter_number: int | None = None
    scene_id: str | None = None
    children: list[WorkspaceStructureNodeBody] = Field(default_factory=list)


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


class NovelFrontMatterBody(BaseModel):
    dedication: str | None = Field(default=None, max_length=100_000)
    acknowledgements: str | None = Field(default=None, max_length=100_000)
    copyright_page: str | None = Field(default=None, max_length=100_000)
    about_author: str | None = Field(default=None, max_length=100_000)
    series_book_list: str | None = Field(default=None, max_length=100_000)


class NovelEpubMetadataBody(BaseModel):
    publisher: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, max_length=24)
    isbn: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=20_000)
    series_name: str | None = Field(default=None, max_length=500)
    series_number: str | None = Field(default=None, max_length=64)


class RevisionBoardItemStateBody(BaseModel):
    item_id: str
    status: str = "pending"
    assigned_version_id: str | None = None
    task_id: str | None = None
    updated_at: str | None = None
    decision: str | None = None
    action: str | None = None
    reason: str | None = None
    source_content_versions: dict[int, int] | None = None
    finding_snapshot: dict[str, Any] | None = None


class RevisionBoardBody(BaseModel):
    items: list[RevisionBoardItemStateBody] | None = None
    last_generated_at: str | None = None


class ActivationStateBody(BaseModel):
    completed_at: str | None = None
    completion_action: str | None = None
    completed_finding_id: str | None = None


class WriterWorkspaceBody(BaseModel):
    word_count_goals: WordCountGoalsBody | None = None
    goal_calendar: list[GoalCalendarItemBody] | None = None
    corkboard_cards: list[CorkboardCardBody] | None = None
    templates: list[WritingTemplateBody] | None = None
    publishing: PublishingPresetBody | None = None
    manuscript_front_matter: ManuscriptFrontMatterBody | None = None
    novel_preface: str | None = None
    novel_front_matter: NovelFrontMatterBody | None = None
    novel_epub_metadata: NovelEpubMetadataBody | None = None
    revision_board: RevisionBoardBody | None = None
    activation: ActivationStateBody | None = None
    editor_preferences: EditorPreferencesBody | None = None
    reading_themes: ReadingThemesBody | None = None
    typewriter_mode: TypewriterModeBody | None = None
    manuscript_layout: ManuscriptLayoutBody | None = None
    structure_tree: list[WorkspaceStructureNodeBody] | None = None
    reprocess: ReprocessMetadataBody | None = None
    index_format: str | None = None


class NovelPrefaceBody(BaseModel):
    preface: str = Field(default="", max_length=100_000)


class NovelSettingsBody(BaseModel):
    preface: str = Field(default="", max_length=100_000)
    front_matter: NovelFrontMatterBody = Field(default_factory=NovelFrontMatterBody)
    epub_metadata: NovelEpubMetadataBody = Field(default_factory=NovelEpubMetadataBody)


class RevisionEvidenceOut(BaseModel):
    chapter_ref: int
    source_label: str | None = None
    excerpt: str
    source_content_version: int


class RevisionActionItemOut(BaseModel):
    id: str
    category: str
    title: str
    description: str
    severity: str
    chapter_ref: int | None = None
    source_label: str | None = None
    recommendation: str | None = None
    status: str = "pending"
    assigned_version_id: str | None = None
    task_id: str | None = None
    why_flagged: str = ""
    evidence_strength: Literal["strong", "moderate", "limited"] = "limited"
    evidence: list[RevisionEvidenceOut] = Field(default_factory=list)
    is_stale: bool = False
    decision: str | None = None
    action: str | None = None
    reason: str | None = None


class RevisionActivationOut(BaseModel):
    eligible: bool = False
    completed: bool = False
    completed_at: str | None = None
    completion_action: str | None = None
    completed_finding_id: str | None = None


class RevisionFindingDecisionBody(BaseModel):
    decision: Literal["accepted", "dismissed", "resolved"]
    action: (
        Literal[
            "added_to_revision_plan",
            "saved_note",
            "manuscript_edit",
            "exported_report",
        ]
        | None
    ) = None
    reason: Literal["intentional", "incorrect", "not_relevant", "other"] | None = None


class RevisionGenreCheckOut(BaseModel):
    genre: str
    label: str
    checks: list[str] = Field(default_factory=list)
    rationale: str
    findings: list[RevisionActionItemOut] = Field(default_factory=list)


class RevisionPlanPassOut(BaseModel):
    title: str
    summary: str
    items: list[RevisionActionItemOut] = Field(default_factory=list)


class CharacterKnowledgeEntryOut(BaseModel):
    character_name: str
    chapter_learned: int | None = None
    source: str


class CharacterKnowledgeFactOut(BaseModel):
    fact: str
    chapter_ref: int | None = None
    entries: list[CharacterKnowledgeEntryOut] = Field(default_factory=list)
    warning: str | None = None


class CharacterKnowledgeTimelineCellOut(BaseModel):
    chapter_number: int
    state: str


class CharacterKnowledgeTimelineRowOut(BaseModel):
    character_name: str
    chapter_learned: int | None = None
    source: str
    cells: list[CharacterKnowledgeTimelineCellOut] = Field(default_factory=list)


class CharacterKnowledgeTimelineFactOut(BaseModel):
    fact: str
    rows: list[CharacterKnowledgeTimelineRowOut] = Field(default_factory=list)
    warning: str | None = None


class RevisionSummaryOut(BaseModel):
    hero_message: str
    active_item_count: int
    high_severity_count: int
    task_ready_count: int
    recent_edit_label: str | None = None


class RevisionIntelligenceOut(BaseModel):
    tagline: str
    summary: RevisionSummaryOut
    change_impacts: list[RevisionActionItemOut] = Field(default_factory=list)
    genre_checks: list[RevisionGenreCheckOut] = Field(default_factory=list)
    revision_plan: list[RevisionPlanPassOut] = Field(default_factory=list)
    knowledge_matrix: list[CharacterKnowledgeFactOut] = Field(default_factory=list)
    knowledge_timeline: list[CharacterKnowledgeTimelineFactOut] = Field(default_factory=list)
    scene_advice: list[RevisionActionItemOut] = Field(default_factory=list)
    confusion_map: list[RevisionActionItemOut] = Field(default_factory=list)
    voice_alerts: list[RevisionActionItemOut] = Field(default_factory=list)
    external_signals: list[RevisionActionItemOut] = Field(default_factory=list)
    priority_findings: list[RevisionActionItemOut] = Field(default_factory=list)
    activation: RevisionActivationOut = Field(default_factory=RevisionActivationOut)
    analysis_complete: bool = False
    continuity_status: Literal[
        "issues_found",
        "clean",
        "insufficient_evidence",
        "stale",
    ] = "insufficient_evidence"
    continuity_scan_id: uuid.UUID | None = None
    continuity_completed_at: datetime | None = None
    continuity_duration_ms: int | None = None
    coverage: dict[str, Any] = Field(default_factory=dict)
    stale_finding_count: int = 0
    analysis_limitations: list[str] = Field(default_factory=list)


class RevisionRoundCreateBody(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class RevisionRoundChapterOut(BaseModel):
    number: int
    title: str
    version_id: str | None = None
    content_version: int
    word_count: int


class RevisionRoundSummaryOut(BaseModel):
    chapter_count: int = 0
    word_count: int = 0
    scene_count: int = 0
    open_finding_count: int = 0
    high_severity_count: int = 0
    open_beta_feedback_count: int = 0


class RevisionRoundOut(BaseModel):
    id: str
    label: str
    note: str | None = None
    created_at: datetime
    chapters: list[RevisionRoundChapterOut] = Field(default_factory=list)
    summary: RevisionRoundSummaryOut = Field(default_factory=RevisionRoundSummaryOut)


class RevisionRoundListOut(BaseModel):
    items: list[RevisionRoundOut] = Field(default_factory=list)


class RevisionRoundComparisonOut(BaseModel):
    base_round_id: str
    target_round_id: str | None = None
    changed_chapters: list[int] = Field(default_factory=list)
    added_chapters: list[int] = Field(default_factory=list)
    removed_chapters: list[int] = Field(default_factory=list)
    chapter_delta: int = 0
    word_count_delta: int = 0
    scene_count_delta: int = 0
    open_finding_delta: int = 0
    open_beta_feedback_delta: int = 0


class WorkflowBridgeChapterPreviewOut(BaseModel):
    incoming_number: int
    incoming_title: str
    matched_chapter_number: int | None = None
    status: Literal["new", "changed", "unchanged"]
    incoming_word_count: int = 0
    current_word_count: int | None = None


class WorkflowBridgePreviewOut(BaseModel):
    format: str
    preview_token: str
    incoming_chapter_count: int
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    chapters: list[WorkflowBridgeChapterPreviewOut] = Field(default_factory=list)
    preserved_chapter_numbers: list[int] = Field(default_factory=list)


class ContinuityScanRequest(BaseModel):
    scope: Literal["full_book", "targeted"] = "full_book"
    chapter_numbers: list[int] = Field(default_factory=list, max_length=100)


class ContinuityEvidenceOut(BaseModel):
    observation_id: uuid.UUID
    role: str
    evidence_order: int
    subject_type: str
    subject_id: str | None = None
    subject_label: str
    predicate: str
    display_value: str
    chapter_number: int
    content_version: int
    excerpt: str
    confidence: float


class ContinuityFindingOut(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    book_id: uuid.UUID
    category: str
    severity: str
    confidence: float
    status: str
    title: str
    explanation: str
    recommendation: str | None = None
    subject_type: str
    subject_id: str | None = None
    subject_label: str
    detector_version: str
    content_versions: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    is_stale: bool = False
    decision: str | None = None
    action: str | None = None
    reason: str | None = None
    evidence: list[ContinuityEvidenceOut] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContinuityScanOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    scope: str
    status: str
    continuity_status: str
    detector_version: str
    chapter_versions: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    word_count: int = 0
    duration_ms: int | None = None
    cost_usd: float | None = None
    error_detail: str | None = None
    finding_count: int = 0
    stale_finding_count: int = 0
    findings: list[ContinuityFindingOut] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class ContinuityFindingDecisionBody(BaseModel):
    decision: Literal["accepted", "dismissed", "intentional", "resolved"]
    action: (
        Literal[
            "added_to_revision_plan",
            "saved_note",
            "manuscript_edit",
            "exported_report",
        ]
        | None
    ) = None
    reason: Literal["intentional", "incorrect", "not_relevant", "fixed", "other"] | None = None


class CanonFactOut(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    subject_type: str
    subject_id: str | None = None
    subject_label: str
    predicate: str
    normalized_value: str
    display_value: str
    chapter_number: int
    content_version: int
    evidence_excerpt: str
    confidence: float
    extractor_version: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    is_author_confirmed: bool = False


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
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EntityTagUpdateBody(BaseModel):
    entity_type: TagTargetLiteral
    entity_id: str | None = None
    chapter_number: int | None = Field(None, ge=1)
    tags: list[str] = Field(default_factory=list)


class EntityTagSetOut(BaseModel):
    entity_type: TagTargetLiteral
    entity_id: str
    chapter_number: int | None = None
    tags: list[str] = Field(default_factory=list)


class ManuscriptAnnotationBody(BaseModel):
    annotation_id: str | None = None
    chapter_number: int | None = Field(None, ge=1)
    category: str | None = None
    status: Literal["open", "resolved"] | None = None
    visibility: Literal["shared", "private"] | None = None
    quote: str | None = None
    comment: str | None = None
    anchor_context_before: str | None = None
    anchor_context_after: str | None = None
    start_offset: int | None = Field(None, ge=0)
    end_offset: int | None = Field(None, ge=0)


class ManuscriptAnnotationOut(BaseModel):
    id: str
    book_id: str
    book_title: str
    chapter_number: int
    chapter_title: str | None = None
    category: str
    status: str
    visibility: str
    quote: str
    comment: str
    anchor_context_before: str | None = None
    anchor_context_after: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    created_by_user_id: str
    created_by_label: str
    can_edit: bool
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VaultPreviewFileOut(BaseModel):
    path: str
    content: str


class VaultPreviewOut(BaseModel):
    root_folder: str
    files: list[VaultPreviewFileOut]


class VaultNoteBody(BaseModel):
    path: str
    content: str


class VaultNoteLinkBody(BaseModel):
    source_path: str
    target_path: str
    link_type: str = "reference"
    target_label: str | None = None


class VaultNoteOut(BaseModel):
    id: str
    book_id: str
    path: str
    source: str
    content: str
    created_at: datetime
    updated_at: datetime


class VaultNoteSaveOut(BaseModel):
    path: str
    source: str
    content: str
    persisted: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VaultNoteTagOut(BaseModel):
    id: str
    book_id: str
    note_id: str
    note_path: str
    tag_name: str
    created_at: datetime


class VaultNoteLinkOut(BaseModel):
    id: str
    book_id: str
    source_note_id: str
    source_note_path: str
    target_note_id: str
    target_note_path: str
    link_type: str
    target_label: str | None = None
    created_at: datetime


class VaultNoteSeriesLinkOut(BaseModel):
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


class VaultNoteLinkListOut(BaseModel):
    links: list[VaultNoteLinkOut]
    backlinks: list[VaultNoteLinkOut]
    tags: list[VaultNoteTagOut]
    series_links: list[VaultNoteSeriesLinkOut]


class SceneMetadataBody(BaseModel):
    pov: str | None = None
    timeline: str | None = None
    location: str | None = None
    tags: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    status_note: str | None = None
    anchors: list[str] = Field(default_factory=list)
    bookmarks: list[str] = Field(default_factory=list)
    summary: str | None = None


class SceneMetadataOut(BaseModel):
    pov: str | None = None
    timeline: str | None = None
    location: str | None = None
    tags: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    status_note: str | None = None
    anchors: list[str] = Field(default_factory=list)
    bookmarks: list[str] = Field(default_factory=list)
    summary: str | None = None


class NovelSceneBody(BaseModel):
    title: str
    description: str | None = None
    body: str
    html_body: str | None = None
    metadata: SceneMetadataBody | dict[str, Any] | None = None
    path: str | None = None
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
    metadata: dict[str, Any] | SceneMetadataOut = Field(default_factory=dict)
    path: str
    status: str
    sort_order: int
    source: str
    origin_chapter_number: int | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NovelSceneInsertBody(BaseModel):
    chapter_number: int
    position: Literal["start", "end"] = "end"


class ChapterSceneOrderUpdateBody(BaseModel):
    scene_ids: list[str] = Field(default_factory=list)
    expected_structure_version: int = Field(..., ge=0)


class WorkspaceChapterNodeOut(BaseModel):
    chapter_number: int
    title: str | None = None
    scene_count: int = 0
    structure_version: int = 0
    tags: list[str] = Field(default_factory=list)


class WorkspaceSceneGroupOut(BaseModel):
    id: str
    label: str
    chapter_number: int | None = None
    structure_version: int | None = None
    collapsed_by_default: bool = False
    scenes: list[NovelSceneOut] = Field(default_factory=list)


class ManuscriptWorkspaceTreeOut(BaseModel):
    chapters: list[WorkspaceChapterNodeOut] = Field(default_factory=list)
    scene_groups: list[WorkspaceSceneGroupOut] = Field(default_factory=list)
    note_paths: list[str] = Field(default_factory=list)
    structure_tree: list[WorkspaceStructureNodeOut] = Field(default_factory=list)
    scene_breadcrumbs: dict[str, list[WorkspaceBreadcrumbOut]] = Field(default_factory=dict)


class ChapterSceneOrderItemOut(BaseModel):
    id: str
    title: str
    sort_order: int


class ChapterSceneOrderOut(BaseModel):
    chapter_number: int
    structure_version: int
    scenes: list[ChapterSceneOrderItemOut] = Field(default_factory=list)


class VaultGraphNodeOut(BaseModel):
    id: str
    path: str
    title: str
    folder: str
    link_count: int = 0


class VaultGraphEdgeOut(BaseModel):
    source: str
    target: str
    label: str | None = None


class VaultGraphOut(BaseModel):
    nodes: list[VaultGraphNodeOut]
    edges: list[VaultGraphEdgeOut]


class WorkspaceSearchFiltersBody(BaseModel):
    chapter_number: int | None = Field(None, ge=1)
    scene_id: str | None = None
    pov: str | None = None
    location: str | None = None
    tags: list[str] = Field(default_factory=list)


class WorkspaceSearchBody(BaseModel):
    query: str = Field(default="", max_length=200)
    scopes: list[str] = Field(default_factory=lambda: ["manuscript", "scenes", "notes"])
    case_sensitive: bool = False
    whole_word: bool = False
    regex: bool = False
    filters: WorkspaceSearchFiltersBody = Field(default_factory=WorkspaceSearchFiltersBody)


class WorkspaceSearchResultOut(BaseModel):
    scope: str
    id: str
    title: str
    excerpt: str
    chapter_number: int | None = None
    scene_id: str | None = None
    note_path: str | None = None
    rank: float = 0


class WritingPeriodStatOut(BaseModel):
    words: int
    target_words: int | None = None
    progress_pct: int | None = None


class WritingHeatmapDayOut(BaseModel):
    date: str
    words: int


class WritingEntryOut(BaseModel):
    book_id: str | None = None
    chapter_number: int | None = None
    title: str
    words: int


class WritingDashboardStatsOut(BaseModel):
    today: WritingPeriodStatOut
    this_week: WritingPeriodStatOut
    this_month: WritingPeriodStatOut
    this_year: WritingPeriodStatOut
    last_24_hours: WritingPeriodStatOut
    last_7_days: WritingPeriodStatOut
    last_30_days: WritingPeriodStatOut
    last_year: WritingPeriodStatOut
    heatmap: list[WritingHeatmapDayOut] = Field(default_factory=list)
    entries_today: list[WritingEntryOut] = Field(default_factory=list)


class PublicUserStats(BaseModel):
    total_books_read: int
    total_words_read: int


class PrivateUserStats(BaseModel):
    total_uploads: int
    manuscript_uploads: int = 0
    worldbuilding_uploads: int = 0
    upload_limit: int | None = None
    uploads_remaining: int | None = None
    upload_limit_unlimited: bool = False
    active_analyzed_words: int = 0
    active_word_limit: int = 0
    active_words_remaining: int = 0
    monthly_processed_words: int = 0
    monthly_processed_word_limit: int = 0
    monthly_processed_words_remaining: int = 0
    source_storage_bytes: int = 0
    source_storage_limit_bytes: int = 0
    source_storage_remaining_bytes: int = 0
    allowances_enforced: bool = False
    total_token_consumption: int
    llm_request_count: int = 0
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    llm_total_tokens: int = 0
    total_chapters_tracked: int
    saved_quotes: int


class UserStatsOut(BaseModel):
    public: PublicUserStats
    private: PrivateUserStats
    writing: WritingDashboardStatsOut


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


WorkspaceStructureNodeOut.model_rebuild()
WorkspaceStructureNodeBody.model_rebuild()
ReaderBootstrapOut.model_rebuild()
ManuscriptBootstrapOut.model_rebuild()


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
