"use client"
import { useEffect, useState } from "react"
import { readerApi } from "@/lib/api/reader"
import type { PlotThread } from "@/types/reader"
import { STATUS_COLORS } from "@/lib/constants"

interface Props { bookId: string; chapter: number }

const STATUS_ICONS: Record<string, string> = {
  introduced: "🔵",
  ongoing: "🔄",
  resolved: "✅",
  abandoned: "⚫",
  unknown: "❓",
}

export function PlotTracker({ bookId, chapter }: Props) {
  const [threads, setThreads] = useState<PlotThread[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    readerApi.getPlotThreads(bookId, chapter)
      .then(setThreads)
      .finally(() => setLoading(false))
  }, [bookId, chapter])

  if (loading) return <div className="text-sm text-gray-400 py-4 text-center">Loading plot threads...</div>
  if (threads.length === 0) return <div className="text-sm text-gray-400 py-4 text-center">No plot threads tracked yet</div>

  const byType = threads.reduce((acc, t) => {
    const key = t.type ?? "other"
    if (!acc[key]) acc[key] = []
    acc[key].push(t)
    return acc
  }, {} as Record<string, PlotThread[]>)

  return (
    <div className="flex flex-col gap-4">
      {Object.entries(byType).map(([type, typeThreads]) => (
        <div key={type}>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 capitalize">{type}</p>
          <div className="flex flex-col gap-2">
            {typeThreads.map(t => (
              <div key={t.id} className="flex items-start gap-2 bg-white rounded-lg border border-gray-100 p-3">
                <span className="text-sm mt-0.5">{STATUS_ICONS[t.status]}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="text-sm font-medium text-gray-800 truncate">{t.title}</p>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full shrink-0 ${STATUS_COLORS[t.status] ?? STATUS_COLORS.unknown}`}>
                      {t.status}
                    </span>
                  </div>
                  {t.description && <p className="text-xs text-gray-500 leading-relaxed">{t.description}</p>}
                  <p className="text-xs text-gray-400 mt-1">
                    Introduced ch. {t.introduced_at}
                    {t.resolved_at ? ` · Resolved ch. ${t.resolved_at}` : ""}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
