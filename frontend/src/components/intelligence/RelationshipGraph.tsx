"use client"
import { useEffect, useRef, useState } from "react"
import { readerApi } from "@/lib/api/reader"
import type { RelationshipGraph as GraphData } from "@/types/character"
import { RELATIONSHIP_COLORS } from "@/lib/constants"

interface Props { bookId: string; upToChapter: number; theme?: "light" | "dark" }

export function RelationshipGraph({ bookId, upToChapter, theme = "light" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    readerApi.getRelationships(bookId, upToChapter)
      .then(setGraph)
      .finally(() => setLoading(false))
  }, [bookId, upToChapter])

  if (loading) return <div className={theme === "dark" ? "flex justify-center py-20 text-gray-500" : "flex justify-center py-20 text-gray-400"}>Building graph...</div>
  if (!graph || graph.nodes.length === 0) return <div className={theme === "dark" ? "flex justify-center py-20 text-gray-500" : "flex justify-center py-20 text-gray-400"}>No relationships extracted yet</div>

  return (
    <div ref={containerRef} className={theme === "dark" ? "bg-white/5 rounded-xl border border-white/10 overflow-hidden" : "bg-white rounded-xl border border-gray-200 overflow-hidden"}>
      <div className={theme === "dark" ? "p-4 border-b border-white/10" : "p-4 border-b border-gray-100"}>
        <p className={theme === "dark" ? "text-sm text-gray-300" : "text-sm text-gray-500"}>{graph.nodes.length} characters · {graph.edges.length} relationships</p>
      </div>
      <div className={theme === "dark" ? "divide-y divide-white/5" : "divide-y divide-gray-50"}>
        {graph.edges.map((edge, i) => {
          const from = graph.nodes.find(n => n.id === edge.source)
          const to = graph.nodes.find(n => n.id === edge.target)
          return (
            <div key={i} className="flex items-center gap-3 px-4 py-3 text-sm">
              <span className={theme === "dark" ? "font-medium text-white w-28 truncate" : "font-medium text-gray-800 w-28 truncate"}>{from?.name}</span>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: RELATIONSHIP_COLORS[edge.type] + "20", color: RELATIONSHIP_COLORS[edge.type] }}>
                {edge.type}
              </span>
              <span className={theme === "dark" ? "font-medium text-white w-28 truncate" : "font-medium text-gray-800 w-28 truncate"}>{to?.name}</span>
              {edge.description && <span className="text-gray-400 text-xs truncate flex-1">{edge.description}</span>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
