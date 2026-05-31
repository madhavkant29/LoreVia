"use client"

import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import Link from "next/link"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"

const ANALYSIS_TOOLS_BASE = [
  {
    href: "voice",
    eyebrow: "Dialogue drift",
    title: "Voice consistency",
    description: "Run dedicated character voice checks and save the findings back into notes or scenes.",
  },
  {
    href: "foreshadowing",
    eyebrow: "Signals and hints",
    title: "Foreshadowing",
    description: "Surface early clues, planted details, and the small lines that carry later weight.",
  },
  {
    href: "timeline",
    eyebrow: "Story structure",
    title: "Arc timeline",
    description: "Follow the chapter-axis view of characters, thread movement, and relationship turns.",
  },
  {
    href: "plot-threads",
    eyebrow: "Open arcs and notes",
    title: "Plot threads",
    description: "See unresolved strands, private notes, and what is still hanging in the manuscript.",
  },
  {
    href: "reports",
    eyebrow: "Chapter-by-chapter checks",
    title: "Chapter Analysis",
    description: "Track characters, relationships, plot threads, and continuity across each chapter.",
  },
  {
    href: "series-ask",
    eyebrow: "Series intelligence",
    title: "Series ask",
    description: "Ask about characters, continuity, or plot threads across all books in your series.",
  },
  {
    href: "relationship-evolution",
    eyebrow: "Shifts over time",
    title: "Relationship evolution",
    description: "Track how pair dynamics change, where the turn happened, and what event caused it.",
  },
  {
    href: "world-gap",
    eyebrow: "World consistency",
    title: "World gap detection",
    description: "Compare the story manuscript against the separate worldbuilding corpus and save inconsistencies as notes.",
  },
]

export default function AnalysisPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: book = null } = useQuery<Book>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
    staleTime: 20_000,
  })

  const analysisTools = ANALYSIS_TOOLS_BASE.map((tool) => {
    if (tool.href === "series-ask" && book?.primary_series_id) {
      return { ...tool, href: `/series/${book.primary_series_id}/ask` }
    }
    if (tool.href === "series-ask") {
      return {
        ...tool,
        href: `/${bookId}/ask`,
        eyebrow: "Book intelligence",
        title: "Ask LoreVia",
        description: "This book is not attached to a series yet. Ask about this book directly instead.",
      }
    }
    return tool
  })

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#0a0a0a] text-slate-100" : "bg-[#f5efe6] text-stone-950"}`}>
      <div className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6 lg:px-8">
        <div className={`rounded-lg border px-6 py-7 shadow-card ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white/70 bg-white/88"}`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className={`text-3xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Analysis</p>
              <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>Keep the deep tools in one place.</h1>
              <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                The reading flow stays centered on the book. These extra analysis surfaces are still here when you want to zoom out and inspect structure, clues, or cross-book signals.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href={`/${bookId}`} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                Overview
              </Link>
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {analysisTools.map((tool: typeof ANALYSIS_TOOLS_BASE[0]) => (
            <Link
              key={tool.href}
              href={tool.href.startsWith("/") ? tool.href as Route : `/${bookId}/${tool.href}` as Route}
              className={`group rounded-lg border p-5 transition ${isDark ? "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]" : "border-stone-200 bg-white/90 hover:bg-white"}`}
            >
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{tool.eyebrow}</p>
              <p className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{tool.title}</p>
              <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{tool.description}</p>
              <p className={`mt-5 text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-800"}`}>Open</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
