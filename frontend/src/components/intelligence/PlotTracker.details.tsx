"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { PlotThread } from "@/types/reader"
import { plotThreadNoteContent, THREAD_STATUS_LABELS, THREAD_STATUS_OPTIONS } from "./PlotTracker.helpers"

type Props = {
  bookId: string; threadId: string; onClose: () => void
  onSaved: (thread: PlotThread) => void
  onDraftState: (state: { dirty: boolean; busy: boolean }) => void
}
const fieldClass = "mt-2 block w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2.5 text-sm leading-6 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[rgb(var(--accent))]"

export function PlotThreadDetails(props: Props) {
  const detail = useQuery({
    queryKey: asQueryKey(readerCacheKey(props.bookId, `plot-threads:detail:${props.threadId}`)),
    queryFn: () => readerApi.getPlotThread(props.bookId, props.threadId),
    refetchOnWindowFocus: false,
  })
  if (!detail.data) return <div className="border-t border-[rgb(var(--border))] py-5 text-sm">
    {detail.isError ? <div role="alert"><p>Thread details could not be loaded. Your saved note has not been changed.</p><button type="button" className="app-button-secondary mt-3" disabled={detail.isFetching} onClick={() => void detail.refetch()}>Retry thread details</button></div> : <p role="status">Loading thread details…</p>}
  </div>
  return <>
    {detail.isError ? <p role="alert" className="mt-3 border-l-2 border-amber-600 pl-3 text-sm">Thread details could not be refreshed. Loaded details and your edits remain available. <button type="button" disabled={detail.isFetching} className="underline" onClick={() => void detail.refetch()}>Retry thread details</button></p> : null}
    <PlotThreadEditor {...props} key={props.threadId} thread={detail.data} />
  </>
}

