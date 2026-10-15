"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"
import Link from "next/link"
import type { Route } from "next"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type { BookVisibilitySummaryItem } from "@/types/uiPreferences"
import { VisibilityNavigation } from "./visibilityPage.navigation"
import { publicAccessStatus, visibilityStateLabel } from "./visibilityPage.helpers"

function VisibilityStatusRow({ title, item, explanation, countLabel }: { title: string; item: BookVisibilitySummaryItem; explanation: string; countLabel?: string }) {
  return <div className="grid gap-2 border-t py-5 sm:grid-cols-[11rem_minmax(0,1fr)_auto] sm:gap-5"><h3 className="text-base font-semibold">{title}</h3><div className="min-w-0">{!countLabel ? <p className="text-sm leading-6">{item.label}</p> : null}{item.detail && !countLabel ? <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[rgb(var(--muted-foreground))]">{item.detail}</p> : null}<p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{explanation}</p></div><p className="text-sm font-semibold sm:text-right">{countLabel ? typeof item.count === "number" && Number.isFinite(item.count) && item.count >= 0 ? `${item.count} ${item.count === 1 ? countLabel.slice(0, -1) : countLabel}` : "Count unavailable" : visibilityStateLabel(item)}</p></div>
}

export default function VisibilityCenterPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <VisibilityWorkspace key={bookId} bookId={bookId} />
}

function VisibilityWorkspace({ bookId }: { bookId: string }) {
  const bookQuery = useBookDetail(bookId)
  const book = bookQuery.data
  const owner = book?.access_class === "owner"
  const [showNavigation, setShowNavigation] = useState(false)
  const summaryQuery = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "visibility-summary")), queryFn: () => booksApi.getVisibilitySummary(bookId), enabled: owner, retry: false, staleTime: 20_000 })
  const summary = summaryQuery.data
  const refreshing = bookQuery.isFetching || summaryQuery.isFetching
  const refresh = () => Promise.all([bookQuery.refetch(), summaryQuery.refetch()])
  if (bookQuery.isLoading) return <div className="p-6" role="status">Loading access workspace…</div>
  if (!book) return <div className="p-6"><h1 className="text-2xl font-semibold">Access & Visibility</h1><p role="alert" className="my-4">This project could not be loaded. Check your access or try again.</p><button className="app-button-secondary" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry project</button><Link className="app-button-secondary ml-3" href="/library">Back to library</Link></div>
  if (!owner) return <div className="p-6"><h1 className="text-2xl font-semibold">Access & Visibility</h1><p className="my-4">Only the project owner can inspect sharing and publication status.</p><Link className="app-button-secondary" href={`/${bookId}`}>Return to project</Link></div>
  const publication = publicAccessStatus(book)
  return <main data-visibility-workspace className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
    <WorkspaceFamilyHeader active="visibility" bookId={bookId} family="publish-export" title="Access & Visibility" description={`Review workspace sharing and public access for ${book.title}. Each form of access is managed separately.`} actions={<><button className="app-button-secondary" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing access…" : "Refresh access"}</button><button className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></>} />
    {bookQuery.isError || summaryQuery.isError ? <div role="alert" className="mt-5 border-y py-4 text-sm leading-6"><p>{summary ? "Access status could not be refreshed. The last loaded information is shown below and may be out of date." : "Visibility status could not be loaded."}</p><button className="app-button-secondary mt-3" disabled={refreshing} onClick={() => void refresh()}>Retry access status</button></div> : null}
    {summaryQuery.isLoading ? <p role="status" className="py-8 text-sm">Checking who can access this book…</p> : null}
    {summary ? <section aria-labelledby="current-access-heading" className="mt-6">
      <div className="grid gap-5 pb-6 md:grid-cols-2"><div><p className="text-sm text-[rgb(var(--muted-foreground))]">Workspace access</p><h2 id="current-access-heading" className="mt-2 text-xl font-semibold">{summary.private_status.label}</h2><p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{summary.private_status.detail || "Only authorized workspace users can access this project."}</p></div><div className="border-l-2 border-[rgb(var(--accent))] pl-4"><p className="text-sm text-[rgb(var(--muted-foreground))]">Public reading access</p><h2 className="mt-2 text-xl font-semibold">{publication.label}</h2><p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{publication.detail}</p>{publication.href ? <Link href={publication.href as Route} className="app-button-secondary mt-3">Open public page</Link> : null}</div></div>
      <p className="mb-4 text-sm text-[rgb(var(--muted-foreground))]">Last loaded {new Date(Math.min(bookQuery.dataUpdatedAt, summaryQuery.dataUpdatedAt)).toLocaleTimeString()}. Refresh after changing access elsewhere.</p>
      <VisibilityStatusRow title="Collaborators" item={summary.collaborators} explanation="Active collaborator records. Revoking one does not remove separate beta or public access." />
      <VisibilityStatusRow title="Beta assignments" countLabel="assignments" item={summary.beta_readers} explanation="Assignment records excluding revoked and disqualified assignments. This is not a count of unique readers or currently open reading windows." />
      <VisibilityStatusRow title="Public publishing" item={summary.public_publishing} explanation="Publication and visibility settings are separate from private workspace access. Review submissions and publication settings in Public uploads." />
      <VisibilityStatusRow title="Discussion records" countLabel="posts" item={summary.public_discussion} explanation="Discussion records excluding removed posts. This includes posts awaiting moderation, so it is not a count of publicly visible posts." />
      <div className="flex flex-wrap gap-3 border-t pt-5"><Link href={`/${bookId}/collaboration`} className="app-button-secondary">Manage collaborators</Link><Link href={`/${bookId}/beta-feedback`} className="app-button-secondary">Manage beta readers</Link><Link href="/public/uploads" className="app-button-secondary">Manage public uploads</Link></div>
      <details className="mt-6 border-y py-4"><summary className="min-h-11 cursor-pointer font-semibold">Rights and moderation</summary><VisibilityStatusRow title="Rights" item={summary.rights} explanation="Rights confirmation records the owner’s declaration for publication." /><VisibilityStatusRow title="Moderation" item={summary.moderation} explanation="Moderation can restrict public access even when a public URL has been reserved." /></details>
    </section> : !summaryQuery.isLoading && !summaryQuery.isError ? <div role="alert" className="py-6"><p>Access information is unavailable.</p><button className="app-button-secondary mt-3" onClick={() => void refresh()}>Retry access status</button></div> : null}
    <details className="mt-8 border-y py-5" onToggle={event => setShowNavigation(event.currentTarget.open)}><summary className="min-h-11 cursor-pointer font-semibold">Advanced: workspace navigation</summary>{showNavigation ? <VisibilityNavigation book={book} preferenceBookId={normalizeBookRouteId(bookId)} /> : null}</details>
  </main>
}
