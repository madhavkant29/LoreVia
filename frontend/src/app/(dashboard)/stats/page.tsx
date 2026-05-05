"use client"

import { useEffect, useMemo, useState } from "react"

import {
  WorkspaceEmptyState,
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import type { UserStats } from "@/types/book"

export default function StatsPage() {
  const [stats, setStats] = useState<UserStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    booksApi.getStats().then(setStats).finally(() => setLoading(false))
  }, [])

  const totals = useMemo(() => {
    if (!stats) return null

    return {
      publicMoments: stats.public.total_books_read + stats.private.saved_quotes,
      privateLoad: stats.private.total_token_consumption + stats.private.total_chapters_tracked,
    }
  }, [stats])

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        <WorkspacePanel tone="strong" className="p-6 sm:p-8">
          <WorkspaceHeader
            eyebrow="Workspace health"
            title="Reading progress and manuscript usage in one calm view."
            description="The stats page should help authors and readers understand momentum quickly, so the layout now separates public-facing reading milestones from private workspace load."
            meta={
              <div className="app-chip">
                {stats ? `${stats.private.total_uploads.toLocaleString()} uploads tracked` : "Syncing stats"}
              </div>
            }
          />
        </WorkspacePanel>

        {loading ? (
          <WorkspaceEmptyState
            title="Loading workspace stats"
            body="LoreVia is gathering your reading milestones and private usage metrics."
          />
        ) : !stats || !totals ? (
          <WorkspaceEmptyState
            title="Stats unavailable"
            body="We could not load your dashboard metrics right now."
          />
        ) : (
          <>
            <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
              <WorkspacePanel className="p-6">
                <p className="app-eyebrow">Public profile</p>
                <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                  Reading milestones you can share
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                  These numbers represent outward-facing reading progress and feel more like proof of momentum than back-office telemetry.
                </p>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <WorkspaceMetric
                    label="Books finished"
                    value={stats.public.total_books_read.toLocaleString()}
                    note="Completed or fully consumed titles"
                    accent="success"
                  />
                  <WorkspaceMetric
                    label="Words read"
                    value={stats.public.total_words_read.toLocaleString()}
                    note="Finished plus in-progress reading"
                    accent="accent"
                  />
                </div>
              </WorkspacePanel>

              <WorkspacePanel className="p-6">
                <p className="app-eyebrow">Snapshot</p>
                <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                  A faster sense of scale
                </h2>
                <div className="mt-6 space-y-4">
                  <div className="rounded-[1.4rem] border border-[rgba(var(--border),0.72)] bg-[rgba(255,255,255,0.44)] p-4 dark:bg-[rgba(255,255,255,0.03)]">
                    <p className="text-sm font-semibold text-[rgb(var(--foreground))]">
                      {totals.publicMoments.toLocaleString()} total public moments
                    </p>
                    <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                      Books completed plus quotes captured creates a useful signal for engagement over time.
                    </p>
                  </div>
                  <div className="rounded-[1.4rem] border border-[rgba(var(--border),0.72)] bg-[rgba(255,255,255,0.44)] p-4 dark:bg-[rgba(255,255,255,0.03)]">
                    <p className="text-sm font-semibold text-[rgb(var(--foreground))]">
                      {totals.privateLoad.toLocaleString()} units of private workspace load
                    </p>
                    <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                      Token volume and tracked chapters give a better signal for how much manuscript intelligence LoreVia is carrying for you.
                    </p>
                  </div>
                </div>
              </WorkspacePanel>
            </section>

            <WorkspacePanel className="p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="app-eyebrow">Private workspace</p>
                  <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                    The operational side of your account
                  </h2>
                </div>
                <p className="max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                  This section stays deliberately practical: it tells you how much manuscript volume and saved context the app is managing behind the scenes.
                </p>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <WorkspaceMetric
                  label="Uploads"
                  value={stats.private.total_uploads.toLocaleString()}
                  note="Includes hidden titles"
                />
                <WorkspaceMetric
                  label="Token load"
                  value={stats.private.total_token_consumption.toLocaleString()}
                  note="Tracked AI processing volume"
                  accent="warning"
                />
                <WorkspaceMetric
                  label="Chapters tracked"
                  value={stats.private.total_chapters_tracked.toLocaleString()}
                  note="Across your complete library"
                />
                <WorkspaceMetric
                  label="Saved quotes"
                  value={stats.private.saved_quotes.toLocaleString()}
                  note="Private notes and evidence"
                  accent="accent"
                />
              </div>
            </WorkspacePanel>
          </>
        )}
      </div>
    </WorkspacePage>
  )
}
