"use client"

import Link from "next/link"
import { useParams } from "next/navigation"

import { WorldbuildingWorkspace } from "@/components/reader/WorldbuildingWorkspace"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function WorldGapPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#040912] text-slate-100" : "bg-[#f3eee6] text-stone-950"}`}>
      <div className="mx-auto max-w-[1480px] px-4 pb-10 pt-4 sm:px-6 lg:px-8">
        <div className={`rounded-[1.85rem] border px-5 py-5 shadow-[0_24px_70px_-56px_rgba(15,23,42,0.42)] ${isDark ? "border-white/10 bg-[#08111d]" : "border-white/80 bg-white/92"}`}>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.32em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>World gap detection</p>
              <h1 className={`mt-2 font-serif text-[2.25rem] leading-[1.1] sm:text-[2.55rem] ${isDark ? "text-white" : "text-stone-950"}`}>Worldbuilding corpus vs. story manuscript</h1>
              <p className={`mt-3 max-w-[46rem] text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                Keep reference lore independent from the manuscript. Compare your world corpus to the story manuscript to find gaps, inconsistencies, and opportunities.
              </p>
            </div>
            <div className={`inline-flex flex-wrap rounded-2xl border p-1 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
              <span className={`rounded-xl border px-3 py-2 text-xs font-medium ${isDark ? "border-teal-400/30 bg-teal-500/10 text-teal-100" : "border-teal-300 bg-teal-50 text-teal-800"}`}>
                Current
              </span>
              <Link href={`/${bookId}`} className={`rounded-xl px-4 py-2 text-sm ${isDark ? "text-slate-300 hover:bg-white/5" : "text-stone-700 hover:bg-white"}`}>
                Overview
              </Link>
              <Link href={`/${bookId}/manuscript`} className={`rounded-xl px-4 py-2 text-sm ${isDark ? "text-slate-300 hover:bg-white/5" : "text-stone-700 hover:bg-white"}`}>
                Manuscript Editor
              </Link>
              <Link href={`/${bookId}/advisor`} className={`rounded-xl px-4 py-2 text-sm ${isDark ? "text-slate-300 hover:bg-white/5" : "text-stone-700 hover:bg-white"}`}>
                Story Advisor
              </Link>
            </div>
          </div>
        </div>
        <div className="mt-6">
          <WorldbuildingWorkspace bookId={bookId} isDark={isDark} focus="gap" />
        </div>
      </div>
    </div>
  )
}
