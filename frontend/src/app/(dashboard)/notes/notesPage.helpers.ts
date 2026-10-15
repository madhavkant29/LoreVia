import type { BookNote } from "@/types/book"
import { htmlToPlainText } from "@/lib/utils/richText"

export function indexNotes(notes: BookNote[]) {
  return notes.map((note) => {
    const plainText = htmlToPlainText(note.body ?? "").replace(/\s+/g, " ").trim()
    return { note, plainText, searchText: [note.title, note.book_title, note.chapter_title, plainText, ...(note.tags ?? [])].filter(Boolean).join(" ").toLocaleLowerCase() }
  })
}

export function filterNotes(notes: ReturnType<typeof indexNotes>, query: string, bookId: string) {
  const term = query.trim().toLocaleLowerCase()
  return notes.filter(({ note, searchText }) => (!bookId || note.book_id === bookId) && (!term || searchText.includes(term)))
}

export function noteBooks(notes: BookNote[]) {
  const books = new Map<string, string>()
  notes.forEach((note) => books.set(note.book_id, note.book_title?.trim() || "Untitled manuscript"))
  return [...books].map(([id, title]) => ({ id, title })).sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id))
}

export function noteUpdatedDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : { iso: date.toISOString(), label: date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) }
}

export function noteChapterHref(note: BookNote) {
  return note.book_id && Number.isSafeInteger(note.chapter_number) && note.chapter_number! > 0 ? `/${encodeURIComponent(note.book_id)}/chapter/${note.chapter_number}` as const : null
}
