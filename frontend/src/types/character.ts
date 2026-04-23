export interface Trait {
  value: string
  confidence: number      // 0.0–1.0
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
  motivations: string[]
  fears: string[]
  archetype: string | null
  arc_summary: string | null
  growth_events?: Array<{
    chapter?: number | null
    event: string
    impact?: string | null
    tone?: string | null
  }>
  relationship_summaries?: string[]
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
