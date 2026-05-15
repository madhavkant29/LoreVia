export type VisualMode = "off" | "minimal" | "full"
export type SummaryMode = "short" | "detailed" | "key_points"
export type ReaderDisplayStyle = "relaxed" | "published"
export type BetaReadViewBucket = "active" | "scheduled" | "completed" | "missed"

export interface ChapterData {
  chapter_number: number
  chapter_title: string | null
  content_version?: number | null
  total_chapters?: number | null
  intelligence_available?: boolean
  can_copy_manuscript?: boolean
  text_url: string | null
  text_content?: string | null
  html_content?: string | null
  media?: ChapterMedia[]
  tags?: string[]
  characters: ChapterCharacter[]
}

export interface ChapterMedia {
  marker: string
  asset_type: string
  content_type: string | null
  caption: string | null
  sort_order: number
  url: string | null
  content_base64: string | null
}

export interface ChapterCharacter {
  id: string
  name: string
  aliases: string[]
  role: string | null
  first_chapter: number
  description?: string | null
  personality_tags: string[]
}

export interface ContextResult {
  type: "character" | "search"
  character?: any
  relationships?: any[]
  results?: SearchResult[]
}

export interface SearchResult {
  text: string
  summary: string
  chunk_index?: number
  chapter_num: number
  chapter_title: string | null
  relevance: number
}

export interface ChapterListItem {
  number: number
  title: string | null
  processed: boolean
  intelligence_available?: boolean
  read: boolean
  tags?: string[]
}

export interface ChapterListResponse {
  read_upto: number
  current_chapter?: number
  chapters: ChapterListItem[]
}

export interface ReadingProgress {
  current_chapter: number
  scroll_pct: number
  chapters_read_count: number
  percent_complete: number
  chapters_left: number
}

export interface RecallResponse {
  recall: string | null
  last_chapter?: number | null
  cached?: boolean
}

export interface BetaReadAssignment {
  id: string
  book_id: string
  author_user_id: string
  reader_user_id: string | null
  reader_email: string
  collaborator_id: string | null
  state: string
  view_bucket: BetaReadViewBucket
  task_label: string
  scope_kind: string
  section_label: string | null
  chapter_start: number | null
  chapter_end: number | null
  window_days: number
  reward_points: number
  projected_reward_points: number
  awarded_points: number
  required_progress_pct: number
  required_comment_count: number
  required_feedback_item_count: number
  require_final_feedback: boolean
  starts_at: string
  expires_at: string
  access_granted_at: string
  submitted_at: string | null
  completed_at: string | null
  awarded_at: string | null
  first_opened_at: string | null
  missed_reason: string | null
  counted_toward_missed_streak: boolean
  revoked_at: string | null
  revoked_reason: string | null
  disqualified_at: string | null
  disqualified_reason: string | null
  book_title: string
  author_name: string
  book_route_title: string
  progress_pct: number
  chapters_total: number
  chapters_read_count: number
  comment_count: number
  feedback_item_count: number
  question_count: number
  answered_question_count: number
  current_chapter: number
  status_label: string
  primary_action: string
  submission_allowed: boolean
  is_overdue: boolean
  consecutive_missed_beta_reads: number
  penalty_status: string
  penalty_warning: string | null
  final_rating: number | null
  rating_sentiment: string | null
  book_average_rating: number | null
  book_rating_count: number
}

export interface BetaReadAssignmentListResponse {
  items: BetaReadAssignment[]
}

export interface BetaReadAssignmentCreateInput {
  readerEmail: string
  taskLabel: string
  scopeKind?: "full_book" | "chapter_range" | "section"
  sectionLabel?: string | null
  chapterStart?: number | null
  chapterEnd?: number | null
  windowDays: number
  rewardPoints: number
  requiredProgressPct?: number
  requiredCommentCount?: number
  requiredFeedbackItemCount?: number
  requireFinalFeedback?: boolean
  startsAt?: string | null
  authorQuestions?: string[]
}

export interface SummaryCollectionItem {
  chapter_number: number
  chapter_title: string | null
  read: boolean
  available: boolean
  content: string | null
  key_events: Array<{ event: string; importance: number }>
}

export interface SummaryCollectionResponse {
  read_upto: number
  summaries: SummaryCollectionItem[]
}

export interface PlotThread {
  id: string
  title: string
  type: string | null
  status: string
  description: string | null
  introduced_at: number | null
  resolved_at: number | null
  first_mentioned: number | null
  last_mentioned: number | null
  mention_count: number
  importance: number
  note: string | null
  character_ids: string[]
  related_characters: string[]
  risk: string | null
  suggested_action: string | null
  tags?: string[]
}

export interface ForeshadowingItem {
  chapter_number: number
  chapter_title: string | null
  clue: string
  foreshadows: string | null
}

export interface TimelineEvent {
  chapter_number: number
  chapter_title: string | null
  kind: string
  title: string
  detail: string | null
}

export interface TimelineChapter {
  number: number
  title: string | null
}

export interface CharacterTimelineTrack {
  id: string
  name: string
  role: string | null
  start_chapter: number
  end_chapter: number
  detail: string | null
}

export interface PlotThreadTimelineTrack {
  id: string
  title: string
  status: string
  start_chapter: number
  end_chapter: number
  note: string | null
  detail: string | null
}

export interface RelationshipTimelineMarker {
  id: string
  title: string
  chapter_number: number
  detail: string | null
}

export interface TimelineResponse {
  chapters: TimelineChapter[]
  events: TimelineEvent[]
  character_tracks: CharacterTimelineTrack[]
  thread_tracks: PlotThreadTimelineTrack[]
  relationship_markers: RelationshipTimelineMarker[]
}

export interface ThematicSearchResult {
  chapter_number: number
  chapter_title: string | null
  score: number
  summary: string | null
}

export interface RelationshipEvolutionPair {
  characters: string[]
  events: Array<{
    chapter: number
    type: string
    description: string | null
    sentiment: number | null
  }>
}

export interface RelationshipGraphNode {
  id: string
  name: string
  role?: string | null
  degree?: number
}

export interface RelationshipGraphEdge {
  id?: string | null
  source: string
  target: string
  type: string
  description?: string | null
  sentiment?: number | null
  from_chapter?: number | null
  to_chapter?: number | null
}

export interface RelationshipGraph {
  nodes: RelationshipGraphNode[]
  edges: RelationshipGraphEdge[]
}

export interface ChapterSummary {
  content: string
  key_events: Array<{ event: string; importance: number }> | null
  char_changes: Array<{ character: string; change: string }> | null
  clues: Array<{ clue: string; foreshadows: string }> | null
  pending?: boolean
}
