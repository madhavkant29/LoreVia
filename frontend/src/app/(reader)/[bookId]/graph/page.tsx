"use client"

import dynamic from "next/dynamic"
import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useSearchParams } from "next/navigation"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { readerApi } from "@/lib/api/reader"
import { capture } from "@/lib/analytics/posthog"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { graphChapterChoices } from "./graphPage.helpers"
import type { RelationshipEvolutionPair } from "@/types/reader"

const RelationshipGraph = dynamic(() => import("@/components/intelligence/RelationshipGraph"), {
  ssr: false,
  loading: () => <p role="status" className="py-10 text-sm text-[rgb(var(--muted-foreground))]">Loading relationship graph…</p>,
})
const buttonClass = "app-button-secondary !rounded-sm disabled:cursor-not-allowed disabled:opacity-50"

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <GraphWorkspace key={bookId} bookId={bookId} />
}

function GraphWorkspace({ bookId }: { bookId: string }) {
  const searchParams = useSearchParams()
  const { theme } = usePreferencesStore()
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const book = useBookDetail(bookId)
  const chapters = useQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId),
  })
  const authorMode = book.data?.mode === "author"
  const choices = useMemo(() => graphChapterChoices(chapters.data?.chapters ?? [], authorMode), [chapters.data, authorMode])
  const chapter = choices.find((item) => item.number === selectedChapter)?.number ?? choices.at(-1)?.number ?? 0
  const activeView = searchParams.get("view") === "evolution" ? "evolution" : "map"
  const ready = !!book.data && !!chapters.data && chapter > 0
  const evolution = useQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, `relationship-evolution:${chapter}`)),
    queryFn: () => readerApi.getRelationshipEvolution(bookId, chapter),
    enabled: activeView === "evolution" && ready,
  })

  useEffect(() => { capture("graph_opened", { book_id: bookId }) }, [bookId])

  return <div className="app-shell min-h-screen">
    <main data-relationship-workspace className="mx-auto flex w-full min-w-0 max-w-[1680px] flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8 [overflow-wrap:anywhere]">
      <WorkspaceFamilyHeader active="relationships" bookId={bookId} family="story-bible" title="Relationships"
        description={activeView === "map" ? "Inspect the character network. Select a character or connection to review its evidence and details." : "Follow the chapter events that changed alliances, tensions, and other relationships."}
        actions={<button type="button" className={buttonClass} onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>} />
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[rgb(var(--border))]">
        <nav aria-label="Relationship views" className="flex gap-6">
          {(["map", "evolution"] as const).map((view) => <Link key={view} href={`/${bookId}/graph${view === "map" ? "" : "?view=evolution"}`} aria-current={activeView === view ? "page" : undefined} className={`border-b-2 px-1 pb-3 text-sm font-medium ${activeView === view ? "border-[rgb(var(--accent))] text-[rgb(var(--foreground))]" : "border-transparent text-[rgb(var(--muted-foreground))]"}`}>{view === "map" ? "Map" : "Evolution"}</Link>)}
        </nav>
        {ready ? <label className="mb-3 flex min-w-0 flex-wrap items-center gap-2 text-sm">
          <span>{authorMode ? "Through manuscript chapter" : "Through read chapter"}</span>
          <select data-graph-scope data-graph-current={chapter} aria-label={authorMode ? "Up to manuscript chapter" : "Up to read chapter"} value={chapter} onChange={(event) => setSelectedChapter(Number(event.target.value))} className="min-h-10 w-full max-w-xs rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm text-[rgb(var(--foreground))] sm:w-64">
            {choices.map((item) => <option key={item.number} value={item.number}>Chapter {item.number}{item.title ? ` — ${item.title}` : ""}</option>)}
          </select>
        </label> : null}
      </div>
      {book.isLoading || chapters.isLoading ? <p role="status" className="py-6 text-sm text-[rgb(var(--muted-foreground))]">Loading available chapters…</p> : null}
      {book.isError ? <div role="alert" className="border-l-2 border-amber-500 pl-4 text-sm"><p>Book access details could not load.</p><button type="button" className={`${buttonClass} mt-2`} disabled={book.isFetching} onClick={() => void book.refetch()}>Retry book details</button></div> : null}
      {chapters.isError ? <div role="alert" className="border-l-2 border-amber-500 pl-4 text-sm"><p>Available chapters could not load.</p><button type="button" className={`${buttonClass} mt-2`} disabled={chapters.isFetching} onClick={() => void chapters.refetch()}>Retry chapters</button></div> : null}
      {!book.isLoading && !chapters.isLoading && !book.isError && !chapters.isError && !chapter ? <section className="py-6"><h2 className="text-lg font-semibold">No chapters available for relationships yet</h2><p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{authorMode ? "Check manuscript analysis progress to make character and relationship evidence available." : "Read an available chapter to begin exploring the story's relationships."}</p><Link className={`${buttonClass} mt-4`} href={`/${bookId}/chapters`}>View chapters</Link></section> : null}
      {ready ? activeView === "map" ? <RelationshipGraph key={chapter} bookId={bookId} upToChapter={chapter} theme={theme === "dark" ? "dark" : "light"} authorMode={authorMode && book.data?.access_class === "owner"} /> : <>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm"><p className="text-[rgb(var(--muted-foreground))]">Recorded changes through chapter {chapter}.</p><button type="button" className={buttonClass} disabled={evolution.isFetching} onClick={() => void evolution.refetch()}>{evolution.isFetching ? "Refreshing…" : "Refresh history"}</button></div>
        {evolution.isLoading ? <p role="status" className="py-6 text-sm text-[rgb(var(--muted-foreground))]">Loading relationship history...</p> : null}
        {evolution.isError ? <div role="alert" className="border-l-2 border-amber-500 pl-4 text-sm"><p>Relationship history could not load.{evolution.data ? " Previously loaded changes remain visible." : ""}</p><button type="button" className={`${buttonClass} mt-2`} disabled={evolution.isFetching} onClick={() => void evolution.refetch()}>Retry history</button></div> : null}
        {evolution.data ? <RelationshipEvolutionView bookId={bookId} chapter={chapter} pairs={evolution.data.pairs} availableChapters={choices.map((item) => item.number)} /> : null}
      </> : null}
    </main>
  </div>
}

