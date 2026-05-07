"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import cytoscape, { type Core, type ElementDefinition } from "cytoscape"

import type { ObsidianGraph } from "@/types/book"

const POSITION_STORAGE_KEY = "obsidian-graph-positions:v1"

type StoredPositions = Record<string, { x: number; y: number }>

function fileTone(path: string) {
  const lower = path.toLowerCase()
  if (lower.includes("character")) return "#8b5cf6"
  if (lower.includes("plot")) return "#f97316"
  if (lower.includes("world")) return "#22c55e"
  return "#60a5fa"
}

function loadStoredPositions() {
  if (typeof window === "undefined") return {}
  try {
    return JSON.parse(window.localStorage.getItem(POSITION_STORAGE_KEY) || "{}") as StoredPositions
  } catch {
    return {}
  }
}

function persistPositions(cy: Core) {
  if (typeof window === "undefined") return
  const current = loadStoredPositions()
  cy.nodes().forEach((node) => {
    const position = node.position()
    current[node.id()] = { x: position.x, y: position.y }
  })
  window.localStorage.setItem(POSITION_STORAGE_KEY, JSON.stringify(current))
}

function buildLocalGraph(graph: ObsidianGraph, focusPath: string | null) {
  if (!focusPath) return graph
  const neighborIds = new Set<string>([focusPath])
  for (const edge of graph.edges) {
    if (edge.source === focusPath) neighborIds.add(edge.target)
    if (edge.target === focusPath) neighborIds.add(edge.source)
  }
  return {
    nodes: graph.nodes.filter((node) => neighborIds.has(node.path)),
    edges: graph.edges.filter((edge) => neighborIds.has(edge.source) && neighborIds.has(edge.target)),
  }
}

