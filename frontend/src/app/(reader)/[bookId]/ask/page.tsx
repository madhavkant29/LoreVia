"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { GroundedCitation } from "@/types/intelligence"

const QUICK_PROMPTS = [
  "When did this character last appear?",
  "What is the relationship between Arthur and Guinevere?",
  "Has this character used magic before?",
  "Where was this plot thread introduced?",
]

interface QAEntry {
  question: string
  answer: string
  citations: GroundedCitation[]
}

export default function AskPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [currentChapter, setCurrentChapter] = useState(1)
  const [bookTitle, setBookTitle] = useState<string | null>(null)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<QAEntry[]>([])

  const inputRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    readerApi.getProgress(bookId)
      .then((progress) => setCurrentChapter(Math.max(1, progress?.current_chapter ?? 1)))
      .catch(() => {})
    import("@/lib/api/books").then(({ booksApi }) =>
      booksApi.get(bookId).then((book) => setBookTitle(book.title)).catch(() => {})
    )
  }, [bookId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [history, loading])

  const ask = useCallback(async (text: string) => {
    const question = text.trim()
    if (!question || loading) return
    setInput("")
    setError(null)
    setLoading(true)
    try {
      const response = await intelligenceApi.answer(bookId, question, currentChapter)
      setHistory((previous) => [
        ...previous,
        {
          question,
          answer: response.answer,
          citations: response.citations ?? [],
        },
      ])
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : ""
      if (message.includes("429")) {
        setError("Too many questions right now. Please try again in a bit.")
      } else {
        setError("Couldn't get an answer right now. Try again.")
      }
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 80)
    }
  }, [bookId, currentChapter, loading])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      ask(input)
    }
  }

  return (
    <div
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100"
          : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"
      }`}
    >
      <header
        className={`sticky top-0 z-20 border-b px-4 py-3 backdrop-blur-xl sm:px-6 ${
          isDark ? "border-white/8 bg-black/85" : "border-stone-200 bg-white/85"
        }`}
      >
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href={`/${bookId}`}
              className={`text-sm font-medium transition ${
                isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"
              }`}
            >
              {"<- Overview"}
            </Link>
            {bookTitle ? (
              <>
                <span className={`text-sm ${isDark ? "text-slate-600" : "text-stone-300"}`}>/</span>
                <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                  {bookTitle}
                </span>
              </>
            ) : null}
          </div>
          <div
            className={`rounded-[0.7rem] border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.24em] ${
              isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-stone-50 text-stone-400"
            }`}
          >
            Up to chapter {currentChapter}
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <div className="mb-8">
          <p
            className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${
              isDark ? "text-indigo-300" : "text-violet-500"
            }`}
          >
            Natural Language Query
          </p>
          <h1 className={`mt-2 font-serif text-4xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>
            Ask LoreVia
          </h1>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Ask plain-English questions about your story and get a short grounded answer with chapter citations.
            Only chapters 1-{currentChapter} are used, so there are no spoilers.
          </p>
        </div>

        {history.length > 0 ? (
          <div className="mb-6 space-y-4">
            {history.map((entry, index) => (
              <div key={`${entry.question}-${index}`} className="space-y-2">
                <div className="flex justify-end">
                  <div
                    className={`max-w-[80%] rounded-[1.2rem] px-5 py-4 ${
                      isDark
                        ? "border border-indigo-500/30 bg-indigo-600/30"
                        : "border border-violet-200 bg-violet-600/12"
                    }`}
                  >
                    <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-800"}`}>
                      {entry.question}
                    </p>
                  </div>
                </div>

                <div
                  className={`rounded-[1.2rem] border px-5 py-5 ${
                    isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"
                  }`}
                >
                  <p
                    className={`mb-3 text-[10px] font-semibold uppercase tracking-[0.26em] ${
                      isDark ? "text-indigo-300" : "text-violet-600"
                    }`}
                  >
                    Answer - Chapters 1-{currentChapter}
                  </p>
                  <p className={`whitespace-pre-wrap text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                    {entry.answer}
                  </p>

                  {entry.citations.length > 0 ? (
                    <div className="mt-4 space-y-2">
                      <p className={`text-[10px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        Citations
                      </p>
                      <div className="space-y-2">
                        {entry.citations.map((citation, citationIndex) => (
                          <div
                            key={`${citation.chapter_num}-${citation.source_type}-${citationIndex}`}
                            className={`rounded-[1rem] border px-4 py-3 ${
                              isDark ? "border-white/10 bg-black/35" : "border-stone-200 bg-stone-50"
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className={`text-xs font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                                Chapter {citation.chapter_num}
                                {citation.chapter_title ? ` - ${citation.chapter_title}` : ""}
                              </p>
                              <span
                                className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                                  isDark ? "bg-white/8 text-slate-300" : "bg-white text-stone-500"
                                }`}
                              >
                                {citation.source_type === "passage" ? "Passage" : "Summary"}
                              </span>
                            </div>
                            <p className={`mt-2 text-xs leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                              {citation.excerpt}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}

            {loading ? (
              <div
                className={`animate-pulse rounded-[1.2rem] border px-5 py-5 ${
                  isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"
                }`}
              >
                <div className={`mb-3 h-2.5 w-28 rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`} />
                <div className={`mb-2 h-2.5 w-full rounded-full ${isDark ? "bg-white/8" : "bg-stone-100"}`} />
                <div className={`mb-2 h-2.5 w-3/4 rounded-full ${isDark ? "bg-white/8" : "bg-stone-100"}`} />
                <div className={`h-2.5 w-1/2 rounded-full ${isDark ? "bg-white/6" : "bg-stone-100"}`} />
              </div>
            ) : null}

            <div ref={bottomRef} />
          </div>
        ) : null}

        {history.length === 0 && !loading ? (
          <div
            className={`mb-6 rounded-[1.5rem] border p-6 ${
              isDark ? "border-indigo-500/20 bg-indigo-500/8" : "border-violet-100 bg-violet-50"
            }`}
          >
            <p
              className={`mb-2 text-[11px] font-semibold uppercase tracking-[0.28em] ${
                isDark ? "text-indigo-300" : "text-violet-500"
              }`}
            >
              Try asking
            </p>
            <p className={`text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
              Good for questions like last appearance, first introduction, relationship status, past ability use, and where a detail was established.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => ask(prompt)}
                  className={`rounded-[0.9rem] border px-3 py-1.5 text-xs font-medium transition ${
                    isDark
                      ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/12"
                      : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                  }`}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {error ? (
          <p
            className={`mb-4 rounded-[0.9rem] border px-4 py-3 text-sm ${
              isDark
                ? "border-red-500/25 bg-red-500/10 text-red-300"
                : "border-red-200 bg-red-50 text-red-700"
            }`}
          >
            {error}
          </p>
        ) : null}

        <div
          className={`sticky bottom-4 rounded-[1.4rem] border px-4 py-3 shadow-[0_8px_32px_-8px_rgba(0,0,0,0.25)] transition ${
            isDark
              ? "border-white/10 bg-black/90 backdrop-blur-xl focus-within:border-white/30"
              : "border-stone-200 bg-white/90 backdrop-blur-xl focus-within:border-violet-300"
          }`}
        >
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              id="ask-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your story up to this point..."
              rows={2}
              disabled={loading}
              className={`flex-1 resize-none bg-transparent text-sm leading-6 outline-none ${
                isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-800 placeholder:text-stone-400"
              }`}
            />
            <button
              id="ask-submit"
              onClick={() => ask(input)}
              disabled={!input.trim() || loading}
              className="shrink-0 rounded-[0.9rem] bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_8px_24px_-12px_rgba(79,70,229,0.7)] transition disabled:opacity-40 hover:-translate-y-[1px]"
            >
              {loading ? "..." : "Ask"}
            </button>
          </div>
          <p className={`mt-2 text-[10px] ${isDark ? "text-slate-600" : "text-stone-400"}`}>
            Enter to ask - Shift+Enter for new line - Answers grounded in chapters 1-{currentChapter}
          </p>
        </div>

        <div className={`mt-5 flex flex-wrap items-center gap-3 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <span>Need direct passage retrieval instead?</span>
          <Link
            href={`/${bookId}/search`}
            className={`font-semibold transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}
          >
            Open Search Your Writing
          </Link>
        </div>

        {history.length >= 3 ? (
          <div
            className={`mt-6 rounded-[1.4rem] border px-5 py-4 ${
              isDark ? "border-indigo-500/20 bg-indigo-500/8" : "border-violet-100 bg-violet-50"
            }`}
          >
            <p className={`text-sm font-semibold ${isDark ? "text-indigo-200" : "text-violet-700"}`}>
              Writing this story?
            </p>
            <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Story Advisor gives you plothole detection, foreshadowing opportunities, and arc
              tradeoff analysis grounded in your full manuscript, not just your read progress.
            </p>
            <Link
              href={`/${bookId}/advisor`}
              className={`mt-3 inline-flex items-center text-xs font-semibold transition ${
                isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-600 hover:text-violet-700"
              }`}
            >
              Open Story Advisor
            </Link>
          </div>
        ) : null}
      </div>
    </div>
  )
}
