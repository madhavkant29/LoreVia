"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { zipSync, strToU8 } from "fflate"
import { booksApi } from "@/lib/api/books"
import { downloadExportBlob, safeFileBase } from "@/lib/utils/exportFiles"
import type { VaultPreview as VaultPreviewData } from "@/types/book"

export function VaultPreview({ bookId, preview, isDark, disabled = false, onStateChange }: { bookId: string; preview: VaultPreviewData; isDark: boolean; disabled?: boolean; onStateChange?: (state: { dirty: boolean; busy: boolean }) => void }) {
  const files = useMemo(() => [...preview.files].sort((a, b) => a.path.localeCompare(b.path)), [preview.files])
  const [query, setQuery] = useState("")
  const [selectedPath, setSelectedPath] = useState(files[0]?.path ?? "")
  const [drafts, setDrafts] = useState<Record<string, string>>(() => Object.fromEntries(files.map((file) => [file.path, file.content])))
  const [saved, setSaved] = useState(drafts)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<string | null>(null)
  const latest = useRef(drafts)
  const queue = useRef(new Map<string, string>())
  const saving = useRef(false)
  const timers = useRef<Record<string, number>>({})
  const alive = useRef(true)
  const selected = files.find((file) => file.path === selectedPath) ?? files[0]
  const content = selected ? drafts[selected.path] ?? selected.content : ""
  const dirty = files.some((file) => drafts[file.path] !== saved[file.path])
  const selectedDirty = !!selected && drafts[selected.path] !== saved[selected.path]
  const filtered = files.filter((file) => `${file.path} ${drafts[file.path] ?? file.content}`.toLowerCase().includes(query.trim().toLowerCase()))
  const relative = (path: string) => path.startsWith(`${preview.root_folder}/`) ? path.slice(preview.root_folder.length + 1) : path
  useEffect(() => { onStateChange?.({ dirty, busy }) }, [dirty, busy, onStateChange])
  useEffect(() => {
    alive.current = true
    const pending = timers.current
    return () => { alive.current = false; Object.values(pending).forEach(window.clearTimeout) }
  }, [])
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (dirty || busy) { event.preventDefault(); event.returnValue = "" } }
    window.addEventListener("beforeunload", unload)
    return () => window.removeEventListener("beforeunload", unload)
  }, [dirty, busy])

  const save = async (path: string, value: string) => {
    window.clearTimeout(timers.current[path]); delete timers.current[path]
    queue.current.set(path, value)
    if (saving.current) return
    saving.current = true; setBusy(true)
    try {
      while (queue.current.size) {
        const [nextPath, nextContent] = queue.current.entries().next().value as [string, string]
        queue.current.delete(nextPath)
        if (alive.current) setStatus(`Saving ${relative(nextPath)}…`)
        try {
          const result = await booksApi.saveCharacterBibleVaultNote(bookId, { path: nextPath, content: nextContent })
          if (!alive.current) continue
          setSaved((current) => ({ ...current, [nextPath]: result.content }))
          if (latest.current[nextPath] === nextContent) { latest.current = { ...latest.current, [nextPath]: result.content }; setDrafts(latest.current) }
          setErrors((current) => { const next = { ...current }; delete next[nextPath]; return next })
          setStatus(`Saved ${relative(nextPath)}`)
        } catch {
          if (alive.current) { setErrors((current) => ({ ...current, [nextPath]: `Could not save ${relative(nextPath)}. Your draft is preserved; select it and retry Save note.` })); setStatus(null) }
        }
      }
    } finally { saving.current = false; if (alive.current) setBusy(false) }
  }
  const edit = (path: string, value: string) => {
    latest.current = { ...latest.current, [path]: value }; setDrafts(latest.current); setStatus(null)
    window.clearTimeout(timers.current[path])
    timers.current[path] = window.setTimeout(() => void save(path, value), 700)
  }
  const restore = (all: boolean) => {
    if (!window.confirm(all ? "Restore every file to the version loaded in this preview? This replaces current edits and saved overrides with those versions." : "Restore this file to the version loaded in this preview?")) return
    for (const file of all ? files : selected ? [selected] : []) { latest.current = { ...latest.current, [file.path]: file.content }; setDrafts(latest.current); void save(file.path, file.content) }
  }
  const download = () => {
    try {
      const archive = zipSync(Object.fromEntries(files.map((file) => [file.path, strToU8(drafts[file.path] ?? file.content)])), { level: 6 })
      downloadExportBlob(new Blob([archive as unknown as BlobPart], { type: "application/zip" }), `${safeFileBase(preview.root_folder, "vault-export").toLowerCase()}-edited.zip`)
      setStatus("Downloaded edited vault. The ZIP includes current drafts, including any unsaved edits.")
    } catch { setStatus("The edited vault could not be downloaded. Your drafts are still here; try again.") }
  }
  return <section className={`min-w-0 border-t border-[rgb(var(--border))] pt-6 ${isDark ? "text-slate-100" : "text-stone-950"}`}>
    <h2 className="text-xl font-semibold">Vault preview and editor</h2><p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">Edit Markdown overrides for character-bible Vault ZIP exports. Changes save automatically. Reset restores the version loaded in this preview.</p>
    <p className="mt-2 text-sm">{files.length} files · {preview.root_folder}</p>
    {Object.values(errors).map((message) => <p key={message} role="alert" className="mt-3 border-l-2 border-rose-600 pl-3 text-sm">{message}</p>)}
    {status ? <p role="status" className="mt-3 text-sm">{status}</p> : null}
    <fieldset disabled={disabled} className="mt-4 grid min-w-0 gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside className="min-w-0"><label className="block text-sm font-medium">Search notes or content<input aria-label="Search notes or content" type="search" value={query} onChange={(event) => setQuery(event.target.value)} className="export-field mt-2 min-h-11 w-full border border-[rgb(var(--border))] px-3" /></label><p className="my-3 text-sm">{filtered.length} notes visible</p>
        {!filtered.length ? <div className="py-3 text-sm"><p>No notes match that search.</p><button type="button" onClick={() => setQuery("")} className="mt-2 underline">Clear search</button></div> : <div className="max-h-64 overflow-auto border-y border-[rgb(var(--border))] lg:max-h-[34rem]">{filtered.map((file) => <button type="button" key={file.path} aria-pressed={selected?.path === file.path} onClick={() => setSelectedPath(file.path)} className={`block w-full border-b border-[rgb(var(--border))] px-3 py-3 text-left text-sm [overflow-wrap:anywhere] ${selected?.path === file.path ? "bg-[rgb(var(--card))] font-semibold underline underline-offset-4" : ""}`}>{relative(file.path)}{drafts[file.path] !== saved[file.path] ? " · unsaved" : ""}</button>)}</div>}
        <button type="button" disabled={busy || !files.length} onClick={() => restore(true)} className="app-button-secondary mt-3">Reset all</button>
      </aside>
      <div className="min-w-0">{selected ? <>
        <h3 className="text-base font-semibold [overflow-wrap:anywhere]">{relative(selected.path)}</h3>
        <p className="mt-2 text-sm">{selectedDirty ? "You have unsaved edits for this note." : "This note is saved."}{busy ? " Saving…" : ""}</p>
        <div className="my-3 flex flex-wrap gap-2"><button type="button" disabled={!selectedDirty || busy} onClick={() => void save(selected.path, content)} className="app-button-primary">Save note</button><button type="button" className="app-button-secondary" onClick={async () => { try { await navigator.clipboard.writeText(content); setStatus("Copied note text.") } catch { setStatus("Could not copy. Select and copy the note text manually.") } }}>Copy text</button><button type="button" disabled={busy} onClick={() => restore(false)} className="app-button-secondary">Reset file</button><button type="button" className="app-button-secondary" onClick={download}>Download edited Vault ZIP</button></div>
        <textarea aria-label="Vault note content" value={content} onChange={(event) => edit(selected.path, event.target.value)} spellCheck={false} className="export-field min-h-80 w-full resize-y border border-[rgb(var(--border))] p-3 font-mono text-sm leading-7 lg:min-h-[30rem]" />
        <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{content.trim() ? content.trim().split(/\s+/).length : 0} words · {content.length} characters</p>
      </> : <p className="py-6 text-sm">No files are available in this preview.</p>}</div>
    </fieldset>
  </section>
}
