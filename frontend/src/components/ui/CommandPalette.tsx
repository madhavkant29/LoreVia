"use client"

import { useEffect, useMemo, useRef, useState, useTransition } from "react"
import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, booksListCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { getBookHref } from "@/lib/utils/bookRoutes"
import { filterCommandActions, getRecentCommandActions, recordRecentCommandAction } from "@/lib/utils/uxActions"
import type { Book } from "@/types/book"
import type { CommandAction } from "@/types/ux"

const BASE_ACTIONS: CommandAction[] = [
  { id: "nav:library", label: "Open Library", href: "/library", group: "Navigation", keywords: ["projects", "dashboard"] },
  { id: "nav:public", label: "Open Public Uploads", href: "/public/uploads", group: "Navigation", keywords: ["browse", "authors"] },
  { id: "nav:forum", label: "Open Public Forum", href: "/public/forum", group: "Navigation", keywords: ["community", "discussion"] },
  { id: "nav:stats", label: "Open Writing Stats", href: "/stats", group: "Navigation", keywords: ["goals", "progress"] },
  { id: "nav:notifications", label: "Open Notifications", href: "/notifications", group: "Navigation", keywords: ["updates", "inbox"] },
  { id: "nav:settings", label: "Open Settings", href: "/settings", group: "Navigation", keywords: ["account", "preferences"] },
  { id: "nav:pricing", label: "Open Pricing", href: "/upgrade", group: "Navigation", keywords: ["billing", "plan"] },
]

function buildBookActions(books: Book[]): CommandAction[] {
  return books.flatMap((book) => {
    const href = getBookHref(book) as Route
    const manuscriptHref = getBookHref(book, "/manuscript") as Route
    const askHref = getBookHref(book, "/ask") as Route
    const charactersHref = getBookHref(book, "/characters") as Route
    const graphHref = getBookHref(book, "/graph") as Route
    const advisorHref = getBookHref(book, "/advisor") as Route
    const searchHref = getBookHref(book, "/search") as Route
    const baseKeywords = [book.title, book.author, book.genre, book.mode, book.status].filter(Boolean) as string[]
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
        id: `book:${book.id}:manuscript`,
        label: `Open manuscript: ${book.title}`,
        description: "Jump to the manuscript editor",
        href: manuscriptHref,
        group: "Project tools",
        keywords: [...baseKeywords, "write", "draft", "editor"],
      },
      {
        id: `book:${book.id}:ask`,
        label: `Ask LoreVia: ${book.title}`,
        description: "Ask grounded questions with citations",
        href: askHref,
        group: "Project tools",
        keywords: [...baseKeywords, "ask", "citations", "question"],
      },
      {
        id: `book:${book.id}:characters`,
        label: `Open character bible: ${book.title}`,
        href: charactersHref,
        group: "Story bible",
        keywords: [...baseKeywords, "characters", "story bible"],
      },
      {
        id: `book:${book.id}:graph`,
        label: `Open relationship graph: ${book.title}`,
        href: graphHref,
        group: "Story bible",
        keywords: [...baseKeywords, "graph", "relationships"],
      },
      {
        id: `book:${book.id}:advisor`,
        label: `Run story advisor: ${book.title}`,
        href: advisorHref,
        group: "Review center",
        keywords: [...baseKeywords, "continuity", "scan", "advisor"],
      },
      {
        id: `book:${book.id}:search`,
        label: `Search writing: ${book.title}`,
        href: searchHref,
        group: "Review center",
        keywords: [...baseKeywords, "search", "passages"],
      },
    ]
  })
}

export function CommandPalette() {
  const router = useRouter()
  const user = useAuthStore((state) => state.user)
  const authHydrated = useAuthStore((state) => state.hydrated)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [activeIndex, setActiveIndex] = useState(0)
  const [isPending, startTransition] = useTransition()
  const inputRef = useRef<HTMLInputElement | null>(null)

  const booksQuery = useQuery<Book[]>({
    queryKey: asQueryKey(booksListCacheKey(true)),
    queryFn: () => booksApi.list(true),
    enabled: open && authHydrated && Boolean(user),
    staleTime: 30_000,
  })

  const actions = useMemo(
    () => [...BASE_ACTIONS, ...buildBookActions(booksQuery.data ?? [])],
    [booksQuery.data],
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
    return () => window.removeEventListener("keydown", onKeyDown)
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

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[75] bg-black/50 px-4 py-16" role="presentation">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="command-palette-title"
        className="mx-auto w-full max-w-2xl overflow-hidden rounded-lg border border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] text-[rgb(var(--card-foreground))] shadow-[var(--shadow-modal)]"
      >
        <div className="border-b border-[rgba(var(--border),0.72)] px-5 py-4">
          <p id="command-palette-title" className="app-eyebrow">Command palette</p>
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
            placeholder="Jump to a project, tool, or action..."
            className="mt-3 w-full bg-transparent text-lg outline-none placeholder:text-[rgb(var(--muted-foreground))]"
            aria-label="Search commands"
          />
        </div>
        <div className="max-h-[27rem] overflow-y-auto p-2">
          {booksQuery.isLoading ? (
            <p className="px-3 py-4 text-sm text-[rgb(var(--muted-foreground))]">Loading project actions...</p>
          ) : visibleActions.length === 0 ? (
            <p className="px-3 py-4 text-sm text-[rgb(var(--muted-foreground))]">No matching commands.</p>
          ) : (
            visibleActions.map((action, index) => (
              <button
                key={action.id}
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
          <span>{isPending ? "Opening..." : "Ctrl/⌘ K"}</span>
        </div>
      </section>
    </div>
  )
}
