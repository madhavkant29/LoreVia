"use client"

import { Suspense, useEffect } from "react"
import type { Route } from "next"
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { getBookRouteSegment, normalizeBookRouteId, replaceBookRouteSegment } from "@/lib/utils/bookRoutes"

const canonicalBookRouteCache = new Map<string, string>()

function getCanonicalRouteCacheKey(bookId: string) {
  return `book-route-segment:${bookId}`
}

function getCachedCanonicalRouteSegment(bookId: string) {
  const cached = canonicalBookRouteCache.get(bookId)
  if (cached) return cached
  if (typeof window === "undefined") return null
  const fromSession = window.sessionStorage.getItem(getCanonicalRouteCacheKey(bookId))
  if (fromSession) {
    canonicalBookRouteCache.set(bookId, fromSession)
  }
  return fromSession
}

function setCachedCanonicalRouteSegment(bookId: string, segment: string) {
  canonicalBookRouteCache.set(bookId, segment)
  if (typeof window === "undefined") return
  window.sessionStorage.setItem(getCanonicalRouteCacheKey(bookId), segment)
}

export default function BookLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={children}>
      <BookLayoutInner>{children}</BookLayoutInner>
    </Suspense>
  )
}

function BookLayoutInner({ children }: { children: React.ReactNode }) {
  const { bookId } = useParams<{ bookId: string }>()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (!bookId || !pathname) return
    const normalizedBookId = normalizeBookRouteId(bookId)
    const cachedCanonicalSegment = getCachedCanonicalRouteSegment(normalizedBookId)

    if (cachedCanonicalSegment === bookId) {
      return
    }

    if (cachedCanonicalSegment) {
      const nextPath = replaceBookRouteSegment(pathname, bookId, cachedCanonicalSegment)
      if (nextPath !== pathname) {
        const query = searchParams.toString()
        router.replace((query ? `${nextPath}?${query}` : nextPath) as Route)
      }
      return
    }

    let cancelled = false

    booksApi.get(normalizedBookId).then((book) => {
      if (cancelled) return
      const canonicalSegment = getBookRouteSegment(book)
      setCachedCanonicalRouteSegment(normalizedBookId, canonicalSegment)
      if (canonicalSegment === bookId) return

      const nextPath = replaceBookRouteSegment(pathname, bookId, canonicalSegment)
      if (nextPath === pathname) return

      const query = searchParams.toString()
      router.replace((query ? `${nextPath}?${query}` : nextPath) as Route)
    }).catch(() => {})

    return () => {
      cancelled = true
    }
  }, [bookId, pathname, router, searchParams])

  return <>{children}</>
}