function RelationshipEvolutionView({ bookId, chapter, pairs, availableChapters }: { bookId: string; chapter: number; pairs: RelationshipEvolutionPair[]; availableChapters: number[] }) {
  if (!pairs.length) return <div className="py-6 text-sm leading-6 text-[rgb(var(--muted-foreground))]">No relationship changes are recorded through chapter {chapter}. Choose a later available chapter or review the character map.</div>
  return <section aria-label="Relationship history" className="divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">
    {pairs.map((pair) => <div key={pair.characters.join("-")} className="grid gap-4 py-5 md:grid-cols-[15rem_minmax(0,1fr)]">
      <div><h2 className="text-base font-semibold">{pair.characters.join(" ↔ ")}</h2><p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">{pair.events.length} recorded {pair.events.length === 1 ? "change" : "changes"}</p></div>
      <ol className="divide-y divide-[rgb(var(--border))]">{pair.events.map((event, index) => <li key={`${event.chapter}-${event.type}-${index}`} className="grid gap-2 py-3 first:pt-0 last:pb-0 sm:grid-cols-[7rem_minmax(0,1fr)]">
        <div className="text-sm">{availableChapters.includes(event.chapter) ? <Link className="underline underline-offset-4" href={`/${bookId}/chapter/${event.chapter}`}>Chapter {event.chapter}</Link> : <span>Chapter unavailable</span>}</div>
        <div><p className="text-sm font-semibold capitalize">{event.type.replaceAll("_", " ")}</p>{event.description ? <p className="mt-1 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{event.description}</p> : <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">No description recorded.</p>}</div>
      </li>)}</ol>
    </div>)}
  </section>
}
