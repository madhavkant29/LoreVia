export interface Trait {
  value: string
  confidence: number      // 0.0-1.0
  type: "objective" | "subjective" | "abstract"
}

export interface TraitState {
  hair?: Trait; eyes?: Trait; face?: Trait; build?: Trait
  age?: Trait; distinguishing?: Trait
  [key: string]: Trait | undefined
}

export interface Character {
  id: string
  book_id: string
  name: string
  aliases: string[]
  alias_records?: CharacterAliasRecord[]
  role: "mc" | "sc" | "background" | null
  first_chapter: number
  last_seen_chapter?: number | null
  mention_count?: number
  status?: "alive" | "deceased"
  trait_state: TraitState
  description: string | null
  personality_tags: string[]
  goal?: string | null
  motivations: string[]
  fears: string[]
  lie_they_believe?: string | null
  backstory_wound?: string | null
  arc_type?: string | null
  archetype: string | null
  arc_summary: string | null
  character_type?: "complex" | "normal" | "gag" | "meme" | null
  character_type_score?: number | null
  subtype_scores?: Record<string, number>
  is_manual?: boolean
  tags?: string[]
  graph_visibility_override?: "include" | "exclude" | null
  analysis_metadata?: {
    persistence_reason?: string | null
    evidence_count?: number | null
    summary_quality?: string | null
    needs_review?: boolean
    rejected_duplicate_candidates?: string[]
    quality_flags?: string[]
    grounding_passage_count?: number
    confidence_band?: string | null
    user_curated?: boolean
    protected_from_repair?: boolean
    canonical_confidence?: number | null
    grounding_coverage?: number | null
    cluster_size?: number
    cluster_mention_count?: number
    resolver_status?: string | null
    review_note?: string | null
    visibility_state?: "visible" | "quarantined" | "noise" | null
    approval_state?: "approved" | "pending_review" | "rejected" | "protected" | null
    approval_source?: "manual_review" | "deterministic_auto" | "backfill_review" | "legacy_import" | null
    approval_reason_codes?: string[]
    dossier_summary?: Record<string, unknown> | null
    trust_tier?: "visible" | "review_only" | "repaired_noise" | null
    trust_reasons?: string[]
  }
  visibility_state?: "visible" | "quarantined" | "noise" | null
  approval_state?: "approved" | "pending_review" | "rejected" | "protected" | null
  approval_source?: "manual_review" | "deterministic_auto" | "backfill_review" | "legacy_import" | null
  approval_reason_codes?: string[]
  approval_updated_at?: string | null
  growth_events?: Array<{
    chapter?: number | null
    chapter_number?: number | null
    event?: string
    event_title?: string
    description?: string | null
    impact?: string | null
    impact_score?: number | null
    role?: string | null
    accomplishments?: string[]
    growth_direction?: string | null
    growth_magnitude?: number | null
    is_major?: boolean
    tone?: string | null
  }>
  relationship_summaries?: string[]
  arc_tracker?: {
    goal?: string | null
    motivation?: string | null
    motivations?: string[]
    fear?: string | null
    fears?: string[]
    lie_they_believe?: string | null
    wound_backstory?: string | null
    arc_type?: string | null
    first_appearance?: number | null
    major_turning_points?: Array<{
      chapter_number: number
      title: string
      description?: string | null
      impact_score?: number | null
      growth_direction?: string | null
      is_major?: boolean
    }>
    relationship_changes?: Array<{
      counterpart_id: string
      counterpart_name: string
      chapter_number: number
      to_chapter?: number | null
      type: string
      sentiment?: number | null
      description?: string | null
    }>
    contradictions?: string[]
    voice_markers?: string[]
    physical_description_history?: Array<{
      chapter_number: number
      trait: string
      label: string
      value: string
      previous_value?: string | null
    }>
    arc_timeline?: string[]
    diagnostics?: string[]
    latest_arc_note?: string | null
    summary?: string | null
  }
}

export interface CharacterAliasRecord {
  id: string
  book_id: string
  character_id: string
  alias_text: string
  normalized_alias: string
  alias_kind: string
  source: string
  confidence: number
  created_at: string
}

export interface CharacterShareResponse {
  share_url: string
  expires_in_minutes: number
}

export interface CharacterRelationship {
  with: string           // character_id
  type: string           // ally | enemy | romantic | family | political | mentor | rival
  sentiment: number | null
  description: string | null
}

export interface CharacterCandidate {
  id: string
  book_id: string
  chapter_number: number
  raw_name: string
  proposed_name: string
  normalized_name: string
  aliases: string[]
  matched_character_id?: string | null
  status: "pending" | "accepted" | "rejected" | "promoted" | "merged" | "suppressed"
  confidence: number
  reason_codes: string[]
  evidence: Record<string, unknown>
  cluster_names: string[]
  cluster_size: number
  cluster_mention_count: number
  resolver_status?: string | null
  resolver_reasons: string[]
  canonical_confidence?: number | null
  grounding_coverage?: number | null
  dossier_summary?: Record<string, unknown>
  snippets: string[]
  source_batch_key?: string | null
  created_at: string
  updated_at: string
}

export interface CharacterDuplicateSuggestion {
  id: string
  book_id: string
  primary_character_id: string
  secondary_character_id: string
  confidence: number
  reasons: string[]
  shared_evidence: Record<string, unknown>
  shared_cluster_keys: string[]
  shared_chapters: number[]
  embedding_similarity?: number | null
  primary_is_protected: boolean
  secondary_is_protected: boolean
  primary_is_manual: boolean
  secondary_is_manual: boolean
  primary_is_curated: boolean
  secondary_is_curated: boolean
  status: "pending" | "accepted" | "dismissed"
  dismissal_reason?: string | null
  auto_dismissed?: boolean
  created_at: string
  updated_at: string
}

