"use client"

import { useEffect, useRef, useState } from "react"
import { intelligenceApi } from "@/lib/api/intelligence"
import type { BookSeries } from "@/types/book"
import type { SeriesContinuityResponse } from "@/types/intelligence"
import { positiveNumberError } from "./seriesPage.helpers"

type Review = { response: SeriesContinuityResponse; bookTitle: string; chapter: string; text: string }
export function SeriesContinuityCheck({ series, disabled, onBusy, onDirty }: { series: BookSeries; disabled: boolean; onBusy: (busy: boolean) => void; onDirty: (dirty: boolean) => void }) {
  const [bookId, setBookId] = useState("")
  const [chapter, setChapter] = useState("")
  const [passage, setPassage] = useState("")
  const [review, setReview] = useState<Review | null>(null)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const alive = useRef(true)
  const book = series.books.find((item) => item.id === bookId)
  const validation = positiveNumberError(chapter, "Chapter or scene") || (passage.trim().length > 4000 ? "Use 4,000 characters or fewer. Longer passages are cut off by the series checker; your full text is preserved here." : null)
  useEffect(() => { onBusy(busy) }, [busy, onBusy])
  useEffect(() => { onDirty(!!passage.trim() || !!bookId || !!chapter) }, [passage, bookId, chapter, onDirty])
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort() } }, [])

  const run = async () => {
    if (controller.current || disabled || !book || !passage.trim() || validation) return
    const snapshot = { bookTitle: book.title, chapter, text: passage.trim() }
    const request = new AbortController()
    controller.current = request; setBusy(true); setError(null); setStage("Preparing comparison…")
    try {
      const response = await intelligenceApi.seriesContinuityCheckStream(series.id, book.id, snapshot.text, chapter.trim() ? Number(chapter) : undefined, { signal: request.signal, onStage: (value) => { if (alive.current && !request.signal.aborted) setStage(value) } })
      if (!response.review) throw new Error("Missing review")
      if (alive.current && !request.signal.aborted) setReview({ ...snapshot, response })
    } catch { if (alive.current) setError(request.signal.aborted ? "Stopped waiting for this check. The server may still finish processing it. Your passage is preserved." : "The continuity check could not be completed. Your passage and previous review are preserved. Try again.") }
    finally { controller.current = null; if (alive.current) { setBusy(false); setStage(null) } }
  }

  return <section className="min-w-0">
    <h3 className="text-lg font-semibold">Continuity check</h3>
    <p className="mt-2 max-w-prose text-sm leading-6 text-[rgb(var(--muted-foreground))]">Compare one passage with up to three earlier projects by series position. An unordered project is compared with up to three other projects. This is a limited review, not a complete series audit.</p>
    {!series.books.length ? <p className="mt-4 text-sm">Add a project to this series before running a check.</p> : null}
    <fieldset disabled={disabled || busy} className="mt-4 min-w-0 space-y-4">
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem]"><label className="min-w-0 text-sm font-medium">Project<select aria-label="Project to check" value={bookId} onChange={(event) => { setBookId(event.target.value); setChapter("") }} className="app-input mt-2"><option value="">Choose a project</option>{series.books.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label className="min-w-0 text-sm font-medium">{book?.work_type === "screenplay" ? "Scene" : "Chapter"} (optional)<input aria-label="Chapter or scene number" inputMode="numeric" value={chapter} onChange={(event) => setChapter(event.target.value)} className="app-input mt-2" /></label></div>
      <label className="block text-sm font-medium">Passage<textarea aria-label="Passage to cross-check" value={passage} onChange={(event) => setPassage(event.target.value)} rows={6} className="app-input mt-2 resize-y leading-7" /></label>
      <p className="text-sm text-[rgb(var(--muted-foreground))]">{passage.trim().length.toLocaleString()} / 4,000 characters · Reviews stay in this page session.</p>
      {validation ? <p role="alert" className="text-sm">{validation}</p> : null}
      <div className="flex flex-wrap gap-3"><button type="button" disabled={!book || !passage.trim() || !!validation} onClick={() => void run()} className="app-button-primary">{busy ? "Checking…" : "Run continuity check"}</button><button type="button" className="app-button-secondary" disabled={!passage && !bookId && !chapter} onClick={() => { if (window.confirm("Clear the continuity passage and project selection?")) { setPassage(""); setBookId(""); setChapter(""); setError(null) } }}>Clear passage</button></div>
    </fieldset>
    {busy ? <div className="mt-4 flex flex-wrap items-center gap-4 text-sm"><p role="status">{stage || "Checking…"}</p><button type="button" className="min-h-11 underline" onClick={() => controller.current?.abort()}>Stop waiting</button></div> : null}
    {error ? <p role="alert" className="mt-4 border-l-2 border-amber-600 pl-4 text-sm leading-6">{error}</p> : null}
    {review ? <section className="mt-6 min-w-0 border-t border-[rgb(var(--border))] pt-5">
      <h4 className="text-lg font-semibold">{review.response.review.overall_verdict || "Continuity review"}</h4>
      <p className="mt-2 text-sm">Reviewed {review.bookTitle}{review.chapter ? ` · Chapter / scene ${review.chapter}` : ""}{review.response.cached ? " · Saved result" : ""}</p>
      <details className="mt-3"><summary className="cursor-pointer text-sm font-semibold">Submitted passage</summary><p className="mt-3 max-w-prose whitespace-pre-wrap text-sm leading-7">{review.text}</p></details>
      <p className="mt-4 text-sm leading-6">{review.response.review.thematic_fit.notes}</p>
      <h5 className="mt-5 text-base font-semibold">Issues to review</h5>
      {review.response.review.continuity_issues.length ? <ul className="mt-2 divide-y divide-[rgb(var(--border))]">{review.response.review.continuity_issues.map((item, index) => <li key={index} className="py-3 text-sm leading-6"><p className="font-semibold">{item.title} · {item.severity}</p><p>{item.description}</p>{item.suggestion ? <p className="mt-2">Suggested change: {item.suggestion}</p> : null}</li>)}</ul> : <p className="mt-2 text-sm leading-6">No issues were returned for this comparison. This does not verify consistency across the whole series.</p>}
      {review.response.review.cross_book_opportunities.length ? <><h5 className="mt-5 text-base font-semibold">Cross-book opportunities</h5><ul className="mt-2 divide-y divide-[rgb(var(--border))]">{review.response.review.cross_book_opportunities.map((item, index) => <li key={index} className="py-3 text-sm leading-6"><p className="font-semibold">{item.title}</p><p>{item.description}</p></li>)}</ul></> : null}
      <h5 className="mt-5 text-base font-semibold">Retrieved excerpts</h5>
      <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Compare these excerpts with the source manuscript before making changes.</p>
      {review.response.retrieved_passages.length ? <ul className="mt-2 divide-y divide-[rgb(var(--border))]">{review.response.retrieved_passages.map((item, index) => <li key={index} className="py-3 text-sm leading-6"><p className="font-semibold">{item.book_title || "Source book not supplied"}{Number.isSafeInteger(item.chapter_num) && item.chapter_num > 0 ? ` · Chapter ${item.chapter_num}` : ""}{item.chapter_title ? ` · ${item.chapter_title}` : ""}</p><blockquote className="mt-2 border-l-2 border-[rgb(var(--border))] pl-3">{item.excerpt || "Excerpt unavailable."}</blockquote></li>)}</ul> : <p className="mt-3 text-sm">No source excerpts were supplied for this review.</p>}
    </section> : null}
  </section>
}
