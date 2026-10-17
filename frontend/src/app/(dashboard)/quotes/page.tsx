"use client"

import { useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { WorkspaceHeader, WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, booksQuotesCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import type { SavedQuote } from "@/types/book"
import { filterQuotes, quoteBooks, quoteSavedDate, quoteSource } from "./quotesPage.helpers"

const EMPTY_QUOTES: SavedQuote[] = []
const PAGE_SIZE = 25

export default function QuotesPage() {
  const userTier = useAuthStore((state) => state.user?.tier)
  const authHydrated = useAuthStore((state) => state.hydrated)
  const permitted = canUseAuthorFeatures(userTier)
  const [query, setQuery] = useState("")
  const [bookId, setBookId] = useState("")
  const [visible, setVisible] = useState(PAGE_SIZE)
  const result = useQuery<SavedQuote[]>({
    queryKey: asQueryKey(booksQuotesCacheKey()),
    queryFn: () => booksApi.listQuotes(),
    enabled: authHydrated && permitted,
    staleTime: 45_000,
  })
  const quotes = result.data ?? EMPTY_QUOTES
  const books = useMemo(() => quoteBooks(quotes), [quotes])
  const filtered = useMemo(() => filterQuotes(quotes, query, bookId), [quotes, query, bookId])
  const filtering = !!query.trim() || !!bookId
  const clear = () => { setQuery(""); setBookId(""); setVisible(PAGE_SIZE) }

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div data-account-quotes className="min-w-0 space-y-6 pb-12 [overflow-wrap:anywhere]">
        <header className="border-b border-[rgb(var(--border))] pb-6">
          <WorkspaceHeader
            eyebrow="Saved passages"
            title="Quotes"
            description="Search highlighted passages from every book. Read the full quote, keep your notes in view, or return to its source chapter."
            actions={<button type="button" className="app-button-secondary self-start" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>}
          />
        </header>
        {!authHydrated ? (
          <p role="status" className="py-6 text-sm">Loading quotes… Preparing your saved passages.</p>
        ) : !permitted ? (
          <section className="border-b border-[rgb(var(--border))] py-6">
            <h2 className="text-xl font-semibold">Saved quotes require an active trial or paid plan.</h2>
            <p className="mt-3 text-sm leading-6">View plans to access your saved passages and their context.</p>
            <div className="mt-4 flex flex-wrap gap-3"><Link href="/pricing" className="app-button-secondary">View plans</Link><Link href="/library" className="app-button-secondary">Return to library</Link></div>
          </section>
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-4">
              <label htmlFor="quotes-search" className="min-w-0 flex-1 basis-72 text-sm font-medium">Search quotes
                <input type="search" id="quotes-search" value={query} onChange={(event) => { setQuery(event.target.value); setVisible(PAGE_SIZE) }} placeholder="Passage, note, character, chapter, or book" className="app-input mt-2" />
              </label>
              <label className="min-w-0 flex-1 basis-52 text-sm font-medium">Book
                <select aria-label="Book" value={bookId} onChange={(event) => { setBookId(event.target.value); setVisible(PAGE_SIZE) }} className="app-input mt-2">
                  <option value="">All books</option>
                  {books.map((book) => <option key={book.id} value={book.id}>{book.title}{books.filter((other) => other.title === book.title).length > 1 ? ` · ${book.id.slice(0, 8)}` : ""}</option>)}
                </select>
              </label>
              {filtering ? <button type="button" className="app-button-secondary" onClick={clear}>Clear filters</button> : null}
              <button type="button" className="app-button-secondary" disabled={result.isFetching} onClick={() => void result.refetch()}>{result.isFetching ? "Refreshing…" : "Refresh quotes"}</button>
            </div>
            {result.isLoading ? <p role="status" className="border-y border-[rgb(var(--border))] py-8 text-sm">Loading saved quotes…</p> : null}
            {result.isError ? <div role="alert" className="border-l-2 border-amber-600 pl-4 text-sm leading-6"><p>{result.data ? "Quotes could not be refreshed. Previously loaded passages are still shown." : "Your quotes could not be loaded. Check your access or try again."}</p><button type="button" disabled={result.isFetching} onClick={() => void result.refetch()} className="mt-2 min-h-11 underline underline-offset-4">Retry quotes</button></div> : null}
            {result.data ? (
              <>
                <p role="status" className="text-sm text-[rgb(var(--muted-foreground))]">{filtering ? `${filtered.length} of ${quotes.length} quotes match` : `${quotes.length} saved ${quotes.length === 1 ? "quote" : "quotes"} across ${books.length} ${books.length === 1 ? "book" : "books"}`} · Most recently saved first</p>
                {!quotes.length ? (
                  <section className="border-y border-[rgb(var(--border))] py-8"><h2 className="text-xl font-semibold">No quotes saved yet</h2><p className="mt-3 max-w-2xl text-sm leading-6">Open a book in the reader and choose Select a quote to save a passage with its chapter context.</p><Link href="/library" className="app-button-secondary mt-4">Choose a book</Link></section>
                ) : !filtered.length ? (
                  <section className="border-y border-[rgb(var(--border))] py-8"><h2 className="text-xl font-semibold">No quotes match that search</h2><p className="mt-3 text-sm">Try another phrase, character, or chapter number, or clear the book filter.</p><button type="button" className="app-button-secondary mt-4" onClick={clear}>Show all quotes</button></section>
                ) : (
                  <>
                    <div className="border-t border-[rgb(var(--border))]">{filtered.slice(0, visible).map((quote) => <QuoteRow key={quote.id} quote={quote} />)}</div>
                    {filtered.length > visible ? <div className="flex flex-wrap items-center gap-4 text-sm"><p>Showing {visible} of {filtered.length} matching quotes.</p><button type="button" className="app-button-secondary" onClick={() => setVisible((count) => count + PAGE_SIZE)}>Show {Math.min(PAGE_SIZE, filtered.length - visible)} more quotes</button></div> : null}
                  </>
                )}
              </>
            ) : null}
          </>
        )}
      </div>
    </WorkspacePage>
  )
}

function QuoteRow({ quote }: { quote: SavedQuote }) {
  const [expanded, setExpanded] = useState(false)
  const [copying, setCopying] = useState(false)
  const copyingRef = useRef(false)
  const [copyStatus, setCopyStatus] = useState<{ error: boolean; message: string } | null>(null)
  const source = quoteSource(quote)
  const saved = quoteSavedDate(quote.created_at)
  const text = quote.quote_text ?? ""
  const note = quote.note ?? ""
  const long = text.length > 360 || note.length > 200

  const copy = async () => {
    if (copyingRef.current || !text.trim()) return
    copyingRef.current = true; setCopying(true); setCopyStatus(null)
    try { await navigator.clipboard.writeText(text); setCopyStatus({ error: false, message: "Copied the complete quote text." }) }
    catch { setExpanded(true); setCopyStatus({ error: true, message: "Could not copy. Select and copy the full quote text below manually." }) }
    finally { copyingRef.current = false; setCopying(false) }
  }

  return (
    <article className="min-w-0 border-b border-[rgb(var(--border))] py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 text-sm text-[rgb(var(--muted-foreground))]"><h2 className="font-semibold text-[rgb(var(--foreground))]">{quote.book_title || "Untitled book"}</h2>{saved ? <time dateTime={saved.iso}>Saved {saved.label}</time> : <span>Save date unavailable</span>}</div>
      <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{source.label}</p>
      {quote.character_name ? <p className="mt-2 text-sm">Character: {quote.character_name}</p> : null}
      {copyStatus ? <p role={copyStatus.error ? "alert" : "status"} className="mt-3 border-l-2 border-[rgb(var(--accent))] pl-3 text-sm leading-6">{copyStatus.message}</p> : null}
      <div id={`quote-text-${quote.id}`} className="mt-4 max-w-prose">
        {text.trim() ? <blockquote className="whitespace-pre-wrap border-l-2 border-[rgb(var(--border))] pl-4 text-base leading-7">{expanded ? text : `${text.slice(0, 360)}${text.length > 360 ? "…" : ""}`}</blockquote> : <p className="text-sm">No passage text is available for this saved quote.</p>}
        {note ? <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[rgb(var(--muted-foreground))]"><span className="font-semibold">Your note: </span>{expanded ? note : `${note.slice(0, 200)}${note.length > 200 ? "…" : ""}`}</p> : null}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        {long ? <button type="button" aria-expanded={expanded} aria-controls={`quote-text-${quote.id}`} onClick={() => setExpanded((value) => !value)} className="min-h-11 font-semibold underline underline-offset-4">{expanded ? "Show less" : "Read full quote and note"}</button> : null}
        {text.trim() ? <button type="button" disabled={copying} onClick={() => void copy()} className="min-h-11 underline underline-offset-4">{copying ? "Copying…" : "Copy quote"}</button> : null}
        {source.href ? <Link href={source.href} className="inline-flex min-h-11 items-center underline underline-offset-4">{source.action}</Link> : <span className="text-[rgb(var(--muted-foreground))]">Source book unavailable</span>}
      </div>
    </article>
  )
}
