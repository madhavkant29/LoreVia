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

  const panelClass = isDark ? "border-white/[0.08] bg-[#1f2427]" : "border-stone-200 bg-white"
  const copyClass = isDark ? "text-[#f5f0e8]" : "text-stone-950"
  const mutedClass = isDark ? "text-[#9f9b94]" : "text-stone-500"
  const nextAssignment = items[0]
  const bodyText = isLoading
    ? "Loading beta reads..."
    : items.length === 0
      ? "No beta reads are assigned to you right now."
      : nextAssignment
        ? `${items.length === 1 ? "One review needs attention." : `${items.length} reviews need attention.`} ${
            betaReadIsUrgent(nextAssignment.expires_at)
              ? betaReadDeadlineLabel(nextAssignment.expires_at)
              : betaReadProgressLabel(nextAssignment)
          }`
        : "No beta reads are assigned to you right now."

  return (
    <section className={`rounded-[1.5rem] border p-6 ${panelClass}`}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-4">
          <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${isDark ? "bg-[#292f33] text-[#d9b88a]" : "bg-[#f7efe5] text-[#b86a1b]"}`}>
            <CalendarIcon />
          </div>
          <div>
            <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-[#d9b88a]" : "text-[#b86a1b]"}`}>Upcoming beta reads</p>
            <h2 className={`mt-2 font-display text-[2rem] tracking-[-0.03em] ${copyClass}`}>Complete reviews before the deadline.</h2>
            <p className={`mt-2 max-w-2xl text-sm leading-7 ${mutedClass}`}>{bodyText}</p>
            {nextAssignment ? (
              <p className={`mt-1 text-sm font-medium ${copyClass}`}>
                {nextAssignment.task_label} - {nextAssignment.author_name}
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {nextAssignment ? (
            <button
              type="button"
              onClick={() => void handlePrimaryAction(nextAssignment)}
              disabled={pendingId === nextAssignment.id}
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#1f615d] px-5 text-sm font-semibold text-white transition hover:bg-[#194f4c] disabled:opacity-60"
            >
              {pendingId === nextAssignment.id ? "Working..." : nextAssignment.primary_action}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => router.push("/beta-reads" as Route)}
            className={`inline-flex min-h-11 items-center justify-center rounded-xl border px-5 text-sm font-medium transition ${
              isDark ? "border-white/[0.08] bg-[#1f2427] text-[#ebe7df] hover:bg-[#252b2f]" : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
            }`}
          >
            View all beta reads
          </button>
        </div>
      </div>
    </section>
  )
}

function CalendarIcon() {
  return (
    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 3.5v3M17 3.5v3M4.5 8.5h15" />
      <rect x="4.5" y="5.5" width="15" height="14" rx="2.5" />
    </svg>
  )
}
