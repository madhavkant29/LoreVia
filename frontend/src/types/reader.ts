export type VisualMode = "off" | "minimal" | "full"
export type SummaryMode = "short" | "detailed" | "key_points"

export interface ChapterData {
  chapter_number: number
  chapter_title: string | null
  total_chapters?: number | null
  intelligence_available?: boolean
  text_url: string | null
  text_content?: string | null
  html_content?: string | null
  media?: ChapterMedia[]
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
  note: string | null
  character_ids: string[]
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
