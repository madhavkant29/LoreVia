import { formatIndex } from "@/lib/utils/chapterLabels"

import type { ManuscriptIndexFormat, ManuscriptChapterListItem } from "./manuscriptPage.helpers"

type ChapterRailItem = ManuscriptChapterListItem & {
  processed?: boolean | null
}

type ChapterRailStats = Record<number, { wordCount: number; sceneCount: number; readingTime: string }>

type ManuscriptChapterRailSectionProps = {
  chapterIndexFormat: ManuscriptIndexFormat
  chapterRowStats: ChapterRailStats
  chapterSearch: string
  deletingChapterNumber: number | null
  dirtyDrafts: number[]
  draftChapterNumber: number | null
  filteredChapterItems: ChapterRailItem[]
  isDark: boolean
  pendingReprocessChapters: ReadonlySet<number>
  reprocessingChapterNumber: number | null
  selectedChapter: number | null
  onChapterSearchChange: (value: string) => void
  onPrefetchChapter: (chapterNumber: number) => void
  onRemoveChapter: (chapterNumber: number) => void
  onReprocessChapter: (chapterNumber: number) => void
  onSelectChapter: (chapterNumber: number) => void
}

export function ManuscriptChapterRailSection({
  chapterIndexFormat,
  chapterRowStats,
  chapterSearch,
  deletingChapterNumber,
  dirtyDrafts,
  draftChapterNumber,
  filteredChapterItems,
  isDark,
  pendingReprocessChapters,
  reprocessingChapterNumber,
  selectedChapter,
  onChapterSearchChange,
  onPrefetchChapter,
  onRemoveChapter,
  onReprocessChapter,
  onSelectChapter,
}: ManuscriptChapterRailSectionProps) {
  return (
    <>
      <input
        type="text"
        value={chapterSearch}
        onChange={(event) => onChapterSearchChange(event.target.value)}
        aria-label="Search chapters"
        className={`mt-4 w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
      />
      <div className="mt-4">
        <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-stone-600"}`}>Chapters</p>
        <div className="mt-2 space-y-2">
          {filteredChapterItems.map((chapter) => {
            const active = selectedChapter === chapter.number || (selectedChapter === null && draftChapterNumber === chapter.number)
            const needsReprocess = pendingReprocessChapters.has(chapter.number)
            const rowStats = chapterRowStats[chapter.number] ?? { wordCount: 0, sceneCount: 0, readingTime: "0 min read" }
            const rowReadingTime = rowStats.readingTime
            const rowWordCount = rowStats.wordCount
            return (
              <div
                key={chapter.number}
                className={`rounded-sm border px-3 py-3 text-sm transition ${active ? isDark ? "border-teal-300 bg-teal-400/10 text-white" : "border-teal-300 bg-teal-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.035] text-slate-300 hover:border-white/15 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <button
                    type="button"
                    onMouseEnter={() => onPrefetchChapter(chapter.number)}
                    onFocus={() => onPrefetchChapter(chapter.number)}
                    onClick={() => onSelectChapter(chapter.number)}
                    className="min-w-0 flex-1 text-left focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">Chapter {formatIndex(chapter.number, chapterIndexFormat)}</p>
                      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${active ? "bg-teal-300" : chapter.processed ? "bg-emerald-400" : isDark ? "bg-slate-600" : "bg-stone-300"}`} />
                    </div>
                    <p className="mt-1 line-clamp-1 text-xs opacity-75">{chapter.title || `Chapter ${formatIndex(chapter.number, chapterIndexFormat)}`}</p>
                    {chapter.title_suggestion ? <p className="mt-1 line-clamp-1 text-3xs opacity-75">Suggested: {chapter.title_suggestion}</p> : null}
                    <p className={`text-3xs ${isDark ? "text-slate-300" : "text-stone-500"}`}>{rowStats.sceneCount} scene{rowStats.sceneCount === 1 ? "" : "s"} - {rowReadingTime}</p>
                    <p className={`mt-2 text-3xs ${needsReprocess ? isDark ? "text-amber-200" : "text-amber-700" : isDark ? "text-slate-300" : "text-stone-500"}`}>
                      {rowWordCount > 0 ? `${rowWordCount.toLocaleString()} words` : "Draft ready"} - {needsReprocess ? "Needs reprocess" : dirtyDrafts.includes(chapter.number) ? "needs review" : "saved"}
                    </p>
                  </button>
                  {needsReprocess ? (
                    <button
                      type="button"
                      disabled={reprocessingChapterNumber === chapter.number}
                      onClick={() => onReprocessChapter(chapter.number)}
                      className={`shrink-0 rounded-sm px-2.5 py-1 text-3xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-amber-400/40 disabled:cursor-wait disabled:opacity-60 ${isDark ? "bg-amber-400/10 text-amber-100 hover:bg-amber-400/20" : "bg-amber-50 text-amber-700 hover:bg-amber-100"}`}
                    >
                      {reprocessingChapterNumber === chapter.number ? "Starting" : "Reprocess"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    aria-label={`Remove Chapter ${chapter.number}`}
                    disabled={deletingChapterNumber === chapter.number}
                    onClick={() => onRemoveChapter(chapter.number)}
                    className={`shrink-0 rounded-none px-2.5 py-1 text-3xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-rose-400/40 disabled:cursor-wait disabled:opacity-60 ${isDark ? "bg-rose-500/10 text-rose-200 hover:bg-rose-500/20" : "bg-rose-50 text-rose-700 hover:bg-rose-100"}`}
                  >
                    {deletingChapterNumber === chapter.number ? "Removing" : "Remove"}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}
