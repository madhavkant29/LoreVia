"use client"

import { useEffect, useMemo, useRef, useState, useTransition } from "react"
import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, booksSelectorCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { getBookHref } from "@/lib/utils/bookRoutes"
import { filterCommandActions, getRecentCommandActions, recordRecentCommandAction } from "@/lib/utils/uxActions"
import { resolveWorkspaceTools } from "@/lib/workspace/toolResolver"
import { toolsForPlacement } from "@/lib/workspace/toolRegistry"
import { COMMAND_PALETTE_EVENT } from "@/components/ui/ShortcutHelp"
import { Dialog } from "@/components/ui/Dialog"
import type { BookSelector } from "@/types/book"
import type { UserBookUiPreference, UserUiPreference } from "@/types/uiPreferences"
import type { CommandAction } from "@/types/ux"

const EXTRA_BASE_ACTIONS: CommandAction[] = [
  { id: "nav:forum", label: "Open Book Discussions", href: "/public/forum", group: "Navigation", keywords: ["book discussions", "forum", "community"] },
  { id: "nav:notifications", label: "Open Notifications", href: "/notifications", group: "Navigation", keywords: ["updates", "inbox"] },
]

const DASHBOARD_COMMAND_TOOLS = toolsForPlacement("dashboard")
const BOOK_COMMAND_TOOLS = toolsForPlacement("command").filter((tool) => tool.id.startsWith("book."))

function hiddenDescription(reason: string | undefined, access: string) {
  if (access === "plan_locked") return "Plan locked; available from search so upgrade/recovery stays clear."
  if (access === "permission_denied") return "Not available with your current permissions."
  if (access === "processing_blocked") return "Available after processing finishes."
  if (reason === "hidden_by_user") return "Hidden from navigation; command search can still open it."
  if (reason === "hidden_by_preset") return "Hidden by the current task preset."
  if (reason === "hidden_by_mode") return "Hidden by the current workspace mode."
  return undefined
}

function buildBaseActions(preferences: UserUiPreference): CommandAction[] {
  const registryActions = resolveWorkspaceTools(DASHBOARD_COMMAND_TOOLS, {
    mode: preferences.complexity_mode,
    globalPreference: preferences,
    placement: "command",
  }).map(({ tool, href, reason, access }) => ({
    id: `registry:${tool.id}`,
    label: `Open ${tool.label}`,
    description: hiddenDescription(reason, access) ?? tool.description ?? tool.group,
    href: href as Route,
    group: tool.group,
    keywords: tool.keywords,
  }))
  return [
    ...registryActions,
    ...EXTRA_BASE_ACTIONS,
    {
      id: "visibility:dashboard",
      label: "Edit workspace visibility",
      href: "/settings" as Route,
      group: "Visibility",
      keywords: ["visibility", "hidden", "layout", "tools"],
    },
    {
      id: "mode:switch",
      label: "Switch workspace mode",
      href: "/settings" as Route,
      group: "Visibility",
      keywords: ["focused", "standard", "power", "mode"],
    },
  ]
}

function buildBookActions(
  books: BookSelector[],
  preferences: UserUiPreference,
  bookPreferences: Record<string, UserBookUiPreference>,
  hasAuthorAccess: boolean,
): CommandAction[] {
  return books.flatMap((book) => {
    const href = getBookHref(book) as Route
    const baseKeywords = [book.title, book.author, book.genre, book.mode, book.status].filter(Boolean) as string[]
    const toolActions = resolveWorkspaceTools(BOOK_COMMAND_TOOLS, {
      mode: preferences.complexity_mode,
      book,
      bookPreference: bookPreferences[book.id],
      globalPreference: preferences,
      placement: "command",
      hasAuthorAccess,
    }).map(({ tool, href: toolHref, reason, access }) => ({
      id: `book:${book.id}:${tool.id}`,
      label: `${tool.label}: ${book.title}`,
      description: hiddenDescription(reason, access) ?? tool.description ?? tool.group,
      href: toolHref as Route,
      group: tool.group,
      keywords: [...baseKeywords, ...tool.keywords],
    }))
    return [
      {
        id: `book:${book.id}:open`,
        label: `Open ${book.title}`,
        description: book.author ? `Project by ${book.author}` : "Open project overview",
        href,
        group: "Projects",
        keywords: baseKeywords,
      },
      {
        id: `book:${book.id}:visibility`,
        label: `Edit visibility: ${book.title}`,
        href: getBookHref(book, "/visibility") as Route,
        group: "Visibility",
        keywords: [...baseKeywords, "visibility", "hidden", "sharing"],
      },
      {
        id: `book:${book.id}:show-hidden`,
        label: `Show hidden tools: ${book.title}`,
        href: getBookHref(book, "/visibility") as Route,
        group: "Visibility",
        keywords: [...baseKeywords, "show hidden tools", "restore"],
      },
      ...toolActions,
    ]
  })
}

