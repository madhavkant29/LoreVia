import { booksApi } from "@/lib/api/books"
import type { BookSelector, BookSeries, BookWorkType } from "@/types/book"
import type { SeriesWorldAnalysis } from "@/types/world-building"

export async function loadAllSeries(): Promise<BookSeries[]> {
  const rows = new Map<string, BookSeries>()
  let offset = 0
  for (;;) {
    const page = await booksApi.listSeries({ limit: 100, offset })
    if (!Array.isArray(page.items)) throw new Error("The series list is incomplete. Try refreshing it.")
    const previous = rows.size
    page.items.forEach((item) => rows.set(item.id, item))
    if (!page.has_more) return [...rows.values()]
    if (rows.size === previous || !Number.isSafeInteger(page.limit) || page.limit < 1) throw new Error("Series pagination did not advance. Try refreshing it.")
    offset += page.limit
  }
}

export async function loadSeriesProjects(): Promise<BookSelector[]> {
  const rows = new Map<string, BookSelector>()
  const seen = new Set<string>()
  let cursor: string | null = null
  do {
    const page = await booksApi.listPage(false, cursor, 100)
    if (!Array.isArray(page.items) || ("has_more" in page && page.has_more && !page.next_cursor)) throw new Error("Available projects are incomplete.")
    page.items.forEach((book) => rows.set(book.id, book))
    cursor = page.next_cursor
    if (cursor && seen.has(cursor)) throw new Error("Available project pagination did not advance.")
    if (cursor) seen.add(cursor)
  } while (cursor)
  return [...rows.values()]
}

export function positiveNumberError(value: string, label: string) {
  if (!value.trim()) return null
  return /^\d+$/.test(value.trim()) && Number.isSafeInteger(Number(value)) && Number(value) > 0 && Number(value) <= 2147483647 ? null : `${label} must be a whole number from 1 to 2,147,483,647, or blank.`
}

export function seriesVolumeLabel(workType?: BookWorkType, position?: number | null) {
  return position && position > 0 ? `${workType === "screenplay" ? "Episode" : "Volume"} ${position}` : "Unordered"
}

export function worldContextItems(analysis: SeriesWorldAnalysis) {
  if (typeof analysis.world_context === "string") return analysis.world_context.trim() ? [analysis.world_context] : []
  return (analysis.world_context ?? []).map((item) => typeof item === "string" ? item : [item.name || item.title, item.description].filter(Boolean).join(" — ") || "Untitled context")
}
