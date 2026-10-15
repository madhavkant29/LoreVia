"use client"

import { useEffect, useRef, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { downloadExportBlob, exportErrorMessage, safeFileBase } from "@/lib/utils/exportFiles"
import type { WorkflowBridgePreview } from "@/types/book"

export function WorkflowBridgePanel({ bookId, bookTitle, isDark, disabled = false, onBusyChange }: { bookId: string; bookTitle: string; isDark: boolean; disabled?: boolean; onBusyChange?: (busy: boolean) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const locked = useRef(false)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<WorkflowBridgePreview | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null)
  useEffect(() => { onBusyChange?.(!!busy) }, [busy, onBusyChange])
  const run = async (label: string, failure: string, action: () => Promise<string>) => {
    if (locked.current || disabled) return
    locked.current = true; setBusy(label); setMessage(null)
    try { setMessage({ error: false, text: await action() }) }
    catch (error) { setMessage({ error: true, text: await exportErrorMessage(error, failure) }) }
    finally { locked.current = false; setBusy(null) }
  }
  const inspect = (nextFile: File) => {
    if (locked.current || disabled) return
    setFile(nextFile); setPreview(null); setConfirmed(false)
    if (!nextFile.size || !/\.(docx|scrivzip|scriv\.zip)$/i.test(nextFile.name)) { setMessage({ error: true, text: "Choose a non-empty DOCX or zipped Scrivener project (.scrivzip or .scriv.zip)." }); return }
    void run("Inspecting incoming draft…", "That file could not be previewed. Try again.", async () => { setPreview(await booksApi.previewWorkflowBridge(bookId, nextFile)); return "Preview ready. Review the chapter changes before applying." })
  }
  const apply = () => {
    if (!file || !confirmed || !preview?.preview_token) return
    void run("Applying reviewed changes…", "The import could not be confirmed. Check the manuscript, then create a fresh preview before applying again.", async () => {
      try {
        const result = await booksApi.applyWorkflowBridge(bookId, file, preview.preview_token)
        setFile(null); if (inputRef.current) inputRef.current.value = ""
        return `Updated ${result.imported_chapters.length} chapter(s). Chapters absent from the file were preserved.`
      } finally { setPreview(null); setConfirmed(false) }
    })
  }
  return <section className={`min-w-0 ${isDark ? "text-slate-100" : "text-stone-950"}`}>
    <h2 className="text-xl font-semibold">Round-trip with Word or Scrivener</h2>
    <p className="mt-2 max-w-3xl text-sm leading-6 text-[rgb(var(--muted-foreground))]">Preview chapter changes before replacing matching chapter numbers. Updated chapters receive pre-replace snapshots; chapters absent from the incoming file stay untouched.</p>
    <fieldset disabled={disabled || !!busy} className="mt-4 min-w-0">
      <div className="flex flex-wrap gap-3"><button type="button" className="app-button-secondary" onClick={() => void run("Preparing Scrivener project…", "The Scrivener project could not be generated. Try again.", async () => { downloadExportBlob(await booksApi.exportScrivenerProject(bookId), `${safeFileBase(bookTitle, "LoreVia-Project")}.scrivzip`); return "Downloaded Scrivener project." })}>Export Scrivener</button><button type="button" className="app-button-secondary" onClick={() => inputRef.current?.click()}>Preview incoming draft</button></div>
      <input ref={inputRef} type="file" aria-label="Choose manuscript or Scrivener archive" accept=".docx,.scrivzip,.scriv.zip" className="hidden" onChange={(event) => { const nextFile = event.target.files?.[0]; if (nextFile) inspect(nextFile); event.target.value = "" }} />
      {file ? <div className="mt-3 flex flex-wrap items-center gap-3 text-sm"><span>{file.name}</span><button type="button" className="underline underline-offset-4" onClick={() => inspect(file)}>Refresh preview</button><button type="button" className="underline underline-offset-4" onClick={() => { setFile(null); setPreview(null); setConfirmed(false); setMessage(null) }}>Clear incoming draft</button></div> : null}
      {preview ? <div className="mt-5 border-y border-[rgb(var(--border))] py-4">
        <p className="text-sm">{preview.changed_count} changed · {preview.new_count} new · {preview.unchanged_count} unchanged · {preview.preserved_chapter_numbers.length} preserved</p>
        <ul aria-label="Incoming chapter changes" tabIndex={0} className="mt-3 max-h-72 overflow-auto divide-y divide-[rgb(var(--border))]">{preview.chapters.map((chapter, index) => <li key={`${chapter.incoming_number}-${index}`} className="flex items-start justify-between gap-4 py-3 text-sm"><span className="min-w-0 [overflow-wrap:anywhere]">Chapter {chapter.incoming_number} — {chapter.incoming_title}</span><span className="shrink-0">{chapter.status}</span></li>)}</ul>
        <label className="mt-4 flex items-start gap-3 text-sm leading-6"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" /><span>I reviewed this preview and want to replace matching chapter numbers. Missing current chapters remain preserved.</span></label>
        <button type="button" disabled={!confirmed || !preview.preview_token || preview.changed_count + preview.new_count === 0} className="app-button-primary mt-4" onClick={apply}>Apply reviewed changes</button>
        {preview.changed_count + preview.new_count === 0 ? <p className="mt-2 text-sm">No changes to apply.</p> : null}
      </div> : null}
    </fieldset>
    {busy ? <p role="status" className="mt-4 text-sm">{busy} Keep this page open.</p> : null}
    {message ? <p role={message.error ? "alert" : "status"} className={`mt-4 border-l-2 pl-3 text-sm leading-6 ${message.error ? "border-rose-600" : "border-[rgb(var(--accent))]"}`}>{message.text}</p> : null}
  </section>
}