export interface CharacterRepairPreview {
  book_id: string
  dry_run: boolean
  allow_merge_safe_pairs: boolean
  allow_demote_obvious_noise: boolean
  auto_merged?: number
  auto_aliases?: number
  auto_suppressed?: number
  blocked_suggestions?: number
  remaining_review_items?: number
  planned_merges: Array<[string, string]>
  planned_aliases?: Array<[string, string]>
  planned_demotions: string[]
  planned_suppressions?: string[]
  blocked_duplicate_suggestions?: string[]
  skipped_protected_merge_pairs: Array<[string, string]>
  skipped_protected_demotions: string[]
  updated_first_chapters: Record<string, number>
  updated_last_seen_chapters: Record<string, number>
  character_labels: Record<string, string>
  pending_duplicate_suggestions: number
  pending_relationship_candidates: number
  pending_character_candidates_suppressed: number
  pending_character_candidates_kept: number
  pending_relationship_candidates_suppressed: number
  pending_relationship_candidates_kept: number
  protected_manual_records_skipped: number
  unresolved_relationship_deltas: Record<string, number>
}

export interface CharacterRepairApplyResult {
  book_id: string
  auto_merged?: number
  auto_aliases?: number
  auto_suppressed?: number
  blocked_suggestions?: number
  remaining_review_items?: number
  merged_pairs: Array<[string, string]>
  planned_aliases?: Array<[string, string]>
  demoted_character_ids: string[]
  planned_suppressions?: string[]
  blocked_duplicate_suggestions?: string[]
  skipped_protected_merge_pairs: Array<[string, string]>
  skipped_protected_demotions: string[]
  pending_character_candidates_suppressed?: number
  pending_character_candidates_kept?: number
  pending_relationship_candidates_suppressed?: number
  pending_relationship_candidates_kept?: number
  suppressed_character_candidate_ids?: string[]
  suppressed_relationship_candidate_ids?: string[]
  first_chapter_recomputes: Record<string, number>
  last_seen_chapter_recomputes: Record<string, number>
  character_labels: Record<string, string>
  duplicate_suggestion_delta: Record<string, number>
  unresolved_relationship_deltas: Record<string, number>
}

export interface CharacterShadowRecord {
  id: string
  book_id: string
  name: string
  aliases: string[]
  role: "mc" | "sc" | "background" | null
  first_chapter: number
  last_seen_chapter?: number | null
  mention_count?: number | null
  analysis_metadata?: Character["analysis_metadata"]
  is_manual?: boolean
}

export interface CharacterRelationshipCandidate {
  id: string
  book_id: string
  chapter_number: number
  raw_character_a: string
  raw_character_b: string
  matched_character_a_id?: string | null
  matched_character_b_id?: string | null
  rel_type?: string | null
  sentiment?: number | null
  description?: string | null
  status: "pending" | "accepted" | "rejected" | "resolved" | "merged" | "suppressed"
  reason_codes: string[]
  evidence: Record<string, unknown>
  source_batch_key?: string | null
  created_at: string
  updated_at: string
}

export interface CharacterReviewResponse {
  candidates: CharacterCandidate[]
  duplicate_suggestions: CharacterDuplicateSuggestion[]
  relationship_candidates: CharacterRelationshipCandidate[]
  shadow_characters: CharacterShadowRecord[]
  decision_events: Array<{
    id: string
    book_id: string
    character_id: string
    actor_user_id?: string | null
    action: string
    visibility_state?: "visible" | "quarantined" | "noise" | null
    approval_state?: "approved" | "pending_review" | "rejected" | "protected" | null
    approval_source?: "manual_review" | "deterministic_auto" | "backfill_review" | "legacy_import" | null
    reason_codes: string[]
    evidence: Record<string, unknown>
    created_at: string
  }>
  auto_actions_summary?: Record<string, number>
  counts: {
    pending_candidates: number
    pending_duplicate_suggestions: number
    pending_relationship_candidates: number
  }
}

export interface CharacterIdentityDiagnostics {
  suppressed_count: number
  auto_merged_count: number
  auto_alias_count: number
  blocked_duplicate_count: number
  hidden_candidate_count: number
  suppression_reasons: Record<string, number>
  recent_identity_actions: Array<{
    id: string
    action_type: string
    source_character_id?: string | null
    target_character_id?: string | null
    surface_text?: string | null
    confidence: number
    reason?: string | null
    reversible: boolean
    created_at: string
  }>
}

export interface RelationshipGraph {
  nodes: Array<{ 
    id: string; 
    name: string; 
    role: string | null; 
    first_chapter: number;
    mention_count?: number;
    is_manual?: boolean;
    graph_visibility_override?: "include" | "exclude" | null;
    visibility_score?: number;
    visibility_reasons?: string[];
    description?: string | null;
    personality_tags?: string[];
    aliases?: string[];
    motivations?: string[];
    fears?: string[];
    archetype?: string | null;
    arc_summary?: string | null;
  }>
  edges: Array<{
    id?: string | null
    source: string
    target: string
    type: string
    sentiment: number | null
    description: string | null
    from_chapter?: number | null
    to_chapter?: number | null
    status?: "ongoing" | "ended"
  }>
  hidden_nodes?: Array<{
    id: string
    name: string
    role: string | null
    first_chapter: number
    mention_count: number
    is_manual?: boolean
    graph_visibility_override?: "include" | "exclude" | null
    visibility_score: number
    visibility_reasons: string[]
    connected_relationship_count: number
  }>
  total_edges?: number
  limit?: number
  offset?: number
  has_more?: boolean
}
