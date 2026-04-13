"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import type { TimelineEvent } from "@/types/reader"

const EVENT_META: Record<string, { label: string; accent: string }> = {
  event: { label: "story beat", accent: "text-sky-600" },
  character_entry: { label: "character arrival", accent: "text-emerald-600" },
  thread_start: { label: "arc begins", accent: "text-amber-600" },
  thread_end: { label: "arc resolves", accent: "text-fuchsia-600" },
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
    <div className="min-h-screen bg-white px-4 py-8 text-black">
      <div className="mx-auto max-w-4xl">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">{"<- Back"}</button>
        <h1 className="mt-4 text-3xl font-semibold">Timeline View</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-500">
          A spoiler-safe reading guide built from chapters you have already unlocked. It highlights major beats, notable arrivals, and the moments where larger arcs begin or resolve.
        </p>
        {error ? <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">{error}</div> : null}
        {!error && loading ? (
          <div className="mt-6 rounded-2xl border border-gray-200 bg-gray-50 p-5 text-sm text-gray-600">
            Building your spoiler-safe timeline...
          </div>
        ) : null}
        {!error && !loading && events.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-gray-200 bg-gray-50 p-5 text-sm text-gray-600">
            No major timeline moments are ready yet. As more chapters are processed, this view will become more detailed.
          </div>
        ) : null}
        <div className="mt-8 space-y-4">
          {events.map((event, index) => (
            <div key={`${event.chapter_number}-${event.kind}-${index}`} className="rounded-2xl border border-gray-200 bg-white p-5">
              <p className={`text-xs uppercase tracking-wide ${EVENT_META[event.kind]?.accent ?? "text-indigo-500"}`}>
                {chapterLabel(event)} - {EVENT_META[event.kind]?.label ?? event.kind.replaceAll("_", " ")}
              </p>
              <p className="mt-2 text-base font-medium text-gray-900">{event.title}</p>
              {event.detail ? <p className="mt-2 text-sm leading-relaxed text-gray-600">{event.detail}</p> : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
