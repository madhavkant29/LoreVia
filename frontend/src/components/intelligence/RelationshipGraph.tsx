"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import cytoscape from "cytoscape"
import { booksApi } from "@/lib/api/books"
import { RELATIONSHIP_COLORS } from "@/lib/constants"
import type { RelationshipGraph as GraphData } from "@/types/character"
import { readerApi } from "@/lib/api/reader"

interface Props {
  bookId: string
  upToChapter: number
  authorMode?: boolean
  theme?: "light" | "dark"
}

type Selection =
  | { type: "node"; data: GraphNodeView }
  | { type: "edge"; data: GraphEdgeView }
  | null

type GraphNode = GraphData["nodes"][number]
type GraphEdge = GraphData["edges"][number]
type GraphNodeView = GraphNode & { label: string; relationshipCount: number }
type GraphEdgeView = GraphEdge & { id: string; relationshipId?: string | null; label: string }

function graphStorageKey(bookId: string, chapter: number) {
  return `lorevia:graph-layout:${bookId}:${chapter}`
}

function graphLabelKey(bookId: string) {
  return `lorevia:graph-labels:${bookId}`
}

function relationshipLabel(value: string | null | undefined) {
  return (value || "connection").replaceAll("_", " ")
}

function sentimentLabel(value: unknown) {
  if (typeof value !== "number" || Number.isNaN(value)) return null
  if (value >= 0.45) return "Strongly positive"
  if (value >= 0.15) return "Positive"
  if (value <= -0.45) return "Strongly tense"
  if (value <= -0.15) return "Tense"
  return "Mixed or neutral"
}

