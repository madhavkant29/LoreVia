"use client"

import React from "react"
import { useMemo, useState } from "react"
import type { Route } from "next"
import Link from "next/link"

import { AuthorFeatureComponent } from "@/components/billing/AuthorFeatureComponent"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import { Button } from "@/components/ui/Button"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { useCachedBookDetail } from "@/lib/hooks/useBookDetail"
import { useAuthStore } from "@/lib/stores/authStore"
import type { Book } from "@/types/book"
import type { CollaborationPermissions } from "@/types/book"

type BookMode = "reader" | "author"

type AuthorToolsNavProps = {
  bookId: string
  active: string
  isDark: boolean
  bookData?: Book | null
  title?: string
  description?: string
  currentChapter?: number
  mode?: BookMode
  variant?: "panel" | "rail"
  railSize?: "default" | "compact"
}

type NavIcon =
  | "book"
  | "read"
  | "chapters"
  | "pen"
  | "voice"
  | "spark"
  | "quill"
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
  | "plus"
  | "chevron-right"

type NavItem = {
  id: string
  label: string
  href: Route
  tone: string
  helper: string
  icon: NavIcon
}

type NavSection = {
  title: string
  items: NavItem[]
  authorOnly?: boolean
}

const READER_SHELL_ITEM_IDS = new Set(["overview", "read", "chapters", "summaries", "search", "timeline", "beta-feedback"])

function canSeeCollaboratorItem(itemId: string, permissions: CollaborationPermissions | null) {
  if (!permissions) return false
  switch (itemId) {
    case "manuscript":
    case "scenes":
      return permissions.can_edit_manuscript
    case "advisor":
    case "editorial-review":
    case "voice":
    case "ask":
    case "world-gap":
      return permissions.can_run_ai_scans
    case "characters":
    case "relationships":
    case "plot-threads":
      return permissions.can_view_story_bible
    case "notes":
    case "beta-feedback":
    case "author-loop":
      return permissions.can_comment || permissions.can_edit_manuscript
    case "export":
      return permissions.can_export
    case "collaboration":
      return false
    default:
      return true
  }
}

