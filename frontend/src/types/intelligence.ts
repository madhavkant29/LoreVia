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
