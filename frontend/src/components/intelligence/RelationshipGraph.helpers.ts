import type cytoscape from "cytoscape"

import { cn } from "@/lib/utils/text"
import type { RelationshipGraph as GraphData } from "@/types/character"

type GraphNode = GraphData["nodes"][number]

export const BASE_LAYOUT: cytoscape.LayoutOptions = {
  name: "cose",
  animate: true,
  padding: 56,
  nodeRepulsion: () => 14500,
  idealEdgeLength: () => 164,
  edgeElasticity: () => 90,
  gravity: 70,
}

export function controlButtonClass(active = false) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70",
    active
      ? "border-violet-400/40 bg-violet-500/20 text-white shadow-[0_10px_30px_rgba(76,29,149,0.18)]"
      : "border-white/10 bg-white/[0.03] text-slate-200 hover:border-white/20 hover:bg-white/[0.06]"
  )
}

export function panelClass() {
  return "rounded-lg border border-white/10 bg-[#080c16] shadow-[0_24px_80px_rgba(0,0,0,0.36)]"
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
