"use client"

import { useEffect } from "react"
import type { Route } from "next"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { AuthorFeatureComponent } from "@/components/billing/AuthorFeatureComponent"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"

type BookMode = "reader" | "author"

type AuthorToolsNavProps = {
  bookId: string
  active: string
  isDark: boolean
  title?: string
  description?: string
  currentChapter?: number
  mode?: BookMode
  variant?: "panel" | "rail"
}

type NavIcon =
  | "book"
  | "read"
  | "chapters"
  | "pen"
  | "plus"
  | "spark"
  | "chat"
  | "gap"
  | "users"
  | "links"
  | "threads"
  | "search"
  | "events"
  | "summary"
  | "analysis"
  | "notes"
  | "quote"
  | "files"

type NavItem = {
  id: string
  label: string
  href: Route
  tone: string
  icon: NavIcon
}

type NavSection = {
  title: string
  items: NavItem[]
  authorOnly?: boolean
}

const NAV_SECTIONS = (bookId: string, currentChapter = 1): NavSection[] => [
  {
    title: "Book",
    items: [
      { id: "overview", label: "Overview", href: `/${bookId}` as Route, tone: "Home", icon: "book" },
      { id: "read", label: "Read", href: `/${bookId}/chapter/${currentChapter}` as Route, tone: "Continue", icon: "read" },
      { id: "chapters", label: "Chapters", href: `/${bookId}/chapters` as Route, tone: "Switch", icon: "chapters" },
    ],
  },
  {
    title: "Writing",
    authorOnly: true,
    items: [
      { id: "manuscript", label: "Manuscript Editor", href: `/${bookId}/manuscript` as Route, tone: "Drafting", icon: "pen" },
      { id: "scenes", label: "Scene Workspace", href: `/${bookId}/scenes` as Route, tone: "File tree", icon: "files" },
      { id: "add-scene", label: "Add Scene", href: `/${bookId}/scenes` as Route, tone: "Create", icon: "plus" },
    ],
  },
  {
    title: "Intelligence",
    authorOnly: true,
    items: [
      { id: "advisor", label: "Story Advisor", href: `/${bookId}/advisor` as Route, tone: "Continuity", icon: "spark" },
      { id: "ask", label: "Ask LoreVia", href: `/${bookId}/ask` as Route, tone: "Questions", icon: "chat" },
      { id: "world-gap", label: "World Gap Detection", href: `/${bookId}/world-gap` as Route, tone: "Lore cleanup", icon: "gap" },
      { id: "characters", label: "Character Bible", href: `/${bookId}/characters` as Route, tone: "Profiles", icon: "users" },
      { id: "relationships", label: "Relationships", href: `/${bookId}/graph` as Route, tone: "Network", icon: "links" },
      { id: "plot-threads", label: "Plot Threads", href: `/${bookId}/plot-threads` as Route, tone: "Arc tracking", icon: "threads" },
    ],
  },
  {
    title: "Tools",
    items: [
      { id: "search", label: "Search Passages", href: `/${bookId}/search` as Route, tone: "Find", icon: "search" },
      { id: "timeline", label: "Major Events", href: `/${bookId}/timeline` as Route, tone: "Plot", icon: "events" },
      { id: "summaries", label: "Summary", href: `/${bookId}/summaries` as Route, tone: "Recap", icon: "summary" },
      { id: "quotes", label: "Saved Quotes", href: "/quotes" as Route, tone: "Highlights", icon: "quote" },
      { id: "analysis", label: "Analysis", href: `/${bookId}/analysis` as Route, tone: "Advanced", icon: "analysis" },
    ],
  },
  {
    title: "Workspace",
    authorOnly: true,
    items: [
      { id: "notes", label: "Notes", href: `/${bookId}/notes` as Route, tone: "Vault", icon: "notes" },
      { id: "export", label: "Import & Export", href: `/${bookId}/export` as Route, tone: "Files", icon: "files" },
    ],
  },
]

