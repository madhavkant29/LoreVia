"use client"

import { useEffect } from "react"
import type { Route } from "next"
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { getBookRouteSegment, normalizeBookRouteId, replaceBookRouteSegment } from "@/lib/utils/bookRoutes"

export default function BookLayout({ children }: { children: React.ReactNode }) {
  const { bookId } = useParams<{ bookId: string }>()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (!bookId || !pathname) return

    let cancelled = false

    booksApi.get(normalizeBookRouteId(bookId)).then((book) => {
      if (cancelled) return
      const canonicalSegment = getBookRouteSegment(book)
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
