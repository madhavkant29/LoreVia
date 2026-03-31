export type BookStatus = "pending" | "processing" | "ready" | "failed"

export interface Book {
  id: string
  title: string
  author: string | null
  genre: string | null
  format: "pdf" | "epub"
  status: BookStatus
  total_chapters: number | null
  total_tokens?: number | null
  is_truncated?: boolean
  archived_at?: string | null
  hidden_at?: string | null
  created_at: string
}

export interface SavedQuote {
  id: string
  book_id: string
  book_title: string
  chapter_number: number | null
  character_name: string | null
  quote_text: string
  note: string | null
  created_at: string
}
