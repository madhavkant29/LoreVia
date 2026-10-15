import type cytoscape from "cytoscape"

import { cn } from "@/lib/utils/text"
import type { RelationshipGraph as GraphData } from "@/types/character"

type GraphNode = GraphData["nodes"][number]

export function storedGraphLabels(raw: string | null): Record<string, string> {
  try {
    const value: unknown = raw ? JSON.parse(raw) : null
    if (!value || typeof value !== "object" || Array.isArray(value)) return {}
    return Object.fromEntries(Object.entries(value).filter((entry): entry is [string, string] => typeof entry[1] === "string"))
  } catch { return {} }
}

export function storedGraphPositions(raw: string | null): Record<string, { x: number; y: number }> | null {
  try {
    const value: unknown = raw ? JSON.parse(raw) : null
    if (!value || typeof value !== "object" || Array.isArray(value)) return null
    const entries = Object.entries(value).filter((entry): entry is [string, { x: number; y: number }] => {
      const position = entry[1]
      return !!position && typeof position === "object" && Number.isFinite(position.x) && Number.isFinite(position.y)
    })
    return entries.length ? Object.fromEntries(entries) : null
  } catch { return null }
}

export const BASE_LAYOUT: cytoscape.LayoutOptions = {
  name: "cose",
  animate: false,
  componentSpacing: 120,
  nodeDimensionsIncludeLabels: true,
  padding: 56,
  nodeRepulsion: () => 14500,
  idealEdgeLength: () => 164,
  edgeElasticity: () => 90,
  gravity: 70,
}

export function controlButtonClass(active = false) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium transition-colors",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70",
    active
      ? "border-violet-400/40 bg-violet-500/20 text-[rgb(var(--foreground))]"
      : "border-[rgb(var(--border))] bg-white/[0.03] text-[rgb(var(--foreground))] hover:border-[rgb(var(--border))] hover:bg-white/[0.06]"
  )
}

export function panelClass() {
  return "rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))]"
}

export function buildIsolatedPositions(nodes: GraphNode[]) {
  if (nodes.length === 0) return null
  if (nodes.length === 1) {
    return { [nodes[0].id]: { x: 420, y: 280 } }
  }

  const centerX = 420
  const centerY = 290
  const radiusX = Math.min(250, 130 + nodes.length * 18)
  const radiusY = Math.min(180, 90 + nodes.length * 14)

  return Object.fromEntries(
    nodes.map((node, index) => {
      const angle = -Math.PI / 2 + (index / nodes.length) * Math.PI * 2
      return [
        node.id,
        {
          x: centerX + Math.cos(angle) * radiusX,
          y: centerY + Math.sin(angle) * radiusY,
        },
      ]
    })
  )
}
