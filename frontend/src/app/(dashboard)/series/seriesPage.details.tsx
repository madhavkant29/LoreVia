"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import { booksApi } from "@/lib/api/books"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { getBookHref } from "@/lib/utils/bookRoutes"
import type { Book, BookSelector, BookSeries, SeriesBible } from "@/types/book"
import type { SeriesWorldAnalysis } from "@/types/world-building"
import { positiveNumberError, seriesVolumeLabel, worldContextItems } from "./seriesPage.helpers"
import { SeriesContinuityCheck } from "./seriesPage.continuity"

type Panel = "bible" | "world" | "continuity" | null
const muted = "text-[rgb(var(--muted-foreground))]"

export function SeriesDetails({ series, available, availabilityError, disabled, onBusy, onDirty, onRefresh, onUpdate }: { series: BookSeries; available: BookSelector[]; availabilityError: boolean; disabled: boolean; onBusy: (busy: boolean) => void; onDirty: (dirty: boolean) => void; onRefresh: () => Promise<void>; onUpdate: (series: BookSeries) => void }) {
  const [panel, setPanel] = useState<Panel>(null)
  const [bible, setBible] = useState<SeriesBible | null>(null)
  const [world, setWorld] = useState<SeriesWorldAnalysis | null>(null)
  const [contextLoading, setContextLoading] = useState<Panel>(null)
  const [contextError, setContextError] = useState<Panel>(null)
  const [adding, setAdding] = useState(false)
  const [bookId, setBookId] = useState("")
  const [position, setPosition] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [continuityBusy, setContinuityBusy] = useState(false)
  const [continuityDirty, setContinuityDirty] = useState(false)
  const [status, setStatus] = useState<{ error: boolean; text: string } | null>(null)
  const locked = useRef(false)
  const request = useRef(0)
  const alive = useRef(true)
  const blocked = disabled || !!busy || continuityBusy
  const positionError = positiveNumberError(position, "Position")
  useEffect(() => { onBusy(!!busy || continuityBusy) }, [busy, continuityBusy, onBusy])
  useEffect(() => { onDirty(continuityDirty || !!bookId || !!position) }, [continuityDirty, bookId, position, onDirty])
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  const run = async (label: string, action: () => Promise<string>) => {
    if (locked.current || blocked) return
    locked.current = true; setBusy(label); setStatus(null)
    try { const text = await action(); if (alive.current) setStatus({ error: false, text }) }
    catch { if (alive.current) setStatus({ error: true, text: "The change could not be confirmed. Your form is preserved. Refresh series to check its current state before retrying." }) }
    finally { locked.current = false; if (alive.current) setBusy(null) }
  }
  const loadContext = async (kind: "bible" | "world") => {
    const id = ++request.current
    setContextLoading(kind); setContextError(null)
    try {
      if (kind === "bible") { const value = await booksApi.getSeriesBible(series.id); if (alive.current && id === request.current) setBible(value) }
      else { const value = await worldBuildingApi.getSeriesAnalysis(series.id); if (alive.current && id === request.current) setWorld(value) }
    } catch { if (alive.current && id === request.current) setContextError(kind) }
    finally { if (alive.current && id === request.current) setContextLoading(null) }
  }
  const togglePanel = (next: Exclude<Panel, null>) => {
    setPanel((current) => current === next ? null : next)
    if (panel !== next && (next === "bible" ? !bible : next === "world" ? !world : false)) void loadContext(next as "bible" | "world")
  }
  const add = () => {
    if (!bookId || positionError || !available.some((book) => book.id === bookId)) return
    void run("Adding project…", async () => {
      const result = await booksApi.addBookToSeries(series.id, bookId, { position: position.trim() ? Number(position) : null })
      onUpdate(result); setBookId(""); setPosition(""); setAdding(false); request.current++; setContextLoading(null); setBible(null); setWorld(null)
      await onRefresh()
      return "Project added. Review its position in the series below."
    })
  }
  const remove = (book: Book) => {
    if (!window.confirm(`Remove “${book.title}” from ${series.name}? The project and its content will stay in your library.`)) return
    void run("Removing project…", async () => { onUpdate(await booksApi.removeBookFromSeries(series.id, book.id)); request.current++; setContextLoading(null); setBible(null); setWorld(null); await onRefresh(); return "Project removed from this series. Its content remains in your library." })
  }
  const complete = (book: Book) => {
    if (!window.confirm(`Mark “${book.title}” complete? This also marks all of its chapters as read.`)) return
    void run("Marking project complete…", async () => { const updated = await booksApi.setSeriesBookStatus(series.id, book.id, true); if (updated.id) onUpdate({ ...series, books: series.books.map((item) => item.id === updated.id ? updated : item) }); await onRefresh(); return "Project marked complete and its chapters marked read." })
  }

  return <section aria-label="Selected series details" className="min-w-0 py-5 lg:pl-6">
    <div className="flex flex-col items-start justify-between gap-4 sm:flex-row"><div className="min-w-0 flex-1"><h2 className="text-2xl font-semibold">{series.name}</h2><p className={`mt-2 max-w-prose text-sm leading-6 ${muted}`}>{series.description || "No series description added."}</p></div><Link href={`/series/${series.id}/ask` as Route} className="app-button-secondary">Ask about this series</Link></div>
    <div className="mt-5 flex flex-wrap gap-3">
      {series.books.some((book) => book.work_type === "screenplay") ? <button type="button" aria-expanded={panel === "bible"} disabled={blocked} className="app-button-secondary" onClick={() => togglePanel("bible")}>{panel === "bible" ? "Hide series bible" : "Series bible"}</button> : null}
      <button type="button" aria-expanded={panel === "world"} disabled={blocked} className="app-button-secondary" onClick={() => togglePanel("world")}>{panel === "world" ? "Hide world analysis" : "World analysis"}</button>
      <button type="button" aria-expanded={panel === "continuity"} disabled={blocked} className="app-button-secondary" onClick={() => togglePanel("continuity")}>{panel === "continuity" ? "Close continuity check" : "Continuity check"}</button>
    </div>
    {panel === "bible" || panel === "world" ? <div className="mt-5 border-y border-[rgb(var(--border))] py-5">
      {contextLoading === panel ? <p role="status" className="text-sm">Loading series context…</p> : null}
      {contextLoading !== panel && contextError !== panel && !(panel === "bible" ? bible : world) ? <p className="text-sm">Series membership changed. Refresh context to load an updated reference.</p> : null}
      {contextError === panel ? <div role="alert" className="text-sm"><p>This series context could not be loaded.</p><button type="button" disabled={blocked} className="min-h-11 underline" onClick={() => void loadContext(panel)}>Retry series context</button></div> : null}
      {panel === "bible" && bible ? <SeriesBibleView bible={bible} /> : null}
      {panel === "world" && world ? <div><h3 className="text-lg font-semibold">World analysis</h3><p className={`mt-2 text-sm ${muted}`}>{world.analysis_count ?? 0} saved analyses across {world.book_count ?? 0} projects. This context may lag recent manuscript changes.</p><SeriesList title="Shared context" empty="No shared world context is available yet." items={worldContextItems(world)} /></div> : null}
      {contextLoading !== panel ? <button type="button" disabled={blocked} className="mt-3 min-h-11 underline" onClick={() => void loadContext(panel)}>Refresh context</button> : null}
    </div> : null}
    <div hidden={panel !== "continuity"} className="mt-5 border-y border-[rgb(var(--border))] py-5"><SeriesContinuityCheck series={series} disabled={disabled || !!busy} onBusy={setContinuityBusy} onDirty={setContinuityDirty} /></div>
    {busy ? <p role="status" className="mt-4 text-sm">{busy}</p> : null}
    {status ? <p role={status.error ? "alert" : "status"} className="mt-4 border-l-2 border-[rgb(var(--accent))] pl-4 text-sm leading-6">{status.text}</p> : null}
    <fieldset disabled={blocked} className="mt-6 min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold">Projects in this series</h3><p className={`mt-1 text-sm ${muted}`}>{series.books.length} projects · Positions define the reading order.</p></div><button type="button" disabled={availabilityError} className="app-button-secondary" onClick={() => { if (adding && (bookId || position) && !window.confirm("Discard the project selection and position?")) return; setAdding(!adding); setBookId(""); setPosition("") }}>{adding ? "Cancel adding project" : "Add project"}</button></div>
      {adding ? <div className="mt-4 space-y-3 border-y border-[rgb(var(--border))] py-4"><p className={`text-sm ${muted}`}>Choose an owned project that is not assigned to a series. Leave position blank to keep it unordered.</p>{available.length ? <><div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_9rem]"><label className="min-w-0 text-sm font-medium">Project<select aria-label="Project to add" value={bookId} onChange={(event) => setBookId(event.target.value)} className="app-input mt-2"><option value="">Choose a project</option>{available.map((book) => <option key={book.id} value={book.id}>{book.title}</option>)}</select></label><label className="min-w-0 text-sm font-medium">Position (optional)<input aria-label="Series position" inputMode="numeric" value={position} onChange={(event) => setPosition(event.target.value)} className="app-input mt-2" /></label></div>{positionError ? <p role="alert" className="text-sm">{positionError}</p> : null}<button type="button" disabled={!bookId || !!positionError} onClick={add} className="app-button-primary">Add</button></> : <p className="text-sm">No unassigned owned projects are available. Remove a project from its current series first, or create a project in your library.</p>}</div> : null}
      {series.books.length ? <div className="mt-4 border-t border-[rgb(var(--border))]">{series.books.map((book) => <div key={book.id} className="min-w-0 border-b border-[rgb(var(--border))] py-4"><div className="flex flex-wrap items-baseline gap-3"><span className={`text-sm ${muted}`}>{seriesVolumeLabel(book.work_type, book.series_order)}</span><Link href={getBookHref(book) as Route} className="min-w-0 text-base font-semibold underline underline-offset-4">{book.title}</Link></div><p className={`mt-2 text-sm ${muted}`}>{book.progress_pct == null ? "Reading progress unavailable" : `${Math.round(book.progress_pct)}% read`}{book.chapters_read_count != null ? ` · ${book.chapters_read_count} ${book.work_type === "screenplay" ? "scenes" : "chapters"} read` : ""}{book.chapters_left != null ? ` · ${book.chapters_left} left` : ""}</p><div className="mt-3 flex flex-wrap items-center gap-3"><Link href={getBookHref(book) as Route} className="app-button-secondary">Open</Link><button type="button" disabled={!!book.marked_complete_in_series} onClick={() => complete(book)} className="app-button-secondary">{book.marked_complete_in_series ? "Marked complete" : "Mark complete"}</button><button type="button" onClick={() => remove(book)} className="min-h-11 px-2 text-sm underline underline-offset-4">Remove</button></div></div>)}</div> : <p className="mt-5 text-sm">No projects have been added to this series.</p>}
    </fieldset>
  </section>
}

export function SeriesList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  const [expanded, setExpanded] = useState(false)
  return <section className="mt-5 min-w-0"><h4 className="text-base font-semibold">{title}</h4>{items.length ? <><ul className="mt-2 divide-y divide-[rgb(var(--border))] text-sm">{(expanded ? items : items.slice(0, 6)).map((item, index) => <li key={index} className="whitespace-pre-wrap py-3 leading-6">{item}</li>)}</ul>{items.length > 6 ? <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} className="min-h-11 text-sm underline">{expanded ? `Show fewer ${title.toLowerCase()}` : `Show all ${items.length} ${title.toLowerCase()}`}</button> : null}</> : <p className={`mt-2 text-sm ${muted}`}>{empty}</p>}</section>
}

