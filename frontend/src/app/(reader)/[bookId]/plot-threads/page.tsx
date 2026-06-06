"use client"

import Link from "next/link"
import { useEffect } from "react"
import { useParams } from "next/navigation"

import { PlotTracker } from "@/components/intelligence/PlotTracker"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage, WorkspacePanel } from "@/components/ui/Workspace"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"

export default function PlotThreadsPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    capture("plot_threads_opened", { book_id: bookId })
  }, [bookId])

  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <div className="mx-auto max-w-7xl px-0 pb-16 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="plot-threads"
          bookId={bookId}
          family="story-bible"
          title="Plot threads"
          description="Track open arcs across the manuscript, identify unresolved pressure points, and keep private reminders beside the story structure."
          actions={(
            <>
              <Link href={`/${bookId}`} className="app-button-secondary">Overview</Link>
              <Link href={`/${bookId}/manuscript`} className="app-button-primary">Manuscript</Link>
            </>
          )}
        />

        <WorkspacePanel className="mt-6 p-5 sm:p-6">
          <PlotTracker bookId={bookId} mode="dashboard" />
        </WorkspacePanel>
      </div>
    </WorkspacePage>
  )
}
