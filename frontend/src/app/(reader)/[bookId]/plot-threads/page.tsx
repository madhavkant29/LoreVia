"use client"

import { useEffect } from "react"
import { useParams } from "next/navigation"

import { PlotTracker } from "@/components/intelligence/PlotTracker"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"

export default function PlotThreadsPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    capture("plot_threads_opened", { book_id: bookId })
  }, [bookId])

  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <main data-plot-threads-workspace className="mx-auto min-w-0 max-w-7xl px-0 pb-16 pt-6 sm:px-2 lg:px-4 [overflow-wrap:anywhere]">
        <WorkspaceFamilyHeader
          active="plot-threads"
          bookId={bookId}
          family="story-bible"
          title="Plot threads"
          description="Track open arcs across the manuscript, identify unresolved pressure points, and keep private reminders beside the story structure."
          actions={<button type="button" className="app-button-secondary !rounded-sm" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>}
        />

        <div className="mt-6">
          <PlotTracker key={bookId} bookId={bookId} mode="dashboard" />
        </div>
      </main>
    </WorkspacePage>
  )
}
