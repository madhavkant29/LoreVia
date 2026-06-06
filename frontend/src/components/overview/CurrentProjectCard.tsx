"use client"

import { memo } from "react"
import { SmartBookCover } from "@/components/ui/SmartBookCover"
import type { Book } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

import { Icon } from "./Icon"
import { InfoRow } from "./InfoRow"
import { PanelTitle } from "./PanelTitle"
import type { IconName } from "./types"
import { clamp, formatDate, formatNumber, panelClass } from "./utils"

export const CurrentProjectCard = memo(function CurrentProjectCard({
  book,
  isDark,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  chapters,
  unitTitle,
  unitPrefix,
  onOpenManuscript,
}: {
  book: Book
  isDark: boolean
  canOpenManuscript: boolean
  currentWords: number | null
  targetWords: number
  percentComplete: number
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  unitPrefix: string
  onOpenManuscript: () => void
}) {
  const recentChapters = chapters.slice(-4).reverse()

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Current Project</PanelTitle>
      <div className="mt-4 grid gap-5 md:grid-cols-[9rem_minmax(0,1fr)_minmax(13rem,0.78fr)]">
        <SmartBookCover
          src={book.cover_url}
          title={book.title}
          isDark={isDark}
          className="aspect-[0.72] min-h-48 rounded-md"
        />

        <div className="min-w-0">
          <div className="flex items-start gap-2">
            <h2 className={`truncate text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h2>
            <Icon name="edit" className={isDark ? "mt-1 h-4 w-4 text-slate-500" : "mt-1 h-4 w-4 text-slate-400"} />
          </div>
          <p className="mt-2 text-sm font-semibold text-teal-800">{book.genre || (book.work_type === "screenplay" ? "Screenplay" : "Manuscript")}</p>

          <div className="mt-7">
            <div className={`flex items-end justify-between text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              <span>Manuscript Progress</span>
              <span>{formatNumber(currentWords)} / {targetWords.toLocaleString()} words</span>
            </div>
            <div className={`mt-2 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-slate-100"}`}>
              <div
                className="h-full rounded-full bg-teal-700"
                style={{ width: `${clamp(percentComplete || (currentWords ? (currentWords / targetWords) * 100 : 0), 0, 100)}%` }}
              />
            </div>
            <div className={`mt-1 text-right text-xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>{clamp(percentComplete, 0, 100)}%</div>
          </div>

          <div className={`mt-6 grid gap-3 border-t pt-4 text-sm ${isDark ? "border-white/10" : "border-slate-100"}`}>
            <InfoRow label="Status" value={book.status === "ready" ? "Drafting" : book.status.replace(/_/g, " ")} isDark={isDark} dot />
            <InfoRow label="Last Edited" value={formatDate(book.created_at)} isDark={isDark} />
          </div>
        </div>

        <div className="flex flex-col">
          <p className={`text-xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>Recent {unitTitle}s</p>
          <div className="mt-4 space-y-3">
            {recentChapters.length > 0 ? recentChapters.map((chapter) => (
              <div key={chapter.number} className="flex items-center justify-between gap-3 text-xs">
                <span className={`truncate ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  {unitPrefix} {chapter.number}. {chapter.title || `${unitTitle} ${chapter.number}`}
                </span>
                <span className={isDark ? "text-slate-600" : "text-slate-400"}>{chapter.read ? "Read" : "Open"}</span>
              </div>
            )) : (
              <p className={`text-sm leading-6 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{unitTitle} indexing is still syncing.</p>
            )}
          </div>

          {canOpenManuscript ? (
            <button
              type="button"
              onClick={onOpenManuscript}
              className={`mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-xs font-semibold transition ${isDark ? "bg-teal-800/10 text-teal-200 hover:bg-teal-800/18" : "bg-teal-50 text-teal-800 hover:bg-teal-100"}`}
            >
              Open Manuscript Editor
              <Icon name="chevron" className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>
    </section>
  )
})