export function CommandPalette() {
  const router = useRouter()
  const user = useAuthStore((state) => state.user)
  const authHydrated = useAuthStore((state) => state.hydrated)
  const preferences = useUiPreferencesStore((state) => state.preferences)
  const bookPreferences = useUiPreferencesStore((state) => state.bookPreferences)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [activeIndex, setActiveIndex] = useState(0)
  const [isPending, startTransition] = useTransition()
  const inputRef = useRef<HTMLInputElement | null>(null)

  const booksQuery = useQuery<BookSelector[]>({
    queryKey: asQueryKey(booksSelectorCacheKey(true)),
    queryFn: () => booksApi.listSelector(true),
    enabled: open && authHydrated && Boolean(user),
    staleTime: 30_000,
  })

  const actions = useMemo(
    () => [
      ...buildBaseActions(preferences),
      ...buildBookActions(booksQuery.data ?? [], preferences, bookPreferences, Boolean(user && user.tier !== "free")),
    ],
    [bookPreferences, booksQuery.data, preferences, user],
  )
  const recentActions = useMemo(() => getRecentCommandActions(actions), [actions])
  const filteredActions = useMemo(() => filterCommandActions(actions, query), [actions, query])
  const visibleActions = query.trim() ? filteredActions : [...recentActions, ...filteredActions.filter((action) => !recentActions.some((recent) => recent.id === action.id))].slice(0, 14)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setOpen((current) => !current)
      }
      if (event.key === "Escape") {
        setOpen(false)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    const onOpenRequest = () => setOpen(true)
    window.addEventListener(COMMAND_PALETTE_EVENT, onOpenRequest)
    return () => {
      window.removeEventListener("keydown", onKeyDown)
      window.removeEventListener(COMMAND_PALETTE_EVENT, onOpenRequest)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    setQuery("")
    setActiveIndex(0)
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }, [open])

  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  const runAction = (action: CommandAction) => {
    recordRecentCommandAction(action.id)
    setOpen(false)
    if (action.run) {
      action.run()
      return
    }
    if (action.href) {
      startTransition(() => router.push(action.href as Route))
    }
  }

  return (
    <Dialog
      open={open}
      onClose={() => setOpen(false)}
      title="Command palette"
      description="Jump to a project, tool, or action."
      size="lg"
      initialFocusRef={inputRef}
      contentClassName="p-0"
      titleClassName="px-5 pt-4 text-sm"
      descriptionClassName="mt-1 px-5 text-xs leading-5"
      className="overflow-hidden"
    >
        <div className="border-b border-[rgba(var(--border),0.72)] px-5 pb-4">
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault()
                setActiveIndex((current) => Math.min(current + 1, Math.max(visibleActions.length - 1, 0)))
              }
              if (event.key === "ArrowUp") {
                event.preventDefault()
                setActiveIndex((current) => Math.max(current - 1, 0))
              }
              if (event.key === "Enter" && visibleActions[activeIndex]) {
                event.preventDefault()
                runAction(visibleActions[activeIndex])
              }
            }}
            className="mt-3 w-full bg-transparent text-lg outline-none"
            aria-label="Search commands"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded="true"
            aria-controls="command-palette-results"
            aria-activedescendant={visibleActions[activeIndex] ? `command-option-${activeIndex}` : undefined}
          />
        </div>
        <div id="command-palette-results" role="listbox" aria-label="Command results" className="max-h-[27rem] overflow-y-auto p-2">
          {booksQuery.isLoading ? (
            <p className="px-3 py-4 text-sm text-[rgb(var(--muted-foreground))]">Loading project actions...</p>
          ) : visibleActions.length === 0 ? (
            <p className="px-3 py-4 text-sm text-[rgb(var(--muted-foreground))]">No matching commands.</p>
          ) : (
            visibleActions.map((action, index) => (
              <button
                key={action.id}
                id={`command-option-${index}`}
                role="option"
                aria-selected={activeIndex === index}
                type="button"
                onClick={() => runAction(action)}
                className={`flex w-full items-start justify-between gap-4 rounded-md px-3 py-3 text-left transition ${
                  activeIndex === index ? "bg-[rgba(var(--muted),0.72)]" : "hover:bg-[rgba(var(--muted),0.48)]"
                }`}
              >
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">{action.label}</span>
                  <span className="mt-1 block text-xs leading-5 text-[rgb(var(--muted-foreground))]">
                    {action.description ?? action.group ?? "Open action"}
                  </span>
                </span>
                <span className="shrink-0 text-3xs font-semibold uppercase tracking-[0.2em] text-[rgb(var(--muted-foreground))]">
                  {action.group}
                </span>
              </button>
            ))
          )}
        </div>
        <div className="flex items-center justify-between border-t border-[rgba(var(--border),0.72)] px-5 py-3 text-xs text-[rgb(var(--muted-foreground))]">
          <span>Enter to open / Esc to close</span>
          <span>{isPending ? "Opening..." : "Ctrl/Cmd K"}</span>
        </div>
    </Dialog>
  )
}
