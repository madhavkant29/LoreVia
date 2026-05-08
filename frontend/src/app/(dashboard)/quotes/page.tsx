"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"

import {
  WorkspaceEmptyState,
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import type { SavedQuote } from "@/types/book"

function formatQuoteChapter(quote: SavedQuote) {
  if (!quote.chapter_number) return "Saved without a chapter"
  return quote.chapter_title
    ? `Chapter ${quote.chapter_number} - ${quote.chapter_title}`
    : `Chapter ${quote.chapter_number}`
}

export default function QuotesPage() {
  const [quotes, setQuotes] = useState<SavedQuote[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState("")

  useEffect(() => {
    booksApi.listQuotes().then(setQuotes).finally(() => setLoading(false))
  }, [])

  const filteredQuotes = useMemo(() => {
    const trimmed = query.trim().toLowerCase()
    if (!trimmed) return quotes

    return quotes.filter((quote) =>
      [
        quote.book_title,
        quote.chapter_title,
        quote.character_name,
        quote.quote_text,
        quote.note,
        quote.chapter_number?.toString(),
      ]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(trimmed))
    )
  }, [quotes, query])

  const booksRepresented = useMemo(
    () => new Set(quotes.map((quote) => quote.book_title).filter(Boolean)).size,
    [quotes]
  )

  const chapterLinkedQuotes = useMemo(
    () => quotes.filter((quote) => typeof quote.chapter_number === "number").length,
    [quotes]
  )

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        <WorkspacePanel tone="strong" className="p-6 sm:p-8">
          <WorkspaceHeader
            eyebrow="Saved quotes"
            title="Keep every highlighted line and its chapter context in one place."
            description="This inbox pulls together the passages you saved while reading, along with chapter placement, speaker hints, and any note you attached when the line mattered."
            meta={
              <div className="flex flex-wrap justify-end gap-3">
                <div className="app-chip">{quotes.length} saved quotes</div>
                <div className="app-chip">{booksRepresented} books represented</div>
              </div>
            }
          />

          <div className="mt-6">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search quotes, character names, chapter titles, notes, or book titles"
              className="app-input"
            />
          </div>
        </WorkspacePanel>

        <section className="grid gap-4 sm:grid-cols-3">
          <WorkspaceMetric
            label="Visible quotes"
            value={filteredQuotes.length.toLocaleString()}
            note={query.trim() ? "Current filtered result set" : "All saved quote cards"}
            accent="accent"
          />
          <WorkspaceMetric
            label="Chapter-linked"
            value={chapterLinkedQuotes.toLocaleString()}
            note="Quotes with chapter placement attached"
            accent="success"
          />
          <WorkspaceMetric
            label="Search mode"
            value={query.trim() ? "Filtered" : "All quotes"}
            note={query.trim() ? `Query: ${query}` : "No active filter"}
          />
        </section>

        {loading ? (
          <WorkspaceEmptyState
            title="Loading quotes"
            body="LoreVia is collecting the lines you saved across your reading workspaces."
          />
        ) : filteredQuotes.length === 0 ? (
          <WorkspaceEmptyState
            title={quotes.length === 0 ? "No quotes saved yet" : "No quotes match that search"}
            body={
              quotes.length === 0
                ? "Use quote mode in the reader to save lines, attach chapter context, and bring them back here."
                : "Try a broader phrase, character name, or chapter reference."
            }
          />
        ) : (
          <div className="grid gap-5 xl:grid-cols-2">
            {filteredQuotes.map((quote) => (
              <WorkspacePanel key={quote.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="app-eyebrow">{quote.book_title}</p>
                    <h2 className="mt-3 text-xl font-semibold text-[rgb(var(--foreground))]">
                      {formatQuoteChapter(quote)}
                    </h2>
                    <div className="mt-2 flex flex-wrap gap-2 text-sm text-[rgb(var(--muted-foreground))]">
                      {quote.character_name ? (
                        <span className="app-chip">{quote.character_name}</span>
                      ) : (
                        <span className="app-chip">Speaker unspecified</span>
                      )}
                      <span className="app-chip">
                        {new Date(quote.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                <blockquote className="mt-5 rounded-[1.5rem] border border-[rgba(var(--border),0.78)] bg-[rgba(255,255,255,0.46)] px-5 py-4 text-base leading-8 text-[rgb(var(--foreground))] shadow-[0_18px_42px_-36px_rgba(15,23,42,0.4)] dark:bg-[rgba(255,255,255,0.03)]">
                  "{quote.quote_text}"
                </blockquote>

                {quote.note ? (
                  <div className="mt-4 rounded-[1.2rem] border border-[rgba(var(--border),0.72)] bg-[rgba(255,255,255,0.34)] px-4 py-3 dark:bg-[rgba(255,255,255,0.02)]">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[rgb(var(--muted-foreground))]">
                      Note
                    </p>
                    <p className="mt-2 text-sm leading-7 text-[rgb(var(--foreground))]">{quote.note}</p>
                  </div>
                ) : null}

                <div className="mt-6 flex flex-wrap gap-3">
                  <Link href={`/${quote.book_id}`} className="app-button-primary">
                    Open workspace
                  </Link>
                  {quote.chapter_number ? (
                    <Link href={`/${quote.book_id}/chapter/${quote.chapter_number}`} className="app-button-secondary">
                      Open chapter
                    </Link>
                  ) : null}
                  <Link href={`/${quote.book_id}/notes`} className="app-button-secondary">
                    Open notes
                  </Link>
                </div>
              </WorkspacePanel>
            ))}
          </div>
        )}
      </div>
    </WorkspacePage>
  )
}