export function RelationshipGraph({ bookId, upToChapter, authorMode = false, theme = "light" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selection, setSelection] = useState<Selection>(null)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [labelOverrides, setLabelOverrides] = useState<Record<string, string>>({})
  const [interactionMode, setInteractionMode] = useState<"arrange" | "inspect">("arrange")
  const [zoomLevel, setZoomLevel] = useState(1)
  const [edgeDraft, setEdgeDraft] = useState({ relType: "", description: "", sentiment: "0", fromChapter: "", toChapter: "" })
  const [savingEdge, setSavingEdge] = useState(false)
  const [edgeMessage, setEdgeMessage] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      const raw = window.localStorage.getItem(graphLabelKey(bookId))
      setLabelOverrides(raw ? JSON.parse(raw) : {})
    } catch {
      setLabelOverrides({})
    }
  }, [bookId])

  useEffect(() => {
    setLoading(true)
    readerApi.getRelationships(bookId, upToChapter)
      .then(setGraphData)
      .finally(() => setLoading(false))
  }, [bookId, upToChapter])

  const relationshipTypes = useMemo(() => {
    if (!graphData) return []
    return Array.from(new Set(graphData.edges.map((edge) => edge.type).filter(Boolean))).sort()
  }, [graphData])

  const filteredGraph = useMemo(() => {
    if (!graphData) return null
    const visibleEdges = graphData.edges.filter((edge) => !filterType || edge.type === filterType)
    const connected = new Set<string>()
    visibleEdges.forEach((edge) => {
      connected.add(edge.source)
      connected.add(edge.target)
    })
    const visibleNodes = graphData.nodes.filter((node) => connected.size === 0 || connected.has(node.id))
    return { nodes: visibleNodes, edges: visibleEdges }
  }, [graphData, filterType])

  const graphStats = useMemo(() => {
    if (!filteredGraph) return { nodeCount: 0, edgeCount: 0 }
    return { nodeCount: filteredGraph.nodes.length, edgeCount: filteredGraph.edges.length }
  }, [filteredGraph])

  useEffect(() => {
    if (!containerRef.current || !filteredGraph || filteredGraph.nodes.length === 0) return

    const savedPositions = (() => {
      if (typeof window === "undefined") return null
      try {
        const raw = window.localStorage.getItem(graphStorageKey(bookId, upToChapter))
        return raw ? JSON.parse(raw) as Record<string, { x: number; y: number }> : null
      } catch {
        return null
      }
    })()

    const nodeRelationshipCount = new Map<string, number>()
    filteredGraph.edges.forEach((edge) => {
      nodeRelationshipCount.set(edge.source, (nodeRelationshipCount.get(edge.source) || 0) + 1)
      nodeRelationshipCount.set(edge.target, (nodeRelationshipCount.get(edge.target) || 0) + 1)
    })

    const elements = [
      ...filteredGraph.nodes.map((node) => ({
        data: {
          ...node,
          label: labelOverrides[node.id] || node.name,
          relationshipCount: nodeRelationshipCount.get(node.id) || 0,
        },
        position: savedPositions?.[node.id],
      })),
      ...filteredGraph.edges.map((edge, index) => ({
        data: {
          ...edge,
          id: `${edge.source}-${edge.target}-${edge.type}-${index}`,
          relationshipId: edge.id,
          label: relationshipLabel(edge.type),
        },
      })),
    ]

    const hasPreset = filteredGraph.nodes.some((node) => Boolean(savedPositions?.[node.id]))

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      autoungrabify: interactionMode === "inspect",
      wheelSensitivity: 0.18,
      layout: hasPreset
        ? { name: "preset", fit: true, padding: 56 }
        : {
            name: "cose",
            animate: true,
            padding: 56,
            nodeRepulsion: () => 14500,
            idealEdgeLength: () => 164,
            edgeElasticity: () => 90,
            gravity: 70,
          },
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            width: (ele: any) => {
              const label = String(ele.data("label") || "")
              return Math.max(140, Math.min(244, 100 + label.length * 4.6))
            },
            height: (ele: any) => {
              const label = String(ele.data("label") || "")
              const lines = Math.max(2, Math.ceil(label.length / 16))
              return Math.max(98, Math.min(158, 62 + lines * 18))
            },
            shape: "round-rectangle",
            "background-color": theme === "dark" ? "#0a0a0a" : "#fffdf9",
            "background-opacity": 0.98,
            "border-width": 1.5,
            "border-color": theme === "dark" ? "#334155" : "#d6d3d1",
            color: theme === "dark" ? "#e5e7eb" : "#1f2937",
            "font-size": 13,
            "font-weight": 600,
            "text-wrap": "wrap",
            "text-max-width": "166px",
            "text-valign": "center",
            "text-halign": "center",
            padding: "16px",
            "overlay-padding": 6,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#2563eb",
            "border-width": 3,
            "background-color": theme === "dark" ? "#171717" : "#eef4ff",
          },
        },
        {
          selector: "edge",
          style: {
            width: "2.4px",
            "curve-style": "bezier",
            "line-color": (ele: any) => RELATIONSHIP_COLORS[ele.data("type")] || "#94a3b8",
            "target-arrow-color": (ele: any) => RELATIONSHIP_COLORS[ele.data("type")] || "#94a3b8",
            "target-arrow-shape": "triangle",
            "target-arrow-fill": "filled",
            opacity: 0.72,
            label: "data(label)",
            "font-size": 10,
            "font-weight": 600,
            color: theme === "dark" ? "#9ca3af" : "#6b7280",
            "text-background-color": theme === "dark" ? "#000000" : "#ffffff",
            "text-background-opacity": 0.96,
            "text-background-padding": "4px",
            "text-background-shape": "roundrectangle",
            "text-rotation": "autorotate",
            "arrow-scale": 0.9,
            "source-endpoint": "outside-to-node",
            "target-endpoint": "outside-to-node",
          },
        },
        {
          selector: "edge:selected",
          style: {
            width: "4px",
            opacity: 1,
          },
        },
      ],
    })

    cy.userPanningEnabled(true)
    cy.userZoomingEnabled(true)
    cy.boxSelectionEnabled(false)
    setZoomLevel(cy.zoom())

    cy.on("tap", "node", (evt) => setSelection({ type: "node", data: evt.target.data() as GraphNodeView }))
    cy.on("tap", "edge", (evt) => setSelection({ type: "edge", data: evt.target.data() as GraphEdgeView }))
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        setSelection(null)
        cy.elements().unselect()
      }
    })
    cy.on("dragfree", "node", () => {
      const positions = Object.fromEntries(cy.nodes().map((node) => [node.id(), node.position()]))
      if (typeof window !== "undefined") {
        window.localStorage.setItem(graphStorageKey(bookId, upToChapter), JSON.stringify(positions))
      }
    })
    cy.on("zoom", () => {
      setZoomLevel(cy.zoom())
    })

    cyRef.current = cy
    return () => cy.destroy()
  }, [bookId, upToChapter, filteredGraph, interactionMode, labelOverrides, theme])

  function updateNodeLabel(nodeId: string, value: string) {
    const fallback = graphData?.nodes.find((node) => node.id === nodeId)?.name || value
    const next = { ...labelOverrides, [nodeId]: value.trim() || fallback }
    setLabelOverrides(next)
    if (typeof window !== "undefined") {
      window.localStorage.setItem(graphLabelKey(bookId), JSON.stringify(next))
    }
  }

  function clearLabelOverride(node: GraphNode) {
    const next = { ...labelOverrides }
    delete next[node.id]
    setLabelOverrides(next)
    if (typeof window !== "undefined") {
      window.localStorage.setItem(graphLabelKey(bookId), JSON.stringify(next))
    }
  }

  function resetLayout() {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(graphStorageKey(bookId, upToChapter))
    }
    cyRef.current?.layout({
      name: "cose",
      animate: true,
      padding: 56,
      nodeRepulsion: () => 14500,
      idealEdgeLength: () => 164,
      edgeElasticity: () => 90,
      gravity: 70,
    }).run()
  }

  function focusSelection() {
    if (!cyRef.current || selection?.type !== "node") return
    const node = cyRef.current.getElementById(selection.data.id)
    if (node.nonempty()) {
      cyRef.current.animate({
        center: { eles: node },
        zoom: Math.min(1.35, cyRef.current.zoom() + 0.1),
        duration: 240,
      })
    }
  }

  function adjustZoom(direction: "in" | "out") {
    const cy = cyRef.current
    if (!cy) return
    const factor = direction === "in" ? 1.18 : 1 / 1.18
    const nextZoom = Math.max(0.3, Math.min(2.4, cy.zoom() * factor))
    cy.zoom({ level: nextZoom, position: { x: cy.width() / 2, y: cy.height() / 2 } })
    setZoomLevel(cy.zoom())
  }

  function resetZoom() {
    const cy = cyRef.current
    if (!cy) return
    cy.zoom({ level: 1, position: { x: cy.width() / 2, y: cy.height() / 2 } })
    setZoomLevel(cy.zoom())
  }

  const selectedNode = selection?.type === "node" ? selection.data : null
  const selectedEdge = selection?.type === "edge" ? selection.data : null

  useEffect(() => {
    if (!selectedEdge) return
    setEdgeDraft({
      relType: selectedEdge.type || "",
      description: selectedEdge.description || "",
      sentiment: typeof selectedEdge.sentiment === "number" ? String(selectedEdge.sentiment) : "0",
      fromChapter: typeof selectedEdge.from_chapter === "number" ? String(selectedEdge.from_chapter) : "",
      toChapter: typeof selectedEdge.to_chapter === "number" ? String(selectedEdge.to_chapter) : "",
    })
    setEdgeMessage(null)
  }, [selectedEdge])

  if (loading) {
    return (
      <div className={`rounded-[1.75rem] border p-8 text-sm ${theme === "dark" ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-slate-200 bg-white text-slate-600"}`}>
        Building the relationship graph...
      </div>
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section className={`rounded-[1.9rem] border p-4 ${theme === "dark" ? "border-white/10 bg-[#050505]" : "border-slate-200 bg-white"}`}>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className={`text-lg font-semibold ${theme === "dark" ? "text-white" : "text-slate-900"}`}>Relationship graph</h2>
            <p className={`mt-1 text-sm ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>Arrange the map to match how you read it. Drag nodes, zoom the canvas, and keep a saved layout on this device.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setInteractionMode((current) => current === "arrange" ? "inspect" : "arrange")}
              className={`rounded-full px-3 py-2 text-xs font-medium ${interactionMode === "arrange" ? "bg-slate-900 text-white" : theme === "dark" ? "border border-white/10 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}
            >
              {interactionMode === "arrange" ? "Arrange mode" : "Inspect mode"}
            </button>
            <button onClick={() => adjustZoom("out")} className={`rounded-full px-3 py-2 text-xs font-medium ${theme === "dark" ? "border border-white/10 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}>Zoom out</button>
            <button onClick={() => adjustZoom("in")} className={`rounded-full px-3 py-2 text-xs font-medium ${theme === "dark" ? "border border-white/10 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}>Zoom in</button>
            <button onClick={resetZoom} className={`rounded-full px-3 py-2 text-xs font-medium ${theme === "dark" ? "border border-white/10 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}>Reset zoom</button>
            <button onClick={() => cyRef.current?.fit(undefined, 56)} className={`rounded-full px-3 py-2 text-xs font-medium ${theme === "dark" ? "border border-white/10 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}>Fit</button>
            <button onClick={focusSelection} disabled={selection?.type !== "node"} className={`rounded-full px-3 py-2 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50 ${theme === "dark" ? "border border-white/10 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}>Center selection</button>
            <button onClick={resetLayout} className={`rounded-full px-3 py-2 text-xs font-medium ${theme === "dark" ? "border border-white/10 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}>Reset layout</button>
          </div>
        </div>

        <div className={`mb-4 flex flex-wrap items-center gap-3 rounded-[1.2rem] border px-4 py-3 text-xs ${theme === "dark" ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-slate-200 bg-stone-50 text-slate-600"}`}>
          <span className="font-medium">{graphStats.nodeCount} characters</span>
          <span className="opacity-60">•</span>
          <span className="font-medium">{graphStats.edgeCount} connections</span>
          <span className="opacity-60">•</span>
          <span>{interactionMode === "arrange" ? "Nodes are draggable right now." : "Nodes are locked so you can inspect without accidental movement."}</span>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          <button
            onClick={() => setFilterType(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium ${filterType === null ? "bg-slate-900 text-white" : theme === "dark" ? "border border-white/10 text-slate-300 hover:bg-white/5" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}
          >
            All
          </button>
          {relationshipTypes.map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${filterType === type ? "text-white" : theme === "dark" ? "border border-white/10 text-slate-300 hover:bg-white/5" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}
              style={filterType === type ? { backgroundColor: RELATIONSHIP_COLORS[type] || "#475569" } : undefined}
            >
              {relationshipLabel(type)}
            </button>
          ))}
        </div>

        {filteredGraph && filteredGraph.nodes.length > 0 ? (
          <div
            ref={containerRef}
            className={`h-[58vh] min-h-[380px] rounded-[1.5rem] border md:h-[72vh] md:min-h-[560px] ${theme === "dark" ? "border-white/5 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.06),_transparent_30%),linear-gradient(180deg,#000000_0%,#0a0a0a_100%)]" : "border-slate-200 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.09),_transparent_26%),linear-gradient(180deg,#f8fafc_0%,#f5f5f4_100%)]"}`}
            style={{ cursor: interactionMode === "arrange" ? "grab" : "default" }}
          />
        ) : (
          <div className={`flex h-[40vh] min-h-[340px] items-center justify-center rounded-[1.5rem] border text-center ${theme === "dark" ? "border-white/5 bg-[linear-gradient(180deg,#000000_0%,#0a0a0a_100%)] text-slate-400" : "border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#f5f5f4_100%)] text-slate-500"}`}>
            <div className="max-w-sm space-y-2 px-6">
              <p className="text-lg font-semibold">No graphable relationships yet</p>
              <p className="text-sm leading-6">Read further or clear the active filter to see more of the character network.</p>
            </div>
          </div>
        )}
      </section>

      <aside className={`rounded-[1.9rem] border p-5 xl:sticky xl:top-6 xl:max-h-[84vh] xl:overflow-y-auto ${theme === "dark" ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-slate-200 bg-white text-slate-800"}`}>
        {selectedNode ? (
          <div className="space-y-5">
            <div>
              <p className={`text-xs uppercase tracking-[0.2em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Character</p>
              <h3 className="mt-2 text-2xl font-semibold">{selectedNode.name}</h3>
            </div>

            <div className={`rounded-[1.2rem] border p-4 ${theme === "dark" ? "border-white/10 bg-black/20" : "border-slate-200 bg-slate-50"}`}>
              <label className={`mb-2 block text-xs uppercase tracking-[0.16em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Display label</label>
              <input
                value={labelOverrides[selectedNode.id] || selectedNode.name}
                onChange={(e) => updateNodeLabel(selectedNode.id, e.target.value)}
                className={`w-full rounded-xl border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-white" : "border-slate-300 bg-white text-slate-900"}`}
              />
              <button
                onClick={() => clearLabelOverride(selectedNode)}
                className={`mt-2 text-xs font-medium ${theme === "dark" ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}
              >
                Reset to canonical name
              </button>
            </div>

            <div className={`rounded-[1.2rem] border p-4 ${theme === "dark" ? "border-white/10 bg-black/20" : "border-slate-200 bg-slate-50"}`}>
              <p className={`text-xs uppercase tracking-[0.16em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Reading note</p>
              <p className={`mt-3 text-sm leading-7 ${theme === "dark" ? "text-slate-300" : "text-slate-600"}`}>{selectedNode.description || "No narrative summary has been saved yet."}</p>
            </div>

            {"arc_summary" in selectedNode && selectedNode.arc_summary ? (
              <div className={`rounded-[1.2rem] border p-4 ${theme === "dark" ? "border-white/10 bg-black/20" : "border-slate-200 bg-slate-50"}`}>
                <p className={`text-xs uppercase tracking-[0.16em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Arc summary</p>
                <p className={`mt-3 text-sm leading-7 ${theme === "dark" ? "text-slate-300" : "text-slate-600"}`}>{selectedNode.arc_summary}</p>
              </div>
            ) : null}

            {selectedNode.aliases?.length ? (
              <div>
                <p className={`text-xs uppercase tracking-[0.16em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Aliases</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedNode.aliases.map((alias) => (
                    <span key={alias} className={`rounded-full px-3 py-1.5 text-xs ${theme === "dark" ? "bg-white/8 text-slate-200" : "bg-slate-100 text-slate-700"}`}>
                      {alias}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {selectedNode.personality_tags?.length ? <p className="text-sm leading-7"><span className="font-medium">Disposition:</span> {selectedNode.personality_tags.join(", ")}</p> : null}
            {selectedNode.motivations?.length ? <p className="text-sm leading-7"><span className="font-medium">Motivations:</span> {selectedNode.motivations.join(", ")}</p> : null}
            {selectedNode.fears?.length ? <p className="text-sm leading-7"><span className="font-medium">Fears:</span> {selectedNode.fears.join(", ")}</p> : null}

            <div className={`rounded-[1.2rem] border p-4 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
              <div className="flex items-center justify-between gap-3">
                <span>Connections in view</span>
                <span className="font-semibold">{selectedNode.relationshipCount ?? 0}</span>
              </div>
            </div>
          </div>
        ) : selectedEdge ? (
          <div className="space-y-5">
            <div>
              <p className={`text-xs uppercase tracking-[0.2em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Connection</p>
              <h3 className="mt-2 text-2xl font-semibold">{relationshipLabel(selectedEdge.type)}</h3>
            </div>

            <div className={`rounded-[1.2rem] border p-4 ${theme === "dark" ? "border-white/10 bg-black/20" : "border-slate-200 bg-slate-50"}`}>
              <p className={`text-xs uppercase tracking-[0.16em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Relationship note</p>
              <p className={`mt-3 text-sm leading-7 ${theme === "dark" ? "text-slate-300" : "text-slate-600"}`}>{selectedEdge.description || "No explicit relationship note has been saved yet."}</p>
            </div>

            {typeof selectedEdge.from_chapter === "number" ? <p className="text-sm"><span className="font-medium">First tracked:</span> Chapter {selectedEdge.from_chapter}</p> : null}
            {typeof selectedEdge.to_chapter === "number" ? <p className="text-sm"><span className="font-medium">Ended:</span> Chapter {selectedEdge.to_chapter}</p> : null}

            {sentimentLabel(selectedEdge.sentiment) ? (
              <div className={`rounded-[1.2rem] border p-4 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
                <div className="flex items-center justify-between gap-3">
                  <span>Emotional direction</span>
                  <span className="font-semibold">{sentimentLabel(selectedEdge.sentiment)}</span>
                </div>
              </div>
            ) : null}

            {authorMode && selectedEdge.relationshipId ? (
              <div className={`rounded-[1.2rem] border p-4 ${theme === "dark" ? "border-white/10 bg-black/20" : "border-slate-200 bg-slate-50"}`}>
                <div className="mb-3">
                  <p className={`text-xs uppercase tracking-[0.16em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Author correction</p>
                  <p className={`mt-2 text-sm leading-6 ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>
                    Correct the extracted relationship if the manuscript context is clearer than the model guess.
                  </p>
                </div>
                <div className="space-y-3">
                  <label className="block">
                    <span className={`mb-1 block text-xs ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>Type</span>
                    <input
                      value={edgeDraft.relType}
                      onChange={(event) => setEdgeDraft((value) => ({ ...value, relType: event.target.value }))}
                      className={`w-full rounded-xl border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-white" : "border-slate-300 bg-white text-slate-900"}`}
                    />
                  </label>
                  <label className="block">
                    <span className={`mb-1 block text-xs ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>Relationship note</span>
                    <textarea
                      value={edgeDraft.description}
                      onChange={(event) => setEdgeDraft((value) => ({ ...value, description: event.target.value }))}
                      rows={4}
                      className={`w-full rounded-xl border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-white" : "border-slate-300 bg-white text-slate-900"}`}
                    />
                  </label>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <label className="block">
                      <span className={`mb-1 block text-xs ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>Sentiment</span>
                      <input
                        type="number"
                        min={-1}
                        max={1}
                        step={0.1}
                        value={edgeDraft.sentiment}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, sentiment: event.target.value }))}
                        className={`w-full rounded-xl border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-white" : "border-slate-300 bg-white text-slate-900"}`}
                      />
                    </label>
                    <label className="block">
                      <span className={`mb-1 block text-xs ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>From chapter</span>
                      <input
                        type="number"
                        min={1}
                        value={edgeDraft.fromChapter}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, fromChapter: event.target.value }))}
                        className={`w-full rounded-xl border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-white" : "border-slate-300 bg-white text-slate-900"}`}
                      />
                    </label>
                    <label className="block">
                      <span className={`mb-1 block text-xs ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>Ends chapter</span>
                      <input
                        type="number"
                        min={1}
                        value={edgeDraft.toChapter}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, toChapter: event.target.value }))}
                        placeholder="Leave blank if ongoing"
                        className={`w-full rounded-xl border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-white" : "border-slate-300 bg-white text-slate-900"}`}
                      />
                    </label>
                  </div>
                  {edgeMessage ? <p className={`text-sm ${edgeMessage.includes("saved") ? "text-emerald-500" : "text-red-500"}`}>{edgeMessage}</p> : null}
                  <button
                    type="button"
                    disabled={savingEdge}
                    onClick={async () => {
                      if (!selectedEdge.relationshipId) return
                      setSavingEdge(true)
                      setEdgeMessage(null)
                      try {
                        const updated = await booksApi.updateRelationship(bookId, selectedEdge.relationshipId, {
                          relType: edgeDraft.relType.trim(),
                          description: edgeDraft.description.trim() || null,
                          sentiment: edgeDraft.sentiment === "" ? null : Number(edgeDraft.sentiment),
                          fromChapter: edgeDraft.fromChapter === "" ? null : Number(edgeDraft.fromChapter),
                          toChapter: edgeDraft.toChapter === "" ? null : Number(edgeDraft.toChapter),
                        })
                        setGraphData((current) => current ? ({
                          ...current,
                          edges: current.edges.map((edge) => edge.id === selectedEdge.relationshipId ? {
                            ...edge,
                            type: updated.rel_type,
                            description: updated.description,
                            sentiment: updated.sentiment,
                            from_chapter: updated.from_chapter,
                            to_chapter: updated.to_chapter,
                          } : edge),
                        }) : current)
                        setSelection((current) => current?.type === "edge" ? {
                          type: "edge",
                          data: {
                            ...current.data,
                            type: updated.rel_type,
                            description: updated.description,
                            sentiment: updated.sentiment,
                            from_chapter: updated.from_chapter,
                            to_chapter: updated.to_chapter,
                          },
                        } : current)
                        setEdgeMessage("Relationship correction saved.")
                      } catch {
                        setEdgeMessage("Could not save the relationship correction.")
                      } finally {
                        setSavingEdge(false)
                      }
                    }}
                    className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-60"
                  >
                    {savingEdge ? "Saving..." : "Save correction"}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <p className={`text-xs uppercase tracking-[0.2em] ${theme === "dark" ? "text-slate-500" : "text-slate-500"}`}>Inspector</p>
              <h3 className="mt-2 text-2xl font-semibold">Read the map</h3>
            </div>
            <p className={`text-sm leading-7 ${theme === "dark" ? "text-slate-400" : "text-slate-500"}`}>
              Select a character to inspect their role in the network, or select a connection to read the relationship note. Arrange mode is best when you want to cluster the cast your own way.
            </p>
            <div className={`rounded-[1.2rem] border p-4 text-sm ${theme === "dark" ? "border-white/10 bg-black/20 text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
              <div className="flex items-center justify-between gap-3">
                <span>Visible characters</span>
                <span className="font-semibold">{graphStats.nodeCount}</span>
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <span>Visible connections</span>
                <span className="font-semibold">{graphStats.edgeCount}</span>
              </div>
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