export function AuthorToolsNav({
  bookId,
  active,
  isDark,
  title = "Book workspace",
  description = "Navigation stays quiet until you need the deeper tools.",
  currentChapter = 1,
  mode = "author",
  variant = "panel",
}: AuthorToolsNavProps) {
  const router = useRouter()
  const tier = useAuthStore((state) => state.user?.tier)
  const showAuthorSections = mode === "author" && canUseAuthorFeatures(tier)
  const sections = NAV_SECTIONS(bookId, currentChapter).filter((section) => showAuthorSections || !section.authorOnly)
  const items = sections.flatMap((section) => section.items)

  useEffect(() => {
    for (const item of items) {
      router.prefetch(item.href)
    }
  }, [items, router])

  const rail = variant === "rail"
  const containerClass = rail
    ? `group/rail sticky top-24 z-20 flex h-[calc(100vh-7.5rem)] w-[4.75rem] flex-col overflow-hidden rounded-2xl border p-3 shadow-[0_24px_70px_-48px_rgba(0,0,0,0.75)] transition-[width,background-color,border-color] duration-300 hover:w-72 focus-within:w-72 ${
        isDark ? "border-white/10 bg-[#0d0f12]/90" : "border-stone-200 bg-white/90"
      }`
    : `rounded-2xl border p-4 ${isDark ? "border-white/10 bg-[#0d0f12]/90" : "border-stone-200 bg-white/92"}`
  const labelVisibility = rail ? "opacity-0 group-hover/rail:opacity-100 group-focus-within/rail:opacity-100" : "opacity-100"

  return (
    <aside className={containerClass}>
      <div className="flex items-center gap-3 px-1">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-200 bg-stone-50 text-stone-900"}`}>
          <NavSvg icon="book" />
        </div>
        <div className={`min-w-0 transition-opacity duration-200 ${labelVisibility}`}>
          <p className={`text-[10px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>LoreVia</p>
          <h2 className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
        </div>
      </div>

      <p className={`mt-3 line-clamp-2 px-1 text-xs leading-5 transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-500" : "text-stone-500"}`}>
        {description}
      </p>

      <div className={`mt-4 space-y-4 ${rail ? "min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1" : ""}`}>
        {sections.map((section) => {
          const sectionMarkup = (
          <div>
            <p className={`mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.24em] transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-600" : "text-stone-400"}`}>
              {section.title}
            </p>
            <div className="space-y-1">
              {section.items.map((item) => {
                const selected = item.id === active
                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    title={item.label}
                    className={`flex h-11 items-center gap-3 rounded-xl px-2 text-sm transition ${
                      selected
                        ? isDark
                          ? "bg-white text-stone-950"
                          : "bg-stone-950 text-white"
                        : isDark
                          ? "text-slate-300 hover:bg-white/8 hover:text-white"
                          : "text-stone-600 hover:bg-stone-100 hover:text-stone-950"
                    }`}
                  >
                    <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${selected ? "bg-transparent" : isDark ? "bg-white/[0.04]" : "bg-white"}`}>
                      <NavSvg icon={item.icon} />
                    </span>
                    <span className={`min-w-0 transition-opacity duration-200 ${labelVisibility}`}>
                      <span className="block truncate font-semibold">{item.label}</span>
                      <span className={`block truncate text-[10px] uppercase tracking-[0.18em] ${selected ? (isDark ? "text-stone-700" : "text-white/70") : (isDark ? "text-slate-600" : "text-stone-400")}`}>
                        {item.tone}
                      </span>
                    </span>
                  </Link>
                )
              })}
            </div>
          </div>
          )
          return section.authorOnly ? (
            <AuthorFeatureComponent key={section.title} locked={null}>
              {sectionMarkup}
            </AuthorFeatureComponent>
          ) : (
            <div key={section.title}>{sectionMarkup}</div>
          )
        })}
      </div>
    </aside>
  )
}

function NavSvg({ icon }: { icon: NavIcon }) {
  const common = "h-4 w-4"
  switch (icon) {
    case "read":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M5 5.5h7A4 4 0 0116 9.5v9.25a4 4 0 00-4-4H5V5.5z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19 5.5h-3a4 4 0 00-4 4" /></svg>
    case "chapters":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h10M7 8h10M6 12h12M6 16h12M8 20h8" /></svg>
    case "pen":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20h4l11-11a2.6 2.6 0 10-4-4L4 16v4z" /></svg>
    case "plus":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
    case "spark":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM18 16l.8 2.2L21 19l-2.2.8L18 22l-.8-2.2L15 19l2.2-.8L18 16z" /></svg>
    case "chat":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M5 6.5A3.5 3.5 0 018.5 3h7A3.5 3.5 0 0119 6.5v4A3.5 3.5 0 0115.5 14H11l-5 5v-5.5A3.5 3.5 0 015 10V6.5z" /><path strokeLinecap="round" strokeLinejoin="round" d="M9 8h6M9 11h4" /></svg>
    case "gap":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h7M13 7h7M4 17h7M13 17h7M11 7l2 10" /></svg>
    case "users":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 100-6 3 3 0 000 6zM4 19a5 5 0 0110 0M17 11a2.5 2.5 0 100-5M15.5 15.5A4.5 4.5 0 0120 20" /></svg>
    case "links":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M10 7H7a5 5 0 000 10h3M14 7h3a5 5 0 010 10h-3M8.5 12h7" /></svg>
    case "threads":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M6 6h4a4 4 0 014 4v4a4 4 0 004 4h1" /><path strokeLinecap="round" strokeLinejoin="round" d="M6 18h4a4 4 0 004-4v-4a4 4 0 014-4h1M4 6h2M4 18h2M19 6h1M19 18h1" /></svg>
    case "search":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
    case "events":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M6 5v14M18 5v14M6 8h12M6 16h12M9 11h6" /></svg>
    case "summary":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M7 5h10M7 9h10M7 13h6M7 17h8" /></svg>
    case "analysis":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8" /><path strokeLinecap="round" strokeLinejoin="round" d="M4 19h17" /></svg>
    case "notes":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 4v4h4M9 13h6M9 16h4" /></svg>
    case "quote":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 9H6v4h3v5l-4-3V9a3 3 0 013-3h1v3zM18 9h-3v4h3v5l-4-3V9a3 3 0 013-3h1v3z" /></svg>
    case "files":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h6l2 2h8v9a2 2 0 01-2 2H6a2 2 0 01-2-2V7z" /><path strokeLinecap="round" strokeLinejoin="round" d="M12 13h5M14.5 10.5L17 13l-2.5 2.5" /></svg>
    case "book":
    default:
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M6 4h9a3 3 0 013 3v13H8a2 2 0 01-2-2V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M8 18h10M9 8h5" /></svg>
  }
}