function PlotThreadEditor({ bookId, thread, onClose, onSaved, onDraftState }: Props & { thread: PlotThread }) {
  // Keep the editor's loaded snapshot through background list/detail refreshes.
  const [saved, setSaved] = useState(thread)
  const [note, setNote] = useState(thread.note ?? "")
  const [status, setStatus] = useState(thread.status === "ongoing" ? "developing" : thread.status)
  const [busy, setBusy] = useState<"save" | "copy" | null>(null)
  const lock = useRef(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [copiedContent, setCopiedContent] = useState<string | null>(null)
  const savedStatus = saved.status === "ongoing" ? "developing" : saved.status
  const dirty = note !== (saved.note ?? "") || status !== savedStatus
  const content = plotThreadNoteContent(saved, note, status)
  const chapters = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "chapters")), queryFn: () => readerApi.getChapterList(bookId), staleTime: 45_000 })
  useEffect(() => { onDraftState({ dirty, busy: !!busy }) }, [dirty, busy, onDraftState])
  useEffect(() => () => onDraftState({ dirty: false, busy: false }), [onDraftState])

  const save = async () => {
    if (lock.current || !dirty) return
    lock.current = true; setBusy("save"); setError(""); setMessage("")
    try {
      const updated = await readerApi.updatePlotThread(bookId, saved.id, { note: note.trim() || null, status })
      setSaved(updated); setNote(updated.note ?? ""); setStatus(updated.status === "ongoing" ? "developing" : updated.status)
      onSaved(updated)
      setMessage("Thread changes saved.")
    } catch { setError("Changes could not be saved. Your draft is still here; try Save changes again.") }
    finally { lock.current = false; setBusy(null) }
  }
  const copy = async () => {
    if (lock.current || copiedContent === content) return
    lock.current = true; setBusy("copy"); setError(""); setMessage("")
    try {
      await saveContextualVaultNote({ bookId, title: saved.title, content, context: "plot_threads", folderSegments: [saved.type || "Threads"] })
      setCopiedContent(content); setMessage("Copied to Notes. The copy includes the current status and private note.")
    } catch { setError("The copy could not be saved to Notes. Your thread and draft are unchanged; try again.") }
    finally { lock.current = false; setBusy(null) }
  }
  const chapterNumbers = new Set(chapters.data?.chapters.map((item) => item.number))
  const sources = [
    { label: "First mentioned", number: saved.first_mentioned ?? saved.introduced_at },
    { label: "Last mentioned", number: saved.last_mentioned },
    { label: "Closed", number: saved.resolved_at },
  ].filter((source) => Number.isInteger(source.number) && Number(source.number) > 0)

  return <section aria-label={`Details for ${saved.title}`} className="border-t border-[rgb(var(--border))] bg-[rgb(var(--muted)/0.25)] px-0 py-5 sm:px-3">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="text-base font-semibold">Thread details</h3><p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Review the source chapters, then update the working status or note.</p></div>
      <button type="button" disabled={!!busy} onClick={onClose} className="min-h-10 px-2 text-sm underline underline-offset-4">Close</button>
    </div>
    <div className="mt-4 border-y border-[rgb(var(--border))] py-3 text-sm">
      <p className="font-semibold">Source chapters</p>
      {chapters.isError ? <div role="alert" className="mt-2">Chapter links could not be checked. <button type="button" disabled={chapters.isFetching} className="underline" onClick={() => void chapters.refetch()}>Retry chapter links</button></div> : null}
      {!sources.length ? <p className="mt-2 text-[rgb(var(--muted-foreground))]">No source chapter is recorded.</p> : <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-2">{sources.map((source) => <li key={source.label}>{source.label}: {chapterNumbers.has(Number(source.number)) ? <Link href={`/${bookId}/chapter/${source.number}`} className="underline underline-offset-4">Chapter {source.number}</Link> : <span>Chapter {source.number}{!chapters.isLoading && !chapters.isError ? " (unavailable)" : ""}</span>}</li>)}</ul>}
      <p className="mt-2 text-[rgb(var(--muted-foreground))]">These are chapter references, not quoted passage evidence.</p>
    </div>
    <dl className="grid gap-4 border-b border-[rgb(var(--border))] py-4 md:grid-cols-3">
      <div><dt className="text-sm text-[rgb(var(--muted-foreground))]">Related characters</dt><dd className="mt-1 text-sm leading-6">{saved.related_characters?.length ? saved.related_characters.join(", ") : "None linked"}</dd></div>
      <div><dt className="text-sm text-[rgb(var(--muted-foreground))]">Risk</dt><dd className="mt-1 text-sm leading-6">{saved.risk || "No risk recorded"}</dd></div>
      <div><dt className="text-sm text-[rgb(var(--muted-foreground))]">Next step</dt><dd className="mt-1 text-sm leading-6">{saved.suggested_action || "No action suggested"}</dd></div>
    </dl>
    <fieldset disabled={!!busy} className="mt-5 grid min-w-0 gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
      <legend className="sr-only">Edit thread</legend>
      <label className="text-sm font-medium">Status<select className={fieldClass} value={status} onChange={(event) => setStatus(event.target.value)}>{!THREAD_STATUS_OPTIONS.includes(status) ? <option value={status}>Unknown ({status})</option> : null}{THREAD_STATUS_OPTIONS.map((value) => <option key={value} value={value}>{THREAD_STATUS_LABELS[value]}</option>)}</select></label>
      <label className="text-sm font-medium">Private note<textarea className={fieldClass} rows={4} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add a revision reminder…" /></label>
    </fieldset>
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <p role="status" className="text-sm text-[rgb(var(--muted-foreground))]">{busy === "save" ? "Saving changes…" : dirty ? "Unsaved changes" : "Changes saved"}</p>
      <div className="flex flex-wrap gap-3"><button type="button" className="app-button-secondary !rounded-sm" disabled={!dirty || !!busy} onClick={() => { setNote(saved.note ?? ""); setStatus(savedStatus); setError(""); setMessage("") }}>Discard changes</button><button type="button" className="app-button-primary !rounded-sm" disabled={!dirty || !!busy} onClick={() => void save()}>{busy === "save" ? "Saving…" : "Save changes"}</button></div>
    </div>
    {error ? <p role="alert" className="mt-3 border-l-2 border-amber-600 pl-3 text-sm">{error}</p> : null}
    {message ? <p role="status" className="mt-3 text-sm">{message}</p> : null}
    <div className="mt-5 border-t border-[rgb(var(--border))] pt-4 text-sm">
      <p className="text-[rgb(var(--muted-foreground))]">The note is stored with this manuscript. Copying to Notes includes your current edits but does not save thread changes.</p>
      <div className="mt-3 flex flex-wrap gap-4"><button type="button" disabled={!!busy || copiedContent === content} className="min-h-10 underline underline-offset-4 disabled:opacity-50" onClick={() => void copy()}>{busy === "copy" ? "Copying…" : copiedContent === content ? "Copied to Notes" : "Save to notes"}</button><Link href={`/${bookId}/notes`} className="inline-flex min-h-10 items-center underline underline-offset-4">Open notes</Link></div>
    </div>
  </section>
}
