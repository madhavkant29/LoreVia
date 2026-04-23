"use client"

import type { ReactNode } from "react"
import { useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { CharacterTimelineTrack, PlotThreadTimelineTrack, RelationshipTimelineMarker, TimelineChapter, TimelineResponse } from "@/types/reader"

const CELL_WIDTH = 68

export default function TimelinePage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [book, setBook] = useState<Book | null>(null)
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    booksApi.get(bookId).then(setBook).catch(() => {})
    setLoading(true)
    readerApi.getTimeline(bookId)
      .then(setTimeline)
      .catch((e) => setError(e.response?.data?.detail ?? "Timeline unavailable"))
      .finally(() => setLoading(false))
  }, [bookId])

  const chapters = timeline?.chapters ?? []
  const chapterCount = chapters.length
  const isAuthor = book?.mode === "author"

  const chapterIndex = useMemo(() => {
    return Object.fromEntries(chapters.map((chapter, index) => [chapter.number, index]))
  }, [chapters])

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-[92rem]">
        <button onClick={() => router.back()} className={`text-sm font-medium transition ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>{"<- Back"}</button>
        <h1 className={`mt-4 font-serif text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>{isAuthor ? "Arc Timeline" : "Timeline"}</h1>
        <p className={`mt-3 max-w-4xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          {isAuthor
            ? "A true chapter-axis view of your manuscript. Track when characters enter the story, how long threads stay active, and where relationships shift."
            : "A spoiler-safe structural map of the story so far."}
        </p>

        {error ? <div className={`mt-6 rounded-[1.5rem] border p-5 text-sm ${isDark ? "border-amber-400/30 bg-amber-500/10 text-amber-200" : "border-amber-300 bg-amber-50 text-amber-800"}`}>{error}</div> : null}
        {!error && loading ? <div className={`mt-6 rounded-[1.6rem] border p-5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/70 text-stone-600"}`}>Building your timeline...</div> : null}
        {!error && !loading && chapterCount === 0 ? <div className={`mt-6 rounded-[1.6rem] border p-5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/70 text-stone-600"}`}>No timeline data is ready yet.</div> : null}

        {chapterCount > 0 ? (
          <>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Chapters mapped" value={String(chapterCount)} isDark={isDark} />
              <MetricCard label="Character tracks" value={String(timeline?.character_tracks.length ?? 0)} isDark={isDark} />
              <MetricCard label="Plot threads" value={String(timeline?.thread_tracks.length ?? 0)} isDark={isDark} />
              <MetricCard label="Relationship shifts" value={String(timeline?.relationship_markers.length ?? 0)} isDark={isDark} />
            </div>

            <div className={`mt-8 overflow-x-auto rounded-[1.8rem] border ${isDark ? "border-white/10 bg-black/70" : "border-stone-200 bg-white/90"}`}>
              <div className="min-w-max">
                <ChapterHeader chapters={chapters} isDark={isDark} />
                <TimelineSection
                  title="Characters"
                  subtitle="Who is active across which chapters"
                  isDark={isDark}
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
                  title="Plot Threads"
                  subtitle="Open and resolved arcs over time"
                  isDark={isDark}
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
                      colorClass={track.status === "resolved" ? (isDark ? "bg-stone-300/90" : "bg-stone-500") : (isDark ? "bg-cyan-400/90" : "bg-cyan-600")}
                      isDark={isDark}
                    />
                  )}
                />
                <RelationshipSection
                  chapters={chapters}
                  markers={timeline?.relationship_markers ?? []}
                  chapterIndex={chapterIndex}
                  isDark={isDark}
                />
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}

function MetricCard({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
    </div>
  )
}

function ChapterHeader({ chapters, isDark }: { chapters: TimelineChapter[]; isDark: boolean }) {
  return (
    <div className={`sticky top-0 z-10 flex border-b ${isDark ? "border-white/10 bg-[#050505]" : "border-stone-200 bg-[#fcf7ef]"}`}>
      <div className={`sticky left-0 z-10 w-72 shrink-0 border-r px-5 py-4 ${isDark ? "border-white/10 bg-[#050505]" : "border-stone-200 bg-[#fcf7ef]"}`}>
        <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Timeline lanes</p>
      </div>
      <div className="flex">
        {chapters.map((chapter) => (
          <div
            key={chapter.number}
            className={`shrink-0 border-r px-2 py-4 text-center ${isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-600"}`}
            style={{ width: CELL_WIDTH }}
          >
            <p className="text-xs font-semibold">Ch. {chapter.number}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function TimelineSection<T extends { id: string }>({
  title,
  subtitle,
  rows,
  renderRow,
  isDark,
}: {
  title: string
  subtitle: string
  rows: T[]
  renderRow: (row: T) => ReactNode
  isDark: boolean
}) {
  return (
    <section className="border-b last:border-b-0 border-white/10">
      <div className={`sticky left-0 z-[1] border-b px-5 py-4 ${isDark ? "border-white/10 bg-black/85" : "border-stone-200 bg-white/90"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{title}</p>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{subtitle}</p>
      </div>
      {rows.map(renderRow)}
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
    <div className={`flex border-b ${isDark ? "border-white/5" : "border-stone-200/70"}`}>
      <div className={`sticky left-0 z-[1] w-72 shrink-0 border-r px-5 py-4 ${isDark ? "border-white/10 bg-black/85" : "border-stone-200 bg-white/90"}`}>
        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{label}</p>
        <p className={`mt-1 text-[11px] uppercase tracking-[0.16em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{meta}</p>
        {detail ? <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{detail}</p> : null}
      </div>
      <div className="relative flex">
        {chapters.map((chapter) => (
          <div key={chapter.number} className={`relative shrink-0 border-r ${isDark ? "border-white/5" : "border-stone-200/60"}`} style={{ width: CELL_WIDTH, minHeight: 96 }} />
        ))}
        <div
          className={`absolute top-1/2 h-4 -translate-y-1/2 rounded-full ${colorClass} shadow-[0_0_0_1px_rgba(255,255,255,0.08)]`}
          style={{ left: start * CELL_WIDTH + 6, width }}
        />
      </div>
    </div>
  )
}

function RelationshipSection({
  chapters,
  markers,
  chapterIndex,
  isDark,
}: {
  chapters: TimelineChapter[]
  markers: RelationshipTimelineMarker[]
  chapterIndex: Record<number, number>
  isDark: boolean
}) {
  return (
    <section>
      <div className={`sticky left-0 z-[1] border-b px-5 py-4 ${isDark ? "border-white/10 bg-black/85" : "border-stone-200 bg-white/90"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Relationship Shifts</p>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Markers for turning points between characters</p>
      </div>
      {markers.map((marker) => (
        <div key={marker.id} className={`flex border-b ${isDark ? "border-white/5" : "border-stone-200/70"}`}>
          <div className={`sticky left-0 z-[1] w-72 shrink-0 border-r px-5 py-4 ${isDark ? "border-white/10 bg-black/85" : "border-stone-200 bg-white/90"}`}>
            <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{marker.title}</p>
            {marker.detail ? <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{marker.detail}</p> : null}
          </div>
          <div className="relative flex">
            {chapters.map((chapter) => (
              <div key={chapter.number} className={`relative shrink-0 border-r ${isDark ? "border-white/5" : "border-stone-200/60"}`} style={{ width: CELL_WIDTH, minHeight: 88 }} />
            ))}
            <div
              className={`absolute top-1/2 h-5 w-5 -translate-y-1/2 rounded-full ${isDark ? "bg-amber-300" : "bg-amber-500"}`}
              style={{ left: (chapterIndex[marker.chapter_number] ?? 0) * CELL_WIDTH + CELL_WIDTH / 2 - 10 }}
            />
          </div>
        </div>
      ))}
    </section>
  )
}
