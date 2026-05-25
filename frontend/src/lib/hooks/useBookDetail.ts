"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import type { Book } from "@/types/book"

export function getBookDetailQueryKey(bookId: string) {
  return asQueryKey(bookCacheKey(bookId, "detail"))
}

type UseBookDetailOptions = {
  enabled?: boolean
  staleTime?: number
  refetchInterval?: ((query: { state: { data: Book | null | undefined } }) => number | false) | number | false
  refetchIntervalInBackground?: boolean
}

export function useBookDetail(bookId: string, options: UseBookDetailOptions = {}) {
  return useQuery<Book | null>({
    queryKey: getBookDetailQueryKey(bookId),
    queryFn: () => booksApi.get(bookId),
    enabled: options.enabled ?? true,
    staleTime: options.staleTime ?? 60_000,
    refetchInterval: options.refetchInterval,
    refetchIntervalInBackground: options.refetchIntervalInBackground,
  })
}

export function useCachedBookDetail(bookId: string) {
  const queryClient = useQueryClient()

  return useQuery<Book | null>({
    queryKey: getBookDetailQueryKey(bookId),
    queryFn: () => booksApi.get(bookId),
    enabled: false,
    staleTime: Number.POSITIVE_INFINITY,
    initialData: () => queryClient.getQueryData<Book | null>(getBookDetailQueryKey(bookId)),
  })
}
