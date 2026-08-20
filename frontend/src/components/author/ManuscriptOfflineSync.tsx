"use client"

import { useCallback, useEffect, useState } from "react"
import { CloudOff, RefreshCw, TriangleAlert } from "lucide-react"

import {
  discardQueuedManuscriptSave,
  filterManuscriptOutboxEntriesForUser,
  listManuscriptOutbox,
  MANUSCRIPT_OUTBOX_EVENT,
  type ManuscriptOutboxEntry,
  queueManuscriptConflictOverwrite,
  syncManuscriptOutbox,
} from "@/lib/offline/manuscriptOutbox"
import { useAuthStore } from "@/lib/stores/authStore"

function downloadOfflineDraft(entry: ManuscriptOutboxEntry) {
  if (useAuthStore.getState().user?.id !== entry.userId) return
  const blob = new Blob([entry.text], { type: "text/plain;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `${entry.title.replace(/[^A-Za-z0-9_-]+/g, "-") || `chapter-${entry.chapterNumber}`}-offline.txt`
  link.click()
  URL.revokeObjectURL(url)
}

export function ManuscriptOfflineSync() {
  const userId = useAuthStore((state) => state.user?.id ?? null)
  const [entries, setEntries] = useState<ManuscriptOutboxEntry[]>([])
  const [syncing, setSyncing] = useState(false)
  const [online, setOnline] = useState(true)
  const refresh = useCallback(async () => {
    if (!userId) {
      setEntries([])
      return
    }
    const nextEntries = await listManuscriptOutbox().catch(() => [])
    if (useAuthStore.getState().user?.id === userId) setEntries(nextEntries)
  }, [userId])
  const sync = useCallback(async () => {
    if (!userId) {
      setEntries([])
      return
    }
    setSyncing(true)
    try {
      await syncManuscriptOutbox()
      await refresh()
    } catch {
      await refresh()
    } finally {
      setSyncing(false)
    }
  }, [refresh, userId])
  useEffect(() => {
    void refresh()
    setOnline(navigator.onLine)
    const onOnline = () => { setOnline(true); void sync() }
    const onOffline = () => setOnline(false)
    const onChange = () => void refresh()
    window.addEventListener("online", onOnline)
    window.addEventListener("offline", onOffline)
    window.addEventListener(MANUSCRIPT_OUTBOX_EVENT, onChange)
    if (navigator.onLine) void sync()
    return () => { window.removeEventListener("online", onOnline); window.removeEventListener("offline", onOffline); window.removeEventListener(MANUSCRIPT_OUTBOX_EVENT, onChange) }
  }, [refresh, sync])
  const visibleEntries = filterManuscriptOutboxEntriesForUser(entries, userId)
  const conflictEntries = visibleEntries.filter((entry) => entry.status === "conflict")
  const resolveConflict = async (entry: ManuscriptOutboxEntry, overwrite: boolean) => {
    if (useAuthStore.getState().user?.id !== entry.userId) return
    const approved = window.confirm(
      overwrite
        ? `Replace the server copy of Chapter ${entry.chapterNumber} with this offline draft?`
        : `Discard the offline copy of Chapter ${entry.chapterNumber} and keep the server version?`,
    )
    if (!approved) return
    setSyncing(true)
    try {
      if (overwrite) {
        if (await queueManuscriptConflictOverwrite(entry)) await syncManuscriptOutbox()
      } else {
        await discardQueuedManuscriptSave(entry)
      }
      await refresh()
    } finally {
      setSyncing(false)
    }
  }
  const pending = visibleEntries.length
  const conflicts = conflictEntries.length
  if (!pending) return null
  return <div className={`fixed bottom-4 right-4 z-[80] max-w-md rounded-xl border px-4 py-3 text-sm shadow-xl ${conflicts ? "border-amber-300 bg-amber-50 text-amber-950" : "border-sky-200 bg-white text-slate-800"}`}><div className="flex items-center gap-3">{conflicts ? <TriangleAlert className="h-5 w-5 shrink-0" /> : <CloudOff className="h-5 w-5 shrink-0" />}<span className="flex-1">{conflicts ? `${conflicts} offline edit(s) need conflict review.` : `${pending} edit(s) saved offline and waiting to sync.`}</span><button type="button" disabled={syncing || !online} onClick={() => void sync()} className="rounded-lg border px-2 py-1 font-semibold disabled:opacity-40" aria-label="Sync offline manuscript edits"><RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} /></button></div>{conflictEntries.length > 0 ? <div className="mt-3 space-y-2 border-t border-amber-200 pt-3">{conflictEntries.map((entry) => <div key={entry.id} className="rounded-lg bg-white/70 p-3"><p className="font-semibold">Chapter {entry.chapterNumber}: {entry.title}</p><p className="mt-1 text-xs text-amber-800">The server changed after this offline copy was created. Download it before choosing which version to keep.</p><div className="mt-2 flex flex-wrap gap-2"><button type="button" onClick={() => downloadOfflineDraft(entry)} className="rounded-md border px-2 py-1 text-xs font-semibold">Download offline copy</button><button type="button" disabled={syncing} onClick={() => void resolveConflict(entry, false)} className="rounded-md border px-2 py-1 text-xs font-semibold disabled:opacity-40">Keep server</button><button type="button" disabled={syncing || !online} onClick={() => void resolveConflict(entry, true)} className="rounded-md bg-amber-700 px-2 py-1 text-xs font-semibold text-white disabled:opacity-40">Use offline copy</button></div></div>)}</div> : null}</div>
}
