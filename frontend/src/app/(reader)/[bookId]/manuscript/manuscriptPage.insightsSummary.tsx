import type { Route } from "next"
import Link from "next/link"

import type { ManuscriptSynopsis } from "@/types/intelligence"
import type { EditorialReviewPassage } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"

import type { buildManuscriptInspectorClasses } from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>

type ManuscriptInsightsSummaryPanelsProps = {
  bookId: string
  inspectorClasses: InspectorClasses
  isDark: boolean
  plotThreads: PlotThread[]
  reviewPassages: EditorialReviewPassage[]
  synopsis: ManuscriptSynopsis | null
  onJumpToChapter: (chapterNumber: number) => void
}

export function ManuscriptInsightsSummaryPanels({
  bookId,
  inspectorClasses,
  isDark,
  plotThreads,
  reviewPassages,
  synopsis,
  onJumpToChapter,
}: ManuscriptInsightsSummaryPanelsProps) {
  return (
    <>
      {synopsis ? (
        <div className={inspectorClasses.section}>
          <p className={inspectorClasses.label}>Synopsis generator</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{synopsis.synopsis}</p>
          {synopsis.focus_points.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {synopsis.focus_points.map((point) => (
                <span key={point} className={inspectorClasses.chip}>{point}</span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className={inspectorClasses.section}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className={inspectorClasses.label}>Character voice consistency</p>
            <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Voice checks moved into a dedicated workspace so notes and scene snapshots stay shared across the app.</p>
          </div>
          <Link href={`/${bookId}/voice` as Route} className={inspectorClasses.secondaryButton}>
            Open voice workspace
          </Link>
        </div>
      </div>

      <div className={inspectorClasses.section}>
        <div className="flex items-center justify-between gap-3">
          <p className={inspectorClasses.label}>Open threads</p>
          <Link href={`/${bookId}/plot-threads`} className={inspectorClasses.secondaryButton}>Dashboard</Link>
        </div>
        <div className="mt-3 space-y-2">
          {plotThreads.length > 0 ? plotThreads.map((thread) => (
            <div key={thread.id} className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
              <p className="font-semibold">{thread.title}</p>
              <p className="mt-1 text-xs opacity-75">Introduced in chapter {thread.introduced_at ?? "?"} · {thread.status}</p>
            </div>
          )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No unresolved threads loaded yet.</p>}
        </div>
      </div>

      {reviewPassages.length > 0 ? (
        <div className={inspectorClasses.section}>
          <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Cross-referenced passages</p>
          <div className="mt-3 space-y-2">
            {reviewPassages.map((passage, index) => (
              <button
                key={`${passage.chapter_num}-${index}`}
                onClick={() => onJumpToChapter(passage.chapter_num)}
                className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
              >
                <p className="font-semibold">Chapter {passage.chapter_num}{passage.chapter_title ? `: ${passage.chapter_title}` : ""}{typeof passage.chunk_index === "number" ? ` | chunk ${passage.chunk_index}` : ""}</p>
                <p className="mt-1 text-xs opacity-80">{passage.excerpt}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </>
  )
}
