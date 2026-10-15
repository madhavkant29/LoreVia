import { useState, useCallback, useEffect, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import type { ContextResult } from "@/types/reader"

export function useReader(bookId: string, chapterNum: number) {
  const queryClient = useQueryClient()
  const cacheKey = readerCacheKey(bookId, chapterNum)

  const {
    data: chapterData,
    isLoading: loading,
    error: queryError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: cacheKey,
    queryFn: () => readerApi.getChapter(bookId, chapterNum),
    staleTime: 60_000,
    retry: false,
  })

  const chaptersQuery = useQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId),
    staleTime: 60_000,
    retry: false,
  })
  const chapterNumbers = [...new Set(chaptersQuery.data?.chapters?.map((chapter) => chapter.number) ?? [])]
    .filter((chapter) => Number.isSafeInteger(chapter) && chapter > 0).sort((a, b) => a - b)
  const previousChapter = chapterNumbers.filter((chapter) => chapter < chapterNum).at(-1) ?? null
  const nextChapter = chapterNumbers.find((chapter) => chapter > chapterNum) ?? null

  const [contextResult, setContextResult] = useState<ContextResult | null>(null)
  const [contextLoading, setContextLoading] = useState(false)
  const [contextError, setContextError] = useState<string | null>(null)
  const contextRequest = useRef(0)
  const lastWord = useRef("")
  const [progressError, setProgressError] = useState(false)
  const lastProgress = useRef(0)
  const progressRequest = useRef(0)

  const tap = useCallback(async (word: string) => {
    const request = ++contextRequest.current
    lastWord.current = word
    setContextResult(null)
    setContextError(null)
    setContextLoading(true)
    try {
      const result = await readerApi.getContext(bookId, word, chapterNum)
      if (request === contextRequest.current) setContextResult(result)
    } catch {
      if (request === contextRequest.current) setContextError("Could not load reading context. Try again.")
    } finally {
      if (request === contextRequest.current) setContextLoading(false)
    }
  }, [bookId, chapterNum])

  const clearContext = useCallback(() => {
    contextRequest.current += 1
    setContextResult(null)
    setContextError(null)
    setContextLoading(false)
  }, [])

  useEffect(() => () => {
    contextRequest.current += 1
    progressRequest.current += 1
  }, [bookId, chapterNum])

  const saveProgress = useCallback(
    async (scrollPct: number) => {
      lastProgress.current = scrollPct
      const request = ++progressRequest.current
      try {
        await readerApi.updateProgress(bookId, chapterNum, scrollPct)
        if (request === progressRequest.current) setProgressError(false)
      } catch {
        if (request === progressRequest.current) setProgressError(true)
      }
    },
    [bookId, chapterNum]
  )

  useEffect(() => {
    const neighbors = [previousChapter, nextChapter].filter((chapter): chapter is number => chapter !== null)
    for (const chapter of neighbors) {
      queryClient.prefetchQuery({
        queryKey: readerCacheKey(bookId, chapter),
        queryFn: () => readerApi.getChapter(bookId, chapter),
        staleTime: 60_000,
      })
    }
  }, [bookId, previousChapter, nextChapter, queryClient])

  const error = queryError ? "Failed to load chapter" : null

  return {
    data: chapterData ?? null,
    loading,
    error,
    refetch,
    isFetching,
    previousChapter,
    nextChapter,
    chaptersError: chaptersQuery.error,
    retryChapters: chaptersQuery.refetch,
    tap,
    contextResult,
    contextLoading,
    contextError,
    retryContext: () => tap(lastWord.current),
    clearContext,
    saveProgress,
    progressError,
    retryProgress: () => saveProgress(lastProgress.current),
  }
}
