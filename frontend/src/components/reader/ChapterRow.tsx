"use client"

import { memo } from "react"
import { chapterKindShortLabel } from "@/lib/utils/chapterLabels"
import type { ChapterListItem, SummaryCollectionItem } from "@/types/reader"

type ChapterRowProps = {
  chapter: ChapterListItem
  summary?: SummaryCollectionItem | null
  unitLabel: string
  isDark: boolean
  readBusy: boolean
  deleteBusy?: boolean
  actionsDisabled?: boolean
  onOpen: () => void
  onToggleRead: () => void
  onDelete?: () => void
}

function formatTagLabel(tag: string) {
  return tag
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

function buildMetadata(chapter: ChapterListItem) {
  const items = [
    { label: "Processing", value: chapter.analysis_included === false ? "Readable supplemental section" : chapter.processed ? "Processed" : "Queued" },
    { label: "Read status", value: chapter.read ? "Marked as read" : "Unread" },
    { label: "Intelligence", value: chapter.analysis_included === false ? "Excluded from story analysis" : chapter.intelligence_available === true ? "Indexed and ready" : chapter.intelligence_available === false ? "Not ready yet" : "Index status unavailable" },
  ]

  const tags = Array.from(new Set((chapter.tags ?? []).filter(Boolean))).slice(0, 3)
  if (tags.length > 0) {
    items.push({ label: "Tags", value: tags.map(formatTagLabel).join(" / ") })
  }

  return items
}

export const ChapterRow = memo(function ChapterRow({ chapter, summary = null, unitLabel, isDark, readBusy, deleteBusy = false, actionsDisabled = false, onOpen, onToggleRead, onDelete }: ChapterRowProps) {
  const kindLabel = chapter.printed_label || chapterKindShortLabel(chapter.chapter_kind, chapter.number, unitLabel === "Scene" ? "Sc." : "Ch.")
  const title = chapter.title || kindLabel
  const metadata = buildMetadata(chapter)
  const tags = metadata.find((item) => item.label === "Tags")?.value ?? null
  const status = metadata.filter((item) => item.label !== "Tags").map((item) => item.value).join(" · ")

  return (
    <article
      aria-labelledby={`chapter-title-${chapter.number}`}
      style={{ contentVisibility: "auto", containIntrinsicSize: "84px" }}
      className={`group border-b px-1 py-4 transition-colors last:border-b-0 ${
        isDark
          ? "border-white/[0.07] hover:bg-white/[0.025]"
          : "border-stone-200 hover:bg-stone-50"
      }`}
    >
      <div className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-3 sm:grid-cols-[4.5rem_minmax(0,1fr)] xl:grid-cols-[4.5rem_minmax(12rem,1fr)_minmax(13rem,0.8fr)_auto] xl:items-center sm:gap-x-5">
        <div className={`text-sm font-medium tabular-nums ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          {kindLabel}
        </div>
        <div className="min-w-0">
          <h3 id={`chapter-title-${chapter.number}`} className={`break-words text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h3>
          {tags ? <p className={`mt-1 break-words text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{tags}</p> : null}
        </div>

        <div className="col-start-2 min-w-0 xl:col-start-auto">
          <p className={`text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{status}</p>
        </div>

        <div className="col-start-2 flex flex-wrap items-center gap-2 xl:col-start-auto xl:justify-end">
          <button
            type="button"
            onClick={onOpen}
            aria-label={`Open ${unitLabel.toLowerCase()} ${chapter.number}: ${title}`}
            className="rounded-sm bg-teal-800 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/60"
          >
            Open
          </button>
          <button
            type="button"
            onClick={onToggleRead}
            disabled={actionsDisabled || readBusy || deleteBusy}
            className={`rounded-sm border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/60 disabled:cursor-not-allowed disabled:opacity-50 ${
              isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.05]" : "border-stone-200 text-stone-700 hover:bg-stone-100"
            }`}
          >
            {readBusy ? "Saving..." : chapter.read ? "Mark unread" : "Mark read"}
          </button>
          {onDelete ? (
            <button
              type="button"
              onClick={onDelete}
              disabled={actionsDisabled || readBusy || deleteBusy}
              className={`px-2 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/60 disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "text-slate-400 hover:text-rose-300" : "text-stone-600 hover:text-rose-700"}`}
            >
              {deleteBusy ? "Removing..." : "Remove"}
            </button>
          ) : null}
        </div>
      </div>
      {summary ? summary.available && summary.content ? (
        <details className={`mt-3 border-t pt-3 sm:ml-[5.75rem] ${isDark ? "border-white/[0.07]" : "border-stone-200"}`}>
          <summary className={`cursor-pointer text-sm font-semibold ${isDark ? "text-teal-300" : "text-teal-800"}`}>Read chapter recap</summary>
          <p className={`mt-3 max-w-4xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{summary.content}</p>
        </details>
      ) : (
        <p className={`mt-3 text-xs sm:ml-[5.75rem] ${isDark ? "text-slate-400" : "text-stone-600"}`}>{chapter.analysis_included === false ? "This section is readable but excluded from story analysis." : `${unitLabel} recap is not available yet.`}</p>
      ) : null}
    </article>
  )
})
