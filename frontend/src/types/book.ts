export type BookStatus = "pending" | "processing" | "ready" | "failed"

export interface Book {
  id: string
  title: string
  author: string | null
  genre: string | null
  format: "pdf" | "epub"
  status: BookStatus
  total_chapters: number | null
  created_at: string
}
