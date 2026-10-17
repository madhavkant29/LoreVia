"use client"

import { useEffect } from "react"
import { useParams, useRouter } from "next/navigation"

export default function SummariesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()

  useEffect(() => {
    router.replace(`/${bookId}`)
  }, [bookId, router])

  return <p className="min-h-screen px-6 py-20 text-sm text-[rgb(var(--muted-foreground))]" role="status">Opening the overview recap…</p>
}
