"use client"

import React from "react"
import { useEffect, useMemo, useState } from "react"
import type { Route } from "next"
import Link from "next/link"

import { AuthorFeatureComponent } from "@/components/billing/AuthorFeatureComponent"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import { Button } from "@/components/ui/Button"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { useCachedBookDetail } from "@/lib/hooks/useBookDetail"
import { useNavigationPrefetch } from "@/lib/hooks/useNavigationPrefetch"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { useAuthStore } from "@/lib/stores/authStore"
import { defaultBookUiPreference, useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { workspaceToolRegistry } from "@/lib/workspace/toolRegistry"
import { resolveWorkspaceTool } from "@/lib/workspace/toolResolver"
import type { Book } from "@/types/book"
import type { CollaborationPermissions } from "@/types/book"
import type { BookPreset } from "@/types/uiPreferences"

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
  variant?: "panel" | "rail" | "bar"
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
  | "settings"
  | "chevron-right"

type NavItem = {
  id: string
  label: string
  href: Route
  tone: string
  helper: string
  icon: NavIcon
  advanced?: boolean
}

type NavSection = {
  title: string
  items: NavItem[]
  authorOnly?: boolean
  processingDependent?: boolean
}

const READER_SHELL_ITEM_IDS = new Set(["overview", "read", "chapters", "search", "timeline", "beta-feedback"])
const FREE_OWNER_AUTHOR_ITEM_IDS = new Set(["overview", "read", "chapters", "advisor", "export", "visibility"])
const BOOK_PRESET_OPTIONS: Array<{ value: BookPreset; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "review", label: "Review" },
  { value: "story_bible", label: "Bible" },
  { value: "share", label: "Share" },
  { value: "all", label: "All" },
]
const BOOK_HUBS: Array<{ value: Exclude<BookPreset, "all">; label: string; entry: string }> = [
  { value: "draft", label: "Draft", entry: "overview" },
  { value: "story_bible", label: "Story Bible", entry: "characters" },
  { value: "review", label: "Review", entry: "advisor" },
  { value: "share", label: "Share", entry: "collaboration" },
]
const HUB_BY_ITEM_ID: Record<string, Exclude<BookPreset, "all">> = {
  overview: "draft",
  read: "draft",
  chapters: "draft",
  manuscript: "draft",
  scenes: "draft",
  notes: "draft",
  characters: "story_bible",
  relationships: "story_bible",
  timeline: "story_bible",
  "plot-threads": "story_bible",
  foreshadowing: "story_bible",
  "world-gap": "story_bible",
  "cross-book-wiki": "story_bible",
  advisor: "review",
  "editorial-review": "review",
  "ai-beta-reader": "review",
  voice: "review",
  reports: "review",
  search: "review",
  summaries: "review",
  analysis: "review",
  "author-loop": "review",
  collaboration: "share",
  "beta-feedback": "share",
  export: "share",
  visibility: "share",
}
const NAV_TOOL_IDS: Record<string, string> = {
  "plot-threads": "book.plot_threads",
  "world-gap": "book.world_gap",
  "cross-book-wiki": "book.cross_book_wiki",
  "editorial-review": "book.editorial_review",
  "beta-feedback": "book.beta_feedback",
  "author-loop": "book.author_lens",
}
const TOOL_BY_ID = new Map(workspaceToolRegistry.map((tool) => [tool.id, tool]))

function toolIdForNavItem(itemId: string) {
  return NAV_TOOL_IDS[itemId] ?? `book.${itemId}`
}

function canSeeCollaboratorItem(itemId: string, permissions: CollaborationPermissions | null) {
  if (!permissions) return false
  switch (itemId) {
    case "manuscript":
    case "scenes":
      return permissions.can_edit_manuscript
    case "advisor":
    case "editorial-review":
    case "voice":
    case "analysis":
    case "reports":
      return permissions.can_run_ai_scans
    case "characters":
    case "relationships":
    case "plot-threads":
    case "timeline":
    case "foreshadowing":
    case "world-gap":
    case "cross-book-wiki":
      return permissions.can_view_story_bible
    case "notes":
    case "beta-feedback":
    case "author-loop":
      return permissions.can_comment || permissions.can_edit_manuscript
    case "export":
      return permissions.can_export
    case "collaboration":
    case "visibility":
      return false
    default:
      return true
  }
}

