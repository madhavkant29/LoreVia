"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useId, useMemo, useState } from "react"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import type { ForeshadowingItem } from "@/types/reader"
import { hasSuggestedConnection, signalChapters, signalMatches, SIGNAL_VIEWS, type SignalView } from "./foreshadowingPage.helpers"

const EMPTY_ITEMS: ForeshadowingItem[] = []
const muted = "text-[rgb(var(--muted-foreground))]"
const field = "mt-2 block min-h-11 w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 text-sm"

export default function ForeshadowingPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <ForeshadowingWorkspace key={bookId} bookId={bookId} />
}

function ForeshadowingWorkspace({ bookId }: { bookId: string }) {
  const id = useId()
  const [activeView, setActiveView] = useState<SignalView>("all")
  const [query, setQuery] = useState("")
  const [chapter, setChapter] = useState("")
  const [limit, setLimit] = useState(40)
  const result = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "foreshadowing")), queryFn: () => readerApi.getForeshadowing(bookId) })
  const items = result.data?.items ?? EMPTY_ITEMS
  const chapters = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "chapters")), queryFn: () => readerApi.getChapterList(bookId), enabled: items.length > 0, staleTime: 45_000 })
  const availableChapters = new Set(chapters.data?.chapters.map((item) => item.number))
  const chapterOptions = useMemo(() => signalChapters(items), [items])
  const linkedCount = items.filter(hasSuggestedConnection).length
  const counts = { all: items.length, linked: linkedCount, unlinked: items.length - linkedCount }
  const visibleItems = useMemo(() => items.filter((item) => signalMatches(item, activeView, query, chapter)), [activeView, items, query, chapter])
  const filtersActive = !!query || !!chapter || activeView !== "all"
  const clear = () => { setQuery(""); setChapter(""); setActiveView("all"); setLimit(40) }

  return <WorkspacePage>
    <main data-foreshadowing-workspace className="mx-auto min-w-0 max-w-6xl px-0 pb-16 pt-6 sm:px-2 lg:px-4 [overflow-wrap:anywhere]">
      <WorkspaceFamilyHeader active="foreshadowing" bookId={bookId} family="story-bible" title="Setup and payoff" description="Review planted details and suggested connections from available chapter summaries. Use the source chapters to assess whether each setup pays off." actions={<><button type="button" disabled={result.isFetching} className="app-button-secondary !rounded-sm disabled:opacity-50" onClick={() => void result.refetch()}>{result.isFetching && result.data ? "Refreshing…" : "Refresh signals"}</button><button type="button" className="app-button-secondary !rounded-sm" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></>} />
      {result.isLoading ? <p role="status" className={`mt-6 border-y border-[rgb(var(--border))] py-8 text-sm ${muted}`}>Loading setup and payoff signals…</p> : null}
      {result.isError ? <div role="alert" className="mt-6 border-l-2 border-amber-600 pl-4 text-sm"><p>{result.data ? "Signals could not be refreshed. Previously loaded evidence remains visible." : "Setup and payoff signals could not be loaded. Check your manuscript access or try again."}</p><button type="button" disabled={result.isFetching} className="app-button-secondary mt-3 !rounded-sm" onClick={() => void result.refetch()}>Retry signals</button></div> : null}
      {result.data && !items.length ? <section className="mt-6 border-y border-[rgb(var(--border))] py-8"><h2 className="text-lg font-semibold">No setup signals yet</h2><p className={`mt-2 max-w-2xl text-sm leading-6 ${muted}`}>This ledger uses clues from detailed summaries of chapters available to you. Check chapter processing and availability; an empty ledger does not mean your story has no setups.</p><Link href={`/${bookId}/chapters`} className="app-button-secondary mt-4 !rounded-sm">View chapters</Link></section> : null}
      {items.length > 0 ? <div className="mt-6">
        <p className={`max-w-3xl text-sm leading-6 ${muted}`}>Linked means a suggested connection is recorded, not that a payoff has been confirmed. Unlinked means no connection was recorded in the chapter summary.</p>
        <div className="my-5 grid gap-4 sm:grid-cols-[minmax(0,1fr)_220px]">
          <label className="text-sm font-medium">Find a setup<input type="search" className={field} value={query} onChange={(event) => { setQuery(event.target.value); setLimit(40) }} placeholder="Search setup, connection, or chapter title" /></label>
          <label className="text-sm font-medium">Source chapter<select className={field} value={chapter} onChange={(event) => { setChapter(event.target.value); setLimit(40) }}><option value="">All chapters</option>{chapter && !chapterOptions.includes(Number(chapter)) ? <option value={chapter}>Chapter {chapter} (no current signals)</option> : null}{chapterOptions.map((number) => <option key={number} value={number}>Chapter {number}</option>)}</select></label>
        </div>
        <div className="flex flex-wrap border-b border-[rgb(var(--border))]" role="tablist" aria-label="Setup and payoff views">
          {SIGNAL_VIEWS.map((view, index) => <button key={view.id} id={`${id}-${view.id}`} type="button" role="tab" aria-selected={activeView === view.id} aria-controls={`${id}-signals`} tabIndex={activeView === view.id ? 0 : -1} onClick={() => { setActiveView(view.id); setLimit(40) }} onKeyDown={(event) => {
            const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : null
            if (next === null) return
            event.preventDefault(); setActiveView(SIGNAL_VIEWS[next].id); setLimit(40); document.getElementById(`${id}-${SIGNAL_VIEWS[next].id}`)?.focus()
          }} className={`min-h-11 border-b-2 px-3 py-3 text-sm font-medium ${activeView === view.id ? "border-[rgb(var(--accent))]" : `border-transparent ${muted}`}`}>{view.label} <span className="ml-1 tabular-nums">{counts[view.id]}</span></button>)}
        </div>
        {chapters.isError ? <p role="alert" className="mt-4 text-sm">Chapter links could not be checked. <button type="button" disabled={chapters.isFetching} className="underline underline-offset-4" onClick={() => void chapters.refetch()}>Retry chapter links</button></p> : null}
        <section id={`${id}-signals`} role="tabpanel" tabIndex={0} aria-labelledby={`${id}-${activeView}`}>
          <div className={`flex flex-wrap items-center justify-between gap-3 py-4 text-sm ${muted}`}><p>{visibleItems.length} {visibleItems.length === 1 ? "signal" : "signals"}{filtersActive ? " matching the current filters" : " in available chapters"}{visibleItems.length > limit ? ` · showing ${limit}` : ""}</p>{filtersActive ? <button type="button" className="min-h-10 underline underline-offset-4" onClick={clear}>Clear filters</button> : null}</div>
          {!visibleItems.length ? <p className={`border-b border-[rgb(var(--border))] py-6 text-sm ${muted}`}>No signals match these filters. Clear the filters or choose another view.</p> : <div className="divide-y divide-[rgb(var(--border))] border-b border-[rgb(var(--border))]">
            {visibleItems.slice(0, limit).map((item, index) => {
              const linked = hasSuggestedConnection(item)
              const validChapter = Number.isInteger(item.chapter_number) && item.chapter_number > 0
              return <article key={`${item.chapter_number}-${index}`} className="grid min-w-0 gap-3 py-5 sm:grid-cols-[145px_minmax(0,1fr)] sm:gap-5">
                <div>{validChapter && availableChapters.has(item.chapter_number) ? <Link href={`/${bookId}/chapter/${item.chapter_number}`} className="text-sm font-medium underline underline-offset-4">Chapter {item.chapter_number}</Link> : <p className="text-sm font-medium">{validChapter ? `Chapter ${item.chapter_number}` : "Chapter not located"}</p>}{typeof item.chapter_title === "string" && item.chapter_title ? <p className={`mt-1 text-sm leading-6 ${muted}`}>{item.chapter_title}</p> : null}{validChapter && chapters.data && !availableChapters.has(item.chapter_number) ? <p className={`mt-1 text-sm ${muted}`}>Chapter unavailable</p> : null}</div>
                <div className="grid min-w-0 gap-4 md:grid-cols-2 md:gap-6">
                  <div><p className={`text-sm ${muted}`}>Setup</p><h2 className="mt-1 text-base font-semibold leading-7">{typeof item.clue === "string" && item.clue.trim() ? item.clue : "Setup text unavailable"}</h2></div>
                  <div className="border-[rgb(var(--border))] md:border-l md:pl-6"><p className={`text-sm ${muted}`}>{linked ? "Suggested connection" : "Connection status"}</p>{linked ? <p className="mt-1 text-sm leading-7">{item.foreshadows}</p> : <><p className="mt-1 text-sm font-medium text-amber-800 dark:text-amber-200">No linked payoff yet</p><p className={`mt-1 text-sm leading-6 ${muted}`}>Check the source before deciding whether this detail needs an echo, payoff, or removal.</p></>}</div>
                </div>
              </article>
            })}
          </div>}
          {visibleItems.length > limit ? <button type="button" className="app-button-secondary mt-4 !rounded-sm" onClick={() => setLimit((value) => value + 40)}>Show more signals</button> : null}
        </section>
      </div> : null}
    </main>
  </WorkspacePage>
}
