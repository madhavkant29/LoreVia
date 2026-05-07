"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
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
  const [notesLoading, setNotesLoading] = useState(true)

  useEffect(() => {
    let active = true
    setNotesLoading(true)

    booksApi.get(bookId)
      .then((bookData) => {
        if (!active) return
        setBook(bookData)
      })
      .catch(() => {})

    booksApi.getBookNotes(bookId)
      .then((bookNotesData) => {
        if (!active) return
        setBookNotes(bookNotesData)
      })
      .catch(() => {})

    booksApi.listObsidianNotes(bookId)
      .then((notesData) => {
        if (!active) return
        setNotes(notesData)
      })
      .catch(() => {})
      .finally(() => {
        if (active) setNotesLoading(false)
      })

    booksApi.getObsidianGraph(bookId)
      .then((graphData) => {
        if (!active) return
        setGraph(graphData)
      })
      .catch(() => {})

    return () => {
      active = false
    }
  }, [bookId])

  return (
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#010409_0%,#07111c_50%,#0b1523_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#f6f3ea_0%,#eef5ef_50%,#eef3f8_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-[108rem] px-4 pb-20 pt-6 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="notes"
            isDark={isDark}
            title="Notes workflow"
            description="Keep the vault tree, manuscript, export studio, and continuity tools one click away while you edit."
          />

          <div className="space-y-8">
            {notesLoading ? (
              <div className={`rounded-[1.8rem] border border-dashed py-24 text-center ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>Loading vault notes workspace...</div>
            ) : (
              <>
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
                <Link
                  href={`/${bookId}/scenes`}
                  className={`inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-700"}`}
                >
                  Open scene workspace
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
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
