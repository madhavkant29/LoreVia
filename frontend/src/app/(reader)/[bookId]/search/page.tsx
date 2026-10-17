"use client"

import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import Link from "next/link"
import { useParams, useSearchParams } from "next/navigation"
import { Suspense, useCallback, useEffect, useId, useRef, useState } from "react"
import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { WorkspacePage } from "@/components/ui/Workspace"
import { capture } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { parseSearchChapter, searchFailureMessage, searchMatches, type SearchMode, type SearchSnapshot } from "./searchPage.helpers"

const muted = "text-[rgb(var(--muted-foreground))]"
const modes: SearchMode[] = ["semantic", "thematic"]
type SearchAttempt = { query: string; mode: SearchMode; chapter?: number }

export default function SearchPage() {
  return <Suspense fallback={<p role="status" className="p-6">Loading search…</p>}><SearchPageInner /></Suspense>
}

function SearchPageInner() {
  const { bookId } = useParams<{ bookId: string }>()
  const params = useSearchParams()
  return <SearchWorkspace key={`${bookId}:${params.toString()}`} bookId={bookId} seed={params.get("q") ?? ""} initialChapter={params.get("chapter") ?? ""} />
}

function SearchWorkspace({ bookId, seed, initialChapter }: { bookId: string; seed: string; initialChapter: string }) {
  const { theme } = usePreferencesStore()
  const id = useId()
  const [query, setQuery] = useState(seed)
  const [chapterInput, setChapterInput] = useState(initialChapter)
  const [mode, setMode] = useState<SearchMode>("semantic")
  const [snapshots, setSnapshots] = useState<Partial<Record<SearchMode, SearchSnapshot>>>({})
  const [pending, setPending] = useState<SearchAttempt | null>(null)
  const [failure, setFailure] = useState<{ attempt: SearchAttempt; message: string } | null>(null)
  const active = useRef(false)
  const mounted = useRef(true)
  const seeded = useRef(false)
  const bookQuery = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "detail")), queryFn: () => booksApi.get(bookId), staleTime: 20_000 })
  const book = bookQuery.data
  const isAuthor = book?.mode === "author"
  const snapshot = snapshots[mode]
  const chapters = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "chapters")), queryFn: () => readerApi.getChapterList(bookId), enabled: !!snapshot?.matches.length, staleTime: 45_000 })
  const available = new Set(chapters.data?.chapters.map((item) => item.number))
  const chapter = parseSearchChapter(chapterInput)
  const invalidChapter = mode === "semantic" && chapter === null
  const ready = !!book && !bookQuery.isError
  const visibleFailure = failure?.attempt.mode === mode ? failure : null

  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  const runSearch = useCallback(async (attempt: SearchAttempt) => {
    if (active.current || !attempt.query.trim() || !ready) return
    const submitted = { ...attempt, query: attempt.query.trim() }
    active.current = true
    setPending(submitted)
    setFailure(null)
    capture("search_submitted", { book_id: bookId, query_len: submitted.query.length, workspace: isAuthor ? "author" : "reader" })
    try {
      const response = submitted.mode === "thematic" ? await readerApi.thematicSearch(bookId, submitted.query) : null
      const results = response ? response.results : await readerApi.search(bookId, submitted.query, submitted.chapter)
      if (!mounted.current) return
      const matches = searchMatches(results, submitted.mode, submitted.chapter)
      setSnapshots((current) => ({ ...current, [submitted.mode]: { query: submitted.query, chapter: submitted.chapter, matches, building: response?.index_status === "building" } }))
      capture("search_results_loaded", { book_id: bookId, result_count: matches.length, mode: submitted.mode })
    } catch (error: unknown) {
      if (mounted.current) setFailure({ attempt: submitted, message: searchFailureMessage(error) })
    } finally {
      active.current = false
      if (mounted.current) setPending(null)
    }
  }, [bookId, isAuthor, ready])

  useEffect(() => {
    if (seeded.current || !seed.trim() || !ready || chapter === null) return
    seeded.current = true
    void runSearch({ query: seed, mode: "semantic", chapter })
  }, [chapter, ready, runSearch, seed])

  return <WorkspacePage>
    <main data-search-workspace className="mx-auto min-w-0 max-w-6xl pb-20 pt-6 sm:px-2 lg:px-4 [overflow-wrap:anywhere]">
      <AuthorToolsNav active="search" bookData={book ?? null} bookId={bookId} isDark={theme === "dark"} mode={book?.mode ?? "author"} title={book?.title || "Search"} variant="bar" />
      <header className="mt-6 border-b border-[rgb(var(--foreground))] pb-5">
        <div className="flex items-start justify-between gap-4"><div><p className={`text-sm ${muted}`}>Book search</p><h1 className="mt-1 text-3xl font-semibold">Search {isAuthor ? "the manuscript" : "this book"}</h1></div><button type="button" className="app-button-secondary shrink-0 !rounded-sm" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></div>
        <p className={`mt-3 max-w-3xl text-sm leading-6 ${muted}`}>Find a remembered passage or trace a recurring theme.</p>
        {book ? <Link href={(isAuthor ? `/${bookId}/advisor?mode=ask` : `/${bookId}/ask`) as Route} className="mt-3 inline-block text-sm font-medium underline underline-offset-4">Need an answer instead?</Link> : null}
      </header>
      {bookQuery.isLoading ? <p role="status" className="mt-4 text-sm">Loading manuscript access…</p> : null}
      {bookQuery.isError ? <div role="alert" className="mt-4 border-l-2 border-amber-600 pl-4 text-sm"><p>Manuscript access could not be loaded. Your search text is preserved.</p><button className="app-button-secondary mt-3 !rounded-sm" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry manuscript</button></div> : null}
      <div className="mt-6 flex gap-6 border-b border-[rgb(var(--border))]" role="tablist" aria-label="Search type">
        {modes.map((value, index) => <button key={value} id={`${id}-${value}`} type="button" role="tab" aria-selected={mode === value} aria-controls={`${id}-panel`} tabIndex={mode === value ? 0 : -1} onClick={() => setMode(value)} onKeyDown={(event) => {
          const next = event.key === "ArrowRight" || event.key === "ArrowLeft" ? 1 - index : event.key === "Home" ? 0 : event.key === "End" ? 1 : null
          if (next === null) return
          event.preventDefault(); setMode(modes[next]); document.getElementById(`${id}-${modes[next]}`)?.focus()
        }} className={`min-h-11 border-b-2 pb-3 text-sm font-semibold ${mode === value ? "border-[rgb(var(--accent))]" : `border-transparent ${muted}`}`}>{value === "semantic" ? "Passages" : "Themes"}</button>)}
      </div>
      <section role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-${mode}`} tabIndex={0}>
        <p id={`${id}-scope`} className={`mt-4 text-sm leading-6 ${muted}`}>{mode === "semantic" ? "Describe a scene, character, object, or phrase." : "Search available chapter summaries and text. Passage chapter limits do not apply."}</p>
        <form className="mt-4 border-b border-[rgb(var(--border))] pb-5" onSubmit={(event) => { event.preventDefault(); if (!invalidChapter) { seeded.current = true; void runSearch({ query, mode, chapter: mode === "semantic" ? chapter ?? undefined : undefined }) } }}>
          <label htmlFor={`${id}-query`} className="text-sm font-medium">{isAuthor ? "Search manuscript" : "Search story"}</label>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row"><input id={`${id}-query`} type="search" value={query} onChange={(event) => setQuery(event.target.value)} aria-describedby={`${id}-scope`} onKeyDown={(event) => { if (event.key === "Enter" && event.nativeEvent.isComposing) event.preventDefault() }} placeholder="Describe what you remember" className="app-input min-h-11 min-w-0 flex-1 !rounded-sm border !border-[rgb(var(--border))] px-3" /><button type="submit" disabled={!!pending || !query.trim() || !ready || invalidChapter} className="app-button-primary min-h-11 !rounded-sm disabled:cursor-not-allowed disabled:opacity-50">{pending ? "Searching…" : isAuthor ? "Search manuscript" : "Search"}</button></div>
          {mode === "semantic" ? <div className="mt-4"><label className="flex flex-wrap items-center gap-3 text-sm" htmlFor={`${id}-chapter`}>Search through chapter <input id={`${id}-chapter`} inputMode="numeric" value={chapterInput} onChange={(event) => setChapterInput(event.target.value)} aria-invalid={invalidChapter} aria-describedby={`${id}-chapter-help`} placeholder="All" className="app-input min-h-11 w-24 !rounded-sm border !border-[rgb(var(--border))] px-3" /></label><p id={`${id}-chapter-help`} className={`mt-2 text-sm ${invalidChapter ? "text-rose-700 dark:text-rose-300" : muted}`}>{invalidChapter ? "Enter a whole chapter number greater than zero, or leave blank for all chapters." : "Includes earlier chapters. Blank searches the full book, regardless of reading position."}</p></div> : null}
        </form>
        <p role="status" className={`mt-4 text-sm ${muted}`}>{pending ? `Searching ${pending.mode === "semantic" ? "passages" : "themes"} for “${pending.query}”…` : snapshot ? `${snapshot.matches.length} ranked ${snapshot.matches.length === 1 ? "match" : "matches"} returned.` : "Enter a query to begin. Switching tabs does not run a search."}</p>
        {visibleFailure ? <div role="alert" className="mt-4 border-l-2 border-rose-600 pl-4 text-sm"><p>{visibleFailure.message}</p><p className={`mt-1 ${muted}`}>Failed query: “{visibleFailure.attempt.query}”. {snapshot ? "Previously returned results remain below." : "No results were loaded for this request."}</p><button type="button" disabled={!!pending || !ready} className="app-button-secondary mt-3 !rounded-sm disabled:opacity-50" onClick={() => void runSearch(visibleFailure.attempt)}>Retry search</button></div> : null}
        {snapshot ? <section className="mt-5" aria-label="Search results">
          <p className={`mb-2 text-sm ${muted}`}>Top matches, not every occurrence.</p><h2 className="text-lg font-semibold">Results for “{snapshot.query}”</h2><p className={`mt-1 text-sm ${muted}`}>{mode === "thematic" ? "Themes · available chapters · up to 20 ranked matches" : `Passages · ${snapshot.chapter ? `chapters 1–${snapshot.chapter}` : "full book scope"}`}</p>
          {snapshot.building ? <p className="mt-4 border-l-2 border-amber-600 pl-4 text-sm leading-6">The theme index is still building or has no available chapter text. These results may be incomplete. Check chapter processing, then submit again.</p> : null}
          {snapshot.matches.length > 0 && chapters.isError ? <p role="alert" className="mt-4 text-sm">Chapter links could not be checked. <button type="button" className="underline underline-offset-4" disabled={chapters.isFetching} onClick={() => void chapters.refetch()}>Retry chapter links</button></p> : null}
          {!snapshot.matches.length ? <p className={`mt-4 border-y border-[rgb(var(--border))] py-6 text-sm leading-6 ${muted}`}>{mode === "thematic" ? "No matching themes returned. Try another word or motif, or check chapter processing." : "No matching passages returned. Try a broader scene description, a character name, or a wider chapter scope."}</p> : <div className="mt-4 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">
            {snapshot.matches.map((match, index) => { const valid = Number.isInteger(match.chapter) && match.chapter > 0; return <article key={`${match.chapter}-${index}`} className="grid min-w-0 gap-2 py-5 sm:grid-cols-[70px_minmax(0,1fr)] sm:gap-5"><p className={`text-sm ${muted}`}>Match {index + 1}</p><div className="min-w-0 max-w-4xl"><h3 className="text-base font-semibold leading-7">{valid ? `Chapter ${match.chapter}` : "Chapter not located"}{match.title ? ` — ${match.title}` : ""}</h3><p className="mt-2 text-base leading-7">{match.summary?.trim() || "Summary unavailable for this match."}</p>{mode === "semantic" ? match.text?.trim() ? <blockquote className={`mt-3 whitespace-pre-wrap border-l-2 border-[rgb(var(--border))] pl-4 text-base leading-7 ${muted}`}>{match.text}</blockquote> : <p className={`mt-3 text-sm ${muted}`}>Source excerpt unavailable.</p> : null}{valid && available.has(match.chapter) ? <Link href={isAuthor ? `/${bookId}/manuscript?chapter=${match.chapter}` : `/${bookId}/chapter/${match.chapter}`} className="mt-3 inline-block py-1 text-sm font-medium underline underline-offset-4">Open chapter {match.chapter}</Link> : <p className={`mt-3 text-sm ${muted}`}>{!valid ? "No source chapter link" : chapters.isError ? "Source chapter not verified" : chapters.data ? "Chapter unavailable" : "Checking source chapter…"}</p>}</div></article> })}
          </div>}
        </section> : !pending && !visibleFailure ? <div className="border-b border-[rgb(var(--border))] py-7"><h2 className="text-lg font-semibold">{mode === "semantic" ? "Search by what you remember" : "Trace an idea through the story"}</h2><p className={`mt-2 max-w-2xl text-sm leading-6 ${muted}`}>{mode === "semantic" ? "Try a scene detail such as a warning at the gate. You do not need the exact wording." : "Try a recurring image, object, or conflict, such as an inherited obligation."}</p></div> : null}
      </section>
    </main>
  </WorkspacePage>
}
