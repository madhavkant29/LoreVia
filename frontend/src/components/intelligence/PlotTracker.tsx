"use client"

import Link from "next/link"
import { isAxiosError } from "axios"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { memo, useId, useMemo, useState } from "react"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import type { PlotThread, PlotThreadPageItem } from "@/types/reader"
import { PlotThreadDetails } from "./PlotTracker.details"
import { usePlotThreadDraftGuard } from "./PlotTracker.draftGuard"
import { loadPlotThreadSummaries, threadChapterRange, threadMatches, threadView, THREAD_STATUS_LABELS, THREAD_VIEWS, type ThreadView } from "./PlotTracker.helpers"

interface Props { bookId: string; chapter?: number; mode?: "compact" | "dashboard" }
const EMPTY_THREADS: PlotThreadPageItem[] = []
const muted = "text-[rgb(var(--muted-foreground))]"

export const PlotTracker = memo(function PlotTracker({ bookId, chapter, mode = "compact" }: Props) {
  const client = useQueryClient()
  const id = useId()
  const [activeView, setActiveView] = useState<ThreadView>("open")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [limit, setLimit] = useState(30)
  const [draftState, setDraftState] = useState({ dirty: false, busy: false })
  const canLeave = usePlotThreadDraftGuard(draftState.dirty, draftState.busy)
  const queryKey = asQueryKey(readerCacheKey(bookId, `plot-threads:list:${chapter ?? "all"}`))
  const result = useQuery({ queryKey, queryFn: () => loadPlotThreadSummaries(bookId, chapter) })
  const threads = result.data ?? EMPTY_THREADS
  const counts = useMemo(() => {
    const values = { open: 0, attention: 0, resolved: 0 }
    for (const thread of threads) values[threadView(thread.status)]++
    return values
  }, [threads])
  const visible = useMemo(() => threads.filter((thread) => threadView(thread.status) === activeView && threadMatches(thread, query)), [threads, activeView, query])
  const changeView = (view: ThreadView) => {
    if (view === activeView || !canLeave()) return
    setActiveView(view); setSelectedId(null); setLimit(30)
  }
  const close = () => { if (canLeave()) setSelectedId(null) }
  const saved = (thread: PlotThread) => {
    client.setQueryData<PlotThreadPageItem[]>(queryKey, (current) => current?.map((item) => item.id === thread.id ? { ...item, ...thread } : item))
    client.setQueryData(asQueryKey(readerCacheKey(bookId, `plot-threads:detail:${thread.id}`)), thread)
    setActiveView(threadView(thread.status))
  }

  if (result.isLoading) return <p role="status" className={`border-y border-[rgb(var(--border))] py-8 text-sm ${muted}`}>Loading plot threads…</p>
  if (!result.data && result.isError) {
    const status = isAxiosError(result.error) ? result.error.response?.status : null
    return <div role="alert" className="border-y border-[rgb(var(--border))] py-6 text-sm"><p>{status === 403 || status === 404 ? "Plot threads are unavailable for this account or manuscript. This tool requires the manuscript owner's author access." : "Plot threads could not be loaded."}</p><button type="button" disabled={result.isFetching} className="app-button-secondary mt-3" onClick={() => void result.refetch()}>Retry plot threads</button></div>
  }
  const recovery = result.isError ? <p role="alert" className="mb-4 border-l-2 border-amber-600 pl-3 text-sm">Refresh failed. Previously loaded threads remain visible; try Refresh threads again.</p> : null
  if (!threads.length) return <div className="border-y border-[rgb(var(--border))] py-8">{recovery}<h2 className="text-lg font-semibold">No plot threads yet</h2><p className={`mt-2 text-sm ${muted}`}>Threads appear after manuscript analysis. Check your chapters and their processing status.</p><div className="mt-4 flex flex-wrap gap-4"><Link className="app-button-secondary" href={`/${bookId}/chapters`}>View chapters</Link><button type="button" disabled={result.isFetching} className="app-button-secondary" onClick={() => void result.refetch()}>Refresh threads</button></div></div>

  if (mode === "compact") return <div className="[overflow-wrap:anywhere]">{recovery}<div className="divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">{threads.slice(0, 6).map((thread) => <div key={thread.id} className="py-3 text-sm"><p className="font-semibold">{thread.title}</p><p className={`mt-1 ${muted}`}>{THREAD_STATUS_LABELS[thread.status] ?? "Unknown"} · {threadChapterRange(thread)}</p></div>)}</div><Link className="mt-3 inline-block text-sm underline underline-offset-4" href={`/${bookId}/plot-threads`}>View all plot threads</Link></div>

  return <div data-plot-tracker className="min-w-0 [overflow-wrap:anywhere]">
    {recovery}
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <label className="block w-full max-w-lg text-sm"><span className="font-medium">Find a thread</span><input type="search" value={query} placeholder="Search title, description, type, or tag" className="mt-2 min-h-11 w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3" onChange={(event) => { if (canLeave()) { setQuery(event.target.value); setSelectedId(null); setLimit(30) } }} /></label>
      <button type="button" disabled={result.isFetching || draftState.dirty || draftState.busy} className="app-button-secondary !rounded-sm" onClick={() => void result.refetch()}>{result.isFetching ? "Refreshing…" : "Refresh threads"}</button>
    </div>
    <div className="flex flex-wrap border-b border-[rgb(var(--border))]" role="tablist" aria-label="Plot thread groups">
      {THREAD_VIEWS.map((view, index) => <button key={view.id} id={`${id}-${view.id}`} type="button" role="tab" aria-selected={activeView === view.id} aria-controls={`${id}-panel`} tabIndex={activeView === view.id ? 0 : -1} onClick={() => changeView(view.id)} onKeyDown={(event) => {
        const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : null
        if (next === null) return
        event.preventDefault()
        if (canLeave()) { setActiveView(THREAD_VIEWS[next].id); setSelectedId(null); setLimit(30); document.getElementById(`${id}-${THREAD_VIEWS[next].id}`)?.focus() }
      }} className={`min-h-11 border-b-2 px-3 py-3 text-sm font-medium ${activeView === view.id ? "border-[rgb(var(--accent))]" : `border-transparent ${muted}`}`}>{view.label} <span className="ml-1 tabular-nums">{counts[view.id]}</span></button>)}
    </div>
    <section role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-${activeView}`} tabIndex={0}>
      <div className={`flex flex-wrap items-center justify-between gap-3 py-4 text-sm ${muted}`}><p>{query.trim() ? `${visible.length} ${visible.length === 1 ? "match" : "matches"} in this group` : `${visible.length} ${visible.length === 1 ? "thread" : "threads"} in this group`}{visible.length > limit ? ` · showing ${limit}` : ""}</p>{query ? <button type="button" className="underline underline-offset-4" onClick={() => { if (canLeave()) { setQuery(""); setSelectedId(null); setLimit(30) } }}>Clear search</button> : null}</div>
      {!visible.length ? <p className={`border-b border-[rgb(var(--border))] py-6 text-sm ${muted}`}>{query.trim() ? "No threads match this search in the selected group. Clear the search or choose another group." : `No ${activeView === "attention" ? "threads need attention" : `${activeView} threads`}.`}</p> : <div className="divide-y divide-[rgb(var(--border))] border-b border-[rgb(var(--border))]">
        {visible.slice(0, limit).map((thread) => <article key={thread.id}>
          <h2><button type="button" aria-expanded={selectedId === thread.id} aria-controls={`${id}-thread-${thread.id}`} disabled={draftState.busy} onClick={() => { if (canLeave()) setSelectedId(selectedId === thread.id ? null : thread.id) }} className={`grid w-full gap-3 py-4 text-left sm:grid-cols-[minmax(0,1fr)_auto] sm:px-3 ${selectedId === thread.id ? "bg-[rgb(var(--muted)/0.5)]" : "hover:bg-[rgb(var(--muted)/0.25)]"}`}>
            <span className="min-w-0"><span className="flex flex-wrap items-center gap-x-3 gap-y-1"><span className="text-base font-semibold">{thread.title}</span><span className={`text-sm ${threadView(thread.status) === "attention" ? "text-amber-800 dark:text-amber-300" : muted}`}>{THREAD_STATUS_LABELS[thread.status] ?? "Unknown"}</span></span>{thread.description ? <span className={`mt-1 block max-w-3xl text-sm leading-6 ${muted}`}>{thread.description}</span> : null}<span className={`mt-2 block text-sm ${muted}`}>{thread.type || "Unclassified thread"}{thread.tags?.length ? ` · ${thread.tags.join(", ")}` : ""}</span></span>
            <span className={`flex flex-wrap gap-x-3 gap-y-1 text-sm sm:max-w-64 sm:justify-end ${muted}`}><span>{threadChapterRange(thread)}</span>{thread.mention_count > 0 ? <span>{thread.mention_count} mentions</span> : null}<span className="basis-full sm:text-right">{selectedId === thread.id ? "Hide details ↑" : "View details ↓"}</span></span>
          </button></h2>
          <div id={`${id}-thread-${thread.id}`}>{selectedId === thread.id ? <PlotThreadDetails bookId={bookId} threadId={thread.id} onClose={close} onSaved={saved} onDraftState={setDraftState} /> : null}</div>
        </article>)}
      </div>}
      {visible.length > limit ? <button type="button" className="app-button-secondary mt-4" onClick={() => setLimit((value) => value + 30)}>Show more threads</button> : null}
    </section>
  </div>
})
