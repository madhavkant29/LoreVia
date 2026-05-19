export interface BetaReadAssignment {
  id: string
  book_id: string
  author_user_id: string
  reader_user_id?: string | null
  reader_email: string
  collaborator_id?: string | null
  state: string
  view_bucket: string
  task_label: string
  scope_kind: string
  section_label?: string | null
  chapter_start?: number | null
  chapter_end?: number | null
  window_days: number
  required_progress_pct: number
  required_comment_count: number
  required_feedback_item_count: number
  require_final_feedback: boolean
  starts_at: string
  expires_at: string
  access_granted_at: string
  submitted_at?: string | null
  completed_at?: string | null
  first_opened_at?: string | null
  missed_reason?: string | null
  counted_toward_missed_streak: boolean
  revoked_at?: string | null
  revoked_reason?: string | null
  disqualified_at?: string | null
  disqualified_reason?: string | null
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
  penalty_warning?: string | null
  final_rating?: number | null
  rating_sentiment?: string | null
  book_average_rating?: number | null
  book_rating_count: number
}

export interface BetaReadQuestion {
  id: string
  prompt: string
  created_at: string
  answer_count: number
}

export interface BetaReadFeedbackItem {
  id: string
  kind: string
  chapter_number?: number | null
  scene_id?: string | null
  scene_title?: string | null
  question_id?: string | null
  question_prompt?: string | null
  reaction?: string | null
  anchor_text?: string | null
  body?: string | null
  author_status: "open" | "resolved" | "archived" | "task_created" | string
  author_task_id?: string | null
  author_updated_at?: string | null
  created_at: string
  updated_at: string
}

export interface BetaReadFeedbackSummary {
  feedback_item_count: number
  chapter_comment_count: number
  scene_reaction_count: number
  answer_count: number
  confusing_count: number
  boring_count: number
  favorite_count: number
}

export interface BetaReadAssignmentDetail {
  assignment: BetaReadAssignment
  author_questions: BetaReadQuestion[]
  feedback_items: BetaReadFeedbackItem[]
  feedback_summary: BetaReadFeedbackSummary
}

export interface BetaReadAssignmentListResponse {
  items: BetaReadAssignment[]
}
