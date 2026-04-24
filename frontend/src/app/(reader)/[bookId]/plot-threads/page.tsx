"use client"

import Link from "next/link"
import { useEffect } from "react"
import { useParams } from "next/navigation"

import { PlotTracker } from "@/components/intelligence/PlotTracker"
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
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.3em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Author dashboard</p>
            <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>Plot Thread Dashboard</h1>
            <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              See every tracked thread across the manuscript, check what is still unresolved, and leave private reminders for future arcs.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href={`/${bookId}`} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>Overview</Link>
            <Link href={`/${bookId}/manuscript`} className="rounded-full bg-[linear-gradient(135deg,#115e59,#0f766e)] px-4 py-2 text-sm font-semibold text-white">Manuscript</Link>
          </div>
        </div>

        <div className={`mt-8 rounded-[1.8rem] border p-5 sm:p-6 ${isDark ? "border-white/10 bg-black/70" : "border-stone-200 bg-white/90"}`}>
          <PlotTracker bookId={bookId} mode="dashboard" />
        </div>
      </div>
    </div>
  )
}
