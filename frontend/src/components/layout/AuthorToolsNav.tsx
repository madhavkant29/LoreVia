"use client"

import { useEffect } from "react"
import type { Route } from "next"
import Link from "next/link"
import { useRouter } from "next/navigation"

type AuthorToolsNavProps = {
  bookId: string
  active: string
  isDark: boolean
  title?: string
  description?: string
}

type NavItem = {
  id: string
  label: string
  href: Route
  tone: string
}

const NAV_ITEMS = (bookId: string): NavItem[] => [
  { id: "overview", label: "Overview", href: `/${bookId}` as Route, tone: "Core workspace" },
  { id: "manuscript", label: "Manuscript", href: `/${bookId}/manuscript` as Route, tone: "Drafting" },
  { id: "notes", label: "Notes workspace", href: `/${bookId}/notes` as Route, tone: "Vault notes" },
  { id: "export", label: "Import & Export", href: `/${bookId}/export` as Route, tone: "Files and vaults" },
  { id: "characters", label: "Characters", href: `/${bookId}/characters` as Route, tone: "Profiles" },
  { id: "advisor", label: "Story Advisor", href: `/${bookId}/advisor` as Route, tone: "Continuity" },
  { id: "timeline", label: "Timeline", href: `/${bookId}/timeline` as Route, tone: "Major events" },
  { id: "plot-threads", label: "Plot Threads", href: `/${bookId}/plot-threads` as Route, tone: "Arc tracking" },
  { id: "world-gap", label: "World Gap", href: `/${bookId}/world-gap` as Route, tone: "Lore cleanup" },
]

export function AuthorToolsNav({
  bookId,
  active,
  isDark,
  title = "Author tools",
  description = "Keep the full writing workflow visible from one left-side rail.",
}: AuthorToolsNavProps) {
  const router = useRouter()
  const items = NAV_ITEMS(bookId)

  useEffect(() => {
    for (const item of items) {
      router.prefetch(item.href)
    }
  }, [items, router])

  return (
    <aside className={`rounded-[1.7rem] border p-4 lg:sticky lg:top-6 ${isDark ? "border-white/10 bg-[#090f17]/90" : "border-stone-200 bg-white/92"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.3em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Author rail</p>
      <h2 className={`mt-3 font-serif text-2xl ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{description}</p>

      <div className="mt-5 space-y-2">
        {items.map((item) => {
          const selected = item.id === active
          return (
            <Link
              key={item.id}
              href={item.href}
              className={`block rounded-[1.1rem] border px-4 py-3 transition ${
                selected
                  ? isDark
                    ? "border-emerald-400/30 bg-emerald-500/10 shadow-[0_18px_40px_-30px_rgba(16,185,129,0.9)]"
                    : "border-emerald-200 bg-emerald-50"
                  : isDark
                    ? "border-white/8 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05]"
                    : "border-stone-200 bg-stone-50/80 hover:bg-stone-100"
              }`}
            >
              <p className={`text-sm font-semibold ${selected ? (isDark ? "text-white" : "text-stone-950") : (isDark ? "text-slate-200" : "text-stone-800")}`}>{item.label}</p>
              <p className={`mt-1 text-[11px] uppercase tracking-[0.2em] ${selected ? (isDark ? "text-emerald-200" : "text-emerald-700") : (isDark ? "text-slate-500" : "text-stone-400")}`}>{item.tone}</p>
            </Link>
          )
        })}
      </div>
    </aside>
  )
}