function SeriesBibleView({ bible }: { bible: SeriesBible }) {
  return <div><h3 className="text-lg font-semibold">Series bible</h3><p className={`mt-2 text-sm ${muted}`}>{bible.episode_count} episodes · Generated reference; verify important details against the manuscript.</p><div className="grid min-w-0 gap-x-6 md:grid-cols-2"><SeriesList title="Episodes" empty="No parsed episodes yet." items={bible.episodes.map((item) => `${item.episode_number ? `Episode ${item.episode_number}: ` : ""}${item.title}`)} /><SeriesList title="Continuity risks" empty="No cross-episode risks returned. This does not verify consistency." items={bible.continuity_risks} /><SeriesList title="Recurring characters" empty="No recurring characters found." items={bible.recurring_characters.map((item) => `${item.name} · ${item.episode_count} episodes`)} /><SeriesList title="Open plot threads" empty="No open threads returned." items={bible.unresolved_plot_threads.map((item) => `${item.title} · ${item.status}${item.note ? ` — ${item.note}` : ""}`)} /><SeriesList title="Recurring relationships" empty="No recurring relationships returned." items={(bible.recurring_relationships ?? []).map((item) => `${(item.characters ?? []).join(" / ")} · ${item.relationship_type || "Relationship"}${item.note ? ` — ${item.note}` : ""}`)} /><SeriesList title="Canon entries" empty="No canon entries returned." items={(bible.canon_entries ?? []).map((item) => `${item.name}${item.description ? ` — ${item.description}` : ""}`)} /></div></div>
}
