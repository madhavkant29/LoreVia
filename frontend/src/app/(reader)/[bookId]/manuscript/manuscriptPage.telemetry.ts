import { useEffect, useRef } from "react"

import { captureTiming } from "@/lib/analytics/posthog"

type UseManuscriptTelemetryRefsOptions = {
  bookId: string
  loading: boolean
}

export function useManuscriptTelemetryRefs({ bookId, loading }: UseManuscriptTelemetryRefsOptions) {
  const manuscriptReadyCapturedRef = useRef(false)
  const firstChapterLoadedCapturedRef = useRef(false)
  const manuscriptLoadStartedAtRef = useRef<number | null>(typeof performance !== "undefined" ? performance.now() : null)

  useEffect(() => {
    if (loading || manuscriptReadyCapturedRef.current) return
    manuscriptReadyCapturedRef.current = true
    captureTiming("manuscript_shell_ready_ms", manuscriptLoadStartedAtRef.current ?? 0, {
      book_id: bookId,
      optional_panels_deferred: true,
    })
  }, [bookId, loading])

  return {
    firstChapterLoadedCapturedRef,
    manuscriptLoadStartedAtRef,
  }
}
