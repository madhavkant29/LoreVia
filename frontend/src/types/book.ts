export type BookStatus = "pending" | "processing" | "ready" | "failed"

export interface Book {
  id: string
  title: string
  author: string | null
  genre: string | null
  format: "pdf" | "epub" | "manual"
  status: BookStatus
  total_chapters: number | null
  total_tokens?: number | null
  is_truncated?: boolean
  series_name?: string | null
  series_order?: number | null
  is_public?: boolean
  public_description?: string | null
  copyright_warning?: boolean
  archived_at?: string | null
  hidden_at?: string | null
  created_at: string
}

export interface PublicChapterMeta {
  number: number
  title: string | null
  description: string | null
}

export interface PublicBook {
  id: string
  title: string
  author: string | null
  genre: string | null
  description: string | null
  format: "pdf" | "epub" | "manual"
  status: BookStatus
  total_chapters: number | null
  copyright_warning?: boolean
  created_at?: string
}

export interface PublicBookDetail extends PublicBook {
  chapters: PublicChapterMeta[]
}

export interface PublicChapter {
  book_id: string
  book_title: string
  chapter_number: number
  chapter_title: string | null
  chapter_description: string | null
  total_chapters: number | null
  text_url: string | null
  text_content?: string | null
}

export interface SavedQuote {
  id: string
  book_id: string
  book_title: string
  chapter_number: number | null
  chapter_title: string | null
  character_name: string | null
  quote_text: string
  note: string | null
  created_at: string
}
