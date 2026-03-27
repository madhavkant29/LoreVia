import { useState, useEffect } from "react"
import { readerApi } from "@/lib/api/reader"
import type { RelationshipGraph } from "@/types/character"

export function useRelationships(bookId: string, upToChapter: number) {
  const [graph, setGraph] = useState<RelationshipGraph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    readerApi.getRelationships(bookId, upToChapter)
      .then(setGraph)
      .catch(() => setError("Failed to load relationship graph"))
      .finally(() => setLoading(false))
  }, [bookId, upToChapter])

  return { graph, loading, error }
}
