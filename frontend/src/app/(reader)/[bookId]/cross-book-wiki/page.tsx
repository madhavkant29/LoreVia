"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { useAuthStore } from "@/lib/stores/authStore"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey, booksSelectorCacheKey } from "@/lib/query/cacheKeys"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { SeriesReferenceList } from "./seriesWikiPage.components"
import { filterSeriesReferences, seriesComparisonIds, seriesReferences, type ReferenceType } from "./seriesWikiPage.helpers"

export default function CrossBookWikiPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <SeriesWikiWorkspace key={bookId} bookId={bookId} />
}

function SeriesWikiWorkspace({ bookId }: { bookId: string }) {
  const bookQuery = useBookDetail(bookId)
  const book = bookQuery.data
  const user = useAuthStore(state => state.user)
  const owner = book?.access_class === "owner"
  const paid = canUseAuthorFeatures(user?.tier)
  const enabled = owner && paid
  const intelligence = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "cross-book-wiki")), queryFn: () => intelligenceApi.getCrossBookIntelligence(bookId), enabled, retry: false, staleTime: 20_000 })
  const titles = useQuery({ queryKey: asQueryKey(booksSelectorCacheKey()), queryFn: () => booksApi.listSelector(), enabled, retry: false, staleTime: 60_000 })
  const [mode, setMode] = useState<"all" | ReferenceType>("all")
  const [scope, setScope] = useState<"current" | "series">("current")
  const [threshold, setThreshold] = useState(90)
  const [query, setQuery] = useState("")
  const [limit, setLimit] = useState(25)
  const [selectedKey, setSelectedKey] = useState<string | null | undefined>(undefined)
  const ids = seriesComparisonIds(intelligence.data)
  const normalizedId = normalizeBookRouteId(bookId)
  const result = seriesReferences(intelligence.data, [...(titles.data ?? []), ...(book ? [book] : [])], normalizedId)
  const references = filterSeriesReferences(result.references, { mode, scope, threshold, query })
  const selected = selectedKey === undefined ? references[0] ?? null : references.find(item => item.key === selectedKey) ?? null
  const resetSelection = () => { setSelectedKey(undefined); setLimit(25) }
  const clearFilters = () => { setQuery(""); setMode("all"); setThreshold(90); setScope("current"); resetSelection() }
  const refresh = () => Promise.all([intelligence.refetch(), titles.refetch()])
  if (bookQuery.isLoading) return <div role="status" className="p-6">Loading series workspace…</div>
  if (!book) return <div className="p-6"><h1 className="text-2xl font-semibold">Series wiki</h1><p role="alert" className="my-4">This project could not be loaded.</p><button className="app-button-secondary" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry project</button></div>
  if (!owner) return <div className="p-6"><h1 className="text-2xl font-semibold">Series wiki</h1><p className="my-4">Only the project owner can compare references across their books.</p><Link href={`/${bookId}`} className="app-button-secondary">Return to project</Link></div>
  if (!paid) return <div className="p-6"><h1 className="text-2xl font-semibold">Series wiki</h1><p className="my-4">Series comparisons require an Author or Architect plan.</p><Link href="/upgrade" className="app-button-secondary">View plans</Link></div>
  return <main data-series-wiki-workspace className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
    <WorkspaceFamilyHeader active="cross-book-wiki" bookId={bookId} family="story-bible" title="Series wiki" description={`Compare recurring characters and lore across ${book.title} and the other books in its primary series.`} actions={<><Link href="/series" className="app-button-secondary">Manage series</Link><button className="app-button-secondary" disabled={intelligence.isFetching || titles.isFetching} onClick={() => void refresh()}>{intelligence.isFetching ? "Refreshing…" : "Refresh references"}</button><button className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></>} />
    {bookQuery.isError ? <p role="alert" className="mt-4 text-sm leading-6">Project details could not be refreshed. <button className="min-h-11 underline" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry project</button></p> : null}
    {intelligence.isError ? <div role="alert" className="mt-5 border-y py-4 text-sm leading-6"><p>Series references could not be loaded.{intelligence.data ? " The last loaded comparison is still shown and may be out of date." : " No comparison result is available yet."}</p><button className="app-button-secondary mt-3" disabled={intelligence.isFetching} onClick={() => void intelligence.refetch()}>Retry references</button></div> : null}
    {titles.isError ? <p role="alert" className="mt-4 text-sm leading-6">Book titles could not be loaded. References remain available using book identifiers or last loaded titles. <button className="min-h-11 underline" disabled={titles.isFetching} onClick={() => void titles.refetch()}>Retry book titles</button></p> : null}
    {intelligence.isLoading ? <p role="status" className="py-8 text-sm">Loading series references…</p> : null}
    {intelligence.data ? <>
      <section aria-label="Comparison scope" className="mt-6 border-b pb-5"><h2 className="text-xl font-semibold">{intelligence.data.series_name || "No primary series assigned"}</h2><p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{ids.length} books in this comparison · {result.references.length} returned reference pairs. Only books you own in this project’s primary series are compared.</p><p className="mt-2 max-w-4xl text-sm leading-6 text-[rgb(var(--muted-foreground))]">The service returns up to 20 character pairs and 20 wiki pairs with at least 90% similarity. It compares stored descriptions; missing matches do not prove that a reference is absent. Refresh reloads the comparison and may use stored results.</p><details className="mt-3"><summary className="min-h-11 cursor-pointer text-sm font-semibold">Books included ({ids.length})</summary><ul className="divide-y border-y">{ids.map(id => <li className="py-3 text-sm" key={id}><Link className="inline-flex min-h-11 items-center underline" href={`/${encodeURIComponent(id)}`}>{id === normalizedId ? book.title : titles.data?.find(item => normalizeBookRouteId(item.id) === id)?.title || `Book ${id}`}</Link>{id === normalizedId ? " · Current book" : ""}</li>)}</ul></details></section>
      {result.omitted ? <p role="status" className="mt-4 text-sm leading-6">{result.omitted} incomplete or invalid comparison records were omitted. Refresh references to check for an updated result.</p> : null}
      <div className="mt-5 grid gap-4 border-b pb-5 sm:grid-cols-2 lg:grid-cols-4">
        <label className="grid gap-2 text-sm">Search references<input type="search" aria-label="Search references" placeholder="Name, book, or entry type" className="app-input" value={query} onChange={event => { setQuery(event.target.value); resetSelection() }} /></label>
        <label className="grid gap-2 text-sm">Reference type<select aria-label="Reference type" className="app-input" value={mode} onChange={event => { setMode(event.target.value as "all" | ReferenceType); resetSelection() }}><option value="all">All references</option><option value="characters">Characters</option><option value="wiki">Wiki entries</option></select></label>
        <label className="grid gap-2 text-sm">Book scope<select className="app-input" value={scope} onChange={event => { setScope(event.target.value as "current" | "series"); resetSelection() }}><option value="current">Involving this book</option><option value="series">Whole series</option></select></label>
        <label className="grid gap-2 text-sm">Minimum similarity<select aria-label="Minimum similarity" className="app-input" value={threshold} onChange={event => { setThreshold(Number(event.target.value)); resetSelection() }}><option value={90}>90% and above</option><option value={95}>95% and above</option><option value={98}>98% and above</option><option value={100}>100%</option></select></label>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p role="status" className="text-sm text-[rgb(var(--muted-foreground))]">Showing {Math.min(limit, references.length)} of {references.length} matching pairs</p><button className="app-button-secondary" onClick={clearFilters}>Reset filters</button></div>
      {references.length ? <><SeriesReferenceList references={references.slice(0, limit)} selected={selected} onSelect={setSelectedKey} onToggle={key => setSelectedKey(selected?.key === key ? null : key)} />{references.length > limit ? <button className="app-button-secondary mt-4" onClick={() => setLimit(value => value + 25)}>Show more references ({references.length - limit} remaining)</button> : null}</> : <section className="mt-5 border-y py-8"><h2 className="text-xl font-semibold">No matches found</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-[rgb(var(--muted-foreground))]">{ids.length < 2 ? "Add at least two of your books to the same primary series before comparing references." : !result.references.length ? "No indexed reference pairs were returned at the service’s 90% minimum. Confirm that the books have processed characters and wiki entries. This comparison is not an exhaustive canon check." : "No returned pairs match these filters. Reset the filters or choose Whole series to inspect pairs between other books."}</p><div className="mt-4 flex flex-wrap gap-3"><Link href="/series" className="app-button-secondary">Review series membership</Link>{result.references.length ? <button className="app-button-secondary" onClick={() => { clearFilters(); setScope("series") }}>Show whole series</button> : null}</div></section>}
    </> : !intelligence.isLoading && !intelligence.isError ? <p role="alert" className="py-6">No comparison response is available. Use Refresh references to try again.</p> : null}
  </main>
}
