export type SeriesWorldContextItem = string | {
  name?: string
  title?: string
  description?: string
  [key: string]: unknown
}

export interface SeriesWorldAnalysis {
  book_count?: number
  analysis_count?: number
  world_context?: SeriesWorldContextItem[]
}

export interface WorldBuildingDocument {
  id: string
  book_id: string
  title: string
  source_name?: string | null
  word_count?: number | null
  is_active: boolean
  archived_at?: string | null
  created_at: string
  updated_at: string
}

export interface WorldBuildingDocumentDetail extends WorldBuildingDocument {
  text: string
  html?: string | null
}

export interface WorldElement {
  id: string
  book_id: string
  series_id?: string | null
  world_document_id?: string | null
  source_scope: string
  element_type: string
  name: string
  description?: string | null
  parent_element_id?: string | null
  dependencies: Array<Record<string, unknown> | string>
  usage_count: number
  gap_score?: number | null
  integration_score?: number | null
  suggestions: Record<string, unknown>[]
  edited_by_author: boolean
  is_series_canonical: boolean
  created_at: string
  updated_at: string
  chapter_number?: number | null
  chapter_title?: string | null
  world_document_title?: string | null
  canonical_name?: string | null
  aliases: string[]
  confidence?: number | null
  provenance: Record<string, unknown>[]
  claims: Record<string, unknown>[]
  chapter_numbers: number[]
  chapter_count: number
  summary_mentions: number
  presence_score?: number | null
  narrative_modes: string[]
  source_excerpt?: string | null
  character_id?: string | null
  author_override: boolean
}

export interface WorldGapItem {
  id: string
  category: string
  severity: string
  title: string
  description: string
  suggested_fix: string
  world_evidence?: string | null
  story_evidence?: string | null
  world_document_id?: string | null
  world_document_title?: string | null
  story_chapter_number?: number | null
  story_chapter_title?: string | null
  character_name?: string | null
  priority: number
  entity_type?: string | null
  canonical_name?: string | null
  confidence: number
  provenance: Record<string, unknown>
}

export interface WorldGapGroup {
  key: string
  label: string
  description?: string | null
  items: WorldGapItem[]
}

export interface WorldGapResult {
  mode: string
  generated_at?: string | null
  gap_categories: Record<string, WorldGapItem[]>
  gap_groups: WorldGapGroup[]
  priority_gaps: WorldGapItem[]
  consistency_flags: Record<string, unknown>[]
  world_elements: WorldElement[]
  world_documents: WorldBuildingDocument[]
}

export interface WorldIntegrationOpportunity {
  id: string
  element_name: string
  element_type: string
  description: string
  suggestions: string[]
  target_chapter?: number | null
  target_chapter_title?: string | null
  priority: number
  world_document_id?: string | null
  world_document_title?: string | null
}

export interface WorldIntegrationResult {
  mode: string
  generated_at?: string | null
  integration_opportunities: WorldIntegrationOpportunity[]
  consistency_flags: Record<string, unknown>[]
  world_elements: WorldElement[]
  world_documents: WorldBuildingDocument[]
  dependency_graph?: Record<string, unknown>[]
}

export interface WorldQueryResponse {
  mode: string
  answer: string
  citations: Array<Record<string, unknown>>
  suggestions: Array<Record<string, unknown>>
  logic_alerts: Array<Record<string, unknown>>
  simulation_steps: string[]
}

export interface WikiEntry {
  id: string
  book_id: string
  entry_type: string
  name: string
  description?: string | null
  first_mention?: number | null
  related_char_ids?: string[] | null
  created_at: string
}

export interface WikiGenerationResponse {
  generated_count: number
  updated_names: string[]
  entries: WikiEntry[]
}

export interface WorldNote {
  id: string
  book_id: string
  world_element_id?: string | null
  world_document_id?: string | null
  note_type: string
  chapter_number?: number | null
  title?: string | null
  body: string
  priority: string
  status: string
  linked_gap_id?: string | null
  linked_integration_id?: string | null
  context_label?: string | null
  suggested_fix?: string | null
  tags?: string[]
  created_at: string
  updated_at: string
  addressed_at?: string | null
}

export interface CanonOverride {
  id: string
  canonical_name: string
  aliases: string[]
  entity_type?: string | null
  notes?: string | null
  created_at: string
  updated_at: string
}

export interface WorldBuildingBootstrapPayload {
  documents: WorldBuildingDocument[]
  selected_document?: WorldBuildingDocumentDetail | null
  notes: WorldNote[]
  canon_overrides: CanonOverride[]
  elements: WorldElement[]
  wiki: WikiEntry[]
  stats?: import("./book").UserStats | null
  gap_analysis?: WorldGapResult | null
}
