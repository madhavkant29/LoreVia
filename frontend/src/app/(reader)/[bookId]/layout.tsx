"use client"

import { Suspense, useEffect } from "react"
import type { Route } from "next"
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation"

import { useBookDetail } from "@/lib/hooks/useBookDetail"
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

function isReaderShellRoute(pathname: string, bookSegment: string) {
  const parts = pathname.split("/").filter(Boolean)
  const bookIndex = parts.findIndex((part) => part === bookSegment)
  const normalized = bookIndex >= 0 ? `/${parts.slice(bookIndex + 1).join("/")}`.replace(/\/$/, "") : ""
  return (
    normalized === "/" ||
    normalized.startsWith("/chapter/") ||
    normalized === "/chapters" ||
    normalized === "/summaries" ||
    normalized === "/search" ||
    normalized === "/timeline" ||
    normalized === "/beta-feedback"
  )
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
  const normalizedBookId = normalizeBookRouteId(bookId)
  const { data: book = null } = useBookDetail(normalizedBookId, { staleTime: 30_000 })

  useEffect(() => {
    if (!bookId || !pathname) return
    const cachedCanonicalSegment = getCachedCanonicalRouteSegment(normalizedBookId)

    if (cachedCanonicalSegment === bookId) {
      return
    }

    const canonicalSegment = cachedCanonicalSegment ?? (book ? getBookRouteSegment(book) : null)
    if (!canonicalSegment) {
      return
    }

    setCachedCanonicalRouteSegment(normalizedBookId, canonicalSegment)

    if (canonicalSegment === bookId) {
      return
    }

    const nextPath = replaceBookRouteSegment(pathname, bookId, canonicalSegment)
    if (nextPath !== pathname) {
      const query = searchParams.toString()
      router.replace((query ? `${nextPath}?${query}` : nextPath) as Route)
    }
  }, [book, bookId, normalizedBookId, pathname, router, searchParams])

  useEffect(() => {
    if (!bookId || !pathname || !book) return
    if (book.access_class !== "reader_collaborator" || book.workspace_shell !== "reader") return
    if (isReaderShellRoute(pathname, bookId)) return

    const target = `/${bookId}?access=reader-workspace`
    if (pathname !== `/${bookId}`) {
      router.replace(target as Route)
    }
  }, [book, bookId, pathname, router])

  return <>{children}</>
}
