"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import type { TimelineEvent } from "@/types/reader"

export default function TimelinePage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    readerApi.getTimeline(bookId).then((res) => setEvents(res.events)).catch((e) => {
      setError(e.response?.data?.detail ?? "Timeline unavailable")
    })
  }, [bookId])

  return (
    <div className="min-h-screen bg-white px-4 py-8 text-black">
      <div className="mx-auto max-w-4xl">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">{"<- Back"}</button>
        <h1 className="mt-4 text-3xl font-semibold">Timeline View</h1>
        <p className="mt-2 text-sm text-gray-500">Major events, arc starts, resolutions, and character entrances from the chapters you have already read.</p>
        {error ? <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">{error}</div> : null}
        <div className="mt-8 space-y-4">
          {events.map((event, index) => (
            <div key={`${event.chapter_number}-${event.kind}-${index}`} className="rounded-2xl border border-gray-200 bg-white p-5">
              <p className="text-xs uppercase tracking-wide text-indigo-500">Chapter {event.chapter_number} · {event.kind.replaceAll("_", " ")}</p>
              <p className="mt-2 text-base font-medium text-gray-900">{event.title}</p>
              {event.detail ? <p className="mt-2 text-sm leading-relaxed text-gray-600">{event.detail}</p> : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
