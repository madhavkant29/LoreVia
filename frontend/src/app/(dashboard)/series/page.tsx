"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { WorkspaceHeader, WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { booksApi } from "@/lib/api/books"
import { isPaidTier } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"
import type { BookSelector, BookSeries } from "@/types/book"
import { loadAllSeries, loadSeriesProjects } from "./seriesPage.helpers"
import { useSeriesNavigationGuard } from "./seriesPage.navigation"
import { SeriesDetails } from "./seriesPage.details"

export default function SeriesPage() {
  const user = useAuthStore((state) => state.user)
  const hydrated = useAuthStore((state) => state.hydrated)
  const permitted = isPaidTier(user?.tier)
  const [series, setSeries] = useState<BookSeries[] | null>(null)
  const [books, setBooks] = useState<BookSelector[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [listError, setListError] = useState(false)
  const [booksError, setBooksError] = useState(false)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [createBusy, setCreateBusy] = useState(false)
  const [detailBusy, setDetailBusy] = useState(false)
  const [detailDirty, setDetailDirty] = useState(false)
  const [status, setStatus] = useState<{ error: boolean; text: string } | null>(null)
  const generation = useRef(0)
  const alive = useRef(true)
  const createLock = useRef(false)
  const selected = series?.find((item) => item.id === selectedId) ?? series?.[0] ?? null
  const blocked = loading || createBusy || detailBusy
  const newDraft = !!name.trim() || !!description.trim()
  const unassigned = useMemo(() => books.filter((book) => (!book.access_class || book.access_class === "owner") && !book.primary_series_id && !book.series_name), [books])
  useSeriesNavigationGuard(newDraft || detailDirty, createBusy || detailBusy)

  const load = useCallback(async (preferredId?: string) => {
    const request = ++generation.current
    setLoading(true)
    const [collection, selector] = await Promise.allSettled([loadAllSeries(), loadSeriesProjects()])
    if (!alive.current || request !== generation.current) return
    if (collection.status === "fulfilled") {
      setSeries(collection.value); setListError(false)
      setSelectedId((current) => collection.value.some((item) => item.id === (preferredId ?? current)) ? preferredId ?? current : collection.value[0]?.id ?? null)
    } else setListError(true)
    if (selector.status === "fulfilled") { setBooks(selector.value); setBooksError(false) } else setBooksError(true)
    setLoading(false)
  }, [])

  useEffect(() => {
    alive.current = true
    if (hydrated && permitted) void load()
    return () => { alive.current = false }
  }, [hydrated, permitted, load])

  const selectSeries = (id: string) => {
    if (blocked || id === selected?.id) return
    if (detailDirty && !window.confirm("Switch series and discard the current project form and continuity passage?")) return
    setDetailDirty(false); setSelectedId(id)
  }
  const closeCreate = () => {
    if (newDraft && !window.confirm("Discard the new series name and description?")) return
    setCreating(false); setName(""); setDescription("")
  }
  const create = async () => {
    if (createLock.current || blocked || !name.trim()) return
    createLock.current = true; setCreateBusy(true); setStatus(null)
    try {
      const created = await booksApi.createSeries({ name: name.trim(), description: description.trim() || null })
      if (!alive.current) return
      setSeries((current) => [...(current ?? []).filter((item) => item.id !== created.id), { ...created, name: created.name || name.trim(), description: created.description ?? description.trim(), books: created.books ?? [] }])
      setName(""); setDescription(""); setCreating(false)
      setStatus({ error: false, text: "Series created. Select it to add projects." })
      // Keep an existing continuity draft attached to its series.
      await load(detailDirty ? selected?.id : created.id)
    } catch { if (alive.current) setStatus({ error: true, text: "Creation could not be confirmed. Your draft is preserved. Refresh the series list before retrying to avoid a duplicate." }) }
    finally { createLock.current = false; if (alive.current) setCreateBusy(false) }
  }

  return <WorkspacePage className="min-h-0 bg-transparent">
    <div data-series-workspace className="min-w-0 space-y-6 pb-12 [overflow-wrap:anywhere]">
      <header className="border-b border-[rgb(var(--border))] pb-6"><WorkspaceHeader eyebrow="Connected projects" title="Series management" description="Group related projects, set their order, and review context across your series." actions={<div className="flex flex-wrap gap-3"><button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>{permitted && hydrated ? <button type="button" className="app-button-secondary" disabled={blocked} onClick={() => void load()}>{loading ? "Refreshing…" : "Refresh series"}</button> : null}</div>} /></header>
      {!hydrated ? <p role="status" className="py-6 text-sm">Loading series workspace…</p> : !permitted ? <section className="border-b border-[rgb(var(--border))] py-6"><h2 className="text-xl font-semibold">Series workspace</h2><p className="mt-3 text-sm">Series mode is reserved for paid plans.</p><Link href="/pricing" className="app-button-secondary mt-4">View plans</Link></section> : <>
        {status ? <p role={status.error ? "alert" : "status"} className="border-l-2 border-[rgb(var(--accent))] pl-4 text-sm leading-6">{status.text}</p> : null}
        {loading && !series ? <p role="status" className="py-6 text-sm">Loading your series…</p> : null}
        {listError ? <div role="alert" className="border-l-2 border-amber-600 pl-4 text-sm"><p>{series ? "Series could not be refreshed. Previously loaded projects remain visible." : "Your series could not be loaded. Check your access or try again."}</p><button type="button" disabled={blocked} className="mt-2 min-h-11 underline" onClick={() => void load()}>Retry series</button></div> : null}
        {booksError ? <div role="alert" className="border-l-2 border-amber-600 pl-4 text-sm"><p>Available projects could not be loaded. Series browsing still works.</p><button type="button" disabled={blocked} className="mt-2 min-h-11 underline" onClick={() => void load()}>Retry available projects</button></div> : null}
        {series ? <div className="min-w-0 border-y border-[rgb(var(--border))] lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]">
          <aside aria-label="Series list" className="min-w-0 border-b border-[rgb(var(--border))] py-4 lg:border-b-0 lg:border-r lg:pr-5">
            <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-base font-semibold">Your series ({series.length})</h2><button type="button" className="app-button-secondary" disabled={blocked} onClick={() => creating ? closeCreate() : setCreating(true)}>{creating ? "Cancel new series" : "New series"}</button></div>
            {creating ? <fieldset disabled={blocked} className="mt-4 min-w-0 space-y-3 border-y border-[rgb(var(--border))] py-4"><label className="block text-sm font-medium">Name<input aria-label="Series name" value={name} onChange={(event) => setName(event.target.value)} className="app-input mt-2" /></label><label className="block text-sm font-medium">Description (optional)<textarea aria-label="Series description" value={description} onChange={(event) => setDescription(event.target.value)} rows={3} className="app-input mt-2 resize-y" /></label><button type="button" className="app-button-primary" disabled={!name.trim()} onClick={() => void create()}>{createBusy ? "Creating…" : "Create series"}</button></fieldset> : null}
            {series.length ? <><div className="mt-4 hidden max-h-[36rem] overflow-auto border-t border-[rgb(var(--border))] lg:block">{series.map((item) => <button key={item.id} type="button" disabled={blocked} aria-current={item.id === selected?.id ? "page" : undefined} onClick={() => selectSeries(item.id)} className={`block w-full border-b border-[rgb(var(--border))] px-2 py-3 text-left text-sm ${item.id === selected?.id ? "bg-[rgb(var(--card))] font-semibold underline underline-offset-4" : ""}`}><span className="block [overflow-wrap:anywhere]">{item.name}</span><span className="mt-1 block text-[rgb(var(--muted-foreground))]">{item.books.length} projects</span></button>)}</div><label className="mt-4 block text-sm font-medium lg:hidden">Selected series<select aria-label="Selected series" className="app-input mt-2" disabled={blocked} value={selected?.id ?? ""} onChange={(event) => selectSeries(event.target.value)}>{series.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></> : <p className="mt-4 text-sm leading-6">No series yet. Create one to group related projects and manage their order.</p>}
          </aside>
          {selected ? <SeriesDetails key={selected.id} series={selected} available={unassigned} availabilityError={booksError} disabled={loading || createBusy || listError} onBusy={setDetailBusy} onDirty={setDetailDirty} onRefresh={() => load(selected.id)} onUpdate={(updated) => { if (updated.books) setSeries((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? [updated]) }} /> : <p className="p-6 text-sm">Create a series, then add projects from your library.</p>}
        </div> : null}
      </>}
    </div>
  </WorkspacePage>
}
