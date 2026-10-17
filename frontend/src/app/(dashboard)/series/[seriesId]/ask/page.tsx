"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { WorkspacePage, WorkspaceHeader } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { isPaidTier } from "@/lib/billing/plans"
import { asQueryKey, booksSeriesCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { loadAllSeries } from "../../seriesPage.helpers"
import { SeriesConversation } from "./seriesAsk.conversation"

export default function SeriesAskPage() {
  const { seriesId } = useParams<{ seriesId: string }>()
  const user = useAuthStore((state) => state.user)
  const hydrated = useAuthStore((state) => state.hydrated)
  const permitted = isPaidTier(user?.tier)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: asQueryKey(`${booksSeriesCacheKey()}:ask-complete:${user?.id}`),
    queryFn: async () => ({ items: await loadAllSeries() }),
    enabled: hydrated && permitted && Boolean(seriesId), retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false,
  })
  const series = data?.items.find((item) => item.id === seriesId)
  return <WorkspacePage><div data-series-workspace className="mx-auto max-w-4xl min-w-0 space-y-6 pb-12 [overflow-wrap:anywhere]">
    <Link href="/series" className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">← Back to series</Link>
    <header className="border-b border-[rgb(var(--border))] pb-6"><WorkspaceHeader eyebrow={series && permitted ? `Series Ask · ${series.books.length} ${series.books.length === 1 ? "project" : "projects"}` : "Connected projects"} title={series && permitted ? `Ask about ${series.name}` : "Series Ask"} description="Explore continuity, character development, plot, and shared lore across connected projects." actions={<button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>} /></header>
    {!hydrated ? <p role="status">Loading your account…</p> : !permitted ? <section><h2 className="text-xl font-semibold">Series mode is reserved for paid plans.</h2><p className="my-3 text-sm">Review the plans to use questions across connected projects.</p><Link href="/upgrade" className="app-button-secondary">View plans</Link></section> : isLoading ? <p role="status">Loading series context…</p> : isError ? <div role="alert"><p>Series context could not be loaded. Check your access or try again.</p><button type="button" className="app-button-secondary mt-3" onClick={() => void refetch()}>Retry series context</button></div> : !series ? <section><h2 className="text-xl font-semibold">Series not found</h2><p className="mt-3 text-sm">Return to Series and choose an available series.</p></section> : <SeriesConversation key={`${user?.id}:${series.id}`} series={series} />}
  </div></WorkspacePage>
}
