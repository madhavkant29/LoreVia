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

export interface RelationshipGraph {
  nodes: Array<{ 
    id: string; 
    name: string; 
    role: string | null; 
    first_chapter: number;
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
  }>
}
