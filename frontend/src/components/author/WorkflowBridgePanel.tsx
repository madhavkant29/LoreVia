"use client"

import { useRef, useState } from "react"
import { ArrowDownToLine, ArrowUpFromLine, CheckCircle2, FileSearch, RefreshCw } from "lucide-react"

import { booksApi } from "@/lib/api/books"
import type { WorkflowBridgePreview } from "@/types/book"

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function WorkflowBridgePanel({ bookId, bookTitle, isDark }: { bookId: string; bookTitle: string; isDark: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<WorkflowBridgePreview | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const inspect = async (nextFile: File) => {
    setFile(nextFile)
    setPreview(null)
    setConfirmed(false)
    setBusy(true)
    setMessage(null)
    try { setPreview(await booksApi.previewWorkflowBridge(bookId, nextFile)) } catch { setMessage("That file could not be previewed. Use a DOCX or zipped Scrivener project.") } finally { setBusy(false) }
  }

  const apply = async () => {
    if (!file || !confirmed || !preview) return
    setBusy(true)
    setMessage(null)
    try {
      const result = await booksApi.applyWorkflowBridge(bookId, file, preview.preview_token)
      setMessage(`Updated ${result.imported_chapters.length} chapter(s). Existing chapters missing from the file were preserved.`)
      setPreview(null)
      setFile(null)
      setConfirmed(false)
    } catch { setMessage("The import could not be applied. LoreVia kept the current draft unchanged.") } finally { setBusy(false) }
  }

  const exportScrivener = async () => {
    setBusy(true)
    try {
      const blob = await booksApi.exportScrivenerProject(bookId)
      downloadBlob(blob, `${bookTitle.replace(/[^A-Za-z0-9_-]+/g, "-") || "LoreVia-Project"}.scrivzip`)
    } catch { setMessage("The Scrivener project could not be generated.") } finally { setBusy(false) }
  }

  return (
    <section className={`border p-5 ${isDark ? "border-violet-300/20 bg-violet-300/[0.05]" : "border-violet-200 bg-violet-50/70"}`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div><p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>Workflow Bridge</p><h2 className="mt-2 text-xl font-semibold">Round-trip with Word or Scrivener</h2><p className={`mt-2 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>Preview chapter-level changes before applying them. Updated chapters receive automatic pre-replace snapshots; chapters absent from the incoming file stay untouched.</p></div>
        <button type="button" disabled={busy} onClick={() => void exportScrivener()} className={`inline-flex items-center gap-2 border px-4 py-2.5 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5" : "border-violet-200 bg-white"}`}><ArrowDownToLine className="h-4 w-4" /> Export Scrivener</button>
      </div>
      <input ref={inputRef} type="file" accept=".docx,.scrivzip,.scriv.zip,application/zip" className="sr-only" onChange={(event) => { const nextFile = event.target.files?.[0]; if (nextFile) void inspect(nextFile) }} />
      <div className="mt-5 flex flex-wrap items-center gap-3"><button type="button" disabled={busy} onClick={() => inputRef.current?.click()} className="inline-flex items-center gap-2 bg-[#1f615d] px-4 py-2.5 text-sm font-semibold text-white"><FileSearch className="h-4 w-4" /> Preview incoming draft</button>{file ? <span className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{file.name}</span> : null}{busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}</div>
      {preview ? <div className={`mt-5 border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-white bg-white"}`}><div className="flex flex-wrap gap-2 text-xs font-semibold"><span className="rounded-full bg-amber-500/10 px-3 py-1.5">{preview.changed_count} changed</span><span className="rounded-full bg-emerald-500/10 px-3 py-1.5">{preview.new_count} new</span><span className="rounded-full bg-slate-500/10 px-3 py-1.5">{preview.unchanged_count} unchanged</span><span className="rounded-full bg-violet-500/10 px-3 py-1.5">{preview.preserved_chapter_numbers.length} preserved</span></div><div className="mt-4 max-h-64 space-y-2 overflow-auto">{preview.chapters.map((chapter) => <div key={`${chapter.incoming_number}:${chapter.incoming_title}`} className={`flex items-center justify-between gap-3 border-b py-2 text-sm ${isDark ? "border-white/[0.06]" : "border-stone-100"}`}><span>{chapter.incoming_title}</span><span className={chapter.status === "changed" ? "text-amber-600" : chapter.status === "new" ? "text-emerald-600" : "text-slate-500"}>{chapter.status}</span></div>)}</div><label className="mt-4 flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" /><span>I reviewed this preview and want to replace matching chapter numbers. Missing current chapters remain preserved.</span></label><button type="button" disabled={!confirmed || busy} onClick={() => void apply()} className="mt-4 inline-flex items-center gap-2 bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"><ArrowUpFromLine className="h-4 w-4" /> Apply reviewed changes</button></div> : null}
      {message ? <p className="mt-4 flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4" />{message}</p> : null}
    </section>
  )
}
