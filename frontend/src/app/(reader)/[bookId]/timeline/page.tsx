"use client"

import { useEffect, useMemo, useState } from "react"
import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"
import Link from "next/link"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { defaultBookUiPreference, useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { capture } from "@/lib/analytics/posthog"
import { nextTimelineEventOffset, timelineItems, type TimelineLane, type TimelineView } from "./timelinePage.helpers"
import { TimelineLanes, TimelineList, TimelineSource, timelineButton, timelineMuted } from "./timelinePage.components"

export default function TimelinePage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <TimelineWorkspace key={bookId} bookId={bookId} />
}

function TimelineWorkspace({ bookId }: { bookId: string }) {
  const { theme } = usePreferencesStore()
  const preferenceBookId = normalizeBookRouteId(bookId)
  const hydrateBookPreferences = useUiPreferencesStore((state) => state.hydrateBook)
  const patchBookPreferences = useUiPreferencesStore((state) => state.patchBook)
  const setTimelineCollapsedSection = useUiPreferencesStore((state) => state.setTimelineCollapsedSection)
  const complexityMode = useUiPreferencesStore((state) => state.preferences.complexity_mode)
  const storedBookPreference = useUiPreferencesStore((state) => state.bookPreferences[preferenceBookId])
  const collapsed = (storedBookPreference ?? defaultBookUiPreference(preferenceBookId, complexityMode)).timeline_collapsed_sections
  const isDark = theme === "dark"
  const [activeLane, setActiveLane] = useState<TimelineLane>("all")
  const [view, setView] = useState<TimelineView>("auto")

  useEffect(() => {
    capture("major_events_opened", { book_id: bookId })
    void hydrateBookPreferences(preferenceBookId)
  }, [bookId, hydrateBookPreferences, preferenceBookId])

  const book = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "detail")), queryFn: () => booksApi.get(bookId), staleTime: 20_000 })
  const timeline = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "timeline")), queryFn: () => readerApi.getTimeline(bookId), staleTime: 45_000 })
  // Fetch events separately: the default timeline request only includes structural tracks.
  const events = useInfiniteQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, "timeline:events")),
    queryFn: ({ pageParam }) => readerApi.getTimeline(bookId, { include: "events", limit: 100, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _pages, lastOffset) => nextTimelineEventOffset(lastPage, lastOffset),
    staleTime: 45_000,
    enabled: !!timeline.data?.chapters.length,
  })
  const chapters = timeline.data?.chapters ?? []
  const items = useMemo(() => timeline.data ? timelineItems(timeline.data, activeLane) : [], [timeline.data, activeLane])
  const storyEvents = events.data?.pages.flatMap((page) => page.events ?? []) ?? []
  const totalEvents = events.data?.pages[0]?.total_events
  const allCollapsed = !!(collapsed.characters && collapsed.plotThreads && collapsed.relationships)
  const showEvents = activeLane === "all" || activeLane === "events"
  const laneClass = view === "auto" ? "hidden md:block" : view === "list" ? "hidden" : "block"
  const listClass = view === "auto" ? "md:hidden" : view === "lanes" ? "hidden" : "block"
  const controlClass = `min-h-10 rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/20 bg-[#111718] text-slate-100" : "border-stone-300 bg-white text-stone-950"}`

  return <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
    <main data-timeline-workspace className="mx-auto min-w-0 max-w-[1600px] px-0 pb-16 pt-6 sm:px-2 lg:px-4 [overflow-wrap:anywhere]">
      <WorkspaceFamilyHeader active="timeline" bookId={bookId} family="story-bible" title={book.data?.mode === "author" ? "Arc timeline" : "Major events"}
        description={book.data?.mode === "author" ? "Trace character spans, plot threads, and relationship turns. Open a chapter to review its context." : "Review a spoiler-safe structural map of the story so far. Only available chapters are shown."}
        actions={<>
          <button type="button" className={timelineButton} disabled={timeline.isFetching || events.isFetching} onClick={() => { void timeline.refetch(); if (chapters.length) void events.refetch() }}>{timeline.isFetching || events.isFetching ? "Refreshing…" : "Refresh timeline"}</button>
          <button type="button" className={timelineButton} onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>
        </>} />

      {book.isError ? <div role="alert" className="mt-4 border-l-2 border-amber-500 pl-4 text-sm"><p>Book details could not load. Your available timeline is shown below.</p><button type="button" className={`${timelineButton} mt-2`} disabled={book.isFetching} onClick={() => void book.refetch()}>Retry book details</button></div> : null}
      {timeline.isError ? <div role="alert" className="mt-5 border-l-2 border-amber-500 pl-4 text-sm"><p>{timeline.data ? "Timeline refresh failed. Previously loaded tracks remain visible." : "Major events unavailable. The timeline could not load."}</p><button type="button" className={`${timelineButton} mt-2`} disabled={timeline.isFetching} onClick={() => void timeline.refetch()}>Retry timeline</button></div> : null}
      {timeline.isLoading ? <p role="status" className={`py-8 text-sm ${timelineMuted}`}>Building your timeline...</p> : null}
      {!timeline.isLoading && !timeline.isError && !chapters.length ? <section className="border-b border-[rgb(var(--border)/0.7)] py-8"><h2 className="text-lg font-semibold">No major-event data yet</h2><p className={`mt-2 max-w-xl text-sm leading-6 ${timelineMuted}`}>Timeline tracks appear after chapters have been analyzed and are available to you. Check the chapter list for reading and analysis progress.</p><Link href={`/${bookId}/chapters`} className={`${timelineButton} mt-4`}>View chapters</Link></section> : null}

      {chapters.length ? <>
        <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2 border-y border-[rgb(var(--border)/0.7)] py-3 text-sm sm:flex sm:flex-wrap sm:gap-x-8">
          {[["Chapters", chapters.length], ["Characters", timeline.data?.character_tracks.length ?? 0], ["Plot threads", timeline.data?.thread_tracks.length ?? 0], ["Relationship shifts", timeline.data?.relationship_markers.length ?? 0]].map(([label, value]) => <div key={label} className="flex flex-wrap items-baseline gap-x-2"><dt className={timelineMuted}>{label}</dt><dd className="font-semibold">{value}</dd></div>)}
        </dl>
        <div className="mt-4 flex flex-wrap items-end gap-3 border-b border-[rgb(var(--border)/0.7)] pb-4">
          <label className="flex flex-col gap-1 text-sm"><span>Show</span><select className={controlClass} value={activeLane} onChange={(event) => setActiveLane(event.target.value as TimelineLane)}><option value="all">All lanes</option><option value="characters">Characters</option><option value="plotThreads">Plot threads</option><option value="relationships">Relationship shifts</option><option value="events">Story events</option></select></label>
          {activeLane !== "events" ? <>
            <label className="flex flex-col gap-1 text-sm"><span>View</span><select className={controlClass} value={view} onChange={(event) => setView(event.target.value as TimelineView)}><option value="auto">Automatic</option><option value="list">List</option><option value="lanes">Lanes</option></select></label>
            <button type="button" className={`${timelineButton} ${laneClass} sm:ml-auto`} onClick={() => void patchBookPreferences(preferenceBookId, ["characters", "plotThreads", "relationships"].map((section) => ({ op: "set" as const, path: `/timeline_collapsed_sections/${section}`, value: !allCollapsed })))}>{allCollapsed ? "Expand all" : "Collapse all"}</button>
          </> : null}
        </div>
        {activeLane !== "events" ? <>
          <div className={listClass}><TimelineList items={items} chapters={chapters} bookId={bookId} /></div>
          <div className={laneClass}><TimelineLanes items={items} chapters={chapters} bookId={bookId} isDark={isDark} activeLane={activeLane} collapsed={collapsed} onToggle={(section, value) => void setTimelineCollapsedSection(preferenceBookId, section, value)} /></div>
        </> : null}
        {showEvents ? <section aria-labelledby="story-events-title" className="mt-8">
          <h2 id="story-events-title" className="text-lg font-semibold">Story events</h2>
          <p className={`mt-1 text-sm leading-6 ${timelineMuted}`}>Chapter moments and structural changes in story order. Some also appear in the lanes above.</p>
          {events.isLoading ? <p role="status" className={`py-5 text-sm ${timelineMuted}`}>Loading story events…</p> : null}
          {events.isError ? <div role="alert" className="mt-3 border-l-2 border-amber-500 pl-4 text-sm"><p>Story events could not {storyEvents.length ? "update. Previously loaded events remain visible" : "load"}.</p><button type="button" className={`${timelineButton} mt-2`} disabled={events.isFetching} onClick={() => events.isFetchNextPageError ? void events.fetchNextPage() : void events.refetch()}>Retry story events</button></div> : null}
          {!events.isLoading && !events.isError && !storyEvents.length ? <p className={`py-5 text-sm ${timelineMuted}`}>No story events recorded in available chapters.</p> : null}
          {storyEvents.length ? <>
            <p role="status" className={`mt-3 text-sm ${timelineMuted}`}>{storyEvents.length}{typeof totalEvents === "number" ? ` of ${totalEvents}` : ""} story events loaded</p>
            <ol className="mt-3 divide-y divide-[rgb(var(--border)/0.7)] border-y border-[rgb(var(--border)/0.7)]">{storyEvents.map((event, index) => <li key={`${event.chapter_number}-${event.kind}-${index}`} className="py-4">
              <p className={`text-sm capitalize ${timelineMuted}`}>{event.kind.replaceAll("_", " ")}{event.chapter_title ? ` · ${event.chapter_title}` : ""}</p>
              <h3 className="mt-1 text-base font-semibold">{event.title}</h3>
              {event.detail ? <p className={`mt-1 max-w-3xl text-sm leading-6 ${timelineMuted}`}>{event.detail}</p> : null}
              <TimelineSource bookId={bookId} chapters={chapters} start={event.chapter_number} end={event.chapter_number} />
            </li>)}</ol>
          </> : null}
          {events.hasNextPage ? <button type="button" className={`${timelineButton} mt-4`} disabled={events.isFetching} onClick={() => void events.fetchNextPage()}>{events.isFetchingNextPage ? "Loading more…" : "Load more story events"}</button> : null}
        </section> : null}
      </> : null}
    </main>
  </WorkspacePage>
}

