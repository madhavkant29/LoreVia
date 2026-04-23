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
    let active = true
    setLoading(true)
    setError(null)
    readerApi.getChapter(bookId, chapterNum)
      .then((chapter) => {
        if (!active) return
        setData(chapter)
      })
      .catch(() => {
        if (!active) return
        setError("Failed to load chapter")
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
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

  useEffect(() => {
    const totalChapters = data?.total_chapters ?? 0
    if (!totalChapters) return
    const neighbors = [chapterNum - 1, chapterNum + 1].filter((chapter) => chapter > 0 && chapter <= totalChapters)
    for (const chapter of neighbors) {
      void readerApi.getChapter(bookId, chapter)
    }
  }, [bookId, chapterNum, data?.total_chapters])

  return { data, loading, error, tap, contextResult, contextLoading, clearContext, saveProgress }
}
