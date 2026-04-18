"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { TimelineEvent } from "@/types/reader"

const EVENT_META: Record<string, { label: string; accent: string }> = {
  event: { label: "story beat", accent: "text-sky-600 dark:text-sky-300" },
  character_entry: { label: "character arrival", accent: "text-emerald-600 dark:text-emerald-300" },
  thread_start: { label: "arc begins", accent: "text-amber-600 dark:text-amber-300" },
  thread_end: { label: "arc resolves", accent: "text-fuchsia-600 dark:text-fuchsia-300" },
}

function chapterLabel(event: TimelineEvent) {
  return event.chapter_title ? `Chapter ${event.chapter_number}: ${event.chapter_title}` : `Chapter ${event.chapter_number}`
}

export default function TimelinePage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    setLoading(true)
    readerApi.getTimeline(bookId).then((res) => {
      setEvents(res.events)
    }).catch((e) => {
      setError(e.response?.data?.detail ?? "Timeline unavailable")
    }).finally(() => {
      setLoading(false)
    })
  }, [bookId])

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[linear-gradient(180deg,#07111f_0%,#0b1830_44%,#0d1b35_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-5xl">
        <button onClick={() => router.back()} className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}>{"<- Back"}</button>
        <h1 className={`mt-4 font-serif text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>Timeline</h1>
        <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          A spoiler-safe reading guide built from chapters you have already unlocked. It highlights major beats, notable arrivals, and the moments where larger arcs begin or resolve.
        </p>
        {error ? <div className={`mt-6 rounded-[1.5rem] border p-5 text-sm ${isDark ? "border-amber-400/30 bg-amber-500/10 text-amber-200" : "border-amber-300 bg-amber-50 text-amber-800"}`}>{error}</div> : null}
        {!error && loading ? (
          <div className={`mt-6 rounded-[1.6rem] border p-5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/70 text-stone-600"}`}>
            Building your spoiler-safe timeline...
          </div>
        ) : null}
        {!error && !loading && events.length === 0 ? (
          <div className={`mt-6 rounded-[1.6rem] border p-5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/70 text-stone-600"}`}>
            No major timeline moments are ready yet. As more chapters are processed, this view will become more detailed.
          </div>
        ) : null}
        <div className="mt-8 space-y-4">
          {events.map((event, index) => (
            <div key={`${event.chapter_number}-${event.kind}-${index}`} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200/80 bg-white/90"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${EVENT_META[event.kind]?.accent ?? (isDark ? "text-indigo-300" : "text-violet-600")}`}>
                {chapterLabel(event)} - {EVENT_META[event.kind]?.label ?? event.kind.replaceAll("_", " ")}
              </p>
              <p className={`mt-3 text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{event.title}</p>
              {event.detail ? <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{event.detail}</p> : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