const NAV_SECTIONS = (bookId: string, currentChapter = 1): NavSection[] => [
  {
    title: "Story",
    items: [
      { id: "overview", label: "Overview", href: `/${bookId}` as Route, tone: "Home", helper: "See progress, next steps, and the latest signals around this book.", icon: "book" },
      { id: "read", label: "Preview Draft", href: `/${bookId}/chapter/${currentChapter}` as Route, tone: "Continue", helper: "Open the current draft in reading view and pick up where the story last left off.", icon: "read" },
      { id: "chapters", label: "Chapters", href: `/${bookId}/chapters` as Route, tone: "Switch", helper: "Jump across chapters and move through the manuscript without losing your place.", icon: "chapters" },
    ],
  },
  {
    title: "Writing",
    authorOnly: true,
    items: [
      { id: "manuscript", label: "Manuscript Editor", href: `/${bookId}/manuscript` as Route, tone: "Drafting", helper: "Write, revise, and shape the working manuscript with your drafting tools close by.", icon: "pen" },
      { id: "scenes", label: "Scene Workspace", href: `/${bookId}/scenes` as Route, tone: "File tree", helper: "Organize scenes, reorder structure, and manage the story at a scene-by-scene level.", icon: "files" },

    ],
  },
  {
    title: "Intelligence",
    authorOnly: true,
    items: [
      { id: "advisor", label: "Story Advisor", href: `/${bookId}/advisor` as Route, tone: "Continuity", helper: "Review continuity risks, unresolved threads, and high-priority story pressure points.", icon: "spark" },
      { id: "editorial-review", label: "Editorial Review", href: `/${bookId}/editorial-review` as Route, tone: "Line edit", helper: "Run an editorial pass that calls out clarity, pacing, and prose-level friction.", icon: "quill" },
      { id: "voice", label: "Voice Consistency", href: `/${bookId}/voice` as Route, tone: "Dialogue drift", helper: "Check whether character voice stays consistent across scenes and revisions.", icon: "voice" },
      { id: "ask", label: "Ask LoreVia", href: `/${bookId}/ask` as Route, tone: "Questions", helper: "Ask direct questions about the manuscript and get answers grounded in the current draft.", icon: "chat" },
      { id: "world-gap", label: "World Gap Detection", href: `/${bookId}/world-gap` as Route, tone: "Lore cleanup", helper: "Spot missing lore, weak canon links, and worldbuilding details that need support.", icon: "gap" },
      { id: "characters", label: "Character Bible", href: `/${bookId}/characters` as Route, tone: "Profiles", helper: "Track character profiles, arcs, and duplicate identity issues across the story.", icon: "users" },
      { id: "relationships", label: "Relationships", href: `/${bookId}/graph` as Route, tone: "Network", helper: "Map connections between characters so alliances, conflicts, and ties stay clear.", icon: "links" },
      { id: "plot-threads", label: "Plot Threads", href: `/${bookId}/plot-threads` as Route, tone: "Arc tracking", helper: "Follow open arcs and see which plot threads are moving, drifting, or unresolved.", icon: "threads" },
    ],
  },
  {
    title: "Story Tools",
    items: [
      { id: "search", label: "Search Passages", href: `/${bookId}/search` as Route, tone: "Find", helper: "Search the manuscript for names, lines, or moments without manually scanning chapters.", icon: "search" },
      { id: "timeline", label: "Major Events", href: `/${bookId}/timeline` as Route, tone: "Plot", helper: "Review key events in sequence so the story timeline stays easy to reason about.", icon: "events" },
      { id: "summaries", label: "Recaps", href: `/${bookId}/summaries` as Route, tone: "Recap", helper: "Read chapter and story recaps when you need context fast before editing.", icon: "summary" },
      { id: "beta-feedback", label: "Feedback", href: `/${bookId}/beta-feedback` as Route, tone: "Review", helper: "Leave chapter comments and open your assignment feedback without leaving the reading flow.", icon: "users" },
      { id: "quotes", label: "Saved Quotes", href: "/quotes" as Route, tone: "Highlights", helper: "Revisit memorable lines and collected excerpts pulled from this and other projects.", icon: "quote" },
      { id: "analysis", label: "Analysis", href: `/${bookId}/analysis` as Route, tone: "Advanced", helper: "Open deeper analysis views for broader manuscript diagnostics and story signals.", icon: "analysis" },
    ],
  },
  {
    title: "Workspace",
    authorOnly: true,
    items: [
      { id: "notes", label: "Notes", href: `/${bookId}/notes` as Route, tone: "Vault", helper: "Keep book-specific notes, reminders, and reference details beside the draft.", icon: "notes" },
      { id: "author-loop", label: "Author Lens", href: `/${bookId}/author-loop` as Route, tone: "Launch flow", helper: "Move through LoreVia's guided author workflow for revision and decision-making.", icon: "spark" },
      { id: "collaboration", label: "Collaborators", href: `/${bookId}/collaboration` as Route, tone: "Invite", helper: "Manage who can access the book and what each collaborator is allowed to do.", icon: "users" },
      { id: "export", label: "Import & Export", href: `/${bookId}/export` as Route, tone: "Files", helper: "Bring files in, send drafts out, and package the manuscript for other workflows.", icon: "files" },
    ],
  },
]

