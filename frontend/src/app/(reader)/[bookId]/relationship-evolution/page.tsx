"use client"

import { useEffect } from "react"
import { useParams, useRouter } from "next/navigation"

export default function RelationshipEvolutionPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()

  useEffect(() => {
    router.replace(`/${bookId}/graph?view=evolution`)
  }, [bookId, router])

  return (
    <div className="grid min-h-screen place-items-center bg-stone-50 px-6 text-sm text-stone-500 dark:bg-[#071211] dark:text-slate-400">
      Opening relationship history...
    </div>
  )
}
