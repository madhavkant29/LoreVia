"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { readerApi } from "@/lib/api/reader"
import { asQueryKey, readerUpcomingBetaReadsCacheKey } from "@/lib/query/cacheKeys"
import { betaReadDeadlineLabel, betaReadIsUrgent, betaReadPrimaryHref, betaReadProgressLabel } from "@/lib/utils/betaReads"
import type { BetaReadAssignment } from "@/types/reader"

export function UpcomingBetaReadsCard({ isDark }: { isDark: boolean }) {
  const router = useRouter()
  const [pendingId, setPendingId] = useState<string | null>(null)
  const { data: items = [], isLoading } = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(readerUpcomingBetaReadsCacheKey()),
    queryFn: () => readerApi.getUpcomingBetaReads(),
    staleTime: 12_000,
  })

  async function handlePrimaryAction(assignment: BetaReadAssignment) {
    setPendingId(assignment.id)
    try {
      if (assignment.primary_action === "Start" || assignment.primary_action === "Continue") {
        if (assignment.primary_action === "Start") {
          await readerApi.startBetaRead(assignment.id)
        }
        router.push(betaReadPrimaryHref(assignment) as Route)
        return
      }
      router.push("/beta-reads" as Route)
    } finally {
      setPendingId(null)
    }
  }

  const panelClass = isDark
    ? "border-white/[0.08] bg-[#111119]"
    : "border-stone-200/80 bg-white/88"
  const copyClass = isDark ? "text-[#f7f3ed]" : "text-stone-950"
  const mutedClass = isDark ? "text-[#9f9ca8]" : "text-stone-500"
  const subtleClass = isDark ? "text-[#c8c4bd]" : "text-stone-700"

  return (
    <section className={`rounded-[1.5rem] border p-6 shadow-[0_22px_70px_-48px_rgba(15,23,42,0.5)] ${panelClass}`}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-[0.7rem] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Upcoming Beta Reads</p>
          <h2 className={`mt-2 font-serif text-[2rem] tracking-[-0.03em] ${copyClass}`}>Complete reviews before the deadline.</h2>
        </div>
        <button
          type="button"
          onClick={() => router.push("/beta-reads" as Route)}
          className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${
            isDark ? "bg-white/[0.05] text-[#f4efe7] hover:bg-white/[0.08]" : "bg-stone-100 text-stone-900 hover:bg-stone-200"
          }`}
        >
          View all beta reads
        </button>
      </div>

      {isLoading ? (
        <div className={`mt-6 rounded-[1.2rem] border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/[0.08] text-[#8c8994]" : "border-stone-200 text-stone-500"}`}>
          Loading beta reads...
        </div>
      ) : items.length === 0 ? (
        <div className={`mt-6 rounded-[1.2rem] border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/[0.08] text-[#8c8994]" : "border-stone-200 text-stone-500"}`}>
          No beta reads are assigned to you right now.
        </div>
      ) : (
        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          {items.slice(0, 3).map((assignment) => {
            const urgent = betaReadIsUrgent(assignment.expires_at)
            return (
              <article
                key={assignment.id}
                className={`rounded-[1.25rem] border p-5 ${isDark ? "border-white/[0.06] bg-[#0d0d14]" : "border-stone-200 bg-stone-50/70"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className={`truncate font-serif text-[1.65rem] tracking-[-0.03em] ${copyClass}`}>{assignment.book_title}</h3>
                    <p className={`mt-1 text-sm ${mutedClass}`}>{assignment.task_label} - {assignment.author_name}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${urgent ? "bg-rose-500/12 text-rose-300" : isDark ? "bg-white/[0.05] text-[#d6d0c7]" : "bg-stone-200 text-stone-700"}`}>
                    {assignment.status_label}
                  </span>
                </div>

                <div className={`mt-5 flex items-center justify-between text-sm ${subtleClass}`}>
                  <span className={urgent ? "text-rose-300" : undefined}>{betaReadDeadlineLabel(assignment.expires_at)}</span>
                  <span>{Math.round(assignment.progress_pct)}% complete</span>
                </div>

                <div className="mt-4">
                  <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`}>
                    <div className={`h-full rounded-full ${urgent ? "bg-[linear-gradient(90deg,#fb7185,#f97316)]" : "bg-[linear-gradient(90deg,#f59e0b,#f97316)]"}`} style={{ width: `${Math.max(4, Math.round(assignment.progress_pct))}%` }} />
                  </div>
                  <p className={`mt-2 text-sm ${mutedClass}`}>{betaReadProgressLabel(assignment)}</p>
                </div>

                <button
                  type="button"
                  onClick={() => void handlePrimaryAction(assignment)}
                  disabled={pendingId === assignment.id}
                  className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-full bg-[#9a3412] px-4 text-sm font-semibold text-white transition hover:bg-[#b45309] disabled:opacity-60"
                >
                  {pendingId === assignment.id ? "Working..." : assignment.primary_action}
                </button>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
