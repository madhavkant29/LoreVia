"use client"

import { useEffect } from "react"
import { useParams, useRouter } from "next/navigation"

export default function ChapterReportsPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()

  useEffect(() => {
    router.replace(`/${bookId}/analysis?view=chapters`)
  }, [bookId, router])

  return (
    <main className="grid min-h-[50vh] place-items-center bg-[rgb(var(--background))] px-6 text-[rgb(var(--muted-foreground))]" role="status">
      <p className="text-sm">Opening chapter reports in Findings…</p>
    </main>
  )
}
