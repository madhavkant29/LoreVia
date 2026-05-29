"use client"

import { usePreferencesStore } from "@/lib/stores/preferencesStore"

interface Props {
  recall: string
  lastChapter: number | null
  onDismiss: () => void
  onContinue: () => void
}

export function RecallCard({ recall, lastChapter, onDismiss, onContinue }: Props) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const chapterLabel = typeof lastChapter === "number" && lastChapter > 0 ? `chapter ${lastChapter}` : "your latest chapter"

  return (
    <section
      className={`relative overflow-hidden rounded-lg border p-6 shadow-[0_26px_100px_-55px_rgba(15,23,42,0.45)] ${
        isDark
          ? "border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(79,70,229,0.18),transparent_24%),radial-gradient(circle_at_88%_12%,rgba(96,165,250,0.16),transparent_28%),linear-gradient(145deg,rgba(10,20,38,0.98),rgba(9,18,34,0.96)_55%,rgba(11,35,68,0.92))] text-white"
          : "border-indigo-100 bg-[linear-gradient(145deg,#eef2ff,#ffffff_55%,#ecfeff)] text-stone-900"
      }`}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.12),transparent_24%)]" />
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
              isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-950 text-white hover:bg-stone-800"
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
}
