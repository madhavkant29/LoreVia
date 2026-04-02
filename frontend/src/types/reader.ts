export type VisualMode = "off" | "minimal" | "full"
export type SummaryMode = "short" | "detailed" | "key_points"

export interface ChapterData {
  chapter_number: number
  chapter_title: string | null
  total_chapters?: number | null
  intelligence_available?: boolean
  text_url: string | null
  text_content?: string | null
  characters: ChapterCharacter[]
}

export interface ChapterCharacter {
  id: string
  name: string
  aliases: string[]
  role: string | null
  first_chapter: number
  trait_state: Record<string, any>
  description?: string | null
  personality_tags: string[]
  motivations: string[]
}

export interface ContextResult {
  type: "character" | "search"
  character?: any
  relationships?: any[]
  results?: SearchResult[]
}

export interface SearchResult {
  text: string
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
}

export interface ChapterListResponse {
  read_upto: number
  current_chapter?: number
  chapters: ChapterListItem[]
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
  importance: number
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

export interface ChapterSummary {
  content: string
  key_events: Array<{ event: string; importance: number }> | null
  char_changes: Array<{ character: string; change: string }> | null
  clues: Array<{ clue: string; foreshadows: string }> | null
  pending?: boolean
}
