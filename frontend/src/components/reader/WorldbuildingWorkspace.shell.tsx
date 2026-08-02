import { Skeleton } from "@/components/ui/Skeleton"

import { MetricCard } from "./WorldbuildingWorkspace.components"
import { panelClass } from "./WorldbuildingWorkspace.helpers"

export function WorldbuildingMetricsStrip({
  isDark,
  documentCount,
  totalWorldWords,
  extractedElementCount,
  openNoteCount,
}: {
  isDark: boolean
  documentCount: number
  totalWorldWords: number
  extractedElementCount: number
  openNoteCount: number
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Active Docs" value={String(documentCount)} note="Separate from story chapters" accent="teal" isDark={isDark} />
      <MetricCard label="Corpus Words" value={totalWorldWords.toLocaleString()} note="Live reference material" accent="blue" isDark={isDark} />
      <MetricCard label="Extracted Lore" value={String(extractedElementCount)} note="Typed world elements" accent="violet" isDark={isDark} />
      <MetricCard label="Open Notes" value={String(openNoteCount)} note="Saved cleanup backlog" accent="amber" isDark={isDark} />
    </div>
  )
}

export function WorldbuildingStatusMessage({
  isDark,
  message,
}: {
  isDark: boolean
  message: string | null
}) {
  if (!message) return null

  return (
    <div className={`rounded-md border px-4 py-3 text-sm ${isDark ? "border-teal-400/20 bg-teal-500/10 text-teal-100" : "border-teal-200 bg-teal-50 text-teal-800"}`}>
      {message}
    </div>
  )
}

export function DocumentBodyLoadingState({ isDark }: { isDark: boolean }) {
  return (
    <div className={`rounded-lg border px-5 py-6 ${panelClass(isDark)}`} role="status" aria-label="Loading document content" aria-busy="true">
      <span className="sr-only">Loading document content</span>
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-4 h-4 w-full" />
      <Skeleton className="mt-2 h-4 w-5/6" />
      <Skeleton className="mt-2 h-4 w-2/3" />
    </div>
  )
}
