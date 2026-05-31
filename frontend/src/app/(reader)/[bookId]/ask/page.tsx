"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { buildDailyCapEventDetail } from "@/lib/limits/dailyCap"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import { AskLoreViaWorkspace } from "@/components/reader/AskLoreViaWorkspace"
import { getAskLoreViaScopeLabel } from "@/lib/utils/askLoreVia"
import type { Book } from "@/types/book"
import type { GroundedCitation } from "@/types/intelligence"
import type { ChapterListResponse, ReadingProgress } from "@/types/reader"

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

  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<QAEntry[]>([])

  const inputRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: book = null } = useQuery<Book>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
    staleTime: 20_000,
  })
  const { data: progress = null } = useQuery<ReadingProgress>({
    queryKey: asQueryKey(readerCacheKey(bookId, "progress")),
    queryFn: () => readerApi.getProgress(bookId),
    staleTime: 12_000,
  })
  const { data: chapterList = null } = useQuery<ChapterListResponse>({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId),
    staleTime: 30_000,
  })

  const currentChapter = (() => {
    if (book?.mode === "author") {
      const processedChapters = (chapterList?.chapters ?? [])
        .filter((chapter) => chapter.processed && chapter.intelligence_available !== false)
        .map((chapter) => chapter.number)
      return Math.max(1, ...(processedChapters.length > 0 ? processedChapters : [book.total_chapters ?? 1]))
    }
    return Math.max(1, progress?.current_chapter ?? 1)
  })()

  const scopeLabel = getAskLoreViaScopeLabel(book?.mode, currentChapter)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [history, loading])

  const ask = useCallback(async (text: string) => {
    const question = text.trim()
    if (!question || loading) return
    setInput("")
    setError(null)
    setLoading(true)
    setHistory((previous) => [
      ...previous,
      {
        question,
        answer: "",
        citations: [],
      },
    ])
    capture("ask_submitted", { book_id: bookId, chapter: currentChapter, question_len: question.length, mode: book?.mode ?? "reader" })
    try {
      const response = await intelligenceApi.answerStream(bookId, question, currentChapter, {
        onDelta: (content) => {
          if (!content) return
          setHistory((previous) => {
            if (previous.length === 0) return previous
            const last = previous[previous.length - 1]
            return [
              ...previous.slice(0, -1),
              {
                ...last,
                answer: `${last.answer}${content}`,
              },
            ]
          })
        },
      })
      setHistory((previous) => {
        if (previous.length === 0) return previous
        const last = previous[previous.length - 1]
        return [
          ...previous.slice(0, -1),
          {
            ...last,
            answer: response.answer,
            citations: response.citations ?? [],
          },
        ]
      })
    } catch (err: unknown) {
      setHistory((previous) => previous.slice(0, -1))
      const dailyCap = buildDailyCapEventDetail(err)
      const message = err instanceof Error ? err.message : ""
      if (dailyCap) {
        setError("You reached today's question limit. Upgrade for more daily capacity or continue tomorrow.")
      } else if (message.includes("429")) {
        setError("Too many questions right now. Please try again in a bit.")
      } else {
        setError("Couldn't get an answer right now. Try again.")
      }
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 80)
    }
  }, [book?.mode, bookId, currentChapter, loading])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      ask(input)
    }
  }

  return (
    <AskLoreViaWorkspace
      bookId={bookId}
      bookTitle={book?.title}
      mode={book?.mode}
      currentChapter={currentChapter}
      scopeLabel={scopeLabel}
      history={history}
      input={input}
      loading={loading}
      error={error}
      isDark={isDark}
      inputRef={inputRef}
      bottomRef={bottomRef}
      onInputChange={setInput}
      onSubmit={ask}
      onKeyDown={handleKeyDown}
      quickPrompts={QUICK_PROMPTS}
    />
  )
}
