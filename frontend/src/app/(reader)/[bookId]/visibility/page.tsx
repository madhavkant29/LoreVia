"use client"

import { useEffect, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import { useParams } from "next/navigation"
import Link from "next/link"
import type { Route } from "next"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { Button } from "@/components/ui/Button"
import { useStatusToast } from "@/components/ui/StatusToast"
import { VisibilityBadge, type VisibilityBadgeState } from "@/components/ui/VisibilityBadge"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { defaultBookUiPreference, useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { getBookHref, normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { toolsForPlacement } from "@/lib/workspace/toolRegistry"
import { resolveWorkspaceTools } from "@/lib/workspace/toolResolver"
import type { Book } from "@/types/book"
import type { BookVisibilitySummary, BookVisibilitySummaryItem } from "@/types/uiPreferences"

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-md border border-white/[0.065] bg-[#0d141c] p-4" />,
  },
)

const BOOK_TOOLS = toolsForPlacement("book").filter((tool) => !tool.nonHideable)

function statusTone(state: string) {
  if (["published", "public", "active", "shared", "confirmed", "clean"].includes(state)) {
    return "success"
  }
  if (["pending", "pending_review", "unconfirmed", "under_review", "reported"].includes(state)) {
    return "warning"
  }
  return "neutral"
}

function visibilityBadgeState(label: string): VisibilityBadgeState {
  const normalized = label.toLowerCase()
  if (normalized.includes("discussion")) return "public_discussion"
  if (normalized.includes("public")) return "public_sample"
  if (normalized.includes("beta")) return "beta_readers"
  if (normalized.includes("shared")) return "shared"
  return "private"
}

function VisibilityStatusCard({
  item,
  isDark,
}: {
  item: BookVisibilitySummaryItem
  isDark: boolean
}) {
  const tone = statusTone(item.state)
  const toneClass =
    tone === "success"
      ? "bg-emerald-500/12 text-emerald-300"
      : tone === "warning"
        ? "bg-amber-500/12 text-amber-300"
        : isDark
          ? "bg-white/[0.06] text-slate-300"
          : "bg-slate-100 text-slate-600"
  return (
    <article className={`rounded-md border p-4 ${isDark ? "border-white/[0.07] bg-[#101720]" : "border-slate-200 bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{item.label}</h2>
          {item.detail ? (
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>{item.detail}</p>
          ) : null}
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${toneClass}`}>
          {item.count ?? item.state.replace(/_/g, " ")}
        </span>
      </div>
    </article>
  )
}

export default function VisibilityCenterPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const preferenceBookId = normalizeBookRouteId(bookId)
  const { theme } = usePreferencesStore()
  const notify = useStatusToast()
  const isDark = theme === "dark"
  const hydrateBook = useUiPreferencesStore((state) => state.hydrateBook)
  const bookPreferences = useUiPreferencesStore((state) => state.bookPreferences)
  const setBookToolHidden = useUiPreferencesStore((state) => state.setBookToolHidden)
  const setBookPreset = useUiPreferencesStore((state) => state.setBookPreset)
  const patchBook = useUiPreferencesStore((state) => state.patchBook)
  const setComplexityMode = useUiPreferencesStore((state) => state.setComplexityMode)
  const globalPreference = useUiPreferencesStore((state) => state.preferences)
  const retrySync = useUiPreferencesStore((state) => state.retrySync)
  const syncState = useUiPreferencesStore((state) => state.syncState)
  const syncMessage = useUiPreferencesStore((state) => state.syncMessage)
  const bookPreference = bookPreferences[preferenceBookId]
    ?? defaultBookUiPreference(preferenceBookId, globalPreference.complexity_mode)

  useEffect(() => {
    void hydrateBook(preferenceBookId)
  }, [hydrateBook, preferenceBookId])

  const { data: book = null } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const { data: summary = null, isLoading, isError, refetch } = useQuery<BookVisibilitySummary | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "visibility-summary")),
    queryFn: () => booksApi.getVisibilitySummary(bookId),
  })

  const resolvedTools = useMemo(
    () => resolveWorkspaceTools(BOOK_TOOLS, {
      mode: globalPreference.complexity_mode,
      book,
      bookPreference,
      globalPreference,
      placement: "book",
      hasAuthorAccess: true,
    }),
    [book, bookPreference, globalPreference],
  )
  const hiddenTools = resolvedTools.filter((tool) => tool.hidden)
  const visibleRecoverableTools = resolvedTools.filter((tool) => !tool.hidden)

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#070b10] text-slate-100" : "bg-[#f7f7fb] text-slate-950"}`}>
      <div className="mx-auto grid max-w-[94rem] gap-5 px-4 pb-28 pt-5 sm:px-6 lg:grid-cols-[18rem_minmax(0,1fr)] lg:px-8">
        <div className="hidden lg:block lg:sticky lg:top-5 lg:self-start">
          <AuthorToolsNav
            bookId={bookId}
            active="visibility"
            isDark={isDark}
            bookData={book}
            title="Author workspace"
            description="Visibility, sharing, and recovery controls for this project."
            mode={book?.workspace_shell ?? "author"}
            variant="rail"
            railSize="compact"
          />
        </div>

        <main className="min-w-0 space-y-5">
          <Link
            href={(book ? getBookHref(book) : `/${bookId}`) as Route}
            className={`inline-flex min-h-11 items-center rounded-md border px-4 text-sm font-semibold lg:hidden ${isDark ? "border-white/10 text-slate-100" : "border-slate-200 text-slate-800"}`}
          >
            Back to book
          </Link>
          <WorkspaceFamilyHeader
            active="visibility"
            bookId={bookId}
            family="publish-export"
            title={`${book?.title ?? "Project"} visibility`}
            description="Private workspace state, collaborator access, beta-read access, public publishing, and hidden-tool recovery."
          />

          {syncMessage ? (
            <div role="status" aria-live="polite" className={`flex flex-col gap-3 rounded-md border p-4 sm:flex-row sm:items-center sm:justify-between ${isDark ? "border-amber-400/20 bg-amber-400/8 text-amber-200" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              <span className="text-sm font-semibold">{syncMessage}</span>
              {syncState === "sync_pending" ? (
                <Button variant="secondary" size="sm" onClick={() => void retrySync()}>
                  Retry
                </Button>
              ) : null}
            </div>
          ) : null}

          <section className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className={`text-lg font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>Status</h1>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(summary?.badges ?? []).map((badge) => (
                    <VisibilityBadge key={badge} state={visibilityBadgeState(badge)} label={badge} />
                  ))}
                  {isLoading ? <span className="text-sm text-[rgb(var(--muted-foreground))]">Checking visibility...</span> : null}
                  {isError ? <span className="text-sm text-rose-400">Status unavailable</span> : null}
                </div>
              </div>
              {summary?.public_url ? (
                <a
                  href={summary.public_url}
                  className={`inline-flex h-11 items-center justify-center rounded-md border px-4 text-sm font-semibold ${isDark ? "border-white/[0.08] text-white hover:bg-white/[0.05]" : "border-slate-200 text-slate-800 hover:bg-slate-50"}`}
                >
                  Open public page
                </a>
              ) : null}
            </div>

            {isLoading ? (
              <p className={`mt-5 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Loading visibility status...</p>
            ) : summary && !isError ? (
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <VisibilityStatusCard item={summary.private_status} isDark={isDark} />
                <VisibilityStatusCard item={summary.collaborators} isDark={isDark} />
                <VisibilityStatusCard item={summary.beta_readers} isDark={isDark} />
                <VisibilityStatusCard item={summary.public_publishing} isDark={isDark} />
                <VisibilityStatusCard item={summary.public_discussion} isDark={isDark} />
                <VisibilityStatusCard item={summary.rights} isDark={isDark} />
                <VisibilityStatusCard item={summary.moderation} isDark={isDark} />
              </div>
            ) : (
              <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-rose-400/20 bg-rose-400/8 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-sm font-semibold">Visibility status could not be loaded.</span>
                  <Button variant="secondary" size="sm" onClick={() => void refetch()}>
                    Retry
                  </Button>
                </div>
              </div>
            )}
          </section>

          <section className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Workspace Tools</h2>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Hidden tools stay reachable through command search, this page, and direct URLs.
                </p>
              </div>
              <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                {hiddenTools.length} hidden
              </span>
            </div>

            <div className="mt-5 grid gap-3 lg:grid-cols-2">
              {hiddenTools.length ? (
                hiddenTools.map(({ tool, reason }) => (
                  <article key={tool.id} className={`rounded-md border p-4 ${isDark ? "border-white/[0.07] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{tool.label}</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{tool.group} / {reason?.replace(/_/g, " ")}</p>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        aria-label={`Show ${tool.label}`}
                        onClick={() => {
                          if (reason === "hidden_by_user") void setBookToolHidden(preferenceBookId, tool.id, false)
                          else if (reason === "hidden_by_preset") void setBookPreset(preferenceBookId, "all")
                          else if (tool.complexity === "advanced") void patchBook(preferenceBookId, [{ op: "set", path: "/advanced_tool_override", value: "show" }])
                          else void setComplexityMode("standard")
                        }}
                      >
                        {reason === "hidden_by_user" ? "Show" : reason === "hidden_by_preset" ? "Use All" : "Reveal"}
                      </Button>
                    </div>
                  </article>
                ))
              ) : (
                <div className={`rounded-md border border-dashed p-5 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-500"}`}>
                  No tools are hidden for this book.
                </div>
              )}

              {visibleRecoverableTools.map(({ tool }) => (
                <article key={tool.id} className={`rounded-md border p-4 ${isDark ? "border-white/[0.07] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{tool.label}</p>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{tool.group}</p>
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      aria-label={`Hide ${tool.label}`}
                      onClick={() => {
                        void setBookToolHidden(preferenceBookId, tool.id, true)
                        notify({
                          title: `${tool.label} hidden`,
                          body: "The tool remains available from command search and this Visibility Center.",
                          actionLabel: "Undo",
                          onAction: () => void setBookToolHidden(preferenceBookId, tool.id, false),
                        })
                      }}
                    >
                      Hide
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}
