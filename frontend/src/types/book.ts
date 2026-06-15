export type BookStatus = "pending" | "processing" | "ready" | "failed"
export type ProcessingStage = "queued" | "parsing" | "extracting" | "summarizing" | "embedding" | "analyzing" | "ready" | "failed"
export type SaveState = "saved" | "saving" | "offline_draft" | "retrying" | "error"
export type BookFormat = "pdf" | "epub" | "docx" | "doc" | "fountain" | "txt" | "md" | "manual"
export type BookWorkType = "novel" | "screenplay" | "other"
export type NovelExportPreset = "standard_novel" | "trade_novel" | "large_print" | "ebook_optimized"
export type NovelImagePlacement = "end" | "inline" | "plates"
export type RevisionTagTarget = "chapter" | "scene" | "character" | "note" | "comment" | "plot_thread" | "world_note"
export type WorkspaceShell = "reader" | "author"
export type BookAccessClass = "owner" | "author_collaborator" | "reader_collaborator"

import type { ChapterListResponse, ReadingProgress, SummaryCollectionResponse } from "./reader"
import type { Character } from "./character"
import type { ManuscriptSynopsis } from "./intelligence"

export interface Book {
  id: string
  title: string
  author: string | null
  genre: string | null
  format: BookFormat
  work_type: BookWorkType
  status: BookStatus
  mode: "reader" | "author"
  workspace_shell: WorkspaceShell
  access_class: BookAccessClass
  can_switch_workspace_mode: boolean
  source_kind?: string
  preserve_chapter_numbers?: boolean
  preserve_source_chapters?: boolean
  cover_url?: string | null
  total_chapters: number | null
  total_tokens?: number | null
  total_words?: number
  is_truncated?: boolean
  primary_series_id?: string | null
  series_name?: string | null
  series_order?: number | null
  is_public?: boolean
  public_status?: "draft" | "pending_review" | "published" | "hidden" | "removed" | string | null
  public_slug?: string | null
  published_at?: string | null
  public_updated_at?: string | null
  public_visibility?: string | null
  rights_confirmation?: boolean
  rights_confirmation_at?: string | null
  content_source_type?: "user_original" | "public_domain" | "licensed" | "admin_seeded" | string | null
  moderation_status?: "clean" | "reported" | "under_review" | "hidden" | "removed" | string | null
  moderation_reason?: string | null
  takedown_reason?: string | null
  takedown_at?: string | null
  public_upload_counted_at?: string | null
  source_title?: string | null
  source_author?: string | null
  source_public_domain_note?: string | null
  source_url?: string | null
  public_description?: string | null
  public_share_status?: "not_requested" | "pending" | "approved" | string | null
  public_share_requested_at?: string | null
  public_share_approved_at?: string | null
  copyright_warning?: boolean
  is_editor_project?: boolean
  archived_at?: string | null
  hidden_at?: string | null
  created_at: string
  progress_pct?: number | null
  chapters_read_count?: number | null
  chapters_left?: number | null
  marked_complete_in_series?: boolean | null
  processing?: BookProcessing | null
  collaboration_role?: CollaborationRole | null
  collaboration_scope?: CollaborationScope | null
  collaboration_permissions?: CollaborationPermissions | null
}

export interface BookOverviewPayload {
  book: Book
  progress: ReadingProgress
  chapter_list: ChapterListResponse
  summary_collection: SummaryCollectionResponse
}

export interface ReaderBootstrapPayload {
  overview: BookOverviewPayload
  notes: BookNote[]
  saved_quotes: SavedQuote[]
  stats: UserStats | null
  characters: Character[]
  chapter_reports: ChapterConsistencyReport[]
  prewriting_check: PreWritingCheck | null
  story_health: StoryHealth | null
  writer_workspace: WriterWorkspace | null
  revision_intelligence: RevisionIntelligence | null
}

