"use client"

import { useEffect, useState } from "react"

import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { UserStats } from "@/types/book"

export default function StatsPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [stats, setStats] = useState<UserStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    booksApi.getStats().then(setStats).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className={`rounded-3xl border border-dashed py-20 text-center ${isDark ? "border-white/15 text-gray-500" : "border-stone-300 text-stone-400"}`}>Loading your stats...</div>
  }

  if (!stats) {
    return <div className={`rounded-3xl border border-dashed py-20 text-center ${isDark ? "border-white/15 text-gray-500" : "border-stone-300 text-stone-400"}`}>Stats unavailable.</div>
  }

  return (
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] ${
        isDark
          ? "border-white/10 bg-[linear-gradient(135deg,rgba(15,23,42,0.95),rgba(8,47,73,0.78)_55%,rgba(120,53,15,0.16))]"
          : "border-stone-200 bg-[linear-gradient(135deg,#f8fbff,white_55%,#fff8ef)]"
      }`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>User stats</p>
        <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-900"}`}>A split view of what you can show and what stays yours.</h1>
        <p className={`mt-3 max-w-3xl text-sm leading-6 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Public-facing reading milestones live in one section. Private usage and upload data live in the other.
        </p>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className={`rounded-[1.75rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-200" : "text-emerald-700"}`}>Public stats</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Reading milestones</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <StatCard label="Total books read" value={stats.public.total_books_read.toLocaleString()} note="Completed books" isDark={isDark} />
            <StatCard label="Total words read" value={stats.public.total_words_read.toLocaleString()} note="Completed plus in-progress reading" isDark={isDark} />
          </div>
        </div>

        <div className={`rounded-[1.75rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Private stats</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Usage and workspace load</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <StatCard label="Total uploads" value={stats.private.total_uploads.toLocaleString()} note="Includes hidden books" isDark={isDark} />
            <StatCard label="Token consumption" value={stats.private.total_token_consumption.toLocaleString()} note="Tracked AI token load" isDark={isDark} />
            <StatCard label="Chapters tracked" value={stats.private.total_chapters_tracked.toLocaleString()} note="Across your uploaded books" isDark={isDark} />
            <StatCard label="Saved quotes" value={stats.private.saved_quotes.toLocaleString()} note="Private highlights and notes" isDark={isDark} />
          </div>
        </div>
      </section>
    </div>
  )
}

function StatCard({ label, value, note, isDark }: { label: string; value: string; note: string; isDark: boolean }) {
  return (
    <div className={`rounded-3xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-gray-400" : "text-stone-500"}`}>{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>{note}</p>
    </div>
  )
}
