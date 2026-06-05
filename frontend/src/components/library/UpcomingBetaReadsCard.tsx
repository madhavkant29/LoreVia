"use client"

import { memo, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { Skeleton } from "@/components/ui/Skeleton"
import { Tooltip } from "@/components/ui/Tooltip"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, readerUpcomingBetaReadsCacheKey } from "@/lib/query/cacheKeys"
import { betaReadDeadlineLabel, betaReadIsUrgent, betaReadPrimaryHref, betaReadProgressLabel } from "@/lib/utils/betaReads"
import type { BetaReadAssignment } from "@/types/reader"

export const UpcomingBetaReadsCard = memo(function UpcomingBetaReadsCard({
  isDark,
  onCountChange,
}: {
  isDark: boolean
  onCountChange?: (count: number, ready: boolean) => void
}) {
  const router = useRouter()
  const [pendingId, setPendingId] = useState<string | null>(null)
  const { data: items = [], isLoading } = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(readerUpcomingBetaReadsCacheKey()),
    queryFn: () => readerApi.getUpcomingBetaReads(),
    staleTime: 12_000,
  })

  useEffect(() => {
    onCountChange?.(items.length, !isLoading)
  }, [items.length, isLoading, onCountChange])

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

  const panelClass = isDark ? "border-white/[0.08] bg-[#101b24]" : "border-stone-200 bg-white"
  const copyClass = isDark ? "text-[#f5f0e8]" : "text-stone-950"
  const mutedClass = isDark ? "text-[#9f9b94]" : "text-stone-500"
  const nextAssignment = items[0]
  const bodyText = items.length === 0
      ? "No beta reads are assigned to you right now."
      : nextAssignment
        ? `${items.length === 1 ? "One review needs attention." : `${items.length} reviews need attention.`} ${
            betaReadIsUrgent(nextAssignment.expires_at)
              ? betaReadDeadlineLabel(nextAssignment.expires_at)
              : betaReadProgressLabel(nextAssignment)
          }`
        : "No beta reads are assigned to you right now."

  return (
    <section className={`rounded-sm border p-5 ${panelClass}`}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-4">
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-md ${isDark ? "bg-amber-300/10 text-amber-200" : "bg-amber-50 text-amber-700"}`}>
            <CalendarIcon />
          </div>
          <div>
            <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Upcoming beta reads</p>
            <h2 className={`mt-1.5 text-base font-semibold tracking-[-0.01em] ${copyClass}`}>Complete reviews before the deadline</h2>
            {isLoading ? (
              <div className="mt-3 max-w-2xl space-y-2" role="status" aria-label="Loading beta reads" aria-busy="true">
                <span className="sr-only">Loading beta reads</span>
                <Skeleton variant="text" className="h-4 w-72 max-w-full" />
                <Skeleton variant="text" className="h-4 w-48 max-w-full" />
              </div>
            ) : (
              <p className={`mt-1.5 max-w-2xl text-sm leading-6 ${mutedClass}`}>{bodyText}</p>
            )}
            {!isLoading && nextAssignment ? (
              <p className={`mt-1 text-sm font-medium ${copyClass}`}>
                {nextAssignment.task_label} - {nextAssignment.author_name}
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {nextAssignment ? (
            <Tooltip content={`${nextAssignment.primary_action} this beta read`}>
              <button
                type="button"
                onClick={() => void handlePrimaryAction(nextAssignment)}
                disabled={pendingId === nextAssignment.id}
                className="inline-flex min-h-11 items-center justify-center rounded-sm bg-[#1f615d] px-5 text-sm font-semibold text-white transition hover:bg-[#194f4c] disabled:opacity-60"
              >
                {pendingId === nextAssignment.id ? "Working..." : nextAssignment.primary_action}
              </button>
            </Tooltip>
          ) : null}
          <Tooltip content="Open the beta-read assignment list">
            <button
              type="button"
              onClick={() => router.push("/beta-reads" as Route)}
              className={`inline-flex min-h-11 items-center justify-center rounded-sm border px-5 text-sm font-medium transition ${
                isDark ? "border-white/[0.08] bg-[#1f2427] text-[#ebe7df] hover:bg-[#252b2f]" : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
              }`}
            >
              View all beta reads
            </button>
          </Tooltip>
        </div>
      </div>
    </section>
  )
})

function CalendarIcon() {
  return (
    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 3.5v3M17 3.5v3M4.5 8.5h15" />
      <rect x="4.5" y="5.5" width="15" height="14" rx="2.5" />
    </svg>
  )
}
