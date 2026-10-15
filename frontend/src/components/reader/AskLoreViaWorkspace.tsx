import { memo } from "react"
import type { KeyboardEvent, ReactNode, RefObject } from "react"
import Link from "next/link"
import { getAskLoreViaAnswerLabel, getAskLoreViaDescription, getAskLoreViaHelperText, isAskCitationInScope, type AskEntry } from "@/lib/utils/askLoreVia"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"

const muted = "text-[rgb(var(--muted-foreground))]"

export const AskLoreViaWorkspace = memo(function AskLoreViaWorkspace({
  bookId, bookTitle, mode, currentChapter, scopeLabel, history, input, loading, error,
  inputRef, bottomRef, onInputChange, onSubmit, onKeyDown, quickPrompts, navigation,
  recentQuestions = [], onClearRecent, storageError = false, contextNotice, disabled = false, onStop,
}: {
  bookId: string; bookTitle?: string | null; mode?: "author" | "reader"; currentChapter: number
  scopeLabel: string; history: AskEntry[]; input: string; loading: boolean; error: string | null
  isDark: boolean; inputRef: RefObject<HTMLTextAreaElement | null>; bottomRef: RefObject<HTMLDivElement | null>
  onInputChange: (value: string) => void; onSubmit: (value: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void; quickPrompts: readonly string[]
  navigation?: ReactNode; recentQuestions?: string[]; onClearRecent?: () => void; storageError?: boolean
  contextNotice?: ReactNode; disabled?: boolean; onStop?: () => void
}) {
  const fillQuestion = (question: string) => {
    if (input.trim() && input.trim() !== question && !window.confirm("Replace the question you are drafting?")) return
    onInputChange(question)
    inputRef.current?.focus()
  }
  return <div data-ask-workspace className="min-h-screen bg-[rgb(var(--background))] text-[rgb(var(--foreground))]">
    <div className="mx-auto max-w-5xl px-4 pb-14 pt-6 sm:px-6 lg:px-8 [overflow-wrap:anywhere]">
      {navigation ? <div className="mb-5">{navigation}</div> : null}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgb(var(--border))] pb-4">
        <div className="min-w-0 text-sm"><Link href={`/${bookId}`} data-testid="ask-workspace-home-link" className="underline underline-offset-4">Back to book</Link>{bookTitle ? <p className="mt-2 font-semibold">{bookTitle}</p> : null}</div>
        <div className="flex flex-wrap items-center gap-4"><p className={`text-sm ${muted}`}>{scopeLabel}</p><button type="button" className="app-button-secondary !rounded-sm" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></div>
      </header>
      <main className="mx-auto max-w-[52rem] space-y-6 pt-7">
        <section><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Ask about the story</h1><p className={`mt-3 max-w-2xl text-sm leading-6 ${muted}`}>{currentChapter > 0 ? getAskLoreViaDescription(mode, currentChapter) : "Load your reading context to ask about the story and review chapter citations."}</p></section>
        {contextNotice ? <div className="border-l-2 border-[rgb(var(--accent))] pl-4 text-sm leading-6">{contextNotice}</div> : null}
        <section className="border-y border-[rgb(var(--border))] py-4">
          <label htmlFor="ask-input" className="block text-sm font-semibold">Your question</label>
          <textarea ref={inputRef} id="ask-input" value={input} onChange={(event) => onInputChange(event.target.value)} onKeyDown={onKeyDown} rows={4} disabled={loading} aria-label="Ask LoreVia a grounded question about the story" aria-describedby="ask-hint" className="mt-3 min-h-28 w-full resize-y rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-base leading-7 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[rgb(var(--accent))]" placeholder="Name a character, relationship, or detail you want to check." />
          <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
            <p id="ask-hint" className={`max-w-lg text-sm leading-6 ${muted}`}>{currentChapter > 0 ? getAskLoreViaHelperText(mode, currentChapter) : "Enter to ask · Shift+Enter for a new line"}</p>
            <div className="flex flex-wrap gap-3">{loading && onStop ? <button type="button" className="app-button-secondary !rounded-sm" onClick={onStop}>Stop answer</button> : null}<button id="ask-submit" type="button" onClick={() => onSubmit(input)} disabled={!input.trim() || loading || disabled} className="min-h-11 rounded-sm bg-violet-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-violet-600 disabled:cursor-not-allowed disabled:opacity-40">{loading ? "Asking..." : "Ask"}</button></div>
          </div>
          {error ? <p role="alert" className="mt-4 border-l-2 border-amber-600 pl-3 text-sm leading-6">{error}</p> : null}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm"><p className={muted}>Need the passage itself? <Link href={`/${bookId}/search`} className="underline underline-offset-4">Open Search Your Writing</Link></p>{history.length ? <button type="button" className="min-h-10 underline underline-offset-4" onClick={() => { const latest = bottomRef.current?.previousElementSibling; if (latest instanceof HTMLElement) { latest.scrollIntoView({ behavior: "smooth", block: "start" }); latest.focus({ preventScroll: true }) } }}>View latest answer</button> : null}</div>
        </section>
        <details className="border-b border-[rgb(var(--border))] pb-4">
          <summary className="cursor-pointer py-2 text-sm font-semibold">Suggested questions</summary>
          <p className={`mt-2 text-sm leading-6 ${muted}`}>Choose a starting point, add the character or detail, then ask.</p>
          <ul className="mt-2 divide-y divide-[rgb(var(--border))]">{quickPrompts.map((prompt) => <li key={prompt}><button type="button" disabled={loading || disabled} aria-label={`Use question: ${prompt}`} className="w-full py-3 text-left text-sm underline underline-offset-4 disabled:opacity-50" onClick={() => fillQuestion(prompt)}>{prompt}</button></li>)}</ul>
        </details>
        {recentQuestions.length ? <details className="border-b border-[rgb(var(--border))] pb-4"><summary className="cursor-pointer py-2 text-sm font-semibold">Recent questions on this device ({recentQuestions.length})</summary><ul className="mt-2 divide-y divide-[rgb(var(--border))]">{recentQuestions.map((question) => <li key={question}><button type="button" disabled={loading || disabled} onClick={() => fillQuestion(question)} className="w-full py-3 text-left text-sm underline underline-offset-4">{question}</button></li>)}</ul>{onClearRecent ? <button type="button" onClick={onClearRecent} className="min-h-10 text-sm underline underline-offset-4">Clear recent questions</button> : null}</details> : null}
        {storageError ? <p role="status" className={`text-sm ${muted}`}>Device storage is unavailable. Recent questions can only be kept for this page session.</p> : null}
        <section aria-label="Answers" className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Answers</h2><p className={`text-sm ${muted}`}>Answers stay in this page session.</p></div>
          <p role="status" className={`text-sm ${muted}`}>{loading ? "Receiving answer…" : history.length ? "Answer history updated." : "Ask a question to begin. Sources will appear with the answer when returned."}</p>
          {history.map((entry, index) => <AskResult key={`${entry.question}-${index}`} entry={entry} bookId={bookId} mode={mode} currentChapter={currentChapter} disabled={disabled || loading} onRetry={() => onSubmit(entry.question)} />)}
          <div ref={bottomRef} />
        </section>
        {mode === "author" && history.length >= 3 ? <p className="border-t border-[rgb(var(--border))] pt-4 text-sm"><Link href={`/${bookId}/advisor`} className="underline underline-offset-4">Open Story Advisor</Link> for manuscript-wide revision questions.</p> : null}
      </main>
    </div>
  </div>
})

