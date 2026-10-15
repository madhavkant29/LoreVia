import { normalizeBookRouteId } from "./bookRoutes"

export interface ReaderBookmark {
  bookId: string
  chapter: number
  chapterTitle: string | null
  scrollPct: number
  selectedText: string | null
  savedAt: string
}

export function parseReaderBookmark(raw: string | null, bookId: string, chapter: number): ReaderBookmark | null {
  try {
    const value = JSON.parse(raw ?? "null")
    if (!value || typeof value.bookId !== "string" || normalizeBookRouteId(value.bookId) !== normalizeBookRouteId(bookId)
      || value.chapter !== chapter || typeof value.scrollPct !== "number" || !Number.isFinite(value.scrollPct)) return null
    return { bookId, chapter, chapterTitle: typeof value.chapterTitle === "string" ? value.chapterTitle : null,
      scrollPct: Math.max(0, Math.min(1, value.scrollPct)), selectedText: null,
      savedAt: typeof value.savedAt === "string" ? value.savedAt : "" }
  } catch { return null }
}

export function readerFontSize(raw: string | null): number {
  const value = Number(raw)
  return raw?.trim() && Number.isFinite(value) ? Math.max(12, Math.min(32, Math.round(value))) : 20
}

export function chapterScrollFraction(scrollTop: number, contentHeight: number, viewportHeight: number): number {
  const maximum = contentHeight - viewportHeight
  return maximum > 0 ? Math.max(0, Math.min(1, scrollTop / maximum)) : 1
}
