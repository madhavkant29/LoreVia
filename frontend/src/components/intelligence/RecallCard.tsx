"use client"

import { memo } from "react"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

interface Props {
  recall: string
  lastChapter: number | null
  onDismiss: () => void
  onContinue: () => void
}

export const RecallCard = memo(function RecallCard({ recall, lastChapter, onDismiss, onContinue }: Props) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const chapterLabel = typeof lastChapter === "number" && lastChapter > 0 ? `chapter ${lastChapter}` : "your latest chapter"

  return (
    <section
      className={`relative overflow-hidden rounded-lg border p-6 ${
        isDark
          ? "border-white/10 bg-[#0b1422] text-white"
          : "border-indigo-100 bg-white text-stone-900"
      }`}
    >
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex-1">
          <div className="flex items-start justify-between gap-4 lg:hidden">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-200" : "text-indigo-600"}`}>
                Story So Far
              </p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-200" : "text-stone-500"}`}>
                Resume with a grounded recap through {chapterLabel}.
              </p>
            </div>
            <button
              onClick={onDismiss}
              className={`rounded-full px-3 py-1 text-sm transition ${
                isDark ? "text-gray-400 hover:bg-white/10 hover:text-white" : "text-stone-400 hover:bg-white hover:text-stone-700"
              }`}
            >
              Dismiss
            </button>
          </div>

          <div className="hidden lg:block">
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-200" : "text-indigo-600"}`}>
              Story So Far
            </p>
            <p className={`mt-2 text-sm ${isDark ? "text-slate-200" : "text-stone-500"}`}>
              Resume with a grounded recap through {chapterLabel}.
            </p>
          </div>

          <p className={`mt-4 max-w-3xl text-sm leading-8 ${isDark ? "text-slate-100" : "text-stone-700"}`}>{recall}</p>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-4">
          <button
            onClick={onContinue}
            className={`rounded-full px-5 py-3 text-sm font-semibold transition ${
              "bg-[#1f615d] text-white hover:bg-teal-700"
            }`}
          >
            Continue Reading
          </button>
          <div className={`rounded-full px-4 py-3 text-xs font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-500 shadow-sm"}`}>
            Last active chapter: {lastChapter ?? "syncing"}
          </div>
          <button
            onClick={onDismiss}
            className={`hidden rounded-full px-3 py-1 text-sm transition lg:block ${
              isDark ? "text-gray-400 hover:bg-white/10 hover:text-white" : "text-stone-400 hover:bg-white hover:text-stone-700"
            }`}
          >
            Dismiss
          </button>
        </div>
      </div>
    </section>
  )
})