function AskResult({ entry, bookId, mode, currentChapter, disabled, onRetry }: { entry: AskEntry; bookId: string; mode?: "author" | "reader"; currentChapter: number; disabled: boolean; onRetry: () => void }) {
  const chapter = entry.chapter ?? currentChapter
  const failed = entry.status === "failed" || entry.status === "stopped"
  const citations = entry.citations.filter((citation) => isAskCitationInScope(citation, chapter))
  return <article tabIndex={-1} aria-busy={entry.status === "streaming"} className="space-y-4 border-y border-[rgb(var(--border))] py-5">
    <div><p className={`text-sm ${muted}`}>You asked</p><h3 className="mt-1 text-base font-semibold leading-7">{entry.question}</h3></div>
    <div><p className={`text-sm ${muted}`}>{getAskLoreViaAnswerLabel(mode, chapter)}{failed ? " · Incomplete" : ""}</p><p className="mt-3 whitespace-pre-wrap text-base leading-7">{entry.answer || (entry.status === "streaming" ? "Searching story context…" : "No answer text was returned.")}</p></div>
    {failed ? <div className="border-l-2 border-amber-600 pl-3 text-sm"><p>{entry.error}</p><button type="button" disabled={disabled} className="app-button-secondary mt-3 !rounded-sm" onClick={onRetry}>Retry question</button></div> : null}
    {citations.length ? <section className="space-y-3"><h4 className="text-sm font-semibold">Sources</h4><div className="divide-y divide-[rgb(var(--border))]">{citations.map((citation, index) => <div key={`${citation.chapter_num}-${index}`} className="py-3"><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm font-semibold">Chapter {citation.chapter_num}{citation.chapter_title ? ` - ${citation.chapter_title}` : ""}</p><div className="flex flex-wrap gap-3 text-sm"><span className={muted}>{citation.source_type === "passage" ? "Passage" : "Summary"}</span><Link href={`/${bookId}/chapter/${citation.chapter_num}`} className="underline underline-offset-4" aria-label={`Jump to chapter ${citation.chapter_num}`}>Jump to chapter</Link></div></div><blockquote className={`mt-3 whitespace-pre-wrap border-l border-[rgb(var(--border))] pl-3 text-sm leading-7 ${muted}`}>{citation.excerpt?.trim() || "No excerpt was returned."}</blockquote></div>)}</div></section> : entry.status !== "streaming" ? <p className={`text-sm ${muted}`}>No chapter citations were returned within this question’s scope. Check the answer against the text.</p> : null}
    {citations.length < entry.citations.length ? <p className={`text-sm ${muted}`}>Some returned sources fall outside this chapter scope and are not shown.</p> : null}
  </article>
}
