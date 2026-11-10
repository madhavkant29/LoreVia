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
  | "clue_review"
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
  evidence_excerpt?: string | null
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
  audit_failure_category?: "invalid_ai_response" | "ai_unavailable" | "database_unavailable" | "not_configured" | "capacity_busy" | "budget_exhausted" | null
  audit_groups_total?: number
  audit_groups_completed?: number
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
  progress?: { completed: number; total: number } | null
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
  finding_key?: string
  decision?: VoiceReviewDecision
  classification?: "confirmed" | "possible" | "justified_variation"
  severity: "critical" | "moderate" | "minor"
  title: string
  description: string
  submitted_excerpt?: string
  baseline_excerpt?: string
  baseline_chapter_number?: number
  confidence?: number
  revision_direction?: string
  evidence?: string
  suggestion?: string
  intentionality_prompt: string
}

export interface VoiceConsistencyReview {
  issues: VoiceConsistencyIssue[]
  overall_verdict: string
  status?: "complete" | "partial_evidence" | "insufficient_evidence"
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

export interface VoiceSourceCoverage {
  processed_ranges: Array<{ start: number; end: number }>
  unattributed_ranges?: Array<{ start: number; end: number }>
  compared_ranges?: Array<{ start: number; end: number }>
  not_compared_ranges?: Array<{ start: number; end: number }>
  unattributed_quoted_ranges?: Array<{ start: number; end: number }>
  total_characters: number
}

export interface VoiceConsistencyResponse {
  review: VoiceConsistencyReview
  voice_mode?: "dialogue" | "first_person_narration"
  retrieved_passages: EditorialReviewPassage[]
  characters_reviewed: string[]
  characters_detected?: string[]
  character_matches?: VoiceConsistencyMatch[]
  baseline_evidence?: Array<{ character_name: string; sample_count: number; word_count: number; chapters: number[]; attribution_confidence: "explicit" | "contextual" | "unattributed" | "user_selected_narrator"; baseline_attribution_confidence?: "explicit" | "contextual" | "unattributed" | "user_selected_narrator" | "unverified_narrator" }>
  warnings: string[]
  coverage?: VoiceSourceCoverage
  coverage_by_character?: Array<VoiceSourceCoverage & { character_name: string }>
  suppressed_findings?: VoiceConsistencyIssue[]
}

export interface VoiceChapterReviewResult {
  status: "complete" | "partial_evidence" | "insufficient_evidence"
  voices: Array<{
    character_id: string
    character_name: string
    voice_mode: "dialogue" | "first_person_narration"
    status: "complete" | "partial_evidence" | "insufficient_evidence"
    issues: VoiceConsistencyIssue[]
    warnings: string[]
    coverage: VoiceSourceCoverage
  }>
  coverage: VoiceSourceCoverage
  unreviewed_ranges: Array<{ start: number; end: number }>
  work_total: number
  work_completed: number
  narrator_identified: boolean
  narration_present?: boolean
}

export interface VoiceChapterReviewJob {
  job_id: string
  status: "queued" | "running" | "paused" | "complete" | "failed"
  chapter_number: number
  progress: { completed: number; total: number }
  next_resume_at: string | null
  result: VoiceChapterReviewResult | null
  error: string | null
}

export type VoiceReviewDecision = "intentional" | "incorrect" | "resolved"

export interface VoiceReviewDecisionResponse {
  finding_key: string
  decision: VoiceReviewDecision
  note: string | null
}

export type BetaReaderScope = "passage" | "chapter" | "chapter_range" | "full_book"
export type BetaReaderCheck = "repetition" | "voice" | "reader_feedback"
export type BetaReaderSeverity = "high" | "medium" | "low"

export interface BetaReaderAnalysisRequest {
  scope: BetaReaderScope
  text?: string | null
  chapter_number?: number | null
  chapter_start?: number | null
  chapter_end?: number | null
  character_ids?: string[]
  checks: BetaReaderCheck[]
}

export interface BetaReaderEvidence {
  chapter_number: number | null
  excerpt: string
}

export interface BetaReaderOverusedTerm {
  id: string
  term: string
  kind: "word" | "phrase"
  count: number
  rate_per_1000: number
  narration_count: number
  dialogue_count: number
  burst_detected: boolean
  chapter_counts: Record<string, number>
  evidence: BetaReaderEvidence[]
}

export interface BetaReaderVoice {
  id: string
  character_id: string
  character_name: string
  distinctness_score: number | null
  confidence: "high" | "medium" | "low" | "insufficient"
  sample_dialogue_count: number
  sample_word_count: number
  closest_character_id: string | null
  closest_character_name: string | null
  similarity_score: number | null
  signals: Record<string, number>
  shared_signals: string[]
  shared_phrases: string[]
}

export interface BetaReaderFinding {
  id: string
  category: string
  severity: BetaReaderSeverity
  title: string
  description: string
  chapter_number: number | null
  evidence: BetaReaderEvidence[]
  recommendation: string
  reader_question: string | null
}

export interface BetaReaderRevisionCandidate {
  id: string
  source_item_id: string
  category: string
  severity: BetaReaderSeverity
  title: string
  description: string
  recommendation: string
  chapter_number: number | null
  evidence: BetaReaderEvidence[]
}

export interface BetaReaderReport {
  report_id: string
  scope: BetaReaderScope
  request_hash: string
  source_fingerprint: string
  created_at: string
  is_stale: boolean
  checks: BetaReaderCheck[]
  coverage: {
    requested_chapters: number[]
    analyzed_chapters: number[]
    missing_chapters: number[]
    word_count: number
    character_count: number
  }
  overall_impression: string
  reader_vibe?: string
  story_understanding?: string
  strengths: string[]
  reader_questions: string[]
  prioritized_revisions: string[]
  overused_terms: BetaReaderOverusedTerm[]
  character_voices: BetaReaderVoice[]
  findings: BetaReaderFinding[]
  revision_candidates: BetaReaderRevisionCandidate[]
  warnings: string[]
}

export interface BetaReaderRunResponse {
  status: "queued" | "complete"
  task_id: string | null
  cached: boolean
  report: BetaReaderReport | null
}

export interface BetaReaderJobResponse {
  task_id: string
  status: "queued" | "running" | "complete" | "failed"
  progress: {
    stage: string
    completed: number
    total: number
    message: string
  } | null
  report: BetaReaderReport | null
  error: string | null
}

export interface BetaReaderReportsResponse {
  reports: BetaReaderReport[]
}

export interface BetaReaderRevisionTaskResponse {
  task_id: string
  candidate_id: string
  created: boolean
}

export interface FirstImpressionResponse {
  status: "not_started" | "queued" | "running" | "complete" | "failed"
  task_id: string | null
  progress: {
    stage: string
    completed: number
    total: number
    message: string
  } | null
  report: BetaReaderReport | null
  error: string | null
  can_retry: boolean
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
