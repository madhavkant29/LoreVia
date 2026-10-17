"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import type { useCollaborationPage } from "./collaborationPage.state"
import { collaborationDate } from "./collaborationPage.helpers"

export function CollaborationActivity({ state, bookId, onClose }: { state: ReturnType<typeof useCollaborationPage>; bookId: string; onClose: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const [limit, setLimit] = useState(30)
  useEffect(() => { heading.current?.focus(); heading.current?.scrollIntoView({ block: "start", behavior: "smooth" }); setLimit(30) }, [state.selectedId])
  const { selected, activityQuery: query } = state
  const data = query.data
  return <section aria-labelledby="activity-heading" className="mt-8 scroll-mt-6 border-t pt-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><p className="text-sm text-[rgb(var(--muted-foreground))]">Recent collaboration activity</p><h2 ref={heading} tabIndex={-1} id="activity-heading" className="mt-2 break-words text-xl font-semibold">{selected?.display_name || selected?.email || "Collaborator no longer listed"}</h2>{selected?.display_name ? <p className="mt-1 break-all text-sm text-[rgb(var(--muted-foreground))]">{selected.email}</p> : null}</div><div className="flex gap-2"><button type="button" disabled={query.isFetching || !selected} className="app-button-secondary" onClick={() => void query.refetch()}>Refresh activity</button><button type="button" className="app-button-secondary" onClick={onClose}>Close activity</button></div></div>
    {query.isLoading ? <p role="status" className="py-6 text-sm">Loading activity…</p> : null}
    {query.isError ? <p role="alert" className="mt-4 text-sm">Could not load recent activity. <button type="button" disabled={query.isFetching} className="min-h-11 underline" onClick={() => void query.refetch()}>Retry activity</button></p> : null}
    {data ? <>
      <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3 border-y py-4 text-sm"><div><dt className="text-[rgb(var(--muted-foreground))]">Assignments</dt><dd className="mt-1 font-semibold">{data.assignments.length}</dd></div><div><dt className="text-[rgb(var(--muted-foreground))]">Chapter comments</dt><dd className="mt-1 font-semibold">{data.chapter_comment_count}</dd></div><div><dt className="text-[rgb(var(--muted-foreground))]">Annotations</dt><dd className="mt-1 font-semibold">{data.annotation_count}</dd></div></dl>
      {data.assignments.length ? <details className="mt-5"><summary className="min-h-11 cursor-pointer text-sm font-semibold">Beta assignments ({data.assignments.length})</summary><ul className="divide-y">{data.assignments.map(assignment => <li key={assignment.id} className="py-3 text-sm leading-6"><p className="font-semibold">{assignment.task_label}</p><p className="text-[rgb(var(--muted-foreground))]">{assignment.status_label} · {Math.round(assignment.progress_pct)}% progress</p></li>)}</ul><Link href={`/${bookId}/beta-feedback`} className="inline-flex min-h-11 items-center text-sm underline">Open beta reader assignments</Link></details> : null}
      <div className="mt-5 divide-y border-y">{data.items.slice(0, limit).map(item => <article key={item.id} className="grid gap-3 py-5 lg:grid-cols-[9rem_minmax(0,1fr)_11rem]"><div className="text-sm text-[rgb(var(--muted-foreground))]">{typeof item.chapter_number === "number" && item.chapter_number > 0 ? <Link className="inline-flex min-h-11 items-center underline" href={`/${bookId}/chapter/${item.chapter_number}`}>Chapter {item.chapter_number}</Link> : item.kind.replaceAll("_", " ")}</div><div className="min-w-0"><h3 className="text-sm font-semibold">{item.title}</h3>{item.body ? <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-7 text-[rgb(var(--muted-foreground))]">{item.body}</p> : null}</div><time dateTime={Number.isFinite(Date.parse(item.created_at)) ? item.created_at : undefined} className="text-sm text-[rgb(var(--muted-foreground))]">{collaborationDate(item.created_at)}</time></article>)}{!data.items.length ? <p className="py-6 text-sm text-[rgb(var(--muted-foreground))]">No activity recorded yet. Chapter comments, annotations, and beta milestones appear here as they are added.</p> : null}</div>
      {limit < data.items.length ? <button type="button" className="app-button-secondary mt-4" onClick={() => setLimit(value => value + 30)}>Show more activity ({data.items.length - limit} remaining)</button> : null}
    </> : null}
  </section>
}
