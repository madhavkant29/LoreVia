export interface Theory {
  theory: string
  confidence: number
  evidence: string[]
  reasoning: string
}

export interface GroundedAnswer {
  answer: string
  citations: GroundedCitation[]
  cached?: boolean
}

export interface GroundedCitation {
  chapter_num: number
  chapter_title: string | null
  excerpt: string
  source_type: "summary" | "passage"
  relevance?: number | null
}

export interface CrossBookMatch {
  left_book_id: string
  left_name: string
  right_book_id: string
  right_name: string
  similarity: number
  entry_type?: string | null
}

export interface CrossBookIntelligence {
  series_name: string | null
  comparison_book_ids: string[]
  character_matches: CrossBookMatch[]
  wiki_matches: CrossBookMatch[]
}

// ─── Story Advisor types ──────────────────────────────────────────────────────

export interface AdvisorMessage {
  role: "user" | "assistant"
  content: string
}

export interface AdvisorPassage {
  chapter_num: number
  chapter_title: string | null
  excerpt: string
  relevance: number
}

export interface AdvisorWorldAnalysis {
  mode: "gap_detection" | "story_integration" | string
  answer: string
  citations: Array<Record<string, unknown>>
  suggestions: Array<Record<string, unknown>>
  logic_alerts: Array<Record<string, unknown>>
  simulation_steps: string[]
}

export interface AdvisorResponse {
  reply: string
  intent: "plothole" | "direction" | "opportunity" | "consistency" | "general"
  response_type: "standard" | "warning" | "opportunity" | "tradeoff"
  retrieved_passages: AdvisorPassage[]
  world_analysis?: AdvisorWorldAnalysis | null
  cached?: boolean
}

export interface AdvisorAsyncAccepted {
  task_id: string
  status: "queued"
  cached?: boolean
}

export interface AdvisorTaskStatusResponse {
  task_id: string
  status: "queued" | "running" | "complete" | "failed"
  result: AdvisorResponse | null
  error?: string | null
}

export interface AdvisorGreeting {
  message: string
  book_title: string
  stats: {
    characters: number
    plot_threads: number
    total_chapters: number | null
  }
}

export type SuggestionSeverity = "warning" | "direction" | "opportunity" | "info"
export type SuggestionType =
  | "trait_contradiction"
  | "dropped_thread"
  | "character_absent"
  | "arc_opportunity"
  | "foreshadowing_opportunity"
  | "unresolved_clue"
  | "future_direction"
  | "manuscript_checkpoint"
  | "editorial_focus"
  | "event_conflict"
  | "relationship_flip"
  | "location_conflict"
  | "object_continuity"
  | "world_rule_conflict"
  | "role_drift"

export interface AdvisorSuggestion {
  id: string
  type: SuggestionType
  severity: SuggestionSeverity
  title: string
  description: string
  chapter_ref: number | null
  action_label: string
  ask_prompt: string
  source?: "heuristic" | "proactive_audit" | "fallback" | string
}

export interface AdvisorScanMeta {
  character_count: number
  state_count: number
  open_thread_count: number
  clue_count: number
  relationship_count: number
  world_element_count: number
  heuristic_count: number
  fallback_applied: boolean
  proactive_audit_applied: boolean
  scan_basis: string[]
  data_gaps: string[]
  audit_summary?: string | null
}

export interface AdvisorSuggestionsResponse {
  suggestions: AdvisorSuggestion[]
  total: number
  book_title: string
  meta: AdvisorScanMeta
  cached?: boolean
}


export interface AdvisorSuggestionScanResponse {
  job_id: string
  status: "queued"
  cached: boolean
}


export interface AdvisorSuggestionJobStatusResponse {
  job_id: string
  status: "queued" | "running" | "complete" | "failed"
  result: AdvisorSuggestionsResponse | null
  error: string | null
}

// ─── Editorial Review types ───────────────────────────────────────────────────

export interface EditorialContinuityIssue {
  type: "character_personality" | "character_trait" | "event_conflict" | "theme_drift" | "timeline"
  severity: "critical" | "moderate" | "minor"
  title: string
  description: string
  suggestion: string
}

export interface EditorialInsertionOpportunity {
  title: string
  problem: string
  target_chapter: number
  target_chapter_title: string | null
  anchor_excerpt: string
  what_to_add: string
  why_here: string
  purpose: "plothole_fix" | "characterization" | "backstory" | "foreshadowing"
}

export interface EditorialGrammarIssue {
  original: string
  issue: string
  fix: string
}

export interface EditorialReview {
  continuity_issues: EditorialContinuityIssue[]
  insertion_opportunities: EditorialInsertionOpportunity[]
  grammar_issues: EditorialGrammarIssue[]
  formatting_notes: string[]
  thematic_fit: {
    score: "strong" | "moderate" | "weak"
    notes: string
  }
  overall_verdict: string
}

export interface EditorialReviewPassage {
  chapter_num: number
  chapter_title: string | null
  chunk_index?: number
  excerpt: string
  relevance: number
}

export interface EditorialReviewResponse {
  review: EditorialReview
  retrieved_passages: EditorialReviewPassage[]
}

export interface SeriesContinuityReview {
  continuity_issues: Array<{ title: string; description: string; severity: string; suggestion?: string }>
  cross_book_opportunities: Array<{ title: string; description: string }>
  thematic_fit: { score: string; notes: string }
  overall_verdict: string
}

export interface SeriesContinuityPassage {
  book_title?: string
  chapter_num: number
  chapter_title?: string | null
  excerpt: string
  relevance: number
}

export interface SeriesContinuityResponse {
  review: SeriesContinuityReview
  retrieved_passages: SeriesContinuityPassage[]
  cached?: boolean
}

export interface ManuscriptSynopsis {
  spoiler_level: "minimal" | "none"
  synopsis: string
  focus_points: string[]
  coverage_chapters: number[]
}

export type ContinuityReportFormat = "pdf" | "md"

export interface VoiceConsistencyIssue {
  character_name: string
  severity: "critical" | "moderate" | "minor"
  title: string
  description: string
  evidence: string
  suggestion: string
  intentionality_prompt: string
}

export interface VoiceConsistencyReview {
  issues: VoiceConsistencyIssue[]
  overall_verdict: string
}

export interface VoiceConsistencyMatch {
  character_name: string
  match_score: number
  baseline_sample_size: number
  sample_dialogue_count: number
  strongest_signals: string[]
  closest_other_character?: string | null
  closest_other_score?: number | null
}

export interface VoiceConsistencyResponse {
  review: VoiceConsistencyReview
  retrieved_passages: EditorialReviewPassage[]
  characters_reviewed: string[]
  character_matches?: VoiceConsistencyMatch[]
  warnings: string[]
}

export interface ProseTightenResponse {
  tightened_text: string
  rationale: string[]
  changed: boolean
}

export interface WhatsTheWordResponse {
  word: string
  gloss: string
}

export interface InlineContinuityIssue {
  severity: string
  title: string
  snippet: string
  explanation: string
  suggestion: string
}

export interface InlineContinuityResponse {
  issues: InlineContinuityIssue[]
  memory_bank: string[]
  overall_verdict: string
}