export function AuthorToolsNav({
  bookId,
  active,
  isDark,
  bookData = null,
  title = "Author workspace",
  description = "Move between drafting, review, and story memory without losing the thread.",
  currentChapter = 1,
  mode = "author",
  variant = "panel",
  railSize = "default",
}: AuthorToolsNavProps) {
  const tier = useAuthStore((state) => state.user?.tier)
  const { data: cachedBook = null } = useCachedBookDetail(bookId)
  const book = bookData ?? cachedBook
  const collaborationRole = book?.collaboration_role ?? null
  const collaborationPermissions = book?.collaboration_permissions ?? null
  const currentShell = book?.workspace_shell ?? mode
  const isOwnerSession = !collaborationRole
  const hasOwnAuthorAccess = canUseAuthorFeatures(tier)
  const hasFreeSampleIntelligenceAccess = tier === "free"
  const hasCollaboratorAccess = Boolean(collaborationRole && collaborationPermissions)
  const showAuthorSections = currentShell === "author" && (isOwnerSession || hasOwnAuthorAccess || hasCollaboratorAccess)

  const sections = useMemo(
    () =>
      NAV_SECTIONS(bookId, currentChapter)
        .filter((section) => {
          if (currentShell === "reader") {
            return !section.authorOnly
          }
          if (showAuthorSections || !section.authorOnly) {
            return true
          }
          return hasFreeSampleIntelligenceAccess && section.title === "Intelligence"
        })
        .map((section) => ({
          ...section,
          items: section.items.filter((item) => {
            if (currentShell === "reader") {
              return READER_SHELL_ITEM_IDS.has(item.id)
            }
            if (!showAuthorSections && hasFreeSampleIntelligenceAccess) {
              return item.id === "advisor" || item.id === "editorial-review"
            }
            if (isOwnerSession || hasOwnAuthorAccess || !collaborationRole) return true
            return canSeeCollaboratorItem(item.id, collaborationPermissions)
          }),
        }))
        .filter((section) => section.items.length > 0),
    [bookId, collaborationPermissions, collaborationRole, currentChapter, currentShell, hasFreeSampleIntelligenceAccess, hasOwnAuthorAccess, showAuthorSections]
  )
  const rail = variant === "rail"
  const [isPinnedOpen, setIsPinnedOpen] = useState(false)
  const collapsedRailWidth = railSize === "compact" ? "xl:w-[4.35rem]" : "xl:w-[4.9rem]"
  const expandedRailWidth = railSize === "compact" ? "xl:w-[16.5rem]" : "xl:w-[18.5rem]"
  const hoverExpandedRailWidth = railSize === "compact" ? "xl:group-hover/navwrap:w-[16.5rem] xl:group-focus-within/navwrap:w-[16.5rem]" : "xl:group-hover/navwrap:w-[18.5rem] xl:group-focus-within/navwrap:w-[18.5rem]"
  const containerClass = rail
    ? `group/rail z-20 flex w-full flex-col overflow-hidden rounded-lg border p-3 shadow-[0_22px_54px_-42px_rgba(58,49,37,0.24)] transition-[width,background-color,border-color,box-shadow] duration-300 xl:h-[calc(100vh-7.5rem)] ${isPinnedOpen ? expandedRailWidth : `${collapsedRailWidth} ${hoverExpandedRailWidth}`} ${
        isDark ? "border-white/10 bg-[#0b1220]/96 text-white xl:hover:border-white/14 xl:hover:bg-[#101826]/96" : "border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.96)] text-stone-950 xl:hover:border-stone-300 xl:hover:bg-white"
      }`
    : `sticky top-5 rounded-lg border p-4 ${isDark ? "border-white/10 bg-[rgba(8,14,24,0.9)]" : "border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.96)]"}`
  const labelVisibility = rail
    ? isPinnedOpen
      ? "opacity-100"
      : "opacity-100 xl:opacity-0 xl:group-hover/navwrap:opacity-100 xl:group-focus-within/navwrap:opacity-100"
    : "opacity-100"
  const helperVisibility = rail
    ? isPinnedOpen
      ? "max-h-20 translate-y-0 opacity-100"
      : "max-h-20 translate-y-0 opacity-100 xl:max-h-0 xl:translate-y-1 xl:opacity-0 xl:group-hover/navwrap:max-h-20 xl:group-hover/navwrap:translate-y-0 xl:group-hover/navwrap:opacity-100 xl:group-focus-within/navwrap:max-h-20 xl:group-focus-within/navwrap:translate-y-0 xl:group-focus-within/navwrap:opacity-100"
    : "max-h-0 opacity-0"

  if (rail) {
    return (
      <div className="group/navwrap relative xl:sticky xl:top-5 xl:self-start" data-testid={`author-tools-nav-${variant}`}>
        <div
          aria-hidden="true"
          className="absolute inset-y-4 left-0 z-20 hidden w-4 xl:block"
        />
        <Button
          variant="secondary"
          size="sm"
          aria-label={isPinnedOpen ? "Collapse sidebar" : "Expand sidebar"}
          data-testid="author-nav-rail-toggle"
          onClick={() => setIsPinnedOpen((current) => !current)}
          className="absolute left-0 top-8 z-30 hidden h-10 w-10 -translate-x-1/2 rounded-full shadow-[0_16px_34px_-24px_rgba(0,0,0,0.75)] xl:flex"
        >
          <span className={`transition-transform duration-200 ${isPinnedOpen ? "rotate-180" : ""}`}>
            <NavSvg icon="chevron-right" />
          </span>
        </Button>
        <aside className={containerClass}>
          <NavHeader isDark={isDark} labelVisibility={labelVisibility} title={title} />
          <p className={`mt-3 line-clamp-2 px-1 text-xs leading-5 transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-500" : "text-stone-500"}`}>
            {description}
          </p>

          <div className={`mt-5 space-y-5 ${rail ? "min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1" : "max-h-[calc(100vh-12rem)] overflow-y-auto pr-1"}`}>
            {sections.map((section) => {
              const sectionMarkup = (
              <div>
                <p className={`mb-2 px-1 text-3xs font-semibold uppercase tracking-[0.24em] transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-600" : "text-stone-400"}`}>
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
                        data-testid={`author-nav-item-${item.id}`}
                        className={`group/item flex min-h-[3.1rem] items-start gap-3 rounded-md border px-2.5 py-2.5 text-sm outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-200 focus-visible:ring-2 focus-visible:ring-offset-0 ${
                          selected
                            ? isDark
                              ? "border-white/12 bg-[linear-gradient(135deg,rgba(94,234,212,0.14),rgba(129,140,248,0.16))] text-white shadow-[0_18px_38px_-28px_rgba(94,234,212,0.18)]"
                              : "bg-teal-800 text-white shadow-[0_18px_34px_-26px_rgba(58,49,37,0.22)]"
                            : isDark
                              ? "border-transparent text-slate-300 hover:border-white/8 hover:bg-white/[0.05] hover:text-white focus-visible:ring-white/25"
                              : "border-transparent text-stone-600 hover:border-stone-200 hover:bg-stone-100 focus-visible:ring-stone-300 hover:text-stone-950"
                        }`}
                      >
                        <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-sm border transition-colors ${
                          selected
                            ? isDark
                              ? "border-white/15 bg-white/10 text-teal-100"
                              : "border-white/20 bg-white/15 text-white"
                            : isDark
                              ? "border-white/[0.06] bg-white/[0.04] text-slate-200 group-hover/item:bg-white/[0.08]"
                              : "border-stone-200 bg-white text-stone-700 group-hover/item:border-stone-300"
                        }`}>
                          <NavSvg icon={item.icon} />
                        </span>
                        <span className={`min-w-0 flex-1 transition-opacity duration-200 ${labelVisibility}`}>
                          <span className="block truncate font-semibold">{item.label}</span>
                          <span className={`mt-0.5 block truncate text-3xs uppercase tracking-[0.18em] ${selected ? (isDark ? "text-slate-300" : "text-white/70") : (isDark ? "text-slate-500" : "text-stone-400")}`}>
                            {item.tone}
                          </span>
                          <span
                            data-testid={`author-nav-helper-${item.id}`}
                            className={`mt-1.5 block overflow-hidden text-3xs leading-4 transition-all duration-200 ${helperVisibility} ${
                              selected
                                ? isDark
                                  ? "text-slate-200"
                                  : "text-white/80"
                                : isDark
                                  ? "text-slate-400"
                                  : "text-stone-500"
                            }`}
                          >
                            {item.helper}
                          </span>
                        </span>
                      </Link>
                    )
                  })}
                </div>
              </div>
              )
              return section.authorOnly ? (
                <AuthorFeatureComponent key={section.title} locked={null} allowAccess={hasCollaboratorAccess}>
                  {sectionMarkup}
                </AuthorFeatureComponent>
              ) : (
                <div key={section.title}>{sectionMarkup}</div>
              )
            })}
          </div>
        </aside>
      </div>
    )
  }

  return (
    <aside className={containerClass} data-testid={`author-tools-nav-${variant}`}>
      <NavHeader isDark={isDark} labelVisibility={labelVisibility} title={title} />

      <p className={`mt-3 line-clamp-2 px-1 text-xs leading-5 transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-500" : "text-stone-500"}`}>
        {description}
      </p>

      <div className={`mt-5 space-y-5 ${rail ? "min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1" : "max-h-[calc(100vh-12rem)] overflow-y-auto pr-1"}`}>
        {sections.map((section) => {
          const sectionMarkup = (
          <div>
            <p className={`mb-2 px-1 text-3xs font-semibold uppercase tracking-[0.24em] transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-600" : "text-stone-400"}`}>
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
                    data-testid={`author-nav-item-${item.id}`}
                    className={`group/item flex min-h-[3.1rem] items-start gap-3 rounded-md border px-2.5 py-2.5 text-sm outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-200 focus-visible:ring-2 focus-visible:ring-offset-0 ${
                      selected
                        ? isDark
                          ? "border-white/12 bg-[linear-gradient(135deg,rgba(94,234,212,0.14),rgba(129,140,248,0.16))] text-white shadow-[0_18px_38px_-28px_rgba(94,234,212,0.18)]"
                          : "bg-teal-800 text-white shadow-[0_18px_34px_-26px_rgba(58,49,37,0.22)]"
                        : isDark
                          ? "border-transparent text-slate-300 hover:border-white/8 hover:bg-white/[0.05] hover:text-white focus-visible:ring-white/25"
                          : "border-transparent text-stone-600 hover:border-stone-200 hover:bg-stone-100 focus-visible:ring-stone-300 hover:text-stone-950"
                    }`}
                  >
                    <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-sm border transition-colors ${
                      selected
                        ? isDark
                          ? "border-white/15 bg-white/10 text-teal-100"
                          : "border-white/20 bg-white/15 text-white"
                        : isDark
                          ? "border-white/[0.06] bg-white/[0.04] text-slate-200 group-hover/item:bg-white/[0.08]"
                          : "border-stone-200 bg-white text-stone-700 group-hover/item:border-stone-300"
                    }`}>
                      <NavSvg icon={item.icon} />
                    </span>
                    <span className={`min-w-0 flex-1 transition-opacity duration-200 ${labelVisibility}`}>
                      <span className="block truncate font-semibold">{item.label}</span>
                      <span className={`mt-0.5 block truncate text-3xs uppercase tracking-[0.18em] ${selected ? (isDark ? "text-slate-300" : "text-white/70") : (isDark ? "text-slate-500" : "text-stone-400")}`}>
                        {item.tone}
                      </span>
                      <span
                        data-testid={`author-nav-helper-${item.id}`}
                        className={`mt-1.5 block overflow-hidden text-3xs leading-4 transition-all duration-200 ${rail ? helperVisibility : selected ? "max-h-20 opacity-100" : "max-h-0 opacity-0"} ${
                          selected
                            ? isDark
                              ? "text-slate-200"
                              : "text-white/80"
                            : isDark
                              ? "text-slate-400"
                              : "text-stone-500"
                        }`}
                      >
                        {item.helper}
                      </span>
                    </span>
                  </Link>
                )
              })}
            </div>
          </div>
          )
          return section.authorOnly ? (
            <AuthorFeatureComponent key={section.title} locked={null} allowAccess={hasCollaboratorAccess}>
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

function NavHeader({
  isDark,
  labelVisibility,
  title,
}: {
  isDark: boolean
  labelVisibility: string
  title: string
}) {
  return (
    <div className="flex items-center gap-3 px-1">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border shadow-sm ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50"}`}>
        <ThemeBrandImage variant="icon" mode={isDark ? "dark" : "light"} className="h-5 w-5 object-contain" />
      </div>
      <div className={`min-w-0 transition-opacity duration-200 ${labelVisibility}`}>
        <ThemeBrandImage variant="lockup" mode={isDark ? "dark" : "light"} className="h-5 w-auto object-contain" />
        <h2 className={`mt-2 truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
      </div>
    </div>
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
    case "voice":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v8" /><path strokeLinecap="round" strokeLinejoin="round" d="M8.5 8.5a3.5 3.5 0 107 0" /><path strokeLinecap="round" strokeLinejoin="round" d="M6 11a6 6 0 0012 0" /><path strokeLinecap="round" strokeLinejoin="round" d="M9 20h6" /><path strokeLinecap="round" strokeLinejoin="round" d="M12 17v3" /></svg>
    case "quill":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M20 7c0 6-5 11-11 11H4v-5C4 7 9 2 15 2c2.5 0 5 2.5 5 5z" /><path strokeLinecap="round" strokeLinejoin="round" d="M13 11l4-4" /></svg>
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
    case "plus":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
    case "chevron-right":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="m9 6 6 6-6 6" /></svg>
    case "book":
    default:
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M6 4h9a3 3 0 013 3v13H8a2 2 0 01-2-2V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M8 18h10M9 8h5" /></svg>
  }
}
