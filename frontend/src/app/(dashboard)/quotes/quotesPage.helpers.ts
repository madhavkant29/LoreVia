import type { SavedQuote } from "@/types/book"

export function filterQuotes(quotes: SavedQuote[], query: string, bookId: string) {
  const term = query.trim().toLocaleLowerCase()
  return quotes.filter((quote) => (!bookId || quote.book_id === bookId) && (!term ||
    [quote.book_title, quote.chapter_title, quote.character_name, quote.quote_text, quote.note, quote.chapter_number?.toString()]
      .filter(Boolean).some((text) => text!.toLocaleLowerCase().includes(term))))
}

export function quoteBooks(quotes: SavedQuote[]) {
  const books = new Map<string, string>()
  quotes.forEach((quote) => books.set(quote.book_id, quote.book_title?.trim() || "Untitled book"))
  return [...books].map(([id, title]) => ({ id, title })).sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id))
}

export function quoteSource(quote: SavedQuote) {
  const chapter = Number.isSafeInteger(quote.chapter_number) && quote.chapter_number! > 0 ? quote.chapter_number : null
  return {
    label: chapter ? `Chapter ${chapter}${quote.chapter_title ? ` · ${quote.chapter_title}` : ""}` : "Saved without a chapter",
    href: !quote.book_id ? null : chapter ? `/${encodeURIComponent(quote.book_id)}/chapter/${chapter}` as const : `/${encodeURIComponent(quote.book_id)}` as const,
    action: chapter ? `Open chapter ${chapter}` : "Open book",
  }
}

export function quoteSavedDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : { iso: date.toISOString(), label: date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) }
}
