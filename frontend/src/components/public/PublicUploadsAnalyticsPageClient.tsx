"use client"

import Link from "next/link"
import type { Route } from "next"

import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicUploadsOverview } from "@/types/public"

function formatNumber(value: number) {
  return value.toLocaleString()
}

function formatCompactDate(value?: string | null) {
  if (!value) return "Date unavailable"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Date unavailable"
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function AnalyticsCard({ label, value, note, isDark }: { label: string; value: string; note: string; isDark: boolean }) {
  return (
    <article className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{note}</p>
    </article>
  )
}

export function PublicUploadsAnalyticsPageClient({ overview }: { overview: PublicUploadsOverview }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <main className={`min-h-screen ${isDark ? "bg-[#071211] text-white" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-3xl">
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Public upload analytics</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight">See how creator-published books are surfacing across LoreVia.</h1>
            <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              These metrics are derived from visible public uploads and open public discussions. They do not include private workspace traffic.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/public/uploads" className={`rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}>
              Browse creator uploads
            </Link>
            <Link href="/public" className={`rounded-md border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}>
              Open mixed library
            </Link>
          </div>
        </div>

        <section className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <AnalyticsCard isDark={isDark} label="Books" value={formatNumber(overview.total_public_books)} note="Visible creator-published books." />
          <AnalyticsCard isDark={isDark} label="Authors" value={formatNumber(overview.total_authors)} note="Distinct authors with public uploads." />
          <AnalyticsCard isDark={isDark} label="Chapters" value={formatNumber(overview.total_visible_chapters)} note="Visible chapters in the public catalog." />
          <AnalyticsCard isDark={isDark} label="Words" value={formatNumber(overview.total_visible_words)} note="Estimated visible reading volume." />
          <AnalyticsCard isDark={isDark} label="Last 30 Days" value={formatNumber(overview.uploads_last_30_days)} note="Recently published creator uploads." />
        </section>

        <section className="mt-10 grid gap-6 lg:grid-cols-2">
          <article className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
            <h2 className="text-2xl font-semibold">Genre breakdown</h2>
            <div className="mt-6 space-y-3">
              {overview.genre_breakdown.length > 0 ? overview.genre_breakdown.map((entry) => (
                <div key={entry.key} className="flex items-center justify-between gap-4">
                  <span className={isDark ? "text-slate-300" : "text-stone-700"}>{entry.label}</span>
                  <span className={`rounded-full px-3 py-1 text-sm font-semibold ${isDark ? "bg-white/10 text-white" : "bg-stone-100 text-stone-900"}`}>{entry.count}</span>
                </div>
              )) : (
                <p className={`text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>Genre metrics will appear after creator-published books become visible.</p>
              )}
            </div>
          </article>

          <article className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
            <h2 className="text-2xl font-semibold">Work type breakdown</h2>
            <div className="mt-6 space-y-3">
              {overview.work_type_breakdown.length > 0 ? overview.work_type_breakdown.map((entry) => (
                <div key={entry.key} className="flex items-center justify-between gap-4">
                  <span className={isDark ? "text-slate-300" : "text-stone-700"}>{entry.label}</span>
                  <span className={`rounded-full px-3 py-1 text-sm font-semibold ${isDark ? "bg-white/10 text-white" : "bg-stone-100 text-stone-900"}`}>{entry.count}</span>
                </div>
              )) : (
                <p className={`text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>Work type metrics will appear after creator-published books become visible.</p>
              )}
            </div>
          </article>
        </section>

        <section className={`mt-10 rounded-lg border p-6 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl font-semibold">Recent uploads</h2>
            <Link href="/public/uploads" className={`text-sm font-semibold ${isDark ? "text-teal-200 hover:text-white" : "text-teal-700 hover:text-teal-900"}`}>
              Open creator catalog
            </Link>
          </div>
          {overview.recent_uploads.length > 0 ? (
            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {overview.recent_uploads.map((book) => (
              <Link
                key={book.id}
                href={`/public/${book.public_slug || book.id}` as Route}
                className={`rounded-md border p-4 transition ${isDark ? "border-white/10 bg-black/20 hover:bg-white/[0.04]" : "border-stone-200 bg-stone-50 hover:bg-stone-100"}`}
              >
                <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                  {book.genre || "Unspecified genre"}
                </p>
                <h3 className="mt-3 text-lg font-semibold">{book.title}</h3>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  {book.author_username ? `@${book.author_username}` : book.author || "Unknown author"}
                </p>
                <p className={`mt-3 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  {book.total_chapters ?? 0} chapters
                  {" - "}
                  {formatCompactDate(book.published_at)}
                </p>
              </Link>
              ))}
            </div>
          ) : (
            <p className={`mt-6 rounded-md border border-dashed px-4 py-5 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-600"}`}>
              Recent creator uploads will appear here after publishing review is complete.
            </p>
          )}
        </section>
      </div>
    </main>
  )
}
