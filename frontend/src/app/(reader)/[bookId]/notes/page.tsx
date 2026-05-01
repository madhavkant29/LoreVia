"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { ObsidianNotesEditor } from "@/components/reader/ObsidianNotesEditor"
import { booksApi } from "@/lib/api/books"
import { renderRichTextHtml } from "@/lib/utils/richText"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, BookNote, ObsidianGraph, ObsidianVaultNote } from "@/types/book"

export default function BookNotesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [book, setBook] = useState<Book | null>(null)
  const [bookNotes, setBookNotes] = useState<BookNote[]>([])
  const [notes, setNotes] = useState<ObsidianVaultNote[]>([])
  const [graph, setGraph] = useState<ObsidianGraph>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void Promise.all([
      booksApi.get(bookId),
      booksApi.getBookNotes(bookId),
      booksApi.listObsidianNotes(bookId),
      booksApi.getObsidianGraph(bookId),
    ]).then(([bookData, bookNotesData, notesData, graphData]) => {
      if (!active) return
      setBook(bookData)
      setBookNotes(bookNotesData)
      setNotes(notesData)
      setGraph(graphData)
      setLoading(false)
    }).catch(() => {
      if (!active) return
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [bookId])

  return (
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#010409_0%,#07111c_50%,#0b1523_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#f6f3ea_0%,#eef5ef_50%,#eef3f8_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-7xl px-4 pb-20 pt-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.3em] ${isDark ? "text-emerald-300" : "text-emerald-600"}`}>Obsidian Notes Workspace</p>
              <h1 className={`mt-2 font-serif text-4xl tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{book?.title || "Notes"}</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`/${bookId}`} className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/5 text-slate-200" : "bg-white text-stone-700"}`}>Back to overview</Link>
            <Link href={`/${bookId}/manuscript`} className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-white" : "bg-stone-900 text-white"}`}>Open manuscript</Link>
          </div>
        </div>

        {loading ? (
            <div className={`rounded-[1.8rem] border border-dashed py-24 text-center ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>Loading Obsidian notes workspace...</div>
        ) : (
          <div className="space-y-8">
            <ObsidianNotesEditor
              bookId={bookId}
              bookTitle={book?.title || "book"}
              initialNotes={notes}
              initialGraph={graph}
              isDark={isDark}
            />

            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/82"}`}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Existing notes</p>
                  <h2 className={`mt-2 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Chapter-linked manuscript notes</h2>
                  <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    Your original manuscript notes still live here. The Obsidian vault is additive, not a replacement.
                  </p>
                </div>
                <Link
                  href={`/${bookId}/manuscript`}
                  className={`inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}
                >
                  Open manuscript notes
                </Link>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                {bookNotes.length === 0 ? (
                  <div className={`rounded-[1.25rem] border border-dashed px-5 py-10 text-center text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
                    No chapter-linked notes saved for this book yet.
                  </div>
                ) : (
                  bookNotes.map((note) => (
                    <article key={note.id} className={`rounded-[1.25rem] border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/70"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                            {note.chapter_number ? `Chapter ${note.chapter_number}${note.chapter_title ? ` - ${note.chapter_title}` : ""}` : "Whole-book note"}
                          </p>
                          <h3 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{note.title || "Untitled note"}</h3>
                        </div>
                        <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                          {new Date(note.updated_at).toLocaleDateString()}
                        </span>
                      </div>

                      <div
                        className={`note-rich-content mt-4 text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}
                        dangerouslySetInnerHTML={{ __html: renderRichTextHtml(note.body) }}
                      />

                      <div className="mt-4 flex flex-wrap gap-2">
                        <Link
                          href={`/${bookId}/manuscript`}
                          className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-700"}`}
                        >
                          Open manuscript
                        </Link>
                        {note.chapter_number ? (
                          <Link
                            href={`/${bookId}/chapter/${note.chapter_number}`}
                            className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-700"}`}
                          >
                            Open chapter
                          </Link>
                        ) : null}
                      </div>
                    </article>
                  ))
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
