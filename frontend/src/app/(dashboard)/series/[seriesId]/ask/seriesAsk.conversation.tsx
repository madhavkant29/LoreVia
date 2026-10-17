"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import { intelligenceApi } from "@/lib/api/intelligence"
import { getBookHref } from "@/lib/utils/bookRoutes"
import type { BookSeries } from "@/types/book"
import { renderSeriesAnswer, seriesAnswerError, seriesQuestionError, seriesQuestionHistory, type SeriesAnswer } from "./seriesAsk.helpers"

const questions = ["Which character changes most across the series?", "What unresolved plot threads remain?", "Where does the timeline need clarification?", "Which recurring detail matters most to the lore?"]
const muted = "text-[rgb(var(--muted-foreground))]"

export function SeriesConversation({ series }: { series: BookSeries }) {
  const [query, setQuery] = useState("")
  const [entries, setEntries] = useState<SeriesAnswer[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copy, setCopy] = useState<{ id: number; failed: boolean } | null>(null)
  const controller = useRef<AbortController | null>(null)
  const nextId = useRef(0)
  const input = useRef<HTMLTextAreaElement>(null)
  const latest = useRef<HTMLElement>(null)
  const current = useRef({ dirty: false, busy: false })
  current.current = { dirty: !!query.trim(), busy }

  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (current.current.dirty || current.current.busy) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download") || /^(#|mailto:|tel:)/.test(anchor.getAttribute("href") ?? "")) return
      if ((current.current.dirty || current.current.busy) && !window.confirm("Leave Series Ask? Your draft and conversation are kept only on this page. An unfinished answer will stop waiting.")) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { controller.current?.abort(); controller.current = null; window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [])

  async function ask(custom?: string) {
    if (controller.current || !series.books.length) return
    const question = (custom ?? query).trim()
    const invalid = seriesQuestionError(question)
    if (invalid) { setError(invalid); input.current?.focus(); return }
    if (custom && query.trim() && query.trim() !== question && !window.confirm("Replace your current draft with this question?")) return
    const request = new AbortController()
    controller.current = request
    const id = ++nextId.current
    const history = seriesQuestionHistory(entries, question)
    setEntries((all) => [...all, { id, question, answer: "", status: "streaming", passages: [] }])
    setQuery(""); setBusy(true); setError(null)
    const update = (change: Partial<SeriesAnswer>) => { if (controller.current === request) setEntries((all) => all.map((entry) => entry.id === id ? { ...entry, ...change } : entry)) }
    try {
      const result = await intelligenceApi.seriesAdvisorMessageStream(series.id, history, {
        signal: request.signal,
        onDelta: (text) => { if (controller.current === request && !request.signal.aborted) setEntries((all) => all.map((entry) => entry.id === id ? { ...entry, answer: entry.answer + text } : entry)) },
      })
      if (request.signal.aborted) throw new Error("Stopped")
      if (!result.reply?.trim()) throw new Error("Empty answer")
      update({ answer: result.reply, status: "complete", passages: result.retrieved_passages ?? [] })
    } catch (failure) {
      update({ status: request.signal.aborted ? "stopped" : "failed", error: seriesAnswerError(failure, request.signal.aborted) })
      if (controller.current === request) setQuery(question)
    } finally {
      if (controller.current === request) { controller.current = null; setBusy(false) }
    }
  }

  async function copyAnswer(entry: SeriesAnswer) {
    try { await navigator.clipboard.writeText(`${entry.question}\n\n${entry.status === "complete" ? "" : "Incomplete answer\n"}${entry.answer}`); setCopy({ id: entry.id, failed: false }) }
    catch { setCopy({ id: entry.id, failed: true }) }
  }

  return <div className="space-y-7">
    <section aria-label="Series context" className={`text-sm leading-6 ${muted}`}><p>Answers use saved story context from this series. This is not a full manuscript review. Check important details in the source projects.</p><details className="mt-2"><summary className="w-fit cursor-pointer py-2 font-medium text-[rgb(var(--foreground))]">Projects in context ({series.books.length})</summary><ul className="space-y-2 py-2">{series.books.map((book) => <li key={book.id}><Link className="inline-flex min-h-11 items-center underline underline-offset-4" href={getBookHref({ ...book, title: book.title || "Untitled project" }) as Route}>{book.title || "Untitled project"}</Link></li>)}</ul></details></section>
    {!series.books.length ? <section className="border-y border-[rgb(var(--border))] py-6"><h2 className="text-xl font-semibold">Add a project to begin</h2><p className="my-3 text-sm">This series has no projects to use as context.</p><Link href="/series" className="app-button-secondary">Manage series projects</Link></section> : <>
      <form className="border-y border-[rgb(var(--border))] py-6" onSubmit={(event) => { event.preventDefault(); void ask() }}>
        <label htmlFor="series-question" className="block text-lg font-semibold">Question about {series.name}</label>
        <textarea ref={input} id="series-question" className="app-input mt-3 min-h-28 w-full resize-y text-base leading-7" rows={3} value={query} disabled={busy} aria-describedby="series-question-hint series-question-error" aria-invalid={!!error} onChange={(event) => { setQuery(event.target.value); setError(null) }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); void ask() } }} />
        <p id="series-question-hint" className={`mt-2 text-sm ${muted}`}>Enter to ask · Shift+Enter for a new line · {query.trim().length.toLocaleString()} / 8,000 characters</p>
        <div id="series-question-error">{error ? <p role="alert" className="mt-3 text-sm">{error}</p> : null}</div>
        <div className="mt-4 flex flex-wrap items-center gap-3"><button className="app-button-primary" type="submit" disabled={busy || !query.trim()}>Ask</button>{busy ? <button className="app-button-secondary" type="button" onClick={() => controller.current?.abort()}>Stop waiting</button> : null}{entries.length ? <button className="app-button-secondary" type="button" onClick={() => { latest.current?.focus(); latest.current?.scrollIntoView({ block: "start", behavior: "smooth" }) }}>Latest answer</button> : null}<span role="status" className={`text-sm ${muted}`}>{busy ? "Reviewing saved series context…" : entries.length ? "Ready for your next question" : "Start with a focused question"}</span></div>
      </form>
      <details><summary className="w-fit cursor-pointer py-2 text-sm font-medium">Suggested questions</summary><div className="mt-2 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">{questions.map((question) => <button key={question} disabled={busy} type="button" onClick={() => void ask(question)} className="block min-h-11 w-full py-3 text-left text-sm hover:underline">{question}</button>)}</div></details>
      <section aria-label={`Conversation about ${series.name}`}><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgb(var(--border))] pb-3"><h2 className="text-xl font-semibold">Answers</h2>{entries.length ? <button type="button" disabled={busy} className="app-button-secondary" onClick={() => { if (window.confirm("Clear all answers from this page? Your current question draft will stay.")) { setEntries([]); setCopy(null) } }}>Clear conversation</button> : null}</div><p className={`mt-3 text-sm leading-6 ${muted}`}>Kept only on this page. Follow-ups include up to seven completed exchanges; long answers may be shortened in the context sent.</p>
        {!entries.length ? <p className="py-6 text-sm">Your answers will appear here. Ask a specific question or choose a suggestion.</p> : entries.map((entry, index) => <article key={entry.id} ref={index === entries.length - 1 ? latest : undefined} tabIndex={-1} className="series-answer scroll-mt-20 border-b border-[rgb(var(--border))] py-6 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[rgb(var(--accent))]">
          <p className={`text-sm ${muted}`}>Question {index + 1} · {entry.status === "complete" ? "Answered" : entry.status === "streaming" ? "Answering…" : "Incomplete answer"}</p><h3 className="mt-2 whitespace-pre-wrap text-lg font-semibold leading-7">{entry.question}</h3>
          {entry.error ? <div role="alert" className="my-4 border-l-2 border-amber-600 pl-4 text-sm leading-6"><p>{entry.error}</p><button type="button" disabled={busy} className="mt-2 min-h-11 underline" onClick={() => void ask(entry.question)}>Retry question {index + 1}</button></div> : null}
          {entry.answer ? <div className="prose prose-sm mt-4 max-w-none leading-7 dark:prose-invert" dangerouslySetInnerHTML={{ __html: renderSeriesAnswer(entry.answer) }} /> : entry.status === "streaming" ? <p className={`mt-4 text-sm ${muted}`}>Waiting for the first words…</p> : null}
          {entry.status === "complete" ? <p className={`mt-4 text-sm ${muted}`}>{entry.passages.length ? "Excerpts were supplied without source project identifiers. Verify their origin before relying on them." : "No chapter excerpts were supplied with this answer."}</p> : null}
          {entry.passages.length ? <details className="mt-3"><summary className="cursor-pointer py-2 text-sm">Read supplied excerpts</summary>{entry.passages.map((passage, i) => <blockquote className="my-3 border-l-2 border-[rgb(var(--border))] pl-4 text-sm leading-7" key={i}><p className="font-medium">{passage.chapter_title || "Untitled chapter"}{passage.chapter_num ? ` · Chapter ${passage.chapter_num}` : ""}</p><p className="whitespace-pre-wrap">{passage.excerpt}</p></blockquote>)}</details> : null}
          {entry.answer && entry.status !== "streaming" ? <button type="button" className="app-button-secondary mt-4" onClick={() => void copyAnswer(entry)}>Copy answer {index + 1}</button> : null}
          {copy?.id === entry.id ? copy.failed ? <div className="mt-3"><p role="status" className="text-sm">Copy was unavailable. Select the text below to copy manually.</p><textarea readOnly aria-label={`Copy text for answer ${index + 1}`} className="app-input mt-2 w-full" rows={5} value={`${entry.question}\n\n${entry.status === "complete" ? "" : "Incomplete answer\n"}${entry.answer}`} onFocus={(event) => event.currentTarget.select()} /></div> : <p role="status" className="mt-2 text-sm">Answer copied.</p> : null}
        </article>)}
      </section>
    </>}
  </div>
}
