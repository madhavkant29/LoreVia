"use client"

import { usePreferencesStore } from "@/lib/stores/preferencesStore"

interface Props {
  recall: string
  lastChapter: number
  onDismiss: () => void
  onContinue: () => void
}

export function RecallCard({ recall, lastChapter, onDismiss, onContinue }: Props) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <section
      className={`relative overflow-hidden rounded-[2rem] border p-6 shadow-[0_26px_100px_-55px_rgba(15,23,42,0.45)] ${
        isDark
          ? "border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.18),transparent_24%),radial-gradient(circle_at_88%_12%,rgba(96,165,250,0.16),transparent_28%),linear-gradient(145deg,rgba(30,41,59,0.98),rgba(15,23,42,0.96)_55%,rgba(8,47,73,0.92))] text-white"
          : "border-indigo-100 bg-[linear-gradient(145deg,#eef2ff,#ffffff_55%,#ecfeff)] text-stone-900"
      }`}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.12),transparent_24%)]" />
      <div className="relative">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-200" : "text-indigo-600"}`}>
              Previously On
            </p>
            <p className={`mt-2 text-sm ${isDark ? "text-slate-200" : "text-stone-500"}`}>
              Resume with a clean recap through chapter {lastChapter}.
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

        <p className={`mt-5 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-100" : "text-stone-700"}`}>{recall}</p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={onContinue}
            className={`rounded-full px-5 py-3 text-sm font-semibold transition ${
              isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-950 text-white hover:bg-stone-800"
            }`}
          >
            Continue Reading
          </button>
          <div className={`rounded-full px-4 py-3 text-xs font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-500 shadow-sm"}`}>
            Last active chapter: {lastChapter}
          </div>
        </div>
      </div>
    </section>
  )
}
