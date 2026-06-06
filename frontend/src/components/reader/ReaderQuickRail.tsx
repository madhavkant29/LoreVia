"use client"
import { memo } from "react"
import type { Route } from "next"
import Link from "next/link"

type ReaderQuickRailProps = {
  bookId: string
  chapterNum: number
  theme: "light" | "dark"
  onSummary: () => void
}

const actions = [
  {
    key: "overview",
    label: "Overview",
    shortLabel: "Book",
    href: (bookId: string) => `/${bookId}` as Route,
    icon: (
      <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M3.75 5.5a2 2 0 0 1 2-2h10.5v12.25H5.75a2 2 0 0 0-2 2V5.5Z" />
        <path d="M5.75 3.5v12.25a2 2 0 0 1 2-2h8.5" />
      </svg>
    ),
  },
  {
    key: "graph",
    label: "Graph",
    shortLabel: "Graph",
    href: (bookId: string) => `/${bookId}/graph` as Route,
    icon: (
      <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="4.5" cy="10.5" r="1.4" />
        <circle cx="10" cy="5" r="1.4" />
        <circle cx="15.5" cy="12.5" r="1.4" />
        <path d="M5.7 9.7 8.8 6.2m2.3-.2 3.2 5.4" />
      </svg>
    ),
  },
  {
    key: "ask",
    label: "Ask with citations",
    shortLabel: "Ask",
    href: (bookId: string) => `/${bookId}/ask` as Route,
    icon: (
      <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M5.25 7.5a4.75 4.75 0 1 1 7.8 3.64L14 15.5l-3.4-2.1A4.75 4.75 0 0 1 5.25 7.5Z" />
      </svg>
    ),
  },
  {
    key: "search",
    label: "Search passages",
    shortLabel: "Search",
    href: (bookId: string) => `/${bookId}/search` as Route,
    icon: (
      <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="8.5" cy="8.5" r="4.5" />
        <path d="m12 12 4 4" />
      </svg>
    ),
  },
] as const

export const ReaderQuickRail = memo(function ReaderQuickRail({ bookId, chapterNum, theme, onSummary }: ReaderQuickRailProps) {
  const shellClass = theme === "dark"
    ? "border-white/10 bg-[#0d1422]/72 text-slate-300"
    : "border-stone-200/80 bg-white/80 text-stone-600"
  const buttonClass = theme === "dark"
    ? "border-white/10 bg-white/[0.02] hover:border-[#8c93ff]/30 hover:bg-white/[0.05] hover:text-white focus-visible:outline-teal-200"
    : "border-stone-200 bg-white hover:border-violet-300 hover:text-stone-950 focus-visible:outline-violet-500"

  return (
    <aside className="reader-nonprint hidden xl:block">
      <div className="sticky top-28">
        <div className={`flex flex-col gap-3 rounded-lg border p-3 ${shellClass}`}>
          {actions.map((action) => (
            <Link
              key={action.key}
              prefetch={false}
              href={action.href(bookId)}
              aria-label={action.label}
              className={`flex h-10 w-10 items-center justify-center rounded-md border transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${buttonClass}`}
              title={action.label}
            >
              {action.icon}
            </Link>
          ))}
          <button
            type="button"
            aria-label="Open summary"
            onClick={onSummary}
            className={`flex h-10 w-10 items-center justify-center rounded-md border transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${buttonClass}`}
            title="Summary"
          >
            <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M5 5.5h10M5 10h10M5 14.5h6.5" />
            </svg>
          </button>
          <div className={`mt-1 border-t pt-3 text-center text-3xs uppercase tracking-[0.24em] ${theme === "dark" ? "border-white/10 text-slate-500" : "border-stone-200 text-stone-400"}`}>
            Chapter {chapterNum}
          </div>
        </div>
      </div>
    </aside>
  )
})
