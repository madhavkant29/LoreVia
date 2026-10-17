import { Skeleton } from "@/components/ui/Skeleton"

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
    <dl className={`flex flex-wrap border-y ${isDark ? "border-white/10" : "border-stone-200"}`}>
      {[
        ["Canon sources", String(documentCount)],
        ["Source words", totalWorldWords.toLocaleString()],
        ["Lore facts", String(extractedElementCount)],
        ["Open cleanup", String(openNoteCount)],
      ].map(([label, value], index) => (
        <div key={label} className={`flex shrink-0 items-baseline gap-2 px-4 py-3 first:pl-0 ${index > 0 ? (isDark ? "border-l border-white/10" : "border-l border-stone-200") : ""}`}>
          <dt className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</dt>
          <dd className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</dd>
        </div>
      ))}
    </dl>
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
    <div role="status" className={`border-y px-1 py-3 text-sm ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-800"}`}>
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
