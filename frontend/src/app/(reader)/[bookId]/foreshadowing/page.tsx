"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspaceEmptyState, WorkspacePage, WorkspacePanel } from "@/components/ui/Workspace"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { ForeshadowingItem } from "@/types/reader"

export default function ForeshadowingPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const { data, isLoading: loading } = useQuery({
    queryKey: asQueryKey(`reader:${bookId}:foreshadowing`),
    queryFn: () => readerApi.getForeshadowing(bookId),
  })
  const items: ForeshadowingItem[] = data?.items ?? []
  const error = !loading && !data ? "Foreshadowing unavailable" : null

  return (
    <WorkspacePage className={isDark ? "text-stone-100" : "text-slate-950"}>
      <div className="mx-auto max-w-5xl px-0 pb-16 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="foreshadowing"
          bookId={bookId}
          family="story-bible"
          title="Foreshadowing signals"
          description="Review planted details and early clues from available chapters without exposing unread material."
          actions={(
            <Link href="/library" className="app-button-secondary">
              Library
            </Link>
          )}
        />

        {error ? <div className={`mt-6 rounded-md border px-4 py-3 text-sm ${isDark ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>{error}</div> : null}

        {loading ? (
          <WorkspacePanel tone="subtle" className="mt-6 px-6 py-10 text-center text-sm text-[rgb(var(--muted-foreground))]">
            Pulling together the strongest hints from your available chapters...
          </WorkspacePanel>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <WorkspaceEmptyState
            className="mt-6"
            title="No foreshadowing highlights yet"
            body="LoreVia will show them here as soon as it finds clear clue patterns in the chapters you have already read."
          />
        ) : null}

        <div className="mt-6 grid gap-4">
          {items.map((item, index) => (
            <WorkspacePanel key={`${item.chapter_number}-${index}`} className="p-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className={isDark ? "rounded-full bg-amber-300/10 px-3 py-1 text-3xs font-semibold uppercase tracking-[0.22em] text-amber-100" : "rounded-full bg-amber-100 px-3 py-1 text-3xs font-semibold uppercase tracking-[0.22em] text-amber-800"}>
                  Chapter {item.chapter_number}
                </span>
                {item.chapter_title ? <span className={isDark ? "text-xs text-stone-400" : "text-xs text-slate-500"}>{item.chapter_title}</span> : null}
              </div>
              <p className={`mt-4 text-lg font-semibold leading-8 ${isDark ? "text-white" : "text-slate-950"}`}>{item.clue}</p>
              {item.foreshadows ? (
                <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>{item.foreshadows}</p>
              ) : (
                <p className={`mt-3 text-sm italic ${isDark ? "text-stone-500" : "text-slate-400"}`}>LoreVia found a notable clue here, but the follow-through description is still sparse.</p>
              )}
            </WorkspacePanel>
          ))}
        </div>
      </div>
    </WorkspacePage>
  )
}
