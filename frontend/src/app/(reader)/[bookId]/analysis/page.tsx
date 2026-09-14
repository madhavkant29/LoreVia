"use client"

import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import Link from "next/link"
import { useParams } from "next/navigation"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"

const ANALYSIS_TOOLS_BASE = [
  {
    href: "ai-beta-reader",
    eyebrow: "Reader experience",
    title: "AI Beta Reader",
    description: "Find repeated words and phrases, compare character voices, and turn reader-style feedback into revision priorities.",
  },
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
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <div className="mx-auto max-w-6xl px-0 pb-16 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="analysis"
          bookId={bookId}
          family="review-center"
          title="Analysis workspace"
          description="Open deeper manuscript diagnostics when you need to inspect structure, clues, continuity, and cross-book signals."
          actions={(
            <Link href={`/${bookId}`} className="app-button-secondary">
              Overview
            </Link>
          )}
        />

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {analysisTools.map((tool: typeof ANALYSIS_TOOLS_BASE[0]) => (
            <Link
              key={tool.href}
              href={tool.href.startsWith("/") ? tool.href as Route : `/${bookId}/${tool.href}` as Route}
              className="app-panel app-panel--subtle group p-5 transition hover:border-[rgba(var(--accent),0.42)]"
            >
              <p className="app-eyebrow">{tool.eyebrow}</p>
              <p className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">{tool.title}</p>
              <p className="app-copy mt-3">{tool.description}</p>
              <p className="mt-5 text-sm font-semibold text-[rgb(var(--accent))]">Open tool</p>
            </Link>
          ))}
        </div>
      </div>
    </WorkspacePage>
  )
}
