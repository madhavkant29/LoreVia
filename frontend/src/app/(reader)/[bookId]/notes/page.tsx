"use client"

import { startTransition, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import Link from "next/link"
import { useParams } from "next/navigation"

import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { renderRichTextHtml } from "@/lib/utils/richText"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { BookNote, VaultGraph, VaultNote } from "@/types/book"

const VaultNotesEditor = dynamic(
  () => import("@/components/reader/VaultNotesEditor").then((module) => module.VaultNotesEditor),
  {
    ssr: false,
    loading: () => (
      <div className="border-y border-stone-200 py-12 text-sm text-inherit">
        Loading notes...
      </div>
    ),
  }
)

const EMPTY_GRAPH: VaultGraph = { nodes: [], edges: [] }

export default function BookNotesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [secondaryDataEnabled, setSecondaryDataEnabled] = useState(false)
  const [chapterNotesOpen, setChapterNotesOpen] = useState(false)
  const { data: book = null } = useBookDetail(bookId)

  useEffect(() => {
    if (secondaryDataEnabled) return

    const schedule =
      typeof window.requestIdleCallback === "function"
        ? window.requestIdleCallback.bind(window)
        : ((callback: IdleRequestCallback) =>
            window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline), 120))
    const cancel =
      typeof window.cancelIdleCallback === "function"
        ? window.cancelIdleCallback.bind(window)
        : window.clearTimeout.bind(window)

    const handle = schedule(() => {
      startTransition(() => setSecondaryDataEnabled(true))
    })

    return () => cancel(handle)
  }, [secondaryDataEnabled])

  const {
    data: bookNotes = [],
    isLoading: bookNotesLoading,
    isError: bookNotesError,
    refetch: retryBookNotes,
    isFetching: bookNotesFetching,
  } = useQuery<BookNote[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "notes")),
    queryFn: () => booksApi.getBookNotes(bookId),
    enabled: chapterNotesOpen,
    staleTime: 30_000,
  })
  const { data: notes, isLoading: notesLoading, isError: notesError, refetch: retryNotes, isFetching: notesFetching } = useQuery<VaultNote[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "vault-notes")),
    queryFn: () => booksApi.listVaultNotes(bookId),
    staleTime: 30_000,
  })
  const { data: graph = EMPTY_GRAPH, isError: graphError, refetch: retryGraph, isFetching: graphFetching } = useQuery<VaultGraph>({
    queryKey: asQueryKey(bookCacheKey(bookId, "vault-graph")),
    queryFn: () => booksApi.getVaultGraph(bookId),
    enabled: secondaryDataEnabled,
    staleTime: 30_000,
  })
  const vaultNotesLoading = notesLoading

  return (
    <main data-notes-workspace className={`min-h-screen ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-[108rem] px-4 pb-20 pt-6 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <AuthorToolsNav
            bookId={bookId}
            active="notes"
            isDark={isDark}
            bookData={book}
            title="Notes workflow"
            variant="bar"
          />

          <div className="space-y-8">
            {notesError ? <div role="alert" className="border-l-2 border-amber-400 py-3 pl-4 text-sm"><p>Notes could not load. Your saved notes have not been changed.</p><button type="button" disabled={notesFetching} onClick={() => void retryNotes()} className="mt-2 min-h-10 underline">Retry notes</button></div> : null}
            {graphError ? <div role="alert" className="border-l-2 border-amber-400 py-3 pl-4 text-sm"><p>The note graph could not load.</p><button type="button" disabled={graphFetching} onClick={() => void retryGraph()} className="min-h-10 underline">Retry note graph</button></div> : null}
            {vaultNotesLoading ? (
              <div className={`border-y py-12 text-sm ${isDark ? "border-white/[0.08] text-slate-400" : "border-stone-200 text-stone-600"}`}>Loading notes...</div>
            ) : notes ? (
              <>
                <VaultNotesEditor
                  key={bookId}
                  bookId={bookId}
                  bookTitle={book?.title || "book"}
                  initialNotes={notes}
                  initialGraph={graph}
                  isDark={isDark}
                />

                <section className={`border-y ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
                  <button
                    type="button"
                    aria-expanded={chapterNotesOpen}
                    onClick={() => setChapterNotesOpen((current) => !current)}
                    className={`flex w-full items-center justify-between gap-4 py-4 text-left ${isDark ? "text-slate-200" : "text-stone-800"}`}
                  >
                    <span>
                      <span className="block text-sm font-semibold">Chapter-linked notes</span>
                      <span className={`mt-1 block text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Notes saved from the manuscript reader</span>
                    </span>
                    <span aria-hidden="true" className="text-lg">{chapterNotesOpen ? "−" : "+"}</span>
                  </button>

                  {chapterNotesOpen ? (
                    <div className={`border-t pb-2 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
                      <div className="flex flex-wrap gap-4 py-4 text-sm font-medium">
                        <Link href={`/${bookId}/manuscript`} className={isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-700"}>Open manuscript</Link>
                        <Link href={`/${bookId}/scenes`} className={isDark ? "text-slate-300 hover:text-white" : "text-stone-600 hover:text-stone-950"}>Open scene workspace</Link>
                      </div>

                      {bookNotesLoading ? (
                        <p className={`border-t py-5 text-sm ${isDark ? "border-white/[0.07] text-slate-400" : "border-stone-200 text-stone-600"}`}>Loading chapter-linked notes...</p>
                      ) : bookNotesError ? <div role="alert" className="py-4 text-sm"><p>Chapter-linked notes could not load.</p><button type="button" disabled={bookNotesFetching} onClick={() => void retryBookNotes()} className="min-h-10 underline">Retry chapter-linked notes</button></div> : bookNotes.length === 0 ? (
                        <p className={`border-t py-5 text-sm ${isDark ? "border-white/[0.07] text-slate-400" : "border-stone-200 text-stone-600"}`}>No chapter-linked notes saved for this book yet.</p>
                      ) : (
                        <div className={`divide-y border-t ${isDark ? "divide-white/[0.07] border-white/[0.07]" : "divide-stone-200 border-stone-200"}`}>
                          {bookNotes.map((note) => (
                            <article key={note.id} className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto]">
                              <div className="min-w-0">
                                <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                                  {note.chapter_number ? `Chapter ${note.chapter_number}${note.chapter_title ? ` · ${note.chapter_title}` : ""}` : "Whole-book note"}
                                </p>
                                <h3 className={`mt-1 text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{note.title || "Untitled note"}</h3>
                                <div className={`note-rich-content mt-2 break-words text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`} dangerouslySetInnerHTML={{ __html: renderRichTextHtml(note.body) }} />
                              </div>
                              <div className="flex items-start gap-4 text-xs sm:flex-col sm:items-end sm:gap-2">
                                <span className={isDark ? "text-slate-400" : "text-stone-600"}>{new Date(note.updated_at).toLocaleDateString()}</span>
                                {note.chapter_number ? (
                                  <Link href={`/${bookId}/chapter/${note.chapter_number}`} className={isDark ? "font-medium text-teal-300" : "font-medium text-teal-800"}>Open chapter</Link>
                                ) : null}
                              </div>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : null}
                </section>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </main>
  )
}
