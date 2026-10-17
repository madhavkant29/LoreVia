"use client"

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { readerApi } from "@/lib/api/reader"
import { intelligenceApi } from "@/lib/api/intelligence"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { RichMessage, buildReplyFollowUps, worldItemTitle, worldItemDescription } from "./advisorPage.components"
import { advisorHistory, advisorFailure, advisorQuestionError, type AdvisorEntry, type AdvisorNote } from "./advisorPage.helpers"

export function AdvisorConversation({ bookId, author, paid, isDark, input, setInput, busy, setBusy, onSave, saving, ready, greeting }: {
  bookId: string; author: boolean; paid: boolean; isDark: boolean; input: string; setInput: (value: string) => void; busy: boolean; setBusy: (value: boolean) => void; onSave: (note: AdvisorNote) => void; saving: boolean; ready: boolean; greeting?: string
}) {
  const [entries, setEntries] = useState<AdvisorEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [copy, setCopy] = useState<{ id: number; failed: boolean } | null>(null)
  const active = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const latest = useRef<HTMLElement>(null)
  const chapters = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "chapters")), queryFn: () => readerApi.getChapterList(bookId), enabled: entries.some((entry) => !!entry.evidence?.retrieved_passages.length), retry: false })
  const available = new Set(chapters.data?.chapters.map((chapter) => chapter.number))
  useEffect(() => () => { active.current?.abort(); active.current = null }, [])

  async function send(custom?: string) {
    if (active.current || !ready) return
    const question = (custom ?? input).trim()
    const invalid = advisorQuestionError(question)
    if (invalid) { setError(invalid); inputRef.current?.focus(); return }
    if (custom && input.trim() && input.trim() !== question && !window.confirm("Replace your current question draft?")) return
    const controller = new AbortController(); active.current = controller
    const id = ++sequence.current
    const messages = advisorHistory(entries, question)
    setEntries((all) => [...all, { id, question, answer: "", status: "streaming" }])
    setInput(""); setBusy(true); setError(null)
    const update = (value: Partial<AdvisorEntry>) => { if (active.current === controller) setEntries((all) => all.map((entry) => entry.id === id ? { ...entry, ...value } : entry)) }
    try {
      const response = await intelligenceApi.advisorMessageStream(bookId, messages, { signal: controller.signal, onDelta: (content) => { if (active.current === controller && !controller.signal.aborted) setEntries((all) => all.map((entry) => entry.id === id ? { ...entry, answer: entry.answer + content } : entry)) } })
      if (controller.signal.aborted || !response.reply?.trim()) throw new Error("Answer incomplete")
      update({ status: "complete", answer: response.reply, evidence: response })
    } catch (failure) {
      update({ status: controller.signal.aborted ? "stopped" : "failed", error: advisorFailure(failure, controller.signal.aborted, paid) })
      if (active.current === controller) setInput(question)
    } finally { if (active.current === controller) { active.current = null; setBusy(false) } }
  }

  async function copyAnswer(entry: AdvisorEntry) {
    try { await navigator.clipboard.writeText(`${entry.question}\n\n${entry.status === "complete" ? "" : "Incomplete answer\n"}${entry.answer}`); setCopy({ id: entry.id, failed: false }) }
    catch { setCopy({ id: entry.id, failed: true }) }
  }

  return <div className="mx-auto max-w-4xl space-y-6">
    <section><h2 className="text-xl font-semibold">Ask the manuscript</h2><p className="advisor-muted mt-2 text-sm leading-6">Ask about contradictions, lore, world rules, endings, and tradeoffs. Answers use extracted story context and available passages; verify important claims in the manuscript.</p></section>
    <form className="border-y border-[rgb(var(--border))] py-5" onSubmit={(event) => { event.preventDefault(); void send() }}>
      <label htmlFor="advisor-input" className="block text-base font-semibold">Advisor question</label>
      <textarea id="advisor-input" aria-label="Advisor question" ref={inputRef} value={input} rows={3} disabled={busy || !ready} className="app-input mt-3 min-h-28 w-full resize-y text-base leading-7" aria-describedby="advisor-input-hint advisor-input-error" aria-invalid={!!error} onChange={(event) => { setInput(event.target.value); setError(null) }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); void send() } }} />
      <p id="advisor-input-hint" className="advisor-muted mt-2 text-sm">Enter to send · Shift+Enter for a new line · {input.trim().length.toLocaleString()} / 8,000 characters</p>
      <div id="advisor-input-error">{error ? <p role="alert" className="mt-3 text-sm">{error}</p> : null}</div>
      <div className="mt-4 flex flex-wrap items-center gap-3"><button type="submit" className="app-button-primary" disabled={busy || !ready || !input.trim()}>Send</button>{busy ? <button type="button" className="app-button-secondary" onClick={() => active.current?.abort()}>Stop waiting</button> : null}{entries.length ? <button type="button" className="app-button-secondary" onClick={() => { latest.current?.focus(); latest.current?.scrollIntoView({ block: "start", behavior: "smooth" }) }}>Latest answer</button> : null}<p role="status" className="advisor-muted text-sm">{busy ? "Reviewing story context…" : entries.at(-1)?.error ? "The last answer is incomplete. Your question is kept; use Latest answer to review it." : "Ready for your question"}</p></div>
    </form>
    {!entries.length ? <p className="text-base leading-7">{greeting || "What aspect of your story feels unsolved right now?"}</p> : null}
    <details><summary className="w-fit cursor-pointer py-2 text-sm font-semibold">Suggested questions</summary><div className="divide-y divide-[rgb(var(--border))]">{["Are there any plotholes I should know about?", "What foreshadowing opportunities am I missing?", "Help me think through how to end the current arc.", "Is there a consistency issue with my magic system?", "I want to suddenly change the genre. Is that a good idea?"].map((prompt) => <button type="button" key={prompt} disabled={busy || !ready} className="block min-h-11 w-full py-3 text-left text-sm hover:underline" onClick={() => { if (!input.trim() || input === prompt || window.confirm("Replace your current question draft?")) { setInput(prompt); inputRef.current?.focus() } }}>{prompt}</button>)}</div></details>
    <section aria-label="Advisor conversation"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgb(var(--border))] pb-3"><h2 className="text-xl font-semibold">Answers</h2>{entries.length ? <button type="button" disabled={busy} className="app-button-secondary" onClick={() => { if (window.confirm("Clear this conversation? Your current question draft will stay.")) { setEntries([]); setCopy(null) } }}>Clear conversation</button> : null}</div><p className="advisor-muted mt-3 text-sm leading-6">Answers stay in this page session. Follow-ups include up to nine completed exchanges; long answers may be shortened in the context sent.</p>
    {entries.map((entry, index) => <article key={entry.id} ref={index === entries.length - 1 ? latest : undefined} tabIndex={-1} className="advisor-answer scroll-mt-40 border-b border-[rgb(var(--border))] py-6">
      <p className="advisor-muted text-sm">Question {index + 1} · {entry.status === "complete" ? "Answered" : entry.status === "streaming" ? "Answering…" : "Incomplete answer"}</p><h3 className="mb-4 mt-2 whitespace-pre-wrap text-lg font-semibold leading-7">{entry.question}</h3>
      {entry.error ? <div role="alert" className="my-4 border-l-2 border-amber-600 pl-4 text-sm leading-6"><p>{entry.error}</p><button type="button" disabled={busy || !ready} className="min-h-11 underline" onClick={() => void send(entry.question)}>Retry question {index + 1}</button></div> : null}
      {entry.answer ? <RichMessage content={entry.answer} isDark={isDark} /> : entry.status === "streaming" ? <p className="advisor-muted text-sm">Waiting for the first words…</p> : null}
      {entry.evidence ? <>
        <details className="mt-4"><summary className="cursor-pointer py-2 text-sm font-semibold">Answer evidence ({entry.evidence.retrieved_passages.length} {entry.evidence.retrieved_passages.length === 1 ? "passage" : "passages"})</summary>{!entry.evidence.retrieved_passages.length ? <p className="advisor-muted py-2 text-sm">No manuscript excerpts were supplied. Check the answer against the source project.</p> : entry.evidence.retrieved_passages.map((passage, p) => <blockquote key={p} className="my-4 border-l-2 border-[rgb(var(--border))] pl-4 text-sm leading-7"><p className="font-semibold">{Number.isInteger(passage.chapter_num) && passage.chapter_num > 0 ? `Chapter ${passage.chapter_num}` : "Chapter not identified"}{passage.chapter_title ? ` · ${passage.chapter_title}` : ""}</p><p className="my-2 whitespace-pre-wrap">{passage.excerpt || "Excerpt unavailable."}</p>{available.has(passage.chapter_num) ? <Link className="inline-flex min-h-11 items-center underline underline-offset-4" href={author ? `/${bookId}/manuscript?chapter=${passage.chapter_num}` : `/${bookId}/chapter/${passage.chapter_num}`}>Open chapter {passage.chapter_num}</Link> : <p className="advisor-muted">Source chapter not verified.</p>}</blockquote>)}{chapters.isError ? <button type="button" className="app-button-secondary" onClick={() => void chapters.refetch()}>Retry source chapters</button> : null}</details>
        {entry.evidence.world_analysis ? <details className="mt-2"><summary className="cursor-pointer py-2 text-sm font-semibold">Worldbuilding context</summary><p className="whitespace-pre-wrap text-sm leading-7">{entry.evidence.world_analysis.answer}</p>{[{ label: "Alerts", items: entry.evidence.world_analysis.logic_alerts }, { label: "Suggestions", items: entry.evidence.world_analysis.suggestions }, { label: "Source context", items: entry.evidence.world_analysis.citations }].map((group) => group.items.length ? <div key={group.label} className="mt-4"><h4 className="font-semibold">{group.label}</h4>{group.items.map((item, n) => <div key={n} className="border-b border-[rgb(var(--border))] py-3 text-sm leading-7"><p className="font-medium">{worldItemTitle(item, `${group.label} ${n + 1}`)}</p><p>{worldItemDescription(item)}</p></div>)}</div> : null)}{entry.evidence.world_analysis.simulation_steps?.length ? <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-7">{entry.evidence.world_analysis.simulation_steps.map((step, n) => <li key={n}>{step}</li>)}</ol> : null}</details> : null}
        <details className="mt-2"><summary className="cursor-pointer py-2 text-sm font-semibold">Follow-up ideas</summary>{buildReplyFollowUps(entry.evidence.response_type).map((prompt) => <button type="button" disabled={busy} key={prompt} className="block min-h-11 py-2 text-left text-sm underline" onClick={() => { if (!input.trim() || input === prompt || window.confirm("Replace your current question draft?")) { setInput(prompt); inputRef.current?.focus() } }}>{prompt}</button>)}</details>
      </> : null}
      {entry.answer && entry.status !== "streaming" ? <div className="mt-4 flex flex-wrap gap-3"><button type="button" className="app-button-secondary" onClick={() => void copyAnswer(entry)}>Copy answer {index + 1}</button>{paid ? <button type="button" className="app-button-secondary" disabled={saving} onClick={() => onSave({ chapterNumber: null, title: "Advisor insight", body: `${entry.question}\n\n${entry.status === "complete" ? "" : "Incomplete answer\n"}${entry.answer}` })}>Save to notes</button> : null}</div> : null}
      {copy?.id === entry.id ? copy.failed ? <div className="mt-3"><p role="status" className="text-sm">Copy unavailable. Select the text below to copy manually.</p><textarea readOnly aria-label={`Copy text for answer ${index + 1}`} rows={5} className="app-input mt-2 w-full" value={`${entry.question}\n\n${entry.status === "complete" ? "" : "Incomplete answer\n"}${entry.answer}`} onFocus={(event) => event.currentTarget.select()} /></div> : <p role="status" className="mt-2 text-sm">Answer copied.</p> : null}
    </article>)}
    {!entries.length ? <p className="py-6 text-sm">Your answers and their evidence will appear here.</p> : null}</section>
  </div>
}
