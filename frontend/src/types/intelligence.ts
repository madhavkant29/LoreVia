export interface Theory {
  theory: string
  confidence: number
  evidence: string[]
  reasoning: string
}

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
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

export interface AdvisorResponse {
  reply: string
  intent: "plothole" | "direction" | "opportunity" | "consistency" | "general"
  response_type: "standard" | "warning" | "opportunity" | "tradeoff"
  retrieved_passages: AdvisorPassage[]
  cached?: boolean
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

export interface AdvisorSuggestion {
  id: string
  type: SuggestionType
  severity: SuggestionSeverity
  title: string
  description: string
  chapter_ref: number | null
  action_label: string
  ask_prompt: string
}

export interface AdvisorSuggestionsResponse {
  suggestions: AdvisorSuggestion[]
  total: number
  book_title: string
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

export interface VoiceConsistencyResponse {
  review: VoiceConsistencyReview
  retrieved_passages: EditorialReviewPassage[]
  characters_reviewed: string[]
}
