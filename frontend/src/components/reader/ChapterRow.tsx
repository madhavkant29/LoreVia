"use client"

import { memo } from "react"
import { ChapterStatusChip } from "@/components/reader/ChapterStatusChip"
import type { ChapterListItem } from "@/types/reader"

type ChapterRowProps = {
  chapter: ChapterListItem
  unitLabel: string
  isDark: boolean
  readBusy: boolean
  deleteBusy?: boolean
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
    { label: "Processing", value: chapter.processed ? "Processed" : "Queued" },
    { label: "Read status", value: chapter.read ? "Marked as read" : "Unread" },
    { label: "Intelligence", value: chapter.intelligence_available !== false ? "Indexed and ready" : "Not ready yet" },
  ]

  const tags = Array.from(new Set((chapter.tags ?? []).filter(Boolean))).slice(0, 3)
  if (tags.length > 0) {
    items.push({ label: "Tags", value: tags.map(formatTagLabel).join(" / ") })
  }

  return items
}

export const ChapterRow = memo(function ChapterRow({ chapter, unitLabel, isDark, readBusy, deleteBusy = false, onOpen, onToggleRead, onDelete }: ChapterRowProps) {
  const title = chapter.title || `${unitLabel} ${chapter.number}`
  const metadata = buildMetadata(chapter)

  return (
    <article
      style={{ contentVisibility: "auto", containIntrinsicSize: "180px" }}
      className={`group rounded-lg border px-5 py-5 transition-colors focus-within:border-teal-300/30 ${
        isDark
          ? "border-white/10 bg-[#0b1118]/78 hover:border-white/15 hover:bg-[#0d141d]"
          : "border-stone-200 bg-white/92 hover:bg-white"
      }`}
    >
      <div className="flex flex-col gap-5 xl:grid xl:grid-cols-[minmax(0,1.15fr)_minmax(16rem,0.8fr)_auto] xl:items-center xl:gap-6">
        <div className="flex items-start gap-4">
          <div
            aria-hidden="true"
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-md border ${
              isDark ? "border-white/10 bg-[#101822] text-teal-200" : "border-stone-200 bg-stone-50 text-teal-700"
            }`}
          >
            <BookChapterIcon />
          </div>

          <div className="min-w-0">
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-sky-300/80" : "text-stone-500"}`}>
              {unitLabel} {chapter.number}
            </p>
            <h2 className={`mt-2 truncate font-serif text-[2rem] leading-none tracking-[-0.03em] ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
          </div>
        </div>

        <dl className={`grid gap-2 border-l pl-5 text-sm ${isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-600"}`}>
          {metadata.map((item) => (
            <div key={item.label} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <dt className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>

        <div className="flex flex-col gap-3 xl:items-end">
          <div className="flex flex-wrap gap-2 xl:justify-end">
            <ChapterStatusChip label={chapter.processed ? "Processed" : "Queued"} tone={chapter.processed ? "processed" : "queued"} isDark={isDark} />
            <ChapterStatusChip label={chapter.read ? "Read" : "Unread"} tone={chapter.read ? "read" : "unread"} isDark={isDark} />
            <ChapterStatusChip
              label={chapter.intelligence_available !== false ? "Intel Ready" : "Intel Locked"}
              tone={chapter.intelligence_available !== false ? "intel-ready" : "intel-locked"}
              isDark={isDark}
            />
          </div>

          <div className="flex flex-wrap gap-2 xl:justify-end">
            <button
              type="button"
              onClick={onOpen}
              className={`inline-flex min-w-[10.5rem] items-center justify-center rounded-md border px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/60 ${
                isDark
                  ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]"
                  : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
              }`}
            >
              <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.75 12s3.75-6 9.25-6 9.25 6 9.25 6-3.75 6-9.25 6S2.75 12 2.75 12Z" />
                <circle cx="12" cy="12" r="2.5" />
              </svg>
              Open
            </button>
            <button
              type="button"
              onClick={onToggleRead}
              disabled={readBusy}
              className={`inline-flex min-w-[12rem] items-center justify-center rounded-md border px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/60 disabled:cursor-not-allowed disabled:opacity-50 ${
                chapter.read
                  ? isDark
                    ? "border-white/10 bg-transparent text-slate-300 hover:bg-white/[0.05]"
                    : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"
                  : isDark
                    ? "border-sky-400/20 bg-sky-400/12 text-sky-100 hover:bg-sky-400/18"
                    : "border-sky-200 bg-sky-50 text-sky-800 hover:bg-sky-100"
              }`}
            >
              <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 4.75h9.25A1.75 1.75 0 0 1 17 6.5v12.75l-5-3-5 3V6.5A1.75 1.75 0 0 1 8.75 4.75Z" />
              </svg>
              {readBusy ? "Saving..." : chapter.read ? "Mark unread" : "Mark read"}
            </button>
            {onDelete ? (
              <button
                type="button"
                onClick={onDelete}
                disabled={deleteBusy}
                className={`inline-flex min-w-[9.5rem] items-center justify-center rounded-md border px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/60 disabled:cursor-not-allowed disabled:opacity-50 ${
                  isDark
                    ? "border-rose-400/25 bg-rose-500/10 text-rose-100 hover:bg-rose-500/15"
                    : "border-rose-200 bg-rose-50 text-rose-800 hover:bg-rose-100"
                }`}
              >
                <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 7.25h10.5M10 10.25v6.25m4-6.25v6.25M8.25 7.25l.5 11.25A1.75 1.75 0 0 0 10.5 20h3A1.75 1.75 0 0 0 15.25 18.5l.5-11.25M10 7.25V5.5A1.5 1.5 0 0 1 11.5 4h1A1.5 1.5 0 0 1 14 5.5v1.75" />
                </svg>
                {deleteBusy ? "Removing..." : "Remove"}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  )
})

function BookChapterIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.75 6.25A2.25 2.25 0 0 1 7 4h5v15.25H7a2.25 2.25 0 0 0-2.25 2.25V6.25Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4h5a2.25 2.25 0 0 1 2.25 2.25V21.5A2.25 2.25 0 0 0 17 19.25h-5V4Z" />
    </svg>
  )
}