const NAV_SECTIONS = (bookId: string, currentChapter = 1): NavSection[] => [
  {
    title: "Write",
    items: [
      { id: "overview", label: "Overview", href: `/${bookId}` as Route, tone: "Home", helper: "See progress, next steps, and the latest signals around this book.", icon: "book" },
      { id: "read", label: "Preview Draft", href: `/${bookId}/chapter/${currentChapter}` as Route, tone: "Continue", helper: "Open the current draft in reading view and pick up where the story last left off.", icon: "read" },
      { id: "chapters", label: "Chapters", href: `/${bookId}/chapters` as Route, tone: "Switch", helper: "Jump across chapters and move through the manuscript without losing your place.", icon: "chapters" },
      { id: "manuscript", label: "Manuscript Editor", href: `/${bookId}/manuscript` as Route, tone: "Drafting", helper: "Write, revise, and shape the working manuscript with your drafting tools close by.", icon: "pen" },
      { id: "scenes", label: "Scene Workspace", href: `/${bookId}/scenes` as Route, tone: "File tree", helper: "Organize scenes, reorder structure, and manage the story at a scene-by-scene level.", icon: "files" },
      { id: "notes", label: "Notes Workspace", href: `/${bookId}/notes` as Route, tone: "Vault", helper: "Keep book-specific notes, reminders, and reference details beside the draft.", icon: "notes" },
    ],
  },
  {
    title: "Story Bible",
    authorOnly: true,
    processingDependent: true,
    items: [
      { id: "characters", label: "Character Bible", href: `/${bookId}/characters` as Route, tone: "Profiles", helper: "Track character profiles, arcs, and duplicate identity issues across the story.", icon: "users" },
      { id: "relationships", label: "Relationships", href: `/${bookId}/graph` as Route, tone: "Network", helper: "Map connections between characters so alliances, conflicts, and ties stay clear.", icon: "links" },
      { id: "timeline", label: "Timeline", href: `/${bookId}/timeline` as Route, tone: "Sequence", helper: "Review character presence, thread duration, and relationship shifts across the manuscript.", icon: "events" },
      { id: "plot-threads", label: "Plot Threads", href: `/${bookId}/plot-threads` as Route, tone: "Arc tracking", helper: "Follow open arcs and see which plot threads are moving, drifting, or unresolved.", icon: "threads" },
      { id: "foreshadowing", label: "Setup & Payoff", href: `/${bookId}/foreshadowing` as Route, tone: "Structure", helper: "Trace planted details to their intended returns and isolate setups that still need a payoff.", icon: "spark", advanced: true },
      { id: "world-gap", label: "World Gaps", href: `/${bookId}/world-gap` as Route, tone: "Lore cleanup", helper: "Spot missing lore, weak canon links, and worldbuilding details that need support.", icon: "gap", advanced: true },
      { id: "cross-book-wiki", label: "Series Wiki", href: `/${bookId}/cross-book-wiki` as Route, tone: "Cross-book", helper: "Compare recurring people and lore entries across books in the same series.", icon: "book", advanced: true },
    ],
  },
  {
    title: "Analyze",
    processingDependent: true,
    items: [
      { id: "advisor", label: "Story Advisor", href: `/${bookId}/advisor` as Route, tone: "Continuity", helper: "Review continuity risks, unresolved threads, and high-priority story pressure points.", icon: "spark" },
      { id: "analysis", label: "Findings", href: `/${bookId}/analysis` as Route, tone: "Review queue", helper: "Triage current evidence and choose the focused review that matches the decision you need to make.", icon: "analysis" },
      { id: "editorial-review", label: "Editorial Review", href: `/${bookId}/editorial-review` as Route, tone: "Line edit", helper: "Run an editorial pass that calls out clarity, pacing, and prose-level friction.", icon: "quill" },
      { id: "ai-beta-reader", label: "AI Beta Reader", href: `/${bookId}/ai-beta-reader` as Route, tone: "Reader pass", helper: "Find repeated language, compare character voices, and turn reader reactions into revision priorities.", icon: "analysis" },
      { id: "voice", label: "Voice Consistency", href: `/${bookId}/voice` as Route, tone: "Dialogue drift", helper: "Check whether character voice stays consistent across scenes and revisions.", icon: "voice" },
      { id: "reports", label: "Chapter Reports", href: `/${bookId}/analysis?view=chapters` as Route, tone: "Evidence", helper: "Review chapter-level continuity evidence, new characters, and thread movement within Findings.", icon: "analysis" },
    ],
  },
  {
    title: "Share & Export",
    items: [
      { id: "collaboration", label: "Collaborators", href: `/${bookId}/collaboration` as Route, tone: "Invite", helper: "Manage who can access the book and what each collaborator is allowed to do.", icon: "users" },
      { id: "beta-feedback", label: "Beta Feedback", href: `/${bookId}/beta-feedback` as Route, tone: "Review", helper: "Review chapter comments and assignment feedback.", icon: "users" },
      { id: "export", label: "Files & Export", href: `/${bookId}/export` as Route, tone: "Files", helper: "Prepare a manuscript, reader edition, reference package, or portable backup.", icon: "files" },
      { id: "visibility", label: "Access & Visibility", href: `/${bookId}/visibility` as Route, tone: "Access", helper: "See who can access this book and whether a public page is active.", icon: "settings" },
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
  const cachedTier = useAuthStore((state) => state.user?.tier)
  const [clientReady, setClientReady] = useState(false)
  useEffect(() => setClientReady(true), [])
  // Session-cached access can differ from the server's initial anonymous snapshot.
  const tier = clientReady ? cachedTier : undefined
  const preferenceBookId = normalizeBookRouteId(bookId)
  const { data: cachedBook = null } = useCachedBookDetail(bookId)
  const book = bookData ?? cachedBook
  const collaborationRole = book?.collaboration_role ?? null
  const collaborationPermissions = book?.collaboration_permissions ?? null
  const currentShell = book?.workspace_shell ?? mode
  const isOwnerSession = !collaborationRole
  const hasOwnAuthorAccess = canUseAuthorFeatures(tier)
  const hasCollaboratorAccess = Boolean(collaborationRole && collaborationPermissions)
  const showAuthorSections = currentShell === "author" && (isOwnerSession || hasOwnAuthorAccess || hasCollaboratorAccess)
  const isLimitedFreeOwner = currentShell === "author" && isOwnerSession && !hasOwnAuthorAccess
  const { prefetchByNavId } = useNavigationPrefetch(bookId)
  const hydrateBookPreferences = useUiPreferencesStore((state) => state.hydrateBook)
  const patchBookPreferences = useUiPreferencesStore((state) => state.patchBook)
  const setBookPreset = useUiPreferencesStore((state) => state.setBookPreset)
  const uiPreferences = useUiPreferencesStore((state) => state.preferences)
  const storedBookPreference = useUiPreferencesStore((state) => state.bookPreferences[preferenceBookId])
  const bookPreference = useMemo(
    () => storedBookPreference ?? defaultBookUiPreference(preferenceBookId, uiPreferences.complexity_mode),
    [preferenceBookId, storedBookPreference, uiPreferences.complexity_mode],
  )
  const advancedToolOverride = useUiPreferencesStore(
    (state) => state.bookPreferences[preferenceBookId]?.advanced_tool_override,
  )
  const showAdvanced =
    advancedToolOverride === "show" ||
    (advancedToolOverride !== "hide" && uiPreferences.complexity_mode === "power")
  const processingReady = book?.status === "ready"
  const resolverBook = useMemo(
    () =>
      (book ?? {
        id: bookId,
        status: "ready",
        collaboration_role: null,
        collaboration_permissions: null,
      }) as Book,
    [book, bookId],
  )

  useEffect(() => {
    void hydrateBookPreferences(preferenceBookId)
  }, [hydrateBookPreferences, preferenceBookId])

  const toggleAdvancedTools = () => {
    void patchBookPreferences(preferenceBookId, [
      { op: "set", path: "/advanced_tool_override", value: showAdvanced ? "hide" : "show" },
    ])
  }

  const sections = useMemo(
    () =>
      NAV_SECTIONS(bookId, currentChapter)
        .filter((section) => {
          if (currentShell === "reader") {
            return !section.authorOnly
          }
          if (isLimitedFreeOwner) {
            return section.title === "Write" || section.title === "Analyze" || section.title === "Share & Export"
          }
          if (showAuthorSections || !section.authorOnly) {
            return true
          }
          return false
        })
        .map((section) => ({
          ...section,
          items: section.items.filter((item) => {
            if (currentShell === "reader" && !READER_SHELL_ITEM_IDS.has(item.id)) return false
            if (isLimitedFreeOwner && !FREE_OWNER_AUTHOR_ITEM_IDS.has(item.id)) return false
            const tool = TOOL_BY_ID.get(toolIdForNavItem(item.id))
            if (tool) {
              const resolved = resolveWorkspaceTool(tool, {
                mode: uiPreferences.complexity_mode,
                activePath: item.id === active ? item.href : null,
                book: resolverBook,
                bookPreference,
                globalPreference: uiPreferences,
                placement: "book",
                hasAuthorAccess: hasOwnAuthorAccess,
                currentChapter,
              })
              if (resolved.hidden) return false
              if (resolved.access !== "available") return false
            } else if (item.advanced && !showAdvanced && item.id !== active) {
              return false
            }
            if (currentShell === "reader") return true
            if (isOwnerSession || !collaborationRole) return true
            return canSeeCollaboratorItem(item.id, collaborationPermissions)
          }),
        }))
        .filter((section) => section.items.length > 0),
    [active, bookId, bookPreference, collaborationPermissions, collaborationRole, currentChapter, currentShell, hasOwnAuthorAccess, isLimitedFreeOwner, isOwnerSession, resolverBook, showAdvanced, showAuthorSections, uiPreferences]
  )
  const bar = variant === "bar"
  const rail = variant === "rail"
  const [isPinnedOpen, setIsPinnedOpen] = useState(false)
  const [allToolsOpen, setAllToolsOpen] = useState(false)
  const collapsedRailWidth = railSize === "compact" ? "xl:w-[4.35rem]" : "xl:w-[4.9rem]"
  const expandedRailWidth = railSize === "compact" ? "xl:w-[16.5rem]" : "xl:w-[18.5rem]"
  const hoverExpandedRailWidth = railSize === "compact" ? "xl:group-hover/navwrap:w-[16.5rem] xl:group-focus-within/navwrap:w-[16.5rem]" : "xl:group-hover/navwrap:w-[18.5rem] xl:group-focus-within/navwrap:w-[18.5rem]"
  const containerClass = rail
    ? `group/rail z-20 flex w-full flex-col overflow-hidden rounded-lg border p-3 transition-[width,background-color,border-color] duration-300 xl:h-[calc(100vh-7.5rem)] ${isPinnedOpen ? expandedRailWidth : `${collapsedRailWidth} ${hoverExpandedRailWidth}`} ${
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

  if (bar) {
    const activeHub = HUB_BY_ITEM_ID[active] ?? "draft"
    const itemById = new Map(NAV_SECTIONS(bookId, currentChapter).flatMap((section) => section.items.map((item) => [item.id, item])))
    const localItems = sections
      .flatMap((section) => section.items)
      .filter((item) => currentShell !== "author" || allToolsOpen || HUB_BY_ITEM_ID[item.id] === activeHub)
    const visibleHubs = currentShell === "reader"
      ? []
      : BOOK_HUBS.filter((hub) => hub.value !== "story_bible" || activeHub === "story_bible" || (!isLimitedFreeOwner && showAuthorSections))

    return (
      <nav
        aria-label="Book workspace"
        className={`overflow-hidden border-y ${isDark ? "border-white/[0.08] bg-[#111719] text-white" : "border-stone-200 bg-white/85 text-stone-950"}`}
        data-testid="author-tools-nav-bar"
      >
        <div className="flex min-h-16 items-center gap-3 px-3 sm:px-4">
          <Link
            href={active === "overview" ? "/library" : `/${bookId}` as Route}
            prefetch={false}
            data-testid="author-nav-home-link"
            className={`flex min-w-0 items-center gap-3 rounded-sm px-1 py-2 ${isDark ? "hover:text-white" : "hover:text-stone-950"}`}
          >
            <ThemeBrandImage variant="icon" mode={clientReady ? isDark ? "dark" : "light" : "auto"} className="h-7 w-7 shrink-0 object-contain" />
            <span className="min-w-0">
              <span className={`block text-[0.68rem] font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                {active === "overview" ? "Back to library" : "Book overview"}
              </span>
              <span className="block max-w-44 truncate text-sm font-semibold sm:max-w-60">
                {book?.title || title}
              </span>
            </span>
          </Link>

          {currentShell === "author" ? (
            <div className="app-scroll ml-auto hidden min-w-0 items-stretch self-stretch overflow-x-auto md:flex" aria-label="Book workspace hubs">
              {visibleHubs.map((hub) => {
                const hubItem = itemById.get(hub.entry)
                if (!hubItem) return null
                const selected = activeHub === hub.value && !allToolsOpen
                return (
                  <Link
                    key={hub.value}
                    href={hubItem.href}
                    prefetch={false}
                    aria-current={selected ? "page" : undefined}
                    onClick={() => {
                      setAllToolsOpen(false)
                      void setBookPreset(preferenceBookId, hub.value)
                    }}
                    className={`flex items-center border-b-2 px-4 text-sm font-medium transition-colors duration-150 ${
                      selected
                        ? isDark ? "border-teal-300 text-white" : "border-teal-800 text-stone-950"
                        : isDark ? "border-transparent text-slate-400 hover:text-white" : "border-transparent text-stone-500 hover:text-stone-950"
                    }`}
                  >
                    {hub.label}
                  </Link>
                )
              })}
            </div>
          ) : null}

          <Link
            href={`/${bookId}/search` as Route}
            prefetch={false}
            aria-label="Search this book"
            className={`ml-auto flex h-10 w-10 shrink-0 items-center justify-center rounded-sm border md:ml-2 ${
              active === "search"
                ? isDark ? "border-teal-300/30 bg-teal-500/10 text-teal-200" : "border-teal-700 bg-teal-50 text-teal-800"
                : isDark ? "border-white/[0.08] text-slate-300 hover:bg-white/[0.05]" : "border-stone-200 text-stone-600 hover:bg-stone-50"
            }`}
          >
            <NavSvg icon="search" />
          </Link>

          {currentShell === "author" ? (
            <button
              type="button"
              aria-expanded={allToolsOpen}
              onClick={() => {
                const nextOpen = !allToolsOpen
                setAllToolsOpen(nextOpen)
                if (nextOpen) void setBookPreset(preferenceBookId, "all")
              }}
              className={`flex h-10 shrink-0 items-center gap-2 rounded-sm border px-3 text-sm font-medium transition-colors duration-150 ${
                allToolsOpen
                  ? isDark ? "border-teal-300/30 bg-teal-500/10 text-white" : "border-teal-700 bg-teal-50 text-teal-900"
                  : isDark ? "border-white/[0.08] text-slate-300 hover:bg-white/[0.05]" : "border-stone-200 text-stone-600 hover:bg-stone-50"
              }`}
            >
              <span>More</span>
              <span className={`transition-transform duration-150 ${allToolsOpen ? "rotate-90" : ""}`}><NavSvg icon="chevron-right" /></span>
            </button>
          ) : null}
        </div>

        <div className={`border-t px-3 sm:px-4 ${isDark ? "border-white/[0.06]" : "border-stone-200/80"}`}>
          <div className="app-scroll flex min-h-12 items-center gap-1 overflow-x-auto py-1.5">
            {currentShell === "author" ? (
              <div className="flex shrink-0 gap-1 md:hidden" aria-label="Book workspace hubs">
                {visibleHubs.map((hub) => {
                  const hubItem = itemById.get(hub.entry)
                  if (!hubItem) return null
                  const selected = activeHub === hub.value && !allToolsOpen
                  return (
                    <Link
                      key={hub.value}
                      href={hubItem.href}
                      prefetch={false}
                      onClick={() => {
                        setAllToolsOpen(false)
                        void setBookPreset(preferenceBookId, hub.value)
                      }}
                      className={`rounded-sm px-3 py-2 text-xs font-medium ${selected ? (isDark ? "bg-white/[0.08] text-white" : "bg-stone-100 text-stone-950") : (isDark ? "text-slate-400" : "text-stone-500")}`}
                    >
                      {hub.label}
                    </Link>
                  )
                })}
                <span className={`mx-1 w-px ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
              </div>
            ) : null}
            <div className="flex min-w-0 items-center gap-1">
              {localItems.map((item) => {
                const selected = item.id === active
                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    prefetch={false}
                    aria-current={selected ? "page" : undefined}
                    data-testid={`author-nav-item-${item.id}`}
                    onMouseEnter={() => prefetchByNavId(item.id)}
                    onFocus={() => prefetchByNavId(item.id)}
                    className={`shrink-0 rounded-sm px-3 py-2 text-xs font-medium transition-colors duration-150 ${
                      selected
                        ? isDark ? "bg-white/[0.09] text-white" : "bg-stone-100 text-stone-950"
                        : isDark ? "text-slate-400 hover:bg-white/[0.04] hover:text-white" : "text-stone-500 hover:bg-stone-50 hover:text-stone-950"
                    }`}
                  >
                    {item.label}
                  </Link>
                )
              })}
            </div>
            {currentShell === "author" && allToolsOpen ? (
              <button
                type="button"
                onClick={toggleAdvancedTools}
                className={`ml-auto shrink-0 rounded-sm px-3 py-2 text-xs font-medium ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-950"}`}
              >
                {showAdvanced ? "Hide advanced" : "Show advanced"}
              </button>
            ) : null}
          </div>
        </div>
      </nav>
    )
  }

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
          className="absolute left-0 top-8 z-30 hidden h-10 w-10 -translate-x-1/2 rounded-full xl:flex"
        >
          <span className={`transition-transform duration-200 ${isPinnedOpen ? "rotate-180" : ""}`}>
            <NavSvg icon="chevron-right" />
          </span>
        </Button>
        <aside className={containerClass}>
          <NavHeader isDark={isDark} labelVisibility={labelVisibility} title={title} bookId={bookId} active={active} />
          <p className={`mt-3 line-clamp-2 px-1 text-xs leading-5 transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-500" : "text-stone-500"}`}>
            {description}
          </p>
          {currentShell === "author" ? (
            <PresetSelector
              bookId={preferenceBookId}
              currentPreset={bookPreference.book_preset}
              isDark={isDark}
              labelVisibility={labelVisibility}
              setBookPreset={setBookPreset}
            />
          ) : null}

          <div className={`mt-5 space-y-5 ${rail ? "min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1" : "max-h-[calc(100vh-12rem)] overflow-y-auto pr-1"}`}>
            {sections.map((section) => {
              const sectionMarkup = (
              <div>
                <p className={`mb-2 px-1 text-3xs font-semibold uppercase tracking-[0.24em] transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-600" : "text-stone-400"}`}>
                  {section.title}{section.processingDependent && !processingReady ? " - processing" : ""}
                </p>
                <div className="space-y-1">
                  {section.items.map((item) => {
                    const selected = item.id === active
                    return (
                      <Link
                        key={item.id}
                        href={item.href}
                        prefetch={false}
                        aria-current={selected ? "page" : undefined}
                        title={item.label}
                        data-testid={`author-nav-item-${item.id}`}
                        onMouseEnter={() => prefetchByNavId(item.id)}
                        onFocus={() => prefetchByNavId(item.id)}
                        className={`group/item flex min-h-[3.1rem] items-start gap-3 rounded-md border px-2.5 py-2.5 text-sm outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-200 focus-visible:ring-2 focus-visible:ring-offset-0 ${
                          selected
                            ? isDark
                              ? "border-teal-300/20 bg-teal-900/70 text-white"
                              : "bg-teal-800 text-white"
                            : isDark
                              ? "border-transparent text-slate-300 hover:border-white/[0.08] hover:bg-white/[0.05] hover:text-white focus-visible:ring-white/25"
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
                <AuthorFeatureComponent key={section.title} locked={null} allowAccess={hasCollaboratorAccess || (isLimitedFreeOwner && section.title === "Share & Export")}>
                  {sectionMarkup}
                </AuthorFeatureComponent>
              ) : (
                <div key={section.title}>{sectionMarkup}</div>
              )
            })}
            {currentShell === "author" ? (
              <button type="button" onClick={toggleAdvancedTools} className={`w-full rounded-md border px-3 py-2 text-left text-xs font-semibold ${labelVisibility} ${isDark ? "border-white/10 text-slate-300 hover:bg-white/5" : "border-stone-200 text-stone-600 hover:bg-stone-50"}`}>
                {showAdvanced ? "Hide advanced tools" : "Show advanced tools"}
              </button>
            ) : null}
          </div>
        </aside>
      </div>
    )
  }

  return (
    <aside className={containerClass} data-testid={`author-tools-nav-${variant}`}>
      <NavHeader isDark={isDark} labelVisibility={labelVisibility} title={title} bookId={bookId} active={active} />

      <p className={`mt-3 line-clamp-2 px-1 text-xs leading-5 transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-500" : "text-stone-500"}`}>
        {description}
      </p>
      {currentShell === "author" ? (
        <PresetSelector
          bookId={preferenceBookId}
          currentPreset={bookPreference.book_preset}
          isDark={isDark}
          labelVisibility={labelVisibility}
          setBookPreset={setBookPreset}
        />
      ) : null}

      <div className={`mt-5 space-y-5 ${rail ? "min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1" : "max-h-[calc(100vh-12rem)] overflow-y-auto pr-1"}`}>
        {sections.map((section) => {
          const sectionMarkup = (
          <div>
            <p className={`mb-2 px-1 text-3xs font-semibold uppercase tracking-[0.24em] transition-opacity duration-200 ${labelVisibility} ${isDark ? "text-slate-600" : "text-stone-400"}`}>
              {section.title}{section.processingDependent && !processingReady ? " - processing" : ""}
            </p>
            <div className="space-y-1">
              {section.items.map((item) => {
                const selected = item.id === active
                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    prefetch={false}
                    aria-current={selected ? "page" : undefined}
                    title={item.label}
                    data-testid={`author-nav-item-${item.id}`}
                    onMouseEnter={() => prefetchByNavId(item.id)}
                    onFocus={() => prefetchByNavId(item.id)}
                    className={`group/item flex min-h-[3.1rem] items-start gap-3 rounded-md border px-2.5 py-2.5 text-sm outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-200 focus-visible:ring-2 focus-visible:ring-offset-0 ${
                      selected
                        ? isDark
                          ? "border-teal-300/20 bg-teal-900/70 text-white"
                          : "bg-teal-800 text-white"
                        : isDark
                          ? "border-transparent text-slate-300 hover:border-white/[0.08] hover:bg-white/[0.05] hover:text-white focus-visible:ring-white/25"
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
            <AuthorFeatureComponent key={section.title} locked={null} allowAccess={hasCollaboratorAccess || (isLimitedFreeOwner && section.title === "Share & Export")}>
              {sectionMarkup}
            </AuthorFeatureComponent>
          ) : (
            <div key={section.title}>{sectionMarkup}</div>
          )
        })}
        {currentShell === "author" ? (
          <button type="button" onClick={toggleAdvancedTools} className={`w-full rounded-md border px-3 py-2 text-left text-xs font-semibold ${isDark ? "border-white/10 text-slate-300 hover:bg-white/5" : "border-stone-200 text-stone-600 hover:bg-stone-50"}`}>
            {showAdvanced ? "Hide advanced tools" : "Show advanced tools"}
          </button>
        ) : null}
      </div>
    </aside>
  )
}

function NavHeader({
  isDark,
  labelVisibility,
  title,
  bookId,
  active,
}: {
  isDark: boolean
  labelVisibility: string
  title: string
  bookId: string
  active: string
}) {
  const homeHref = active === "overview" ? "/library" : `/${bookId}`

  return (
    <div className="flex items-center gap-3 px-1">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md border ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50"}`}>
        <ThemeBrandImage variant="icon" mode={isDark ? "dark" : "light"} className="h-5 w-5 object-contain" />
      </div>
      <div className={`min-w-0 transition-opacity duration-200 ${labelVisibility}`}>
        <h2 className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
        <Link
          href={homeHref as Route}
          prefetch={false}
          data-testid="author-nav-home-link"
          className={`mt-1 inline-flex items-center rounded-sm text-3xs font-semibold uppercase tracking-[0.18em] hover:text-teal-600 ${isDark ? "text-slate-500" : "text-stone-500"}`}
        >
          Home
        </Link>
      </div>
    </div>
  )
}

function PresetSelector({
  bookId,
  currentPreset,
  isDark,
  labelVisibility,
  setBookPreset,
}: {
  bookId: string
  currentPreset: BookPreset
  isDark: boolean
  labelVisibility: string
  setBookPreset: (bookId: string, preset: BookPreset) => Promise<void>
}) {
  return (
    <div className={`mt-4 grid grid-cols-5 gap-1 transition-opacity duration-200 ${labelVisibility}`} aria-label="Book task preset">
      {BOOK_PRESET_OPTIONS.map((preset) => {
        const active = currentPreset === preset.value
        return (
          <button
            key={preset.value}
            type="button"
            aria-pressed={active}
            title={preset.label}
            onClick={() => void setBookPreset(bookId, preset.value)}
            className={`min-h-11 overflow-hidden rounded-sm border px-1 text-center text-[0.65rem] font-semibold leading-tight transition-colors ${
              active
                ? isDark
                  ? "border-teal-300/30 bg-teal-500/15 text-teal-100"
                  : "border-teal-800 bg-teal-800 text-white"
                : isDark
                  ? "border-white/[0.08] text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"
                  : "border-stone-200 text-stone-500 hover:bg-stone-100 hover:text-stone-900"
            }`}
          >
            {preset.label}
          </button>
        )
      })}
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
    case "settings":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8.5a3.5 3.5 0 110 7 3.5 3.5 0 010-7z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19 12a7.2 7.2 0 00-.1-1.2l2-1.5-2-3.4-2.4 1a7 7 0 00-2-1.1L14.2 3h-4.4l-.3 2.8a7 7 0 00-2 1.1l-2.4-1-2 3.4 2 1.5A7.2 7.2 0 005 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.4-1a7 7 0 002 1.1l.3 2.8h4.4l.3-2.8a7 7 0 002-1.1l2.4 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z" /></svg>
    case "chevron-right":
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="m9 6 6 6-6 6" /></svg>
    case "book":
    default:
      return <svg className={common} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M6 4h9a3 3 0 013 3v13H8a2 2 0 01-2-2V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M8 18h10M9 8h5" /></svg>
  }
}
