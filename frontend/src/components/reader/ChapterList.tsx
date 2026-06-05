"use client"

import { ChapterRow } from "@/components/reader/ChapterRow"
import type { ChapterListItem } from "@/types/reader"

type ChapterListProps = {
  chapters: ChapterListItem[]
  unitLabel: string
  isDark: boolean
  readBusyKey: string | null
  deleteBusyKey?: string | null
  onOpenChapter: (chapterNumber: number) => void
  onToggleChapterRead: (chapterNumber: number, nextRead: boolean) => void
  onDeleteChapter?: (chapterNumber: number) => void
}

export function ChapterList({
  chapters,
  unitLabel,
  isDark,
  readBusyKey,
  deleteBusyKey = null,
  onOpenChapter,
  onToggleChapterRead,
  onDeleteChapter,
}: ChapterListProps) {
  return (
    <section aria-labelledby="chapters-section-heading" className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2
          id="chapters-section-heading"
          className={`text-3xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-slate-500" : "text-stone-500"}`}
        >
          Chapters
        </h2>
      </div>

      <div className={`space-y-3 rounded-lg border p-3 sm:p-4 ${isDark ? "border-white/10 bg-[#091018]/58" : "border-stone-200 bg-white/78"}`}>
        {chapters.map((chapter) => (
          <ChapterRow
            key={chapter.number}
            chapter={chapter}
            unitLabel={unitLabel}
            isDark={isDark}
            readBusy={readBusyKey === `chapter:${chapter.number}`}
            deleteBusy={deleteBusyKey === `chapter:${chapter.number}`}
            onOpen={() => onOpenChapter(chapter.number)}
            onToggleRead={() => onToggleChapterRead(chapter.number, !chapter.read)}
            onDelete={onDeleteChapter ? () => onDeleteChapter(chapter.number) : undefined}
          />
        ))}
      </div>
    </section>
  )
}
