"use client"

import { useCallback, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { worldBuildingApi } from "@/lib/api/worldBuilding"

interface PrefetchEntry {
  queryKey: unknown[]
  queryFn: () => Promise<unknown>
  staleTime?: number
}

function buildPrefetchEntries(bookId: string): Record<string, PrefetchEntry[]> {
  return {
    overview: [
      {
        queryKey: [`book:${bookId}:overview`],
        queryFn: () => booksApi.getOverview(bookId),
        staleTime: 20_000,
      },
    ],
    advisor: [
      {
        queryKey: [`advisor:${bookId}:greeting`],
        queryFn: () => intelligenceApi.advisorGreeting(bookId),
        staleTime: 30_000,
      },
    ],
    characters: [
      {
        queryKey: [`book:${bookId}:characters`],
        queryFn: () => booksApi.getCharacters(bookId),
        staleTime: 30_000,
      },
    ],
    "world-gap": [
      {
        queryKey: [`worldbuilding:${bookId}:documents`],
        queryFn: () => worldBuildingApi.listDocuments(bookId),
        staleTime: 30_000,
      },
      {
        queryKey: [`worldbuilding:${bookId}:elements`],
        queryFn: () => worldBuildingApi.listElements(bookId),
        staleTime: 30_000,
      },
    ],
  }
}

const DEBOUNCE_MS = 120

export function useNavigationPrefetch(bookId: string) {
  const queryClient = useQueryClient()
  const prefetchedRef = useRef(new Set<string>())
  const timersRef = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  const prefetchByNavId = useCallback(
    (navId: string) => {
      if (!bookId) return

      const entries = buildPrefetchEntries(bookId)
      const targets = entries[navId]
      if (!targets || targets.length === 0) return
      if (prefetchedRef.current.has(navId)) return

      const existing = timersRef.current.get(navId)
      if (existing) {
        clearTimeout(existing)
      }

      timersRef.current.set(
        navId,
        setTimeout(() => {
          timersRef.current.delete(navId)
          if (prefetchedRef.current.has(navId)) return

          for (const entry of targets) {
            queryClient.prefetchQuery({
              queryKey: entry.queryKey,
              queryFn: entry.queryFn,
              staleTime: entry.staleTime,
            })
          }
          prefetchedRef.current.add(navId)
        }, DEBOUNCE_MS)
      )
    },
    [bookId, queryClient]
  )

  return { prefetchByNavId }
}