export function GraphViewer({
  graph,
  selectedPath,
  onOpenNote,
  isDark,
  heightClassName = "min-h-[23rem]",
}: {
  graph: ObsidianGraph
  selectedPath: string | null
  onOpenNote: (path: string) => void
  isDark: boolean
  heightClassName?: string
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<Core | null>(null)
  const [hoveredPath, setHoveredPath] = useState<string | null>(null)
  const [localMode, setLocalMode] = useState(false)
  const [labelsVisible, setLabelsVisible] = useState(true)

  const renderedGraph = useMemo(
    () => (localMode ? buildLocalGraph(graph, selectedPath) : graph),
    [graph, localMode, selectedPath]
  )

  const focusPath = hoveredPath || selectedPath
  const focusNode = renderedGraph.nodes.find((node) => node.path === focusPath) ?? null

  useEffect(() => {
    if (!containerRef.current) return

    const storedPositions = loadStoredPositions()
    const stylesheet: any = [
      {
        selector: "node",
        style: {
          label: "data(label)",
          width: "data(size)",
          height: "data(size)",
          "background-color": "data(tone)",
          "background-opacity": isDark ? 0.78 : 0.72,
          "border-width": isDark ? 1.2 : 1,
          "border-color": isDark ? "#dbe4ff" : "#ffffff",
          "border-opacity": isDark ? 0.18 : 0.48,
          color: isDark ? "#cad5f5" : "#334155",
          "font-size": "11",
          "font-family": '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif',
          "text-wrap": "wrap",
          "text-max-width": "92",
          "text-valign": "bottom",
          "text-margin-y": 8,
          "overlay-opacity": 0,
          "shadow-blur": isDark ? 18 : 10,
          "shadow-color": "data(tone)",
          "shadow-opacity": isDark ? 0.35 : 0.18,
          "shadow-offset-x": 0,
          "shadow-offset-y": 0,
        },
      },
      {
        selector: "edge",
        style: {
          width: 1.05,
          opacity: isDark ? 0.42 : 0.34,
          "line-color": isDark ? "#63708a" : "#94a3b8",
          "curve-style": "bezier",
          "target-arrow-shape": "none",
        },
      },
      {
        selector: ".active-node",
        style: {
          "background-opacity": 1,
          "border-width": 2.2,
          "border-opacity": 0.95,
          "border-color": "#f8fafc",
          color: isDark ? "#ffffff" : "#0f172a",
          "font-size": "12",
        },
      },
      {
        selector: ".active-edge",
        style: {
          opacity: 0.95,
          width: 2.2,
          "line-color": "#93c5fd",
        },
      },
      {
        selector: ".dimmed",
        style: {
          opacity: 0.12,
        },
      },
    ]

    const elements: ElementDefinition[] = [
      ...renderedGraph.nodes.map((node) => ({
        data: {
          id: node.id,
          label: node.title,
          path: node.path,
          links: node.link_count,
          tone: fileTone(node.path),
          size: Math.max(16, 16 + Math.min(node.link_count, 10) * 1.8),
        },
        position: storedPositions[node.path],
      })),
      ...renderedGraph.edges.map((edge, index) => ({
        data: {
          id: `${edge.source}-${edge.target}-${index}`,
          source: edge.source,
          target: edge.target,
          label: edge.label ?? "",
        },
      })),
    ]

    const hasStoredPositions = renderedGraph.nodes.some((node) => storedPositions[node.path])

    const cy = cytoscape({
      container: containerRef.current,
      wheelSensitivity: 0.18,
      minZoom: 0.42,
      maxZoom: 2.2,
      elements,
      style: stylesheet,
      layout: hasStoredPositions
        ? { name: "preset", fit: true, padding: 40 }
        : {
            name: "cose",
            animate: false,
            fit: true,
            padding: 30,
            idealEdgeLength: 110,
            nodeOverlap: 10,
            componentSpacing: 50,
          },
    })

    cyRef.current = cy

    const updateLabelVisibility = () => {
      const show = cy.zoom() >= 0.72
      setLabelsVisible(show)
      cy.style()
        .selector("node")
        .style("label", show ? "data(label)" : "")
        .update()
    }

    const highlightNeighborhood = (path: string | null) => {
      cy.elements().removeClass("dimmed active-node active-edge")
      if (!path) return
      const node = cy.getElementById(path)
      if (!node.length) return
      cy.elements().addClass("dimmed")
      node.removeClass("dimmed").addClass("active-node")
      node.connectedEdges().removeClass("dimmed").addClass("active-edge")
      node.connectedEdges().connectedNodes().removeClass("dimmed")
    }

    cy.on("tap", "node", (event) => {
      onOpenNote(String(event.target.data("path")))
    })

    cy.on("mouseover", "node", (event) => {
      const path = String(event.target.data("path"))
      setHoveredPath(path)
      highlightNeighborhood(path)
    })

    cy.on("mouseout", "node", () => {
      setHoveredPath(null)
      highlightNeighborhood(selectedPath)
    })

    cy.on("dragfree", "node", () => {
      persistPositions(cy)
    })

    cy.on("zoom", updateLabelVisibility)

    updateLabelVisibility()
    highlightNeighborhood(selectedPath)

    return () => {
      persistPositions(cy)
      cy.destroy()
      cyRef.current = null
    }
  }, [isDark, onOpenNote, renderedGraph, selectedPath])

  const runAction = (fn: (cy: Core) => void) => {
    const cy = cyRef.current
    if (!cy) return
    fn(cy)
  }

  if (renderedGraph.nodes.length === 0) {
    return (
      <div
        className={`flex min-h-[20rem] items-center justify-center rounded-[1.35rem] border border-dashed text-sm ${
          isDark ? "border-white/10 bg-[#0b1220] text-slate-400" : "border-stone-300 bg-[#f8fafc] text-stone-500"
        }`}
      >
        {localMode ? "Pick a note with wiki-links to see its local graph." : <>Add a few wiki-links like <code className="mx-1">[[Character Name]]</code> to see the graph.</>}
      </div>
    )
  }

  return (
    <div
      className={`relative overflow-hidden rounded-[1.35rem] border ${
        isDark ? "border-white/10 bg-[#0a101b]" : "border-stone-200 bg-[#f7fafc]"
      }`}
    >
      <div
        className="absolute inset-0 opacity-100"
        style={{
          backgroundImage: isDark
            ? "radial-gradient(circle at 20% 18%, rgba(96,165,250,0.14), transparent 22%), radial-gradient(circle at 80% 16%, rgba(167,139,250,0.12), transparent 18%), radial-gradient(circle at 50% 76%, rgba(52,211,153,0.1), transparent 24%), linear-gradient(rgba(148,163,184,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.08) 1px, transparent 1px)"
            : "radial-gradient(circle at 22% 16%, rgba(96,165,250,0.1), transparent 20%), radial-gradient(circle at 82% 14%, rgba(167,139,250,0.08), transparent 18%), radial-gradient(circle at 50% 74%, rgba(34,197,94,0.08), transparent 24%), linear-gradient(rgba(148,163,184,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.12) 1px, transparent 1px)",
          backgroundSize: "auto, auto, auto, 26px 26px, 26px 26px",
          backgroundPosition: "center, center, center, center, center",
        }}
      />

      <div className="absolute inset-x-3 top-3 z-10 flex items-start justify-between gap-3">
        <div className={`rounded-2xl border px-3 py-2 backdrop-blur-md ${isDark ? "border-white/10 bg-black/35 text-slate-200" : "border-white/70 bg-white/70 text-stone-700"}`}>
          <p className={`text-[10px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Graph View</p>
          <p className="mt-1 text-sm font-medium">{renderedGraph.nodes.length} notes | {renderedGraph.edges.length} links</p>
          {focusNode ? (
            <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Focus: {focusNode.title}</p>
          ) : (
            <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{localMode ? "Showing the current note neighborhood." : "Hover a node to isolate its neighborhood."}</p>
          )}
        </div>

        <div className={`flex flex-wrap items-center gap-2 rounded-2xl border px-2 py-2 backdrop-blur-md ${isDark ? "border-white/10 bg-black/35" : "border-white/70 bg-white/70"}`}>
          <GraphButton label="+" onClick={() => runAction((cy) => cy.zoom({ level: cy.zoom() * 1.18, renderedPosition: { x: 180, y: 120 } }))} />
          <GraphButton label="-" onClick={() => runAction((cy) => cy.zoom({ level: cy.zoom() / 1.18, renderedPosition: { x: 180, y: 120 } }))} />
          <GraphButton label="Fit" onClick={() => runAction((cy) => cy.fit(undefined, 28))} wide />
          <GraphButton
            label={localMode ? "Global" : "Local"}
            onClick={() => setLocalMode((current) => !current)}
            wide
            active={localMode}
          />
          <GraphButton
            label="Reset"
            onClick={() =>
              runAction((cy) => {
                if (typeof window !== "undefined") {
                  window.localStorage.removeItem(POSITION_STORAGE_KEY)
                }
                cy.layout({
                  name: "cose",
                  animate: true,
                  fit: true,
                  padding: 30,
                  idealEdgeLength: 110,
                  nodeOverlap: 10,
                  componentSpacing: 50,
                }).run()
              })
            }
            wide
          />
        </div>
      </div>

      <div ref={containerRef} className={`relative z-[1] rounded-[1.35rem] ${heightClassName}`} />

      <div className="absolute bottom-3 left-3 z-10 flex flex-wrap gap-2">
        {[
          { label: "Characters", tone: "#8b5cf6" },
          { label: "Plot", tone: "#f97316" },
          { label: "World", tone: "#22c55e" },
          { label: "General", tone: "#60a5fa" },
          { label: labelsVisible ? "Labels on" : "Labels off", tone: labelsVisible ? "#f8fafc" : "#64748b" },
        ].map((item) => (
          <div
            key={item.label}
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] backdrop-blur-md ${isDark ? "border-white/10 bg-black/30 text-slate-300" : "border-white/70 bg-white/70 text-stone-600"}`}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.tone }} />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  )
}

function GraphButton({
  label,
  onClick,
  wide = false,
  active = false,
}: {
  label: string
  onClick: () => void
  wide?: boolean
  active?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
        active
          ? "border-sky-400/40 bg-sky-500/15 text-sky-100"
          : "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
      } ${wide ? "min-w-[3.8rem]" : "min-w-[2rem]"}`}
    >
      {label}
    </button>
  )
}
