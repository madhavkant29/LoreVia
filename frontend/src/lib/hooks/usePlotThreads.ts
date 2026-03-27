import { useState, useEffect } from "react"
import { readerApi } from "@/lib/api/reader"
import type { PlotThread } from "@/types/reader"

export function usePlotThreads(bookId: string, chapter: number) {
  const [threads, setThreads] = useState<PlotThread[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    readerApi.getPlotThreads(bookId, chapter)
      .then(setThreads)
      .finally(() => setLoading(false))
  }, [bookId, chapter])

  const counts = {
    ongoing:    threads.filter(t => t.status === "ongoing").length,
    resolved:   threads.filter(t => t.status === "resolved").length,
    introduced: threads.filter(t => t.status === "introduced").length,
    unknown:    threads.filter(t => t.status === "unknown").length,
  }

  return { threads, loading, counts }
}
