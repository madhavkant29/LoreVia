import { memo } from "react"
import type { KeyboardEvent, MutableRefObject, RefObject } from "react"
import Link from "next/link"

import { cn } from "@/lib/utils/text"
import {
  getAskLoreViaAnswerLabel,
  getAskLoreViaDescription,
  getAskLoreViaHelperText,
} from "@/lib/utils/askLoreVia"
import { Skeleton } from "@/components/ui/Skeleton"
import type { GroundedCitation } from "@/types/intelligence"

interface QAEntry {
  question: string
  answer: string
  citations: GroundedCitation[]
}

export const AskLoreViaWorkspace = memo(function AskLoreViaWorkspace({
  bookId,
  bookTitle,
  mode,
  currentChapter,
  scopeLabel,
  history,
  input,
  loading,
  error,
  isDark,
  inputRef,
  bottomRef,
  onInputChange,
  onSubmit,
  onKeyDown,
  quickPrompts,
}: {
  bookId: string
  bookTitle?: string | null
  mode?: "author" | "reader"
  currentChapter: number
  scopeLabel: string
  history: QAEntry[]
  input: string
  loading: boolean
  error: string | null
  isDark: boolean
  inputRef: RefObject<HTMLTextAreaElement | null>
  bottomRef: RefObject<HTMLDivElement | null>
  onInputChange: (value: string) => void
  onSubmit: (value: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  quickPrompts: readonly string[]
}) {
  const description = getAskLoreViaDescription(mode, currentChapter)
  const helperText = getAskLoreViaHelperText(mode, currentChapter)
  const answerLabel = getAskLoreViaAnswerLabel(mode, currentChapter)

  return (
    <div
      className={cn(
        "min-h-screen transition-colors",
        isDark
          ? "bg-[#071211] text-slate-100"
          : "bg-stone-50 text-stone-950"
      )}
    >
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 pb-14 pt-6 sm:px-6 lg:px-8">
        <header
          className={cn(
            "flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-center sm:justify-between",
            isDark ? "border-white/10" : "border-stone-200"
          )}
        >
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
            <Link
              href={`/${bookId}`}
              className={cn(
                "inline-flex items-center gap-2 font-medium transition",
                isDark ? "text-sky-300 hover:text-sky-200" : "text-violet-700 hover:text-violet-800"
              )}
            >
              <ArrowLeftIcon className="h-4 w-4" />
              <span>Overview</span>
            </Link>
            {bookTitle ? (
              <>
                <span className={cn("text-xs", isDark ? "text-white/25" : "text-stone-300")}>/</span>
                <span className={cn("truncate font-semibold", isDark ? "text-white" : "text-stone-950")}>
                  {bookTitle}
                </span>
              </>
            ) : null}
          </div>

          <div
            className={cn(
              "inline-flex items-center gap-2 self-start rounded-full border px-3.5 py-2 text-3xs font-semibold uppercase tracking-[0.24em] sm:self-auto",
              isDark
                ? "border-cyan-300/15 bg-white/[0.04] text-cyan-200/85"
                : "border-stone-200 bg-white/90 text-stone-500"
            )}
          >
            <LayersIcon className="h-3.5 w-3.5 shrink-0" />
            <span>{scopeLabel}</span>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-[62rem] flex-1 flex-col gap-8 pt-10 sm:gap-10 sm:pt-14">
          <section className="mx-auto max-w-3xl text-center">
            <p className={cn("text-3xs font-semibold uppercase tracking-[0.34em]", isDark ? "text-indigo-300" : "text-violet-500")}>
              Natural Language Query
            </p>
            <h1
              className={cn(
                "mt-4 text-5xl leading-none sm:text-6xl",
                isDark ? "text-white" : "text-stone-950"
              )}
              style={{ fontFamily: "var(--reader-display)" }}
            >
              Ask LoreVia
            </h1>
            <p className={cn("mx-auto mt-5 max-w-2xl text-sm leading-7 sm:text-base", isDark ? "text-slate-300" : "text-stone-600")}>
              {description}
            </p>
          </section>

          <SuggestedQuestionsCard
            isDark={isDark}
            prompts={quickPrompts}
            onPromptClick={onSubmit}
          />

          <section className="space-y-4">
            <AskQuestionCard
              currentValue={input}
              loading={loading}
              helperText={helperText}
              isDark={isDark}
              inputRef={inputRef}
              onInputChange={onInputChange}
              onKeyDown={onKeyDown}
              onSubmit={() => onSubmit(input)}
            />

            <div className={cn("flex flex-wrap items-center justify-center gap-2 text-sm", isDark ? "text-slate-400" : "text-stone-500")}>
              <span>Need direct passage retrieval instead?</span>
              <Link
                href={`/${bookId}/search`}
                className={cn(
                  "inline-flex items-center gap-2 font-semibold transition",
                  isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"
                )}
              >
                <span>Open Search Your Writing</span>
                <ArrowRightIcon className="h-4 w-4" />
              </Link>
            </div>

            {error ? (
              <div
                role="alert"
                className={cn(
                  "rounded-lg border px-4 py-3 text-sm",
                  isDark ? "border-red-400/20 bg-red-500/10 text-red-200" : "border-red-200 bg-red-50 text-red-700"
                )}
              >
                {error}
              </div>
            ) : null}
          </section>

          <section className="space-y-4" aria-live="polite">
            {history.map((entry, index) => (
              <AskResultCard
                key={`${entry.question}-${index}`}
                entry={entry}
                answerLabel={answerLabel}
                isDark={isDark}
              />
            ))}

            {loading ? <LoadingResultCard isDark={isDark} /> : null}
            <div ref={bottomRef} />
          </section>

          {history.length >= 3 ? (
            <section
              className={cn(
                "rounded-lg border px-5 py-5 sm:px-6",
                isDark ? "border-indigo-400/15 bg-indigo-400/[0.06]" : "border-violet-100 bg-violet-50"
              )}
            >
              <p className={cn("text-sm font-semibold", isDark ? "text-indigo-200" : "text-violet-700")}>
                Writing this story?
              </p>
              <p className={cn("mt-2 max-w-2xl text-sm leading-6", isDark ? "text-slate-400" : "text-stone-600")}>
                Story Advisor gives you plothole detection, foreshadowing opportunities, and arc tradeoff analysis grounded in your full manuscript, not just your read progress.
              </p>
              <Link
                href={`/${bookId}/advisor`}
                className={cn(
                  "mt-4 inline-flex items-center gap-2 text-sm font-semibold transition",
                  isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"
                )}
              >
                <span>Open Story Advisor</span>
                <ArrowRightIcon className="h-4 w-4" />
              </Link>
            </section>
          ) : null}
        </main>
      </div>
    </div>
  )
})

function SuggestedQuestionsCard({
  isDark,
  prompts,
  onPromptClick,
}: {
  isDark: boolean
  prompts: readonly string[]
  onPromptClick: (prompt: string) => void
}) {
  return (
    <section
      className={cn(
        "rounded-lg border px-5 py-5 sm:px-7 sm:py-6",
        isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white/90"
      )}
    >
      <div className="flex items-center gap-2">
        <SparkIcon className={cn("h-4 w-4", isDark ? "text-indigo-300" : "text-violet-500")} />
        <p className={cn("text-3xs font-semibold uppercase tracking-[0.3em]", isDark ? "text-indigo-300" : "text-violet-500")}>
          Try Asking
        </p>
      </div>
      <p className={cn("mt-3 max-w-3xl text-sm leading-7", isDark ? "text-slate-300" : "text-stone-600")}>
        Good for questions like last appearance, first introduction, relationship status, past ability use, and where a detail was established.
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPromptClick(prompt)}
            className={cn(
              "group flex min-h-14 items-center gap-3 rounded-md border px-4 py-3 text-left text-sm font-medium transition focus-visible:outline-none",
              isDark
                ? "border-white/10 bg-white/[0.03] text-slate-100 hover:border-cyan-300/30 hover:bg-white/[0.06]"
                : "border-stone-200 bg-stone-50 text-stone-800 hover:border-violet-200 hover:bg-white"
            )}
            aria-label={`Ask: ${prompt}`}
          >
            <SearchIcon className={cn("h-4 w-4 shrink-0 transition", isDark ? "text-cyan-300 group-hover:text-cyan-200" : "text-violet-500 group-hover:text-violet-600")} />
            <span>{prompt}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

function AskQuestionCard({
  currentValue,
  loading,
  helperText,
  isDark,
  inputRef,
  onInputChange,
  onKeyDown,
  onSubmit,
}: {
  currentValue: string
  loading: boolean
  helperText: string
  isDark: boolean
  inputRef: RefObject<HTMLTextAreaElement | null>
  onInputChange: (value: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  onSubmit: () => void
}) {
  return (
    <section
      className={cn(
        "rounded-lg border px-4 py-4 sm:px-6 sm:py-5",
        isDark ? "border-white/10 bg-[#0b1020]/88" : "border-stone-200 bg-white/95"
      )}
    >
      <label htmlFor="ask-input" className="sr-only">
        Ask LoreVia a grounded question about the story
      </label>
      <textarea
        ref={inputRef}
        id="ask-input"
        value={currentValue}
        onChange={(event) => onInputChange(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask anything about your story up to this point..."
        rows={4}
        disabled={loading}
        aria-label="Ask LoreVia a grounded question about the story"
        className={cn(
          "min-h-[10rem] w-full resize-none bg-transparent text-base leading-7 outline-none",
          isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"
        )}
      />

      <div className="mt-4 flex flex-col gap-4 border-t pt-4 sm:flex-row sm:items-end sm:justify-between">
        <p className={cn("text-xs leading-6", isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-500")}>
          {helperText}
        </p>
        <button
          id="ask-submit"
          type="button"
          onClick={onSubmit}
          disabled={!currentValue.trim() || loading}
          className={cn(
            "inline-flex min-w-28 items-center justify-center gap-2 self-start rounded-md px-5 py-3 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-40 sm:self-auto",
            "bg-violet-700 hover:bg-violet-600"
          )}
        >
          <span>{loading ? "Asking..." : "Ask"}</span>
          <ArrowRightIcon className="h-4 w-4" />
        </button>
      </div>
    </section>
  )
}

function AskResultCard({
  entry,
  answerLabel,
  isDark,
}: {
  entry: QAEntry
  answerLabel: string
  isDark: boolean
}) {
  return (
    <article
      className={cn(
        "rounded-lg border px-5 py-5 sm:px-6 sm:py-6",
        isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white/95"
      )}
    >
      <div className="flex flex-col gap-5">
        <div className="flex justify-end">
          <div
            className={cn(
              "max-w-3xl rounded-md border px-4 py-3 sm:px-5",
              isDark ? "border-indigo-400/20 bg-indigo-500/[0.12]" : "border-violet-200 bg-violet-50"
            )}
          >
            <p className={cn("text-xs font-semibold uppercase tracking-[0.24em]", isDark ? "text-indigo-200" : "text-violet-600")}>
              Question
            </p>
            <p className={cn("mt-2 text-sm leading-7", isDark ? "text-slate-100" : "text-stone-800")}>
              {entry.question}
            </p>
          </div>
        </div>

        <div>
          <p className={cn("text-3xs font-semibold uppercase tracking-[0.26em]", isDark ? "text-cyan-200/85" : "text-cyan-700")}>
            {answerLabel}
          </p>
          <p className={cn("mt-3 whitespace-pre-wrap text-sm leading-7 sm:text-base", isDark ? "text-slate-200" : "text-stone-700")}>
            {entry.answer}
          </p>
        </div>

        {entry.citations.length > 0 ? (
          <div className="space-y-3">
            <p className={cn("text-3xs font-semibold uppercase tracking-[0.24em]", isDark ? "text-slate-500" : "text-stone-400")}>
              Citations
            </p>
            <div className="flex flex-wrap gap-2">
              {entry.citations.map((citation, index) => (
                <span
                  key={`${citation.chapter_num}-${citation.source_type}-${index}`}
                  className={cn(
                    "inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-medium",
                    isDark ? "border-white/10 bg-white/[0.05] text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"
                  )}
                >
                  Chapter {citation.chapter_num}
                  {citation.chapter_title ? ` - ${citation.chapter_title}` : ""}
                </span>
              ))}
            </div>
            <div className="grid gap-3">
              {entry.citations.map((citation, index) => (
                <div
                  key={`${citation.chapter_num}-${citation.source_type}-detail-${index}`}
                  className={cn(
                    "rounded-md border px-4 py-4",
                    isDark ? "border-white/10 bg-black/25" : "border-stone-200 bg-stone-50"
                  )}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className={cn("text-sm font-semibold", isDark ? "text-white" : "text-stone-900")}>
                      Chapter {citation.chapter_num}
                      {citation.chapter_title ? ` - ${citation.chapter_title}` : ""}
                    </p>
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em]",
                        isDark ? "bg-white/8 text-slate-300" : "bg-white text-stone-500"
                      )}
                    >
                      {citation.source_type === "passage" ? "Passage" : "Summary"}
                    </span>
                  </div>
                  <p className={cn("mt-3 text-sm leading-7", isDark ? "text-slate-300" : "text-stone-600")}>
                    {citation.excerpt}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </article>
  )
}

function LoadingResultCard({ isDark }: { isDark: boolean }) {
  return (
    <div
      className={cn(
        "rounded-lg border px-5 py-5 sm:px-6",
        isDark ? "border-white/8 bg-white/[0.03]" : "border-stone-200 bg-white/90"
      )}
      role="status"
      aria-label="Loading Ask LoreVia answer"
      aria-busy="true"
    >
      <span className="sr-only">Loading Ask LoreVia answer</span>
      <Skeleton className={cn("h-2.5 w-40", isDark ? "bg-white/10" : "bg-stone-200")} />
      <Skeleton className={cn("mt-4 h-3 w-full", isDark ? "bg-white/8" : "bg-stone-100")} />
      <Skeleton className={cn("mt-3 h-3 w-5/6", isDark ? "bg-white/8" : "bg-stone-100")} />
      <Skeleton className={cn("mt-3 h-3 w-2/3", isDark ? "bg-white/8" : "bg-stone-100")} />
    </div>
  )
}

function ArrowLeftIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M8.25 5.25 3.5 10m0 0 4.75 4.75M3.5 10h13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M11.75 5.25 16.5 10m0 0-4.75 4.75M16.5 10h-13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <circle cx="8.75" cy="8.75" r="4.75" stroke="currentColor" strokeWidth="1.5" />
      <path d="m12.5 12.5 3.75 3.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function SparkIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M10 2.75 11.18 6l3.07 1.18L11.18 8.36 10 11.6 8.82 8.36 5.75 7.18 8.82 6 10 2.75Z" fill="currentColor" />
      <path d="m14.75 11.5.58 1.58 1.67.58-1.67.58-.58 1.59-.58-1.59-1.67-.58 1.67-.58.58-1.58Z" fill="currentColor" opacity=".9" />
    </svg>
  )
}

function LayersIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="m10 3.5 6 3.25-6 3.25-6-3.25 6-3.25Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="m4 10.5 6 3.25 6-3.25" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m4 14 6 3 6-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
