"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import { useAuthStore } from "@/lib/stores/authStore"
import { defaultBookUiPreference, useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { toolsForPlacement } from "@/lib/workspace/toolRegistry"
import { resolveWorkspaceTools } from "@/lib/workspace/toolResolver"
import type { Book } from "@/types/book"
import type { UserBookUiPreference } from "@/types/uiPreferences"
import { navigationToolDetail, navigationToolOperations, restoreNavigationToolOperations } from "./visibilityPage.helpers"

const BOOK_TOOLS = toolsForPlacement("book").filter(tool => !tool.nonHideable && tool.id !== "book.visibility")

export function VisibilityNavigation({ book, preferenceBookId }: { book: Book; preferenceBookId: string }) {
  const user = useAuthStore(state => state.user)
  const activeUserId = useUiPreferencesStore(state => state.activeUserId)
  const global = useUiPreferencesStore(state => state.preferences)
  const saved = useUiPreferencesStore(state => state.bookPreferences[preferenceBookId])
  const pending = useUiPreferencesStore(state => state.pendingBookOperations[preferenceBookId]?.length ?? 0)
  const syncState = useUiPreferencesStore(state => state.syncState)
  const hydrateBook = useUiPreferencesStore(state => state.hydrateBook)
  const retrySync = useUiPreferencesStore(state => state.retrySync)
  const patchBook = useUiPreferencesStore(state => state.patchBook)
  const preference = saved ?? defaultBookUiPreference(preferenceBookId, global.complexity_mode)
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState("")
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState("all")
  const [undo, setUndo] = useState<{ toolId: string; label: string; previous: UserBookUiPreference } | null>(null)
  const lock = useRef(false)
  const searchInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let live = true
    setLoading(true)
    void hydrateBook(preferenceBookId).then(success => { if (live) { setLoaded(success); setLoadError(!success); setLoading(false) } })
    return () => { live = false }
  }, [hydrateBook, preferenceBookId, activeUserId])

  const load = async () => {
    if (lock.current) return
    lock.current = true; setLoading(true)
    try { const success = await hydrateBook(preferenceBookId); setLoaded(success); setLoadError(!success) }
    finally { lock.current = false; setLoading(false) }
  }
  const currentPreference = () => useUiPreferencesStore.getState().bookPreferences[preferenceBookId] ?? preference
  const change = async (toolId: string, label: string, visible: boolean) => {
    if (lock.current || !loaded || !activeUserId) return
    lock.current = true; setSaving(true)
    const previous = currentPreference()
    try {
      await patchBook(preferenceBookId, navigationToolOperations(previous, toolId, visible))
      setUndo({ toolId, label, previous }); setMessage(`${label} ${visible ? "shown" : "hidden"} in this book’s navigation.`)
    } catch { setMessage("Navigation could not be changed. Try again.") }
    finally { lock.current = false; setSaving(false) }
  }
  const undoChange = async () => {
    if (!undo || lock.current || !activeUserId) return
    lock.current = true; setSaving(true)
    try { await patchBook(preferenceBookId, restoreNavigationToolOperations(currentPreference(), undo.previous, undo.toolId)); setMessage(`${undo.label} navigation setting restored.`); setUndo(null) }
    catch { setMessage("The previous navigation setting could not be restored. Try again.") }
    finally { lock.current = false; setSaving(false) }
  }
  const retry = async () => {
    if (lock.current) return
    lock.current = true; setSaving(true)
    try { await retrySync() }
    finally { lock.current = false; setSaving(false) }
  }
  const tools = resolveWorkspaceTools(BOOK_TOOLS, { mode: global.complexity_mode, book, bookPreference: preference, globalPreference: global, placement: "book", hasAuthorAccess: canUseAuthorFeatures(user?.tier) })
  const filtered = tools.filter(item => (filter === "all" || (filter === "hidden" ? item.hidden : !item.hidden)) && `${item.tool.label} ${item.tool.group}`.toLowerCase().includes(query.trim().toLowerCase()))
  const disabled = loading || saving || !loaded || !activeUserId
  return <div className="mt-5 border-t pt-5">
    <h2 className="text-xl font-semibold">Hidden and visible tools</h2>
    <p className="mt-2 max-w-3xl text-sm leading-6 text-[rgb(var(--muted-foreground))]">Choose which tools appear in this book’s navigation. Revealing one tool preserves your workspace mode and book preset. Plan and access requirements still apply.</p>
    <p className="mt-2 text-sm leading-6">This does not change who can access the book.</p>
    <p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">Access & Visibility stays available here so you can recover hidden tools.</p>
    {loading ? <p role="status" className="mt-4 text-sm">Loading navigation preferences…</p> : null}
    {loadError ? <div role="alert" className="mt-4 border-l-2 pl-4 text-sm leading-6"><p>Navigation preferences could not be loaded. The last local layout is shown; load the saved preferences before changing it.</p><button className="app-button-secondary mt-3" disabled={loading} onClick={() => void load()}>Retry navigation preferences</button></div> : null}
    {pending ? <div role="status" className="mt-4 flex flex-wrap items-center gap-3 border-y py-3 text-sm"><span>{syncState === "syncing" ? "Syncing this book’s navigation…" : "Navigation changes are pending sync. They are applied on this device."}</span><button className="app-button-secondary" disabled={saving || syncState === "syncing"} onClick={() => void retry()}>Retry navigation sync</button></div> : null}
    {message ? <div role="status" className="mt-4 flex flex-wrap items-center gap-3 text-sm"><p>{message}</p>{undo ? <button className="app-button-secondary" disabled={disabled} onClick={() => void undoChange().then(() => requestAnimationFrame(() => searchInput.current?.focus()))}>Undo navigation change</button> : null}</div> : null}
    <div className="my-5 grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem]"><label className="grid gap-2 text-sm">Search tools<input ref={searchInput} type="search" className="app-input" value={query} onChange={event => setQuery(event.target.value)} placeholder="Tool name or group" /></label><label className="grid gap-2 text-sm">Navigation visibility<select className="app-input" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All tools</option><option value="hidden">Hidden</option><option value="visible">Shown</option></select></label></div>
    <p className="text-sm text-[rgb(var(--muted-foreground))]">{tools.filter(item => item.hidden).length} hidden · {filtered.length} matching tools</p>
    <ul className="mt-3 divide-y border-y">{filtered.map(item => <li key={item.tool.id} className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><div className="min-w-0"><h3 className="text-sm font-semibold">{item.tool.label}</h3><p className="mt-1 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{item.tool.group} · {navigationToolDetail(item)}</p></div><div className="flex flex-wrap gap-3">{item.access === "available" ? <Link className="app-button-secondary" href={item.href as Route} aria-label={`Open ${item.tool.label}`}>Open</Link> : null}<button className="app-button-secondary" disabled={disabled} aria-label={`${item.hidden ? "Show" : "Hide"} ${item.tool.label}`} onClick={event => { const trigger = event.currentTarget; void change(item.tool.id, item.tool.label, item.hidden).then(() => requestAnimationFrame(() => { if (trigger.isConnected) trigger.focus(); else searchInput.current?.focus() })) }}>{item.hidden ? "Show" : "Hide"}</button></div></li>)}</ul>
    {!filtered.length ? <div className="py-5 text-sm"><p>No tools match these filters.</p><button className="app-button-secondary mt-3" onClick={() => { setQuery(""); setFilter("all") }}>Clear tool filters</button></div> : null}
  </div>
}
