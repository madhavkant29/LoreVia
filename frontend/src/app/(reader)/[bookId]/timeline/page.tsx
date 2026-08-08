"use client"

import type { ReactNode } from "react"
import { useEffect, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspaceEmptyState, WorkspaceMetric, WorkspacePage, WorkspacePanel } from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { defaultBookUiPreference, useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import type { Book } from "@/types/book"
import type { CharacterTimelineTrack, PlotThreadTimelineTrack, RelationshipTimelineMarker, TimelineChapter, TimelineResponse } from "@/types/reader"
import { capture } from "@/lib/analytics/posthog"

const CELL_WIDTH = 68

export default function TimelinePage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const preferenceBookId = normalizeBookRouteId(bookId)
  const hydrateBookPreferences = useUiPreferencesStore((state) => state.hydrateBook)
  const patchBookPreferences = useUiPreferencesStore((state) => state.patchBook)
  const setTimelineCollapsedSection = useUiPreferencesStore((state) => state.setTimelineCollapsedSection)
  const timelineCollapsedSections = useUiPreferencesStore(
    (state) => (
      state.bookPreferences[preferenceBookId]
      ?? defaultBookUiPreference(preferenceBookId, state.preferences.complexity_mode)
    ).timeline_collapsed_sections,
  )
  const isDark = theme === "dark"

  useEffect(() => {
    capture("major_events_opened", { book_id: bookId })
    void hydrateBookPreferences(preferenceBookId)
  }, [bookId, hydrateBookPreferences, preferenceBookId])
  const setTimelineAllCollapsed = (collapsed: boolean) => {
    void patchBookPreferences(preferenceBookId, [
      { op: "set", path: "/timeline_collapsed_sections/characters", value: collapsed },
      { op: "set", path: "/timeline_collapsed_sections/plotThreads", value: collapsed },
      { op: "set", path: "/timeline_collapsed_sections/relationships", value: collapsed },
    ])
  }
  const { data: book = null } = useQuery<Book>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
    staleTime: 20_000,
  })
  const {
    data: timeline = null,
    isLoading: loading,
    isError,
  } = useQuery<TimelineResponse>({
    queryKey: asQueryKey(readerCacheKey(bookId, "timeline")),
    queryFn: () => readerApi.getTimeline(bookId),
    staleTime: 45_000,
  })
  const error = isError ? "Major events unavailable" : null

  const chapters = timeline?.chapters ?? []
  const chapterCount = chapters.length
  const isAuthor = book?.mode === "author"

  const chapterIndex = useMemo(() => {
    return Object.fromEntries(chapters.map((chapter, index) => [chapter.number, index]))
  }, [chapters])

  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <div className="mx-auto max-w-[1600px] px-0 pb-16 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="timeline"
          bookId={bookId}
          family="story-bible"
          title={isAuthor ? "Arc timeline" : "Major events"}
          description={
            isAuthor
              ? "Map character presence, thread duration, and relationship turns across the complete manuscript."
              : "Review a spoiler-safe structural map of the story so far."
          }
        />

        {error ? <div className={`mt-6 rounded-md border p-5 text-sm ${isDark ? "border-amber-400/30 bg-amber-500/10 text-amber-200" : "border-amber-300 bg-amber-50 text-amber-800"}`}>{error}</div> : null}
        {!error && loading ? <WorkspacePanel tone="subtle" className="mt-6 p-5 text-sm text-[rgb(var(--muted-foreground))]">Building your timeline...</WorkspacePanel> : null}
        {!error && !loading && chapterCount === 0 ? <WorkspaceEmptyState className="mt-6" title="No major-event data yet" body="Timeline tracks will appear after LoreVia has analyzed enough manuscript structure." /> : null}

        {chapterCount > 0 ? (
          <>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Chapters mapped" value={String(chapterCount)} isDark={isDark} />
              <MetricCard label="Character tracks" value={String(timeline?.character_tracks.length ?? 0)} isDark={isDark} />
              <MetricCard label="Plot threads" value={String(timeline?.thread_tracks.length ?? 0)} isDark={isDark} />
              <MetricCard label="Relationship shifts" value={String(timeline?.relationship_markers.length ?? 0)} isDark={isDark} />
            </div>

            <div className={`mt-6 overflow-x-auto rounded-lg border ${isDark ? "border-white/[0.08] bg-[#1d2225]" : "border-stone-200 bg-white"}`}>
              <div className="min-w-max">
                <ChapterHeader chapters={chapters} isDark={isDark} />
                <TimelineSection
                  sectionId="characters"
                  title="Characters"
                  subtitle="Who is active across which chapters"
                  isDark={isDark}
                  isCollapsed={timelineCollapsedSections.characters ?? false}
                  onToggle={(collapsed) => {
                    void setTimelineCollapsedSection(preferenceBookId, "characters", collapsed)
                    if (collapsed) {
                      setTimelineAllCollapsed(true)
                    }
                  }}
                  rows={timeline?.character_tracks ?? []}
                  renderRow={(track) => (
                    <TrackRow
                      key={track.id}
                      label={track.name}
                      meta={track.role ? track.role.toUpperCase() : "Character"}
                      detail={track.detail}
                      chapters={chapters}
                      startChapter={track.start_chapter}
                      endChapter={track.end_chapter}
                      chapterIndex={chapterIndex}
                      colorClass={isDark ? "bg-emerald-400/90" : "bg-emerald-600"}
                      isDark={isDark}
                    />
                  )}
                />
                <TimelineSection
                  sectionId="plotThreads"
                  title="Plot Threads"
                  subtitle="Open and resolved arcs over time"
                  isDark={isDark}
                  isCollapsed={timelineCollapsedSections.plotThreads ?? false}
                  onToggle={(collapsed) => {
                    void setTimelineCollapsedSection(preferenceBookId, "plotThreads", collapsed)
                    if (collapsed) {
                      setTimelineAllCollapsed(true)
                    }
                  }}
                  rows={timeline?.thread_tracks ?? []}
                  renderRow={(track) => (
                    <TrackRow
                      key={track.id}
                      label={track.title}
                      meta={track.status}
                      detail={track.note || track.detail}
                      chapters={chapters}
                      startChapter={track.start_chapter}
                      endChapter={track.end_chapter}
                      chapterIndex={chapterIndex}
                      colorClass={track.status === "resolved" ? (isDark ? "bg-stone-300/90" : "bg-stone-500") : (isDark ? "bg-violet-400/90" : "bg-violet-600")}
                      isDark={isDark}
                    />
                  )}
                />
                <RelationshipSection
                  sectionId="relationships"
                  chapters={chapters}
                  markers={timeline?.relationship_markers ?? []}
                  chapterIndex={chapterIndex}
                  isDark={isDark}
                  isCollapsed={timelineCollapsedSections.relationships ?? false}
                  onToggle={(collapsed) => {
                    void setTimelineCollapsedSection(preferenceBookId, "relationships", collapsed)
                    if (collapsed) {
                      setTimelineAllCollapsed(true)
                    }
                  }}
                />
              </div>
            </div>
          </>
        ) : null}
      </div>
    </WorkspacePage>
  )
}

