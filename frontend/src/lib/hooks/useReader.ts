import { useState, useEffect, useCallback, useRef } from "react"
import { readerApi } from "@/lib/api/reader"
import type { ChapterData, ContextResult, SummaryMode } from "@/types/reader"

export function useReader(bookId: string, chapterNum: number) {
  const [data, setData] = useState<ChapterData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [contextResult, setContextResult] = useState<ContextResult | null>(null)
  const [contextLoading, setContextLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    readerApi.getChapter(bookId, chapterNum)
      .then(setData)
      .catch(() => setError("Failed to load chapter"))
      .finally(() => setLoading(false))
  }, [bookId, chapterNum])

  const tap = useCallback(async (word: string) => {
    setContextLoading(true)
    try {
      const result = await readerApi.getContext(bookId, word, chapterNum)
      setContextResult(result)
    } finally {
      setContextLoading(false)
    }
  }, [bookId, chapterNum])

  const clearContext = useCallback(() => setContextResult(null), [])

  const saveProgress = useCallback(
    (scrollPct: number) => readerApi.updateProgress(bookId, chapterNum, scrollPct),
    [bookId, chapterNum]
  )

  return { data, loading, error, tap, contextResult, contextLoading, clearContext, saveProgress }
}
