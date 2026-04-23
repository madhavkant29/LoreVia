export type BookStatus = "pending" | "processing" | "ready" | "failed"

export interface Book {
  id: string
  title: string
  author: string | null
  genre: string | null
  format: "pdf" | "epub" | "manual"
  status: BookStatus
  mode: "reader" | "author"
  source_kind?: string
  cover_url?: string | null
  total_chapters: number | null
  total_tokens?: number | null
  is_truncated?: boolean
  primary_series_id?: string | null
  series_name?: string | null
  series_order?: number | null
  is_public?: boolean
  public_description?: string | null
  copyright_warning?: boolean
  archived_at?: string | null
  hidden_at?: string | null
  created_at: string
  progress_pct?: number | null
  chapters_read_count?: number | null
  chapters_left?: number | null
  marked_complete_in_series?: boolean | null
}

export interface BookSeries {
  id: string
  name: string
  description: string | null
  created_at: string
  books: Book[]
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
  cover_url?: string | null
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
  html_content?: string | null
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

export interface BookNote {
  id: string
  book_id: string
  book_title: string
  chapter_number: number | null
  chapter_title: string | null
  title: string | null
  body: string
  created_at: string
  updated_at: string
}

export interface UserStats {
  public: {
    total_books_read: number
    total_words_read: number
  }
  private: {
    total_uploads: number
    total_token_consumption: number
    total_chapters_tracked: number
    saved_quotes: number
  }
}

export interface ChapterReportCharacter {
  id: string
  name: string
  role: string | null
  first_chapter: number | null
  arc_summary: string | null
}

export interface ChapterConsistencyReport {
  chapter_number: number
  chapter_title: string | null
  summary: string
  new_characters: ChapterReportCharacter[]
  relationship_changes: string[]
  plot_threads_opened: string[]
  plot_threads_resolved: string[]
  continuity_flags: string[]
}

export interface PreWritingCharacter {
  id: string
  name: string
  role: string | null
  last_seen_chapter: number | null
  arc_summary: string | null
}

export interface PreWritingThread {
  id: string
  title: string
  status: string
  introduced_at: number | null
  note: string | null
}

export interface PreWritingEvent {
  chapter_number: number
  chapter_title: string | null
  detail: string
}

export interface AuthorAlert {
  kind: string
  title: string
  body: string
  chapter_ref: number | null
}

export interface PreWritingCheck {
  upcoming_chapter: number
  active_characters: PreWritingCharacter[]
  unresolved_threads: PreWritingThread[]
  recent_events: PreWritingEvent[]
  alerts: AuthorAlert[]
}

export interface ChapterVersion {
  id: string
  chapter_number: number
  title: string | null
  word_count: number | null
  note: string | null
  created_at: string
}
