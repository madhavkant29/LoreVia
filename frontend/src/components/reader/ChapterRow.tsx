"use client"

import { ChapterStatusChip } from "@/components/reader/ChapterStatusChip"
import type { ChapterListItem } from "@/types/reader"

type ChapterRowProps = {
  chapter: ChapterListItem
  unitLabel: string
  isDark: boolean
  readBusy: boolean
  onOpen: () => void
  onToggleRead: () => void
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

export function ChapterRow({ chapter, unitLabel, isDark, readBusy, onOpen, onToggleRead }: ChapterRowProps) {
  const title = chapter.title || `${unitLabel} ${chapter.number}`
  const metadata = buildMetadata(chapter)

  return (
    <article
      style={{ contentVisibility: "auto", containIntrinsicSize: "180px" }}
      className={`group rounded-[1.35rem] border px-5 py-5 transition-colors focus-within:border-teal-300/30 ${
        isDark
          ? "border-white/10 bg-[#0b1118]/78 hover:border-white/15 hover:bg-[#0d141d]"
          : "border-stone-200 bg-white/92 hover:bg-white"
      }`}
    >
      <div className="flex flex-col gap-5 xl:grid xl:grid-cols-[minmax(0,1.15fr)_minmax(16rem,0.8fr)_auto] xl:items-center xl:gap-6">
        <div className="flex items-start gap-4">
          <div
            aria-hidden="true"
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-[1rem] border shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] ${
              isDark ? "border-white/10 bg-[linear-gradient(180deg,#131d28_0%,#101822_100%)] text-teal-200" : "border-stone-200 bg-stone-50 text-teal-700"
            }`}
          >
            <BookChapterIcon />
          </div>

          <div className="min-w-0">
            <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-sky-300/80" : "text-stone-500"}`}>
              {unitLabel} {chapter.number}
            </p>
            <h2 className={`mt-2 truncate font-serif text-[2rem] leading-none tracking-[-0.03em] ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
          </div>
        </div>

        <dl className={`grid gap-2 border-l pl-5 text-sm ${isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-600"}`}>
          {metadata.map((item) => (
            <div key={item.label} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <dt className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{item.label}</dt>
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
              className={`inline-flex min-w-[10.5rem] items-center justify-center rounded-[0.95rem] border px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/60 ${
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
              className={`inline-flex min-w-[12rem] items-center justify-center rounded-[0.95rem] border px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/60 disabled:cursor-not-allowed disabled:opacity-50 ${
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
          </div>
        </div>
      </div>
    </article>
  )
}

function BookChapterIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.75 6.25A2.25 2.25 0 0 1 7 4h5v15.25H7a2.25 2.25 0 0 0-2.25 2.25V6.25Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4h5a2.25 2.25 0 0 1 2.25 2.25V21.5A2.25 2.25 0 0 0 17 19.25h-5V4Z" />
    </svg>
  )
}