function MetricCard({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return <WorkspaceMetric label={label} value={value} className={isDark ? "text-slate-100" : "text-stone-950"} />
}

function ChapterHeader({ chapters, isDark }: { chapters: TimelineChapter[]; isDark: boolean }) {
  return (
    <div className={`sticky top-0 z-10 flex border-b ${isDark ? "border-white/[0.06] bg-[#050505]" : "border-stone-200 bg-[#fcf7ef]"}`}>
      <div className={`sticky left-0 z-10 w-80 shrink-0 border-r px-6 py-5 ${isDark ? "border-white/[0.06] bg-[#050505]" : "border-stone-200 bg-[#fcf7ef]"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Major-event lanes</p>
      </div>
      <div className="flex">
        {chapters.map((chapter, idx) => (
          <div
            key={chapter.number}
            className={`shrink-0 border-r px-2 py-5 text-center ${isDark ? `border-white/[0.06] text-slate-300 ${idx % 2 === 0 ? 'bg-white/[0.015]' : ''}` : `border-stone-200 text-stone-600 ${idx % 2 === 0 ? 'bg-stone-50/50' : ''}`}`}
            style={{ width: CELL_WIDTH }}
          >
            <p className="text-sm font-semibold">Ch. {chapter.number}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function TimelineSection<T extends { id: string }>({
  sectionId,
  title,
  subtitle,
  rows,
  renderRow,
  isDark,
  isCollapsed,
  onToggle,
}: {
  sectionId: string
  title: string
  subtitle: string
  rows: T[]
  renderRow: (row: T) => ReactNode
  isDark: boolean
  isCollapsed: boolean
  onToggle: (collapsed: boolean) => void
}) {
  return (
    <section className="border-b last:border-b-0 border-white/[0.06]">
      <button
        onClick={() => onToggle(!isCollapsed)}
        className={`sticky left-0 z-[1] w-full border-b px-6 py-5 text-left transition-colors ${isDark ? "border-white/[0.06] bg-black/85 hover:bg-black/95" : "border-stone-200 bg-white/90 hover:bg-white"}`}
      >
        <div className="flex items-center gap-3">
          {isCollapsed ? (
            <svg className={`h-5 w-5 ${isDark ? "text-slate-400" : "text-stone-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          ) : (
            <svg className={`h-5 w-5 ${isDark ? "text-slate-400" : "text-stone-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          )}
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{title}</p>
            <p className={`mt-1 text-base ${isDark ? "text-slate-400" : "text-stone-500"}`}>{subtitle}</p>
          </div>
        </div>
      </button>
      {!isCollapsed && rows.map(renderRow)}
    </section>
  )
}

function TrackRow({
  label,
  meta,
  detail,
  chapters,
  startChapter,
  endChapter,
  chapterIndex,
  colorClass,
  isDark,
}: {
  label: string
  meta: string
  detail: string | null | undefined
  chapters: TimelineChapter[]
  startChapter: number
  endChapter: number
  chapterIndex: Record<number, number>
  colorClass: string
  isDark: boolean
}) {
  const start = chapterIndex[startChapter] ?? 0
  const end = chapterIndex[endChapter] ?? start
  const width = Math.max(1, end - start + 1) * CELL_WIDTH - 12

  return (
    <div className={`flex border-b ${isDark ? "border-white/[0.06]" : "border-stone-200/70"}`}>
      <div className={`sticky left-0 z-[1] w-80 shrink-0 border-r px-6 py-5 ${isDark ? "border-white/[0.06] bg-black/85" : "border-stone-200 bg-white/90"}`}>
        <p className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{label}</p>
        <p className={`mt-1 text-xs uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{meta}</p>
        {detail ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{detail}</p> : null}
      </div>
      <div className="relative flex">
        {chapters.map((chapter, idx) => (
          <div key={chapter.number} className={`relative shrink-0 border-r ${isDark ? `border-white/[0.06] ${idx % 2 === 0 ? 'bg-white/[0.015]' : ''}` : `border-stone-200/60 ${idx % 2 === 0 ? 'bg-stone-50/50' : ''}`}`} style={{ width: CELL_WIDTH, minHeight: 100 }} />
        ))}
        <div
          className={`absolute top-1/2 h-4 -translate-y-1/2 rounded-full ${colorClass}`}
          style={{ left: start * CELL_WIDTH + 6, width }}
        />
      </div>
    </div>
  )
}

function RelationshipSection({
  sectionId,
  chapters,
  markers,
  chapterIndex,
  isDark,
  isCollapsed,
  onToggle,
}: {
  sectionId: string
  chapters: TimelineChapter[]
  markers: RelationshipTimelineMarker[]
  chapterIndex: Record<number, number>
  isDark: boolean
  isCollapsed: boolean
  onToggle: (collapsed: boolean) => void
}) {
  return (
    <section>
      <button
        onClick={() => onToggle(!isCollapsed)}
        className={`sticky left-0 z-[1] w-full border-b px-6 py-5 text-left transition-colors ${isDark ? "border-white/[0.06] bg-black/85 hover:bg-black/95" : "border-stone-200 bg-white/90 hover:bg-white"}`}
      >
        <div className="flex items-center gap-3">
          {isCollapsed ? (
            <svg className={`h-5 w-5 ${isDark ? "text-slate-400" : "text-stone-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          ) : (
            <svg className={`h-5 w-5 ${isDark ? "text-slate-400" : "text-stone-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          )}
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Relationship Shifts</p>
            <p className={`mt-1 text-base ${isDark ? "text-slate-400" : "text-stone-500"}`}>Markers for turning points between characters</p>
          </div>
        </div>
      </button>
      {!isCollapsed && markers.map((marker) => (
        <div key={marker.id} className={`flex border-b ${isDark ? "border-white/[0.06]" : "border-stone-200/70"}`}>
          <div className={`sticky left-0 z-[1] w-80 shrink-0 border-r px-6 py-5 ${isDark ? "border-white/[0.06] bg-black/85" : "border-stone-200 bg-white/90"}`}>
            <p className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{marker.title}</p>
            {marker.detail ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{marker.detail}</p> : null}
          </div>
          <div className="relative flex">
            {chapters.map((chapter, idx) => (
              <div key={chapter.number} className={`relative shrink-0 border-r ${isDark ? `border-white/[0.06] ${idx % 2 === 0 ? 'bg-white/[0.015]' : ''}` : `border-stone-200/60 ${idx % 2 === 0 ? 'bg-stone-50/50' : ''}`}`} style={{ width: CELL_WIDTH, minHeight: 100 }} />
            ))}
            <div
              className={`absolute top-1/2 h-6 w-6 -translate-y-1/2 rounded-full ${isDark ? "bg-amber-400" : "bg-amber-500"}`}
              style={{ left: (chapterIndex[marker.chapter_number] ?? 0) * CELL_WIDTH + CELL_WIDTH / 2 - 12 }}
            />
          </div>
        </div>
      ))}
    </section>
  )
}