export interface ManuscriptBootstrapPayload {
  book: Book
  characters: Character[]
  writer_workspace: WriterWorkspace | null
  emotional_arc: EmotionalArcOverview | null
  synopsis: ManuscriptSynopsis | null
  workspace_tree: ManuscriptWorkspaceTree | null
  annotations: ManuscriptAnnotation[]
  notes: BookNote[]
  vault_notes: VaultNote[]
  chapter_versions: ChapterVersion[]
  prewriting_check: PreWritingCheck | null
}

export type CollaborationRole =
  | "viewer"
  | "reader_only"
  | "commenter"
  | "editor"
  | "beta_reader"
  | "developmental_editor"
  | "coauthor"
  | "co_writer"

export interface CollaborationScope {
  chapter_start?: number | null
  chapter_end?: number | null
  character_bible: boolean
  continuity_report: boolean
  reader_confusion_report: boolean
}

export interface CollaborationPermissions {
  can_edit_manuscript: boolean
  can_view_story_bible: boolean
  can_run_ai_scans: boolean
  can_export: boolean
  can_comment: boolean
  can_view_selected_chapters_only: boolean
}

export interface BookCollaborator {
  id: string
  book_id: string
  email: string
  display_name?: string | null
  role: CollaborationRole
  scope: CollaborationScope
  permissions: CollaborationPermissions
  invite_status: "active" | "revoked" | string
  invited_at: string
  updated_at: string
}

export interface CollaboratorActivityItem {
  id: string
  kind: string
  title: string
  body?: string | null
  chapter_number?: number | null
  chapter_title?: string | null
  assignment_id?: string | null
  feedback_item_id?: string | null
  annotation_id?: string | null
  created_at: string
}

export interface CollaboratorActivity {
  collaborator: BookCollaborator
  assignments: import("./betaRead").BetaReadAssignment[]
  items: CollaboratorActivityItem[]
  chapter_comment_count: number
  annotation_count: number
  latest_activity_at?: string | null
}

export interface BookSeries {
  id: string
  name: string
  description: string | null
  created_at: string
  books: Book[]
}

