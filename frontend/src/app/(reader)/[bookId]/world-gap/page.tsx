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
    <div className={`min-h-screen ${isDark ? "bg-[#080808] text-slate-100" : "bg-[#f3eee6] text-stone-950"}`}>
      <div className="mx-auto max-w-[1600px] px-4 pb-12 pt-5 sm:px-6 lg:px-8">
        <div className={`rounded-[2rem] border px-5 py-5 shadow-[0_22px_70px_-55px_rgba(15,23,42,0.2)] ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white/80 bg-white/92"}`}>
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.32em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>World gap detection</p>
              <h1 className={`mt-2 font-serif text-4xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>Worldbuilding corpus vs. story manuscript</h1>
              <p className={`mt-3 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                Keep reference lore independent from the manuscript, compare them for contradictions, and turn the findings into a reusable cleanup backlog.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link href={`/${bookId}`} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                Overview
              </Link>
              <Link href={`/${bookId}/manuscript`} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                Manuscript Editor
              </Link>
              <Link href={`/${bookId}/advisor`} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                Story Advisor
              </Link>
            </div>
          </div>
        </div>
        <div className="mt-8">
          <WorldbuildingWorkspace bookId={bookId} isDark={isDark} focus="gap" />
        </div>
      </div>
    </div>
  )
}
