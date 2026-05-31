"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { asQueryKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { ForeshadowingItem } from "@/types/reader"

export default function ForeshadowingPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const { data, isLoading: loading } = useQuery({
    queryKey: asQueryKey(`reader:${bookId}:foreshadowing`),
    queryFn: () => readerApi.getForeshadowing(bookId),
  })
  const items: ForeshadowingItem[] = data?.items ?? []
  const error = !loading && !data ? "Foreshadowing unavailable" : null

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[radial-gradient(circle_at_top,#182033,#090b12_60%)] text-stone-100" : "bg-[linear-gradient(180deg,#fbfbfd,#f3f5f8)] text-slate-950"}`}>
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={() => router.back()} className={isDark ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white" : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"}>
            {"<- Back"}
          </button>
          <Link href="/library" className={isDark ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white" : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"}>
            Library
          </Link>
          <Link href="/" className={isDark ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white" : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"}>
            Home
          </Link>
        </div>

        <section className={`mt-6 overflow-hidden rounded-lg border p-8 shadow-[0_30px_120px_-60px_rgba(15,23,42,0.35)] ${isDark ? "border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(96,165,250,0.16),transparent_28%),linear-gradient(145deg,#121826,#0b0f18)]" : "border-white/70 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.12),transparent_26%),linear-gradient(145deg,#ffffff,#f5f7fb)]"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.34em] ${isDark ? "text-amber-200" : "text-indigo-700"}`}>Foreshadowing</p>
          <h1 className={`mt-3 font-serif text-5xl leading-tight ${isDark ? "text-white" : "text-slate-950"}`}>Signals, omens, and early tremors.</h1>
          <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
            This view pulls forward the hints already present in the chapters you have reached. It avoids unread material and now fills missing analysis on demand when the background worker has not caught up yet.
          </p>
        </section>

        {error ? <div className={`mt-6 rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>{error}</div> : null}

        {loading ? (
          <div className={`mt-8 rounded-lg border px-6 py-10 text-center text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-stone-400" : "border-slate-200 bg-white text-slate-500"}`}>
            Pulling together the strongest hints from your available chapters...
          </div>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <div className={`mt-8 rounded-lg border px-6 py-10 ${isDark ? "border-white/10 bg-white/[0.03] text-stone-300" : "border-slate-200 bg-white text-slate-700"}`}>
            <p className="text-lg font-semibold">No foreshadowing highlights yet.</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-stone-400" : "text-slate-500"}`}>
              LoreVia will show them here as soon as it finds clear clue patterns in the chapters you have already read.
            </p>
          </div>
        ) : null}

        <div className="mt-8 grid gap-4">
          {items.map((item, index) => (
            <article key={`${item.chapter_number}-${index}`} className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-200 bg-white shadow-card"}`}>
              <div className="flex flex-wrap items-center gap-3">
                <span className={isDark ? "rounded-full bg-amber-300/10 px-3 py-1 text-3xs font-semibold uppercase tracking-[0.22em] text-amber-100" : "rounded-full bg-amber-100 px-3 py-1 text-3xs font-semibold uppercase tracking-[0.22em] text-amber-800"}>
                  Chapter {item.chapter_number}
                </span>
                {item.chapter_title ? <span className={isDark ? "text-xs text-stone-400" : "text-xs text-slate-500"}>{item.chapter_title}</span> : null}
              </div>
              <p className={`mt-4 text-lg font-semibold leading-8 ${isDark ? "text-white" : "text-slate-950"}`}>{item.clue}</p>
              {item.foreshadows ? (
                <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>{item.foreshadows}</p>
              ) : (
                <p className={`mt-3 text-sm italic ${isDark ? "text-stone-500" : "text-slate-400"}`}>LoreVia found a notable clue here, but the follow-through description is still sparse.</p>
              )}
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
