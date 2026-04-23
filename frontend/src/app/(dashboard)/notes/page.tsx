"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"

import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { BookNote } from "@/types/book"

export default function NotesPage() {
  const [notes, setNotes] = useState<BookNote[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState("")
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    booksApi.listNotes().then(setNotes).finally(() => setLoading(false))
  }, [])

  const filteredNotes = useMemo(() => {
    const trimmed = query.trim().toLowerCase()
    if (!trimmed) return notes
    return notes.filter((note) =>
      [note.book_title, note.chapter_title, note.title, note.body]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(trimmed))
    )
  }, [notes, query])

  return (
    <div className={`min-h-screen transition-colors ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3eb_42%,#f4f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6 lg:px-8">
        <section className={`rounded-[2rem] border p-6 shadow-[0_28px_100px_-60px_rgba(79,70,229,0.24)] ${isDark ? "border-white/10 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.12),transparent_34%),linear-gradient(180deg,rgba(11,24,48,0.92),rgba(10,20,38,0.88))]" : "border-white/70 bg-[radial-gradient(circle_at_top,#ecfff7,transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,255,255,0.76))]"}`}>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-emerald-300" : "text-emerald-600"}`}>Notes</p>
              <h1 className={`mt-3 font-serif text-4xl tracking-tight sm:text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>Story notes across your books</h1>
              <p className={`mt-3 max-w-2xl text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                Chapter-linked notes from the manuscript workspace stay here, so you can revisit open thoughts without hunting through the editor.
              </p>
            </div>
            <div className={`rounded-[1.1rem] border px-5 py-3 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/80 text-stone-500"}`}>
              {notes.length} saved note{notes.length === 1 ? "" : "s"}
            </div>
          </div>

          <div className="mt-6">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search notes, chapter names, or book titles"
              className={`w-full rounded-[1.1rem] border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
            />
          </div>
        </section>

        <div className="mt-8">
          {loading ? (
            <div className={`rounded-[1.75rem] border border-dashed py-20 text-center ${isDark ? "border-white/15 bg-white/5 text-slate-400" : "border-stone-300 bg-white/60 text-stone-400"}`}>
              Loading notes...
            </div>
          ) : filteredNotes.length === 0 ? (
            <div className={`rounded-[1.75rem] border border-dashed py-20 text-center ${isDark ? "border-white/15 bg-white/5 text-slate-400" : "border-stone-300 bg-white/60 text-stone-400"}`}>
              {notes.length === 0 ? "No notes saved yet." : "No notes match that search."}
            </div>
          ) : (
            <div className="grid gap-5 lg:grid-cols-2">
              {filteredNotes.map((note) => (
                <article key={note.id} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200/80 bg-white/88"}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{note.book_title}</p>
                      <h2 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || "Untitled note"}</h2>
                      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        {note.chapter_number ? `Chapter ${note.chapter_number}${note.chapter_title ? ` - ${note.chapter_title}` : ""}` : "General book note"}
                      </p>
                    </div>
                    <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                      {new Date(note.updated_at).toLocaleDateString()}
                    </span>
                  </div>

                  <p className={`mt-4 whitespace-pre-wrap text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{note.body}</p>

                  <div className="mt-5 flex flex-wrap gap-2">
                    <Link
                      href={`/${note.book_id}/manuscript`}
                      className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-100 text-stone-700"}`}
                    >
                      Open manuscript
                    </Link>
                    {note.chapter_number ? (
                      <Link
                        href={`/${note.book_id}/chapter/${note.chapter_number}`}
                        className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-700"}`}
                      >
                        Open chapter
                      </Link>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
