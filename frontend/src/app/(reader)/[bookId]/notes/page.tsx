"use client"

import { startTransition, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import type { Route } from "next"
import Link from "next/link"
import { useParams } from "next/navigation"

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
      <div className="rounded-lg border border-dashed py-24 text-center text-sm text-inherit">
        Loading vault notes workspace...
      </div>
    ),
  }
)

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-lg border border-dashed p-8" />,
  }
)

const EMPTY_GRAPH: VaultGraph = { nodes: [], edges: [] }

export default function BookNotesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [secondaryDataEnabled, setSecondaryDataEnabled] = useState(false)
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
  } = useQuery<BookNote[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "notes")),
    queryFn: () => booksApi.getBookNotes(bookId),
    enabled: secondaryDataEnabled,
    staleTime: 30_000,
  })
  const { data: notes = [], isLoading: notesLoading } = useQuery<VaultNote[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "vault-notes")),
    queryFn: () => booksApi.listVaultNotes(bookId),
    enabled: secondaryDataEnabled,
    staleTime: 30_000,
  })
  const { data: graph = EMPTY_GRAPH } = useQuery<VaultGraph>({
    queryKey: asQueryKey(bookCacheKey(bookId, "vault-graph")),
    queryFn: () => booksApi.getVaultGraph(bookId),
    enabled: secondaryDataEnabled,
    staleTime: 30_000,
  })
  const vaultNotesLoading = !secondaryDataEnabled || notesLoading

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-[108rem] px-4 pb-20 pt-6 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="notes"
            isDark={isDark}
            bookData={book}
            title="Notes workflow"
            description="Keep the vault tree, manuscript, export studio, and continuity tools one click away while you edit."
            variant="rail"
            railSize="compact"
          />

          <div className="space-y-8">
            {vaultNotesLoading ? (
              <div className={`rounded-lg border border-dashed py-24 text-center ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>Loading vault notes workspace...</div>
            ) : (
              <>
                <VaultNotesEditor
                  bookId={bookId}
                  bookTitle={book?.title || "book"}
                  initialNotes={notes}
                  initialGraph={graph}
                  isDark={isDark}
                />

                <section className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/82"}`}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Existing notes</p>
                  <h2 className={`mt-2 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Chapter-linked manuscript notes</h2>
                  <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    Your original manuscript notes still live here. The vault is additive, not a replacement.
                  </p>
                </div>
                <Link
                  href={`/${bookId}/manuscript`}
                  className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium ${isDark ? "bg-[#1f615d] text-white" : "bg-[#1f615d] text-white"}`}
                >
                  Open manuscript notes
                </Link>
                <Link
                  href={`/${bookId}/scenes`}
                  className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-700"}`}
                >
                  Open scene workspace
                </Link>
                <Link
                  href={`/${bookId}/voice` as Route}
                  className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-700"}`}
                >
                  Open voice workspace
                </Link>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                {bookNotes.length === 0 ? (
                  !secondaryDataEnabled || bookNotesLoading ? (
                    <div className={`rounded-md border border-dashed px-5 py-10 text-center text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
                      Loading chapter-linked notes...
                    </div>
                  ) : (
                  <div className={`rounded-md border border-dashed px-5 py-10 text-center text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
                    No chapter-linked notes saved for this book yet.
                  </div>
                  )
                ) : (
                  bookNotes.map((note) => (
                    <article key={note.id} className={`rounded-md border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/70"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
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
                          className={`rounded-md px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-700"}`}
                        >
                          Open manuscript
                        </Link>
                        {note.chapter_number ? (
                          <Link
                            href={`/${bookId}/chapter/${note.chapter_number}`}
                            className={`rounded-md border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-700"}`}
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
