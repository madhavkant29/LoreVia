import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"

export function bookCacheKey(bookId: string, scope: string) {
  return `book:${normalizeBookRouteId(bookId)}:${scope}`
}

export function readerCacheKey(bookId: string, chapterNumber: number): readonly [string, string, string]
export function readerCacheKey(bookId: string, scope: string): string
export function readerCacheKey(bookId: string, scopeOrChapter: string | number): string | readonly [string, string, string] {
  const normalized = normalizeBookRouteId(bookId)
  if (typeof scopeOrChapter === "number") {
    return ["reader", normalized, String(scopeOrChapter)] as const
  }
  return `reader:${normalized}:${scopeOrChapter}`
}

export function booksListCacheKey(includeHidden = false) {
  return `books:list:${includeHidden ? "all" : "active"}`
}

export function booksPageCacheKey(includeHidden = false) {
  return `books:page:${includeHidden ? "all" : "active"}`
}

export function booksSelectorCacheKey(includeHidden = false) {
  return `books:selector:${includeHidden ? "all" : "active"}`
}

export function booksStatsCacheKey() {
  return "books:stats"
}

export function booksQuotesCacheKey() {
  return "books:quotes"
}

export function booksNotesCacheKey() {
  return "books:notes"
}

export function booksSeriesCacheKey() {
  return "books:series"
}

export function booksSeriesBibleCacheKey(seriesId: string) {
  return `books:series-bible:${seriesId}`
}

export function readerUpcomingBetaReadsCacheKey() {
  return "reader:beta-reads:upcoming"
}

export function notificationsCacheKey(limit: number) {
  return `notifications:list:${limit}`
}

export function socialConversationsCacheKey() {
  return "social:conversations"
}

export function socialRelationshipsCacheKey() {
  return "social:relationships"
}

export function asQueryKey(key: string) {
  return [key] as const
}
