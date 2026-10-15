"use client"

import { ChapterRow } from "@/components/reader/ChapterRow"
import type { ChapterListItem, SummaryCollectionItem } from "@/types/reader"

type ChapterListProps = {
  chapters: ChapterListItem[]
  summaries?: SummaryCollectionItem[]
  unitLabel: string
  isDark: boolean
  readBusyKey: string | null
  deleteBusyKey?: string | null
  onOpenChapter: (chapterNumber: number) => void
  onToggleChapterRead: (chapterNumber: number, nextRead: boolean) => void
  onDeleteChapter?: (chapterNumber: number) => void
  canDeleteChapter?: (chapterNumber: number) => boolean
}

export function ChapterList({
  chapters,
  summaries = [],
  unitLabel,
  isDark,
  readBusyKey,
  deleteBusyKey = null,
  onOpenChapter,
  onToggleChapterRead,
  onDeleteChapter,
  canDeleteChapter,
}: ChapterListProps) {
  return (
    <section aria-labelledby="chapters-section-heading">
      <div className="flex items-center justify-between gap-3">
        <h2
          id="chapters-section-heading"
          className="sr-only"
        >
          {unitLabel}s
        </h2>
      </div>

      <div className={`mt-3 border-y ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        {chapters.map((chapter) => (
          <ChapterRow
            key={chapter.number}
            chapter={chapter}
            summary={summaries.find((summary) => summary.chapter_number === chapter.number) ?? null}
            unitLabel={unitLabel}
            isDark={isDark}
            actionsDisabled={readBusyKey !== null || deleteBusyKey !== null}
            readBusy={readBusyKey === `chapter:${chapter.number}`}
            deleteBusy={deleteBusyKey === `chapter:${chapter.number}`}
            onOpen={() => onOpenChapter(chapter.number)}
            onToggleRead={() => onToggleChapterRead(chapter.number, !chapter.read)}
            onDelete={onDeleteChapter && (!canDeleteChapter || canDeleteChapter(chapter.number)) ? () => onDeleteChapter(chapter.number) : undefined}
          />
        ))}
      </div>
    </section>
  )
}