export interface PaginatedSeries {
  items: BookSeries[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface SeriesBibleEpisode {
  book_id: string
  title: string
  episode_number?: number | null
  format: BookFormat
  work_type: BookWorkType
  total_scenes: number
  total_dialogue_lines: number
  total_words: number
  status: BookStatus | string
}

export interface SeriesBibleCharacter {
  name: string
  normalized_name: string
  episode_count: number
  total_mentions: number
  first_episode?: number | null
  last_episode?: number | null
  episodes: SeriesBibleEpisode[]
}

export interface SeriesBibleRelationship {
  characters: string[]
  relationship_type: string
  episode_count: number
  episodes: SeriesBibleEpisode[]
  note?: string | null
}

export interface SeriesBiblePlotThread {
  title: string
  status: string
  episode_count: number
  episodes: SeriesBibleEpisode[]
  note?: string | null
}

export interface SeriesBibleCanonEntry {
  name: string
  entry_type: string
  episode_count: number
  episodes: SeriesBibleEpisode[]
  description?: string | null
}

export interface SeriesBible {
  series_id: string
  name: string
  description?: string | null
  work_type: BookWorkType | string
  episode_count: number
  episodes: SeriesBibleEpisode[]
  recurring_characters: SeriesBibleCharacter[]
  recurring_relationships: SeriesBibleRelationship[]
  unresolved_plot_threads: SeriesBiblePlotThread[]
  canon_entries: SeriesBibleCanonEntry[]
  continuity_risks: string[]
}

export interface PublicChapterMeta {
  number: number
  title: string | null
  description: string | null
}

export interface PublicBook {
  id: string
  public_kind?: "public_demo" | "user_public_share"
  public_slug?: string | null
  title: string
  author: string | null
  author_username: string | null
  creator_display_name?: string | null
  genre: string | null
  description: string | null
  format: BookFormat
  work_type: BookWorkType
  status: BookStatus
  public_status?: string
  moderation_status?: string
  content_source_type?: "user_original" | "public_domain" | "licensed" | "admin_seeded" | string
  source_title?: string | null
  source_author?: string | null
  source_public_domain_note?: string | null
  source_url?: string | null
  cover_url?: string | null
  total_chapters: number | null
  copyright_warning?: boolean
  active_forum_post_id?: string | null
  analytics?: import("./public").PublicBookAnalytics | null
  ranking?: import("./public").PublicRankingMetadata | null
  created_at?: string
  published_at?: string | null
  public_updated_at?: string | null
}

export interface PublicBookDetail extends PublicBook {
  chapters: PublicChapterMeta[]
  visibility_notice?: string | null
  analytics?: import("./public").PublicBookAnalytics | null
}

export interface PublicChapter {
  book_id: string
  book_title: string
  chapter_number: number
  chapter_title: string | null
  chapter_description: string | null
  total_chapters: number | null
  text_url: string | null
  text_content?: string | null
  html_content?: string | null
}

export interface SavedQuote {
  id: string
  book_id: string
  book_title: string
  chapter_number: number | null
  chapter_title: string | null
  character_name: string | null
  quote_text: string
  note: string | null
  created_at: string
}

export interface BookNote {
  id: string
  book_id: string
  book_title: string
  chapter_number: number | null
  chapter_title: string | null
  title: string | null
  body: string
  tags?: string[]
  created_at: string
  updated_at: string
}

export interface RevisionTagSet {
  entity_type: RevisionTagTarget
  entity_id: string
  chapter_number?: number | null
  tags: string[]
}

export type ManuscriptAnnotationCategory =
  | "general"
  | "continuity"
  | "character"
  | "worldbuilding"
  | "pacing"
  | "line_edit"
  | "theme"

export interface ManuscriptAnnotation {
  id: string
  book_id: string
  book_title: string
  chapter_number: number
  chapter_title: string | null
  category: ManuscriptAnnotationCategory | string
  status: "open" | "resolved" | string
  visibility: "shared" | "private" | string
  quote: string
  comment: string
  anchor_context_before?: string | null
  anchor_context_after?: string | null
  start_offset?: number | null
  end_offset?: number | null
  created_by_user_id: string
  created_by_label: string
  can_edit: boolean
  resolved_at?: string | null
  created_at: string
  updated_at: string
}

export interface VaultPreviewFile {
  path: string
  content: string
}

export interface VaultPreview {
  root_folder: string
  files: VaultPreviewFile[]
}

export interface VaultNote {
  id: string
  book_id: string
  path: string
  source: string
  content: string
  created_at: string
  updated_at: string
}

export interface VaultNoteSaveResult {
  path: string
  source: string
  content: string
  persisted: boolean
  created_at: string | null
  updated_at: string | null
}

export interface VaultNoteLink {
  id: string
  book_id: string
  source_note_id: string
  source_note_path: string
  target_note_id: string
  target_note_path: string
  link_type: string
  target_label?: string | null
  created_at: string
}

export interface VaultNoteTag {
  id: string
  book_id: string
  note_id: string
  note_path: string
  tag_name: string
  created_at: string
}

export interface VaultNoteSeriesLink {
  id: string
  series_id: string
  source_book_id: string
  target_book_id: string
  source_note_id: string
  source_note_path: string
  target_note_id: string
  target_note_path: string
  link_type: string
  created_at: string
}

export interface VaultNoteRelations {
  links: VaultNoteLink[]
  backlinks: VaultNoteLink[]
  tags: VaultNoteTag[]
  series_links: VaultNoteSeriesLink[]
}

export interface VaultGraphNode {
  id: string
  path: string
  title: string
  folder: string
  link_count: number
}

export interface VaultGraphEdge {
  source: string
  target: string
  label?: string | null
}

export interface VaultGraph {
  nodes: VaultGraphNode[]
  edges: VaultGraphEdge[]
}

export interface UserStats {
  public: {
    total_books_read: number
    total_words_read: number
  }
  private: {
    total_uploads: number
    manuscript_uploads?: number
    worldbuilding_uploads?: number
    upload_limit?: number | null
    uploads_remaining?: number | null
    upload_limit_unlimited?: boolean
    total_token_consumption: number
    llm_request_count?: number
    llm_prompt_tokens?: number
    llm_completion_tokens?: number
    llm_total_tokens?: number
    total_chapters_tracked: number
    saved_quotes: number
  }
  writing: WritingDashboardStats
}

export interface WritingPeriodStat {
  words: number
  target_words?: number | null
  progress_pct?: number | null
}

export interface WritingHeatmapDay {
  date: string
  words: number
}

export interface WritingEntry {
  book_id?: string | null
  chapter_number?: number | null
  title: string
  words: number
}

export interface WritingDashboardStats {
  today: WritingPeriodStat
  this_week: WritingPeriodStat
  this_month: WritingPeriodStat
  this_year: WritingPeriodStat
  last_24_hours: WritingPeriodStat
  last_7_days: WritingPeriodStat
  last_30_days: WritingPeriodStat
  last_year: WritingPeriodStat
  heatmap: WritingHeatmapDay[]
  entries_today: WritingEntry[]
}

export interface ChapterReportCharacter {
  id: string
  name: string
  role: string | null
  first_chapter: number | null
  arc_summary: string | null
}

export interface ChapterConsistencyReport {
  chapter_number: number
  chapter_title: string | null
  summary: string
  new_characters: ChapterReportCharacter[]
  relationship_changes: string[]
  plot_threads_opened: string[]
  plot_threads_resolved: string[]
  continuity_flags: string[]
}

export interface StoryHealthMetric {
  label: string
  score: number
  detail: string
}

export interface StoryHealth {
  score: number
  status: string
  summary: string
  metrics: StoryHealthMetric[]
}

export interface PreWritingCharacter {
  id: string
  name: string
  role: string | null
  last_seen_chapter: number | null
  arc_summary: string | null
}

export interface PreWritingThread {
  id: string
  title: string
  status: string
  introduced_at: number | null
  note: string | null
}

export interface PreWritingEvent {
  chapter_number: number
  chapter_title: string | null
  detail: string
}

export interface AuthorAlert {
  kind: string
  title: string
  body: string
  chapter_ref: number | null
}

export interface PreWritingCheck {
  upcoming_chapter: number
  active_characters: PreWritingCharacter[]
  unresolved_threads: PreWritingThread[]
  recent_events: PreWritingEvent[]
  alerts: AuthorAlert[]
}

export interface ChapterVersion {
  id: string
  chapter_number: number
  title: string | null
  word_count: number | null
  note: string | null
  snapshot_kind?: string
  created_at: string
}

export interface ChapterVersionDetail extends ChapterVersion {
  text: string
  html: string | null
}

export interface SceneVersion {
  id: string
  scene_id?: string | null
  chapter_number?: number | null
  scene_title: string
  scene_path?: string | null
  word_count?: number | null
  note?: string | null
  snapshot_kind?: string
  created_at: string
}

export interface SceneVersionDetail extends SceneVersion {
  description?: string | null
  body: string
  html_body?: string | null
}

export interface WordCountGoals {
  chapter_target?: number | null
  book_target?: number | null
  session_target?: number | null
}

export interface CorkboardCard {
  id: string
  title: string
  description: string
  status: string
  lane: string
  chapter_number?: number | null
  template_id?: string | null
}

export interface WritingTemplate {
  id: string
  kind: string
  title: string
  description: string
  content: string
}

export interface PublishingPreset {
  active_preset: "standard_manuscript" | "trade_paperback" | "kdp_paperback"
  trim_size: string
  include_title_page: boolean
  mirror_margins: boolean
}

export interface EditorPreferences {
  font_family: string
  font_size: number
  line_height: number
  manuscript_width: "narrow" | "standard" | "wide"
  show_page_guides: boolean
  focus_mode: boolean
  default_scene_separator: "asterisks" | "hashes" | "divider"
}

export interface ReadingThemes {
  active_theme: "light" | "dark" | "sepia" | "paper"
  allow_dark_mode: boolean
}

export interface TypewriterModeSettings {
  enabled: boolean
  center_offset_px: number
}

export interface ManuscriptLayoutSettings {
  margins: "standard" | "wide" | "custom"
  page_size: string
  orientation: "portrait" | "landscape"
  show_headers: boolean
  show_footers: boolean
  page_numbering: boolean
  different_first_page: boolean
}

export interface WorkspaceStructureNode {
  id: string
  label: string
  kind: "book" | "part" | "arc" | "chapter" | "scene"
  chapter_number?: number | null
  scene_id?: string | null
  children: WorkspaceStructureNode[]
}

export interface WorkspaceBreadcrumb {
  id: string
  label: string
  kind: "book" | "part" | "arc" | "chapter" | "scene"
}

export interface SceneMetadata {
  pov?: string | null
  timeline?: string | null
  location?: string | null
  tags?: string[]
  mood?: string[]
  status_note?: string | null
  anchors?: string[]
  bookmarks?: string[]
  summary?: string | null
  [key: string]: unknown
}

export interface ManuscriptFrontMatter {
  author_name: string
  pen_name: string
  contact_email: string
  contact_phone: string
  contact_address: string
  title: string
  subtitle: string
  header_last_name: string
  header_title: string
  approximate_word_count_override?: number | null
  dedication: string
  acknowledgments: string
  epigraph: string
  prologue: string
  include_dedication: boolean
  include_acknowledgments: boolean
  include_epigraph: boolean
  include_prologue: boolean
}

export interface RevisionBoardItemState {
  item_id: string
  status: "pending" | "fixed" | "ignored" | "task_created" | string
  assigned_version_id?: string | null
  task_id?: string | null
  updated_at?: string | null
}

export interface RevisionBoard {
  items: RevisionBoardItemState[]
  last_generated_at?: string | null
}

export interface GoalCalendarItem {
  id: string
  title: string
  due_date: string
  quota_value?: number | null
  quota_unit?: string | null
  completed: boolean
}

export interface WriterWorkspace {
  word_count_goals: WordCountGoals
  goal_calendar: GoalCalendarItem[]
  corkboard_cards: CorkboardCard[]
  templates: WritingTemplate[]
  publishing: PublishingPreset
  manuscript_front_matter: ManuscriptFrontMatter
  novel_preface?: string
  novel_front_matter?: NovelFrontMatter
  novel_epub_metadata?: NovelEpubMetadata
  revision_board: RevisionBoard
  editor_preferences?: EditorPreferences
  reading_themes?: ReadingThemes
  typewriter_mode?: TypewriterModeSettings
  manuscript_layout?: ManuscriptLayoutSettings
  structure_tree?: WorkspaceStructureNode[]
  reprocess?: ReprocessMetadata
  processing?: BookProcessing | null
  index_format?: string
}

export interface NovelFrontMatter {
  dedication: string
  acknowledgements: string
  copyright_page: string
  about_author: string
  series_book_list: string
}

export interface NovelEpubMetadata {
  publisher: string
  language: string
  isbn: string
  description: string
  series_name: string
  series_number: string
}

export interface ReprocessMetadata {
  auto_reprocess_enabled: boolean
  pending_chapters: number[]
  last_mode_changed_at?: string | null
  last_manual_chapter_started_at?: string | null
  last_manual_chapter_number?: number | null
}

export interface RevisionActionItem {
  id: string
  category: string
  title: string
  description: string
  severity: "high" | "medium" | "low" | string
  chapter_ref?: number | null
  source_label?: string | null
  recommendation?: string | null
  status: "pending" | "fixed" | "ignored" | "task_created" | string
  assigned_version_id?: string | null
  task_id?: string | null
}

export interface RevisionGenreCheck {
  genre: string
  label: string
  checks: string[]
  rationale: string
  findings: RevisionActionItem[]
}

export interface RevisionPlanPass {
  title: string
  summary: string
  items: RevisionActionItem[]
}

export interface CharacterKnowledgeEntry {
  character_name: string
  chapter_learned?: number | null
  source: string
}

export interface CharacterKnowledgeFact {
  fact: string
  chapter_ref?: number | null
  entries: CharacterKnowledgeEntry[]
  warning?: string | null
}

export interface CharacterKnowledgeTimelineCell {
  chapter_number: number
  state: string
}

export interface CharacterKnowledgeTimelineRow {
  character_name: string
  chapter_learned?: number | null
  source: string
  cells: CharacterKnowledgeTimelineCell[]
}

export interface CharacterKnowledgeTimelineFact {
  fact: string
  rows: CharacterKnowledgeTimelineRow[]
  warning?: string | null
}

export interface RevisionIntelligenceSummary {
  hero_message: string
  active_item_count: number
  high_severity_count: number
  task_ready_count: number
  recent_edit_label?: string | null
}

export interface RevisionIntelligence {
  tagline: string
  summary: RevisionIntelligenceSummary
  change_impacts: RevisionActionItem[]
  genre_checks: RevisionGenreCheck[]
  revision_plan: RevisionPlanPass[]
  knowledge_matrix: CharacterKnowledgeFact[]
  knowledge_timeline: CharacterKnowledgeTimelineFact[]
  scene_advice: RevisionActionItem[]
  confusion_map: RevisionActionItem[]
  voice_alerts: RevisionActionItem[]
}

export interface NovelScene {
  id: string
  book_id: string
  chapter_id?: string | null
  chapter_number?: number | null
  title: string
  description?: string | null
  body: string
  html_body?: string | null
  metadata?: SceneMetadata
  path: string
  status: string
  sort_order: number
  source: string
  origin_chapter_number?: number | null
  tags?: string[]
  created_at: string
  updated_at: string
}

export interface WorkspaceChapterNode {
  chapter_number: number
  title?: string | null
  scene_count: number
  structure_version: number
  tags?: string[]
}

export interface WorkspaceSceneGroup {
  id: string
  label: string
  chapter_number?: number | null
  structure_version?: number | null
  collapsed_by_default: boolean
  scenes: NovelScene[]
}

export interface ManuscriptWorkspaceTree {
  chapters: WorkspaceChapterNode[]
  scene_groups: WorkspaceSceneGroup[]
  note_paths: string[]
  structure_tree?: WorkspaceStructureNode[]
  scene_breadcrumbs?: Record<string, WorkspaceBreadcrumb[]>
}

export interface WorkspaceSearchFilters {
  chapter_number?: number | null
  scene_id?: string | null
  pov?: string | null
  location?: string | null
  tags?: string[]
}

export interface WorkspaceSearchResult {
  scope: "manuscript" | "scenes" | "notes"
  id: string
  title: string
  excerpt: string
  chapter_number?: number | null
  scene_id?: string | null
  note_path?: string | null
  rank: number
}

export interface ChapterSceneOrder {
  chapter_number: number
  structure_version: number
  scenes: Array<{
    id: string
    title: string
    sort_order: number
  }>
}

export interface BookProcessing {
  status?: string | null
  stage?: ProcessingStage | string | null
  current_step_label?: string | null
  progress_pct?: number | null
  chapters_completed?: number | null
  chapters_total?: number | null
  eta_seconds?: number | null
  queue_wait_ms?: number | null
  last_chapter_number?: number | null
  last_chapter_title?: string | null
  started_at?: string | null
  updated_at?: string | null
  last_error?: string | null
  is_fully_ready?: boolean
  retry_actions?: string[]
  retry_available?: boolean
  pipeline?: {
    extraction?: ProcessingPipelineStage | null
    analysis?: ProcessingPipelineStage | null
  } | null
}

export interface ProcessingPipelineStage {
  status?: string | null
  completed_chapters?: number | null
  total_chapters?: number | null
  updated_at?: string | null
  eta_seconds?: number | null
  last_error?: string | null
  failed_chapters?: number[]
}

export interface OptimisticDraft<T> {
  id: string
  value: T
  saveState: SaveState
  updatedAt: string
  error?: string | null
}

export interface ReadabilityMetrics {
  words: number
  sentences: number
  paragraphs: number
  average_sentence_length: number
  reading_ease: number
  grade_level: number
  label: string
}

export interface EmotionalArcPoint {
  chapter_number: number
  label: string
  sentiment: number
  impact_score: number
  growth_direction: string
}

export interface EmotionalArcCharacter {
  character_id: string
  character_name: string
  role?: string | null
  arc_summary?: string | null
  trajectory_score: number
  points: EmotionalArcPoint[]
}

export interface EmotionalArcOverview {
  focus_character_count: number
  latest_turning_points: string[]
  characters: EmotionalArcCharacter[]
}

export interface MajorEvent {
  chapter_number: number
  chapter_title: string | null
  event_title: string
  description: string
  importance: number
  involved_characters?: string[] | null
  involved_character_names?: string[] | null
  event_type?: string | null
}

export interface CharacterEvent {
  character_id: string
  character_name: string
  chapter_number: number
  event_title: string
  description: string
  impact_score: number
  role?: string | null
  accomplishments: string[]
  growth_direction?: string
  growth_magnitude?: number
  is_major?: boolean
}

export interface BookEventsPaginated {
  items: BookEventsItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface BookEvents {
  major_events: MajorEvent[]
  character_events: CharacterEvent[]
}

export interface ChapterVersionRestoreStatus {
  id: string
  chapter_number: number
  restore_status: string | null
  restore_error: string | null
  restore_task_id: string | null
  restore_started_at: string | null
  restore_completed_at: string | null
}

// ── Import Preview ─────────────────────────────────────────────────────────

export type SectionType =
  | "title_page" | "copyright" | "dedication" | "toc" | "foreword"
  | "preface" | "acknowledgements" | "prologue" | "part" | "chapter"
  | "interlude" | "epilogue" | "afterword" | "appendix" | "glossary"
  | "notes" | "unknown"

export interface SectionMeta {
  id: string
  type: SectionType
  title: string
  number: number | null
  start_page: number | null
  end_page: number | null
  confidence: number
  include_in_analysis: boolean
}

export interface ImportWarning {
  message: string
  severity: "info" | "warning" | "error"
}

export interface ImportPreview {
  detected_language: string
  language_confidence: number
  title: string
  author: string
  sections: SectionMeta[]
  chapter_count: number
  toc_detected: boolean
  front_matter_count: number
  confidence: number
  warnings: ImportWarning[]
}

export interface BookEventsItem {
  type: "major" | "character"
  chapter_number: number
  chapter_title: string | null
  event_title: string
  description: string
  importance?: number
  involved_characters?: string[] | null
  involved_character_names?: string[] | null
  event_type?: string | null
  character_id?: string
  character_name?: string
  impact_score?: number
  role?: string | null
  accomplishments?: string[]
  growth_direction?: string
  growth_magnitude?: number
  is_major?: boolean
}

export interface BookEventsPaginated {
  items: BookEventsItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface BookEvents {
  major_events: MajorEvent[]
  character_events: CharacterEvent[]
}
