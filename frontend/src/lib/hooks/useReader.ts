import { useState, useCallback, useEffect } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { readerApi } from "@/lib/api/reader"
import { readerCacheKey } from "@/lib/query/cacheKeys"
import type { ContextResult } from "@/types/reader"

export function useReader(bookId: string, chapterNum: number) {
  const queryClient = useQueryClient()
  const cacheKey = readerCacheKey(bookId, chapterNum)

  const {
    data: chapterData,
    isLoading: loading,
    error: queryError,
  } = useQuery({
    queryKey: cacheKey,
    queryFn: () => readerApi.getChapter(bookId, chapterNum),
    staleTime: 60_000,
  })

  const [contextResult, setContextResult] = useState<ContextResult | null>(null)
  const [contextLoading, setContextLoading] = useState(false)

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
    const totalChapters = chapterData?.total_chapters ?? 0
    if (!totalChapters) return
    const neighbors = [chapterNum - 1, chapterNum + 1].filter(
      (chapter) => chapter > 0 && chapter <= totalChapters
    )
    for (const chapter of neighbors) {
      queryClient.prefetchQuery({
        queryKey: readerCacheKey(bookId, chapter),
        queryFn: () => readerApi.getChapter(bookId, chapter),
        staleTime: 60_000,
      })
    }
  }, [bookId, chapterNum, chapterData?.total_chapters, queryClient])

  const error = queryError ? "Failed to load chapter" : null

  return {
    data: chapterData ?? null,
    loading,
    error,
    tap,
    contextResult,
    contextLoading,
    clearContext,
    saveProgress,
  }
}
