"use client"

import Link from "next/link"
import { memo, type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import cytoscape from "cytoscape"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { RELATIONSHIP_COLORS } from "@/lib/constants"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { cn } from "@/lib/utils/text"
import type { RelationshipGraph as GraphData } from "@/types/character"
import {
  BASE_LAYOUT,
  buildIsolatedPositions,
  controlButtonClass,
  panelClass,
} from "./RelationshipGraph.helpers"

import {
  DIRECTIONAL_RELATIONSHIP_LABEL_OPTIONS,
  PRIMARY_RELATIONSHIP_TYPE_OPTIONS,
  SHARED_RELATIONSHIP_LABEL_OPTIONS,
  graphLabelKey,
  graphStorageKey,
  nodeInitial,
  relationshipFacetLabel,
  relationshipFacetSummary,
  relationshipLabel,
  sentimentLabel,
  zoomPercentLabel,
} from "./relationshipGraphDisplay"

interface Props {
  bookId: string
  upToChapter: number
  authorMode?: boolean
  includeInactive?: boolean
  theme?: "light" | "dark"
  compact?: boolean
  focusCharacterId?: string | null
  onSelectCharacterId?: (characterId: string | null) => void
  onGraphDataChange?: (graph: GraphData) => void
}

type Selection =
  | { type: "node"; data: GraphNodeView }
  | { type: "edge"; data: GraphEdgeView }
  | null

type GraphNode = GraphData["nodes"][number]
type GraphEdge = GraphData["edges"][number]
type GraphNodeView = GraphNode & { label: string; relationshipCount: number }
type GraphEdgeView = GraphEdge & { id: string; relationshipId?: string | null; label: string }
type InteractionMode = "arrange" | "inspect"
type GraphTestHandle = {
  cy: cytoscape.Core
  selectNode: (id: string) => void
  selectEdge: (id: string) => void
  clearSelection: () => void
}

function GraphToolbarButton({
  active = false,
  ariaPressed,
  children,
  disabled = false,
  icon,
  onClick,
}: {
  active?: boolean
  ariaPressed?: boolean
  children: ReactNode
  disabled?: boolean
  icon: ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-pressed={ariaPressed}
      disabled={disabled}
      onClick={onClick}
      className={cn(controlButtonClass(active), disabled && "cursor-not-allowed opacity-45")}
    >
      {icon}
      <span>{children}</span>
    </button>
  )
}

function GraphStatusPill({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300">
      <span className="text-slate-400">{icon}</span>
      <span>{children}</span>
    </div>
  )
}

function FilterSelect({
  filterId,
  filterType,
  relationshipTypes,
  setFilterType,
}: {
  filterId: string
  filterType: string | null
  relationshipTypes: string[]
  setFilterType: (value: string | null) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={filterId} className="sr-only">Filter relationships</label>
      <div className="relative min-w-[132px]">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
          <FilterIcon className="h-4 w-4" />
        </span>
        <select
          id={filterId}
          aria-label="Filter relationships"
          value={filterType ?? ""}
          onChange={(event) => setFilterType(event.target.value || null)}
          className="w-full appearance-none rounded-xl border border-white/10 bg-[#0b1020] py-2 pl-9 pr-9 text-sm text-slate-100 transition hover:border-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
        >
          <option value="">All</option>
          {relationshipTypes.map((type) => (
            <option key={type} value={type}>
              {relationshipLabel(type)}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">
          <ChevronDownIcon className="h-4 w-4" />
        </span>
      </div>
    </div>
  )
}

function InspectorMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-300">{label}</span>
      <span className="font-semibold text-white">{value}</span>
    </div>
  )
}

function RelationshipLabelChecklist({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: readonly string[]
  selected: string[]
  onChange: (labels: string[]) => void
}) {
  const selectedSet = new Set(selected)
  return (
    <fieldset className="rounded-lg border border-white/10 bg-black/15 p-3">
      <legend className="px-1 text-xs text-slate-400">{label}</legend>
      <div className="mt-2 grid max-h-36 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
        {options.map((option) => (
          <label key={option} className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1 text-xs text-slate-300 hover:bg-white/[0.04]">
            <input
              type="checkbox"
              checked={selectedSet.has(option)}
              onChange={(event) => {
                if (event.target.checked) {
                  onChange(Array.from(new Set([...selected, option])))
                } else {
                  onChange(selected.filter((item) => item !== option))
                }
              }}
              className="h-3.5 w-3.5 rounded border-white/20 bg-[#0b1020] text-violet-500 focus:ring-violet-400"
            />
            <span className="truncate">{relationshipFacetLabel(option)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function InspectorSection({
  children,
  title,
}: {
  children: ReactNode
  title: string
}) {
  return (
    <section className="rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-3xs font-semibold uppercase tracking-[0.24em] text-slate-500">{title}</p>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function EmptyInspector({
  edgeCount,
  nodeCount,
}: {
  edgeCount: number
  nodeCount: number
}) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-violet-300/85">Inspector</p>
        <h3 className="mt-3 text-[2rem] font-semibold tracking-tight text-white">Read the map</h3>
      </div>

      <p className="text-sm leading-7 text-slate-400">
        Select a character to inspect their role in the network, or select a connection to read the relationship note. Arrange mode is best when you want to cluster the cast your own way.
      </p>

      <InspectorSection title="Visible now">
        <div className="space-y-3 text-sm">
          <InspectorMetric label="Visible characters" value={nodeCount} />
          <InspectorMetric label="Visible connections" value={edgeCount} />
        </div>
      </InspectorSection>

      <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed border-white/10 bg-[radial-gradient(circle_at_top,rgba(139,92,246,0.18),transparent_38%),rgba(255,255,255,0.02)] px-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full border border-violet-400/40 bg-violet-500/8 text-violet-200">
          <CursorIcon className="h-7 w-7" />
        </div>
        <p className="mt-5 text-lg font-semibold text-white">Select a character or connection</p>
        <p className="mt-2 max-w-xs text-sm leading-7 text-slate-400">
          Use the graph to explore relationships between characters in your manuscript.
        </p>
      </div>

      <InspectorSection title="Tip">
        <p className="text-sm leading-7 text-slate-300">
          Drag nodes to cluster related characters. Your layout is saved automatically.
        </p>
      </InspectorSection>
    </div>
  )
}

function CompactSelectionSummary({
  selectedEdge,
  selectedNode,
}: {
  selectedEdge: GraphEdgeView | null
  selectedNode: GraphNodeView | null
}) {
  if (selectedNode) {
    return <>{selectedNode.name} selected. {selectedNode.relationshipCount ?? 0} visible ties.</>
  }

  if (selectedEdge) {
    return <>{relationshipLabel(selectedEdge.type)} selected.</>
  }

  return <>Select a node to sync the graph with the character profile.</>
}

function installGraphTestHandle(cy: cytoscape.Core) {
  if (typeof window === "undefined" || process.env.NODE_ENV === "production") return

  const graphWindow = window as Window & {
    __LOREVIA_RELATIONSHIP_GRAPH__?: GraphTestHandle
  }

  graphWindow.__LOREVIA_RELATIONSHIP_GRAPH__ = {
    cy,
    selectNode: (id: string) => {
      const node = cy.getElementById(id)
      if (node.nonempty()) {
        node.emit("tap")
      }
    },
    selectEdge: (id: string) => {
      const directEdge = cy.getElementById(id)
      const edge = directEdge.nonempty()
        ? directEdge
        : cy.edges().filter((item) => item.data("relationshipId") === id)
      if (edge.nonempty()) {
        edge.emit("tap")
      }
    },
    clearSelection: () => {
      cy.emit("tap", [{ target: cy }])
    },
  }
}

function clearGraphTestHandle(cy: cytoscape.Core) {
  if (typeof window === "undefined" || process.env.NODE_ENV === "production") return

  const graphWindow = window as Window & {
    __LOREVIA_RELATIONSHIP_GRAPH__?: GraphTestHandle
  }

  if (graphWindow.__LOREVIA_RELATIONSHIP_GRAPH__?.cy === cy) {
    delete graphWindow.__LOREVIA_RELATIONSHIP_GRAPH__
  }
}

export const RelationshipGraph = memo(function RelationshipGraph({
  bookId,
  upToChapter,
  authorMode = false,
  includeInactive = false,
  theme = "light",
  compact = false,
  focusCharacterId = null,
  onSelectCharacterId,
  onGraphDataChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const selectCharacterRef = useRef(onSelectCharacterId)
  const layoutPersistTimerRef = useRef<number | null>(null)
  const filterId = useId()
  const labelInputId = useId()
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [selection, setSelection] = useState<Selection>(null)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [showIsolated, setShowIsolated] = useState(authorMode)
  const [labelOverrides, setLabelOverrides] = useState<Record<string, string>>({})
  const [interactionMode, setInteractionMode] = useState<InteractionMode>("arrange")
  const [zoomLevel, setZoomLevel] = useState(1)
  const [showGrid, setShowGrid] = useState(true)
  const [edgeDraft, setEdgeDraft] = useState({
    relType: "",
    description: "",
    sentiment: "0",
    fromChapter: "",
    toChapter: "",
    sharedLabels: [] as string[],
    sourceToTargetLabels: [] as string[],
    targetToSourceLabels: [] as string[],
  })
  const [savingEdge, setSavingEdge] = useState(false)
  const [edgeMessage, setEdgeMessage] = useState<string | null>(null)

  const { data: graphQueryData = null, isLoading: loading } = useQuery<GraphData | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, `relationships:${upToChapter}:${includeInactive ? "all" : "active"}`)),
    queryFn: () => readerApi.getRelationships(bookId, upToChapter, { includeInactive, include: "nodes,edges,hidden_nodes" }),
  })

  useEffect(() => {
    selectCharacterRef.current = onSelectCharacterId
  }, [onSelectCharacterId])

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
    setGraphData(graphQueryData)
    if (graphQueryData) {
      onGraphDataChange?.(graphQueryData)
    }
  }, [graphQueryData, onGraphDataChange])

  useEffect(() => {
    setShowIsolated(authorMode)
  }, [authorMode])

  const relationshipTypes = useMemo(() => {
    if (!graphData) return []
    return Array.from(new Set(graphData.edges.map((edge) => edge.type).filter(Boolean))).sort()
  }, [graphData])

  const filteredGraph = useMemo(() => {
    if (!graphData) return null
    const visibleEdges = graphData.edges.filter((edge) => !filterType || edge.type === filterType)

    if (showIsolated) {
      return { nodes: graphData.nodes, edges: visibleEdges }
    }

    const connected = new Set<string>()
    visibleEdges.forEach((edge) => {
      connected.add(edge.source)
      connected.add(edge.target)
    })

    const visibleNodes = graphData.nodes.filter((node) => connected.size === 0 || connected.has(node.id))
    return { nodes: visibleNodes, edges: visibleEdges }
  }, [graphData, filterType, showIsolated])

  const graphStats = useMemo(() => {
    if (!filteredGraph) return { nodeCount: 0, edgeCount: 0 }
    return { nodeCount: filteredGraph.nodes.length, edgeCount: filteredGraph.edges.length }
  }, [filteredGraph])

  const nodeLookup = useMemo(() => new Map((graphData?.nodes ?? []).map((node) => [node.id, node])), [graphData])

  const selectedNode = selection?.type === "node" ? selection.data : null
  const selectedEdge = selection?.type === "edge" ? selection.data : null

  const selectedNodeConnections = useMemo(() => {
    if (!selectedNode || !filteredGraph) return []

    return filteredGraph.edges
      .filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
      .map((edge, index) => {
        const otherId = edge.source === selectedNode.id ? edge.target : edge.source
        const otherNode = nodeLookup.get(otherId)
        return {
          id: `${otherId}-${edge.type}-${index}`,
          label: relationshipFacetSummary([...(edge.character_a_to_b_labels ?? []), ...(edge.character_b_to_a_labels ?? []), ...(edge.shared_labels ?? [])], edge.type),
          name: otherNode?.name ?? "Unknown character",
          chapter: edge.from_chapter,
        }
      })
  }, [filteredGraph, nodeLookup, selectedNode])

  const selectedEdgeParticipants = useMemo(() => {
    if (!selectedEdge) return null
    return {
      source: nodeLookup.get(selectedEdge.source)?.name ?? "Unknown character",
      target: nodeLookup.get(selectedEdge.target)?.name ?? "Unknown character",
    }
  }, [nodeLookup, selectedEdge])

  const relationshipStylesheet = useMemo<any>(
    () => [
      {
        selector: "node",
        style: {
          label: "data(label)",
          width: (ele: cytoscape.NodeSingular) => {
            const label = String(ele.data("label") || "")
            return Math.max(98, Math.min(156, 76 + label.length * 3.6))
          },
          height: (ele: cytoscape.NodeSingular) => {
            const label = String(ele.data("label") || "")
            const lines = Math.max(1, Math.ceil(label.length / 14))
            return Math.max(52, Math.min(80, 38 + lines * 14))
          },
          shape: "round-rectangle",
          "background-color": theme === "dark" ? "#0b1020" : "#fffdf9",
          "background-opacity": 0.98,
          "border-width": 1.4,
          "border-color": (ele: cytoscape.NodeSingular) => {
            if (ele.data("graph_visibility_override") === "include") return "#14b8a6"
            if (ele.data("is_manual")) return "#f59e0b"
            return theme === "dark" ? "#6d5bd0" : "#c4b5fd"
          },
          color: theme === "dark" ? "#f8fafc" : "#111827",
          "font-size": 11,
          "font-weight": 600,
          "text-wrap": "wrap",
          "text-max-width": "100px",
          "text-valign": "center",
          "text-halign": "center",
          padding: "8px",
          "overlay-padding": 8,
          "overlay-opacity": 0,
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-color": "#8b5cf6",
          "border-width": 2.6,
          "background-color": theme === "dark" ? "#11172a" : "#eef4ff",
        },
      },
      {
        selector: "edge",
        style: {
          width: "1.6px",
          "curve-style": "bezier",
          "line-color": (ele: cytoscape.EdgeSingular) => RELATIONSHIP_COLORS[ele.data("type")] || "#64748b",
          "target-arrow-color": (ele: cytoscape.EdgeSingular) => RELATIONSHIP_COLORS[ele.data("type")] || "#64748b",
          "target-arrow-shape": "triangle",
          "target-arrow-fill": "filled",
          opacity: 0.5,
          label: "data(label)",
          "font-size": 9,
          "font-weight": 600,
          color: theme === "dark" ? "#94a3b8" : "#6b7280",
          "text-background-color": theme === "dark" ? "#04050b" : "#ffffff",
          "text-background-opacity": 0.94,
          "text-background-padding": "3px",
          "text-background-shape": "roundrectangle",
          "text-rotation": "autorotate",
          "arrow-scale": 0.8,
          "source-endpoint": "outside-to-node",
          "target-endpoint": "outside-to-node",
        },
      },
      {
        selector: "edge:selected",
        style: {
          width: "3.2px",
          opacity: 0.96,
        },
      },
    ],
    [theme],
  )

  useEffect(() => {
    if (!containerRef.current || !filteredGraph || filteredGraph.nodes.length === 0) return

    const savedPositions = (() => {
      if (typeof window === "undefined") return null

      try {
        const raw = window.localStorage.getItem(graphStorageKey(bookId, upToChapter))
        return raw ? (JSON.parse(raw) as Record<string, { x: number; y: number }>) : null
      } catch {
        return null
      }
    })()

    const nodeRelationshipCount = new Map<string, number>()
    filteredGraph.edges.forEach((edge) => {
      nodeRelationshipCount.set(edge.source, (nodeRelationshipCount.get(edge.source) || 0) + 1)
      nodeRelationshipCount.set(edge.target, (nodeRelationshipCount.get(edge.target) || 0) + 1)
    })

    const generatedPositions = !savedPositions && filteredGraph.edges.length === 0 ? buildIsolatedPositions(filteredGraph.nodes) : null

    const elements: cytoscape.ElementDefinition[] = [
      ...filteredGraph.nodes.map((node) => ({
        data: {
          ...node,
          label: labelOverrides[node.id] || node.name,
          relationshipCount: nodeRelationshipCount.get(node.id) || 0,
        },
        position: savedPositions?.[node.id] ?? generatedPositions?.[node.id],
      })),
      ...filteredGraph.edges.map((edge, index) => ({
        data: {
          ...edge,
          id: `${edge.source}-${edge.target}-${edge.type}-${index}`,
          relationshipId: edge.id,
          label: relationshipFacetSummary([...(edge.character_a_to_b_labels ?? []), ...(edge.character_b_to_a_labels ?? []), ...(edge.shared_labels ?? [])], edge.type),
        },
      })),
    ]

    const hasPreset = filteredGraph.nodes.some((node) => Boolean(savedPositions?.[node.id]))
    const shouldUsePreset = hasPreset || Boolean(generatedPositions)

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      autoungrabify: interactionMode === "inspect",
      wheelSensitivity: 0.18,
      layout: shouldUsePreset ? { name: "preset", fit: true, padding: 96 } : BASE_LAYOUT,
      style: relationshipStylesheet,
    })

    cy.userPanningEnabled(true)
    cy.userZoomingEnabled(true)
    cy.boxSelectionEnabled(false)

    if (compact) {
      window.setTimeout(() => {
        if (!cy.destroyed()) {
          cy.fit(undefined, 92)
          if (cy.zoom() > 0.72) {
            cy.zoom({ level: 0.72, position: { x: cy.width() / 2, y: cy.height() / 2 } })
          }
          setZoomLevel(cy.zoom())
        }
      }, shouldUsePreset ? 30 : 260)
    } else {
      setZoomLevel(cy.zoom())
    }

    cy.on("tap", "node", (event) => {
      const nextSelection = { type: "node", data: event.target.data() as GraphNodeView } as const
      setSelection(nextSelection)
      selectCharacterRef.current?.(nextSelection.data.id)
    })

    cy.on("tap", "edge", (event) => {
      setSelection({ type: "edge", data: event.target.data() as GraphEdgeView })
    })

    cy.on("tap", (event) => {
      if (event.target === cy) {
        setSelection(null)
        cy.elements().unselect()
      }
    })

    cy.on("dragfree", "node", () => {
      const positions = Object.fromEntries(cy.nodes().map((node) => [node.id(), node.position()]))
      if (typeof window !== "undefined") {
        if (layoutPersistTimerRef.current) {
          window.clearTimeout(layoutPersistTimerRef.current)
        }
        layoutPersistTimerRef.current = window.setTimeout(() => {
          window.localStorage.setItem(graphStorageKey(bookId, upToChapter), JSON.stringify(positions))
          layoutPersistTimerRef.current = null
        }, 180)
      }
    })

    cy.on("zoom", () => {
      setZoomLevel(cy.zoom())
    })

    cyRef.current = cy
    installGraphTestHandle(cy)

    return () => {
      if (layoutPersistTimerRef.current) {
        window.clearTimeout(layoutPersistTimerRef.current)
        layoutPersistTimerRef.current = null
      }

      const positions = Object.fromEntries(cy.nodes().map((node) => [node.id(), node.position()]))
      if (typeof window !== "undefined") {
        window.localStorage.setItem(graphStorageKey(bookId, upToChapter), JSON.stringify(positions))
      }
      clearGraphTestHandle(cy)
      cy.destroy()
    }
  }, [bookId, compact, filteredGraph, interactionMode, labelOverrides, theme, upToChapter])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !focusCharacterId) return

    const node = cy.getElementById(focusCharacterId)
    if (node.empty()) return

    cy.elements().unselect()
    node.select()
    setSelection({ type: "node", data: node.data() as GraphNodeView })

    if (compact) {
      cy.animate({
        center: { eles: node },
        zoom: Math.min(cy.zoom(), 0.72),
        duration: 220,
      })
    }
  }, [compact, filteredGraph, focusCharacterId])

  useEffect(() => {
    if (!selectedEdge) return

    setEdgeDraft({
      relType: selectedEdge.type || "",
      description: selectedEdge.description || "",
      sentiment: typeof selectedEdge.sentiment === "number" ? String(selectedEdge.sentiment) : "0",
      fromChapter: typeof selectedEdge.from_chapter === "number" ? String(selectedEdge.from_chapter) : "",
      toChapter: typeof selectedEdge.to_chapter === "number" ? String(selectedEdge.to_chapter) : "",
      sharedLabels: selectedEdge.shared_labels ?? [],
      sourceToTargetLabels: selectedEdge.character_a_to_b_labels ?? [],
      targetToSourceLabels: selectedEdge.character_b_to_a_labels ?? [],
    })
    setEdgeMessage(null)
  }, [selectedEdge])

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

    cyRef.current?.layout(BASE_LAYOUT).run()
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

  function fitCanvas() {
    cyRef.current?.fit(undefined, compact ? 72 : 96)
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

  async function saveEdgeCorrection() {
    if (!selectedEdge?.relationshipId) return

    setSavingEdge(true)
    setEdgeMessage(null)

    try {
      const updated = await booksApi.updateRelationship(bookId, selectedEdge.relationshipId, {
        relType: edgeDraft.relType.trim(),
        description: edgeDraft.description.trim() || null,
        sentiment: edgeDraft.sentiment === "" ? null : Number(edgeDraft.sentiment),
        fromChapter: edgeDraft.fromChapter === "" ? null : Number(edgeDraft.fromChapter),
        toChapter: edgeDraft.toChapter === "" ? null : Number(edgeDraft.toChapter),
        sharedLabels: edgeDraft.sharedLabels,
        characterAToBLabels: edgeDraft.sourceToTargetLabels,
        characterBToALabels: edgeDraft.targetToSourceLabels,
      })

      setGraphData((current) => {
        if (!current) return current

        const nextGraph = {
          ...current,
          edges: current.edges.map((edge) =>
            edge.id === selectedEdge.relationshipId
              ? {
                  ...edge,
                  type: updated.rel_type,
                  description: updated.description,
                  sentiment: updated.sentiment,
                  from_chapter: updated.from_chapter,
                  to_chapter: updated.to_chapter,
                  shared_labels: updated.shared_labels,
                  character_a_to_b_labels: updated.character_a_to_b_labels,
                  character_b_to_a_labels: updated.character_b_to_a_labels,
                  label_evidence: updated.label_evidence,
                  status: (typeof updated.to_chapter === "number" && updated.to_chapter < upToChapter ? "ended" : "ongoing") as "ended" | "ongoing",
                }
              : edge
          ),
        }
        onGraphDataChange?.(nextGraph)
        return nextGraph
      })

      setSelection((current) =>
        current?.type === "edge"
          ? {
              type: "edge",
              data: {
                ...current.data,
                type: updated.rel_type,
                description: updated.description,
                sentiment: updated.sentiment,
                from_chapter: updated.from_chapter,
                to_chapter: updated.to_chapter,
                shared_labels: updated.shared_labels,
                character_a_to_b_labels: updated.character_a_to_b_labels,
                character_b_to_a_labels: updated.character_b_to_a_labels,
                label_evidence: updated.label_evidence,
              },
            }
          : current
      )
      setEdgeMessage("Relationship correction saved.")
    } catch {
      setEdgeMessage("Could not save the relationship correction.")
    } finally {
      setSavingEdge(false)
    }
  }

  async function deleteSelectedRelationship() {
    if (!selectedEdge?.relationshipId) return

    setSavingEdge(true)
    setEdgeMessage(null)

    try {
      await booksApi.deleteRelationship(bookId, selectedEdge.relationshipId)

      setGraphData((current) => {
        if (!current) return current

        const nextGraph = {
          ...current,
          edges: current.edges.filter((edge) => edge.id !== selectedEdge.relationshipId),
        }
        onGraphDataChange?.(nextGraph)
        return nextGraph
      })

      setSelection(null)
      setEdgeMessage("Relationship removed.")
    } catch {
      setEdgeMessage("Could not remove the relationship.")
    } finally {
      setSavingEdge(false)
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-white/10 bg-white/[0.03] p-8 text-sm text-slate-300 shadow-[0_24px_80px_rgba(0,0,0,0.32)]">
        Building the relationship graph...
      </div>
    )
  }

  if (compact) {
    return (
      <section className="rounded-lg border border-white/10 bg-[#060915] p-3 text-slate-100 shadow-[0_16px_50px_rgba(0,0,0,0.24)]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-white">Relationship graph</h2>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              Zoomed out by default. Tap a node to sync the profile.
            </p>
          </div>
          <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-slate-300">
            {graphStats.nodeCount} cast - {graphStats.edgeCount} ties
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <FilterSelect filterId={filterId} filterType={filterType} relationshipTypes={relationshipTypes} setFilterType={setFilterType} />
          <div className="flex flex-wrap gap-2">
            <GraphToolbarButton icon={<FitIcon className="h-4 w-4" />} onClick={fitCanvas}>Fit</GraphToolbarButton>
            <GraphToolbarButton icon={<MinusIcon className="h-4 w-4" />} onClick={() => adjustZoom("out")}>Zoom out</GraphToolbarButton>
            <GraphToolbarButton
              active={showIsolated}
              ariaPressed={showIsolated}
              icon={<EyeIcon className="h-4 w-4" />}
              onClick={() => setShowIsolated((current) => !current)}
            >
              {showIsolated ? "Hide isolated" : "Show isolated"}
            </GraphToolbarButton>
            <GraphToolbarButton icon={<ResetIcon className="h-4 w-4" />} onClick={resetLayout}>Reset</GraphToolbarButton>
          </div>
        </div>

        {filteredGraph && filteredGraph.nodes.length > 0 ? (
          <div className="relative mt-3 overflow-hidden rounded-md border border-white/10 bg-[#050814]">
            <div
              aria-hidden="true"
              className={cn(
                "pointer-events-none absolute inset-0 transition-opacity",
                showGrid ? "opacity-100" : "opacity-0"
              )}
              style={{
                backgroundImage:
                  "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.18) 1px, transparent 0)",
                backgroundSize: "22px 22px",
              }}
            />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(109,91,208,0.18),transparent_42%),linear-gradient(180deg,rgba(5,8,20,0.88),rgba(3,5,11,0.98))]"
            />
            <div
              ref={containerRef}
              className="relative z-10 h-[260px] min-h-[260px]"
              style={{ cursor: interactionMode === "arrange" ? "grab" : "default" }}
            />
          </div>
        ) : (
          <div className="mt-3 flex min-h-[220px] items-center justify-center rounded-md border border-white/10 bg-[linear-gradient(180deg,#050814_0%,#03050b_100%)] text-center text-slate-400">
            <div className="max-w-sm space-y-3 px-6">
              <p className="text-base font-semibold text-white">No graphable relationships yet</p>
              <p className="text-sm leading-6">Relationships appear after character extraction has enough scene evidence. Clear filters, open Characters, or retry processing if extraction failed.</p>
              <div className="flex flex-wrap justify-center gap-2 pt-1">
                <Link href={`/${bookId}/characters`} className="rounded-md border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-white/[0.1]">
                  Open characters
                </Link>
                <Link href={`/${bookId}/manuscript`} className="rounded-md border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-white/[0.1]">
                  Open manuscript
                </Link>
              </div>
            </div>
          </div>
        )}

        <div className="mt-3 rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs leading-5 text-slate-300">
          <CompactSelectionSummary selectedNode={selectedNode} selectedEdge={selectedEdge} />
        </div>
      </section>
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className={cn(panelClass(), "p-4 md:p-5")}>
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-violet-300/85">Relationship graph</p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Relationship graph</h2>
              <p className="mt-2 text-sm leading-7 text-slate-400">
                Arrange the map to match how you read it. Drag nodes, zoom the canvas, and keep a saved layout on this device.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <GraphToolbarButton
                active={interactionMode === "arrange"}
                ariaPressed={interactionMode === "arrange"}
                icon={<ArrangeIcon className="h-4 w-4" />}
                onClick={() => setInteractionMode((current) => (current === "arrange" ? "inspect" : "arrange"))}
              >
                {interactionMode === "arrange" ? "Arrange mode" : "Inspect mode"}
              </GraphToolbarButton>
              <GraphToolbarButton
                active={showIsolated}
                ariaPressed={showIsolated}
                icon={<EyeIcon className="h-4 w-4" />}
                onClick={() => setShowIsolated((current) => !current)}
              >
                {showIsolated ? "Hide isolated" : "Show isolated"}
              </GraphToolbarButton>
              <GraphToolbarButton icon={<MinusIcon className="h-4 w-4" />} onClick={() => adjustZoom("out")}>Zoom out</GraphToolbarButton>
              <GraphToolbarButton icon={<PlusIcon className="h-4 w-4" />} onClick={() => adjustZoom("in")}>Zoom in</GraphToolbarButton>
              <GraphToolbarButton icon={<ScopeIcon className="h-4 w-4" />} onClick={resetZoom}>Reset zoom</GraphToolbarButton>
              <GraphToolbarButton icon={<FitIcon className="h-4 w-4" />} onClick={fitCanvas}>Fit</GraphToolbarButton>
              <GraphToolbarButton
                disabled={selection?.type !== "node"}
                icon={<TargetIcon className="h-4 w-4" />}
                onClick={focusSelection}
              >
                Center selection
              </GraphToolbarButton>
              <GraphToolbarButton icon={<ResetIcon className="h-4 w-4" />} onClick={resetLayout}>Reset layout</GraphToolbarButton>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <GraphStatusPill icon={<UsersIcon className="h-4 w-4" />}>
              <span className="font-medium text-white">{graphStats.nodeCount}</span> characters
            </GraphStatusPill>
            <GraphStatusPill icon={<LinksIcon className="h-4 w-4" />}>
              <span className="font-medium text-white">{graphStats.edgeCount}</span> connections
            </GraphStatusPill>
            <GraphStatusPill icon={<EyeIcon className="h-4 w-4" />}>
              {showIsolated ? "Isolated cast members stay visible." : "Only connected cast members are visible."}
            </GraphStatusPill>
            <GraphStatusPill icon={<HandIcon className="h-4 w-4" />}>
              {interactionMode === "arrange" ? "Nodes are draggable right now." : "Nodes are locked for inspection."}
            </GraphStatusPill>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <FilterSelect filterId={filterId} filterType={filterType} relationshipTypes={relationshipTypes} setFilterType={setFilterType} />

            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300">
              <ScopeIcon className="h-4 w-4 text-slate-400" />
              <span>Zoom {zoomPercentLabel(zoomLevel)}</span>
            </div>
          </div>

          {filteredGraph && filteredGraph.nodes.length > 0 ? (
            <div className="relative overflow-hidden rounded-lg border border-white/10 bg-[#040712]">
              <div
                aria-hidden="true"
                className={cn(
                  "pointer-events-none absolute inset-0 transition-opacity",
                  showGrid ? "opacity-100" : "opacity-0"
                )}
                style={{
                  backgroundImage:
                    "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.18) 1px, transparent 0)",
                  backgroundSize: "22px 22px",
                }}
              />
              <div
                aria-hidden="true"
                className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(109,91,208,0.18),transparent_42%),linear-gradient(180deg,rgba(5,8,20,0.88),rgba(3,5,11,0.98))]"
              />

              <div className="absolute right-4 top-4 z-20 flex items-center gap-2">
                <button
                  type="button"
                  aria-pressed={showGrid}
                  onClick={() => setShowGrid((current) => !current)}
                  className={controlButtonClass(showGrid)}
                >
                  <GridIcon className="h-4 w-4" />
                  <span>Grid</span>
                </button>
                <button
                  type="button"
                  onClick={() => adjustZoom("out")}
                  className={controlButtonClass()}
                  aria-label="Zoom out"
                >
                  <MinusIcon className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => adjustZoom("in")}
                  className={controlButtonClass()}
                  aria-label="Zoom in"
                >
                  <PlusIcon className="h-4 w-4" />
                </button>
              </div>

              <div
                ref={containerRef}
                className="relative z-10 h-[56vh] min-h-[380px] md:h-[70vh] md:min-h-[560px]"
                style={{ cursor: interactionMode === "arrange" ? "grab" : "default" }}
              />

              <div className="pointer-events-none absolute bottom-4 left-4 z-20 flex flex-wrap gap-2">
                <div className="rounded-full border border-white/10 bg-black/35 px-3 py-1.5 text-xs text-slate-300 backdrop-blur">
                  Saved layout on this device
                </div>
                {filteredGraph.edges.length === 0 ? (
                  <div className="rounded-full border border-white/10 bg-black/35 px-3 py-1.5 text-xs text-slate-300 backdrop-blur">
                    No relationships extracted yet. Characters remain visible so you can arrange the cast.
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="flex h-[40vh] min-h-[340px] items-center justify-center rounded-lg border border-white/10 bg-[linear-gradient(180deg,#050814_0%,#03050b_100%)] text-center text-slate-400">
              <div className="max-w-sm space-y-3 px-6">
                <p className="text-lg font-semibold text-white">No graphable relationships yet</p>
                <p className="text-sm leading-6">Relationship edges appear after character extraction has enough scene evidence. If this manuscript just finished uploading, processing may still be catching up.</p>
                <div className="flex flex-wrap justify-center gap-2 pt-1">
                  <Link href={`/${bookId}/manuscript`} className="rounded-md border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-white/[0.1]">
                    Open manuscript
                  </Link>
                  <Link href={`/${bookId}/characters`} className="rounded-md bg-violet-500/20 px-3 py-2 text-xs font-semibold text-violet-100 hover:bg-violet-500/30">
                    Review characters
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <aside className={cn(panelClass(), "p-5 xl:sticky xl:top-6 xl:max-h-[84vh] xl:overflow-y-auto")}>
        {selectedNode ? (
          <div className="space-y-5">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-violet-400/30 bg-violet-500/10 text-lg font-semibold text-violet-100">
                {nodeInitial(selectedNode.name)}
              </div>
              <div className="min-w-0">
                <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-violet-300/85">Character</p>
                <h3 className="mt-2 truncate text-[1.9rem] font-semibold tracking-tight text-white">{selectedNode.name}</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedNode.role ? (
                    <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-3xs text-slate-200">{selectedNode.role}</span>
                  ) : null}
                  {selectedNode.is_manual ? (
                    <span className="rounded-full border border-amber-400/20 bg-amber-500/12 px-3 py-1 text-3xs text-amber-100">manual</span>
                  ) : null}
                  {selectedNode.graph_visibility_override === "include" ? (
                    <span className="rounded-full border border-teal-400/20 bg-teal-500/12 px-3 py-1 text-3xs text-teal-100">forced visible</span>
                  ) : null}
                  {typeof selectedNode.visibility_score === "number" ? (
                    <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-3xs text-slate-300">score {selectedNode.visibility_score}</span>
                  ) : null}
                </div>
              </div>
            </div>

            <InspectorSection title="Quick view">
              <div className="space-y-3 text-sm text-slate-300">
                {typeof selectedNode.mention_count === "number" ? <InspectorMetric label="Mentions" value={selectedNode.mention_count} /> : null}
                <InspectorMetric label="Connections in view" value={selectedNode.relationshipCount ?? 0} />
                <InspectorMetric label="First chapter" value={selectedNode.first_chapter} />
              </div>
            </InspectorSection>

            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={focusSelection} className={controlButtonClass(true)}>
                <TargetIcon className="h-4 w-4" />
                <span>Center node</span>
              </button>
              <Link href={`/${bookId}/characters`} className={controlButtonClass()}>
                <UsersIcon className="h-4 w-4" />
                <span>Open characters workspace</span>
              </Link>
            </div>

            <InspectorSection title="Display label">
              <label htmlFor={labelInputId} className="sr-only">Display label</label>
              <input
                id={labelInputId}
                value={labelOverrides[selectedNode.id] || selectedNode.name}
                onChange={(event) => updateNodeLabel(selectedNode.id, event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#0b1020] px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
              />
              <button
                type="button"
                onClick={() => clearLabelOverride(selectedNode)}
                className="mt-3 text-xs font-medium text-slate-400 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
              >
                Reset to canonical name
              </button>
            </InspectorSection>

            <InspectorSection title="Reading note">
              <p className="text-sm leading-7 text-slate-300">
                {selectedNode.description || "No narrative summary has been saved yet."}
              </p>
            </InspectorSection>

            {"arc_summary" in selectedNode && selectedNode.arc_summary ? (
              <InspectorSection title="Arc summary">
                <p className="text-sm leading-7 text-slate-300">{selectedNode.arc_summary}</p>
              </InspectorSection>
            ) : null}

            {selectedNode.aliases?.length ? (
              <InspectorSection title="Aliases">
                <div className="flex flex-wrap gap-2">
                  {selectedNode.aliases.map((alias) => (
                    <span key={alias} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-200">
                      {alias}
                    </span>
                  ))}
                </div>
              </InspectorSection>
            ) : null}

            {selectedNode.personality_tags?.length ? (
              <InspectorSection title="Disposition">
                <p className="text-sm leading-7 text-slate-300">{selectedNode.personality_tags.join(", ")}</p>
              </InspectorSection>
            ) : null}

            {selectedNode.motivations?.length ? (
              <InspectorSection title="Motivations">
                <p className="text-sm leading-7 text-slate-300">{selectedNode.motivations.join(", ")}</p>
              </InspectorSection>
            ) : null}

            {selectedNode.fears?.length ? (
              <InspectorSection title="Fears">
                <p className="text-sm leading-7 text-slate-300">{selectedNode.fears.join(", ")}</p>
              </InspectorSection>
            ) : null}

            {selectedNodeConnections.length > 0 ? (
              <InspectorSection title="Visible connections">
                <div className="space-y-3">
                  {selectedNodeConnections.map((connection) => (
                    <div key={connection.id} className="flex items-start justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2 text-sm">
                      <div>
                        <p className="font-medium text-white">{connection.name}</p>
                        <p className="mt-1 text-xs text-slate-400">{connection.label}</p>
                      </div>
                      {typeof connection.chapter === "number" ? (
                        <span className="text-xs text-slate-500">Ch. {connection.chapter}</span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </InspectorSection>
            ) : null}
          </div>
        ) : selectedEdge ? (
          <div className="space-y-5">
            <div>
              <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-violet-300/85">Connection</p>
              <h3 className="mt-3 text-[1.9rem] font-semibold tracking-tight text-white">
                {relationshipFacetSummary([...(selectedEdge.character_a_to_b_labels ?? []), ...(selectedEdge.character_b_to_a_labels ?? []), ...(selectedEdge.shared_labels ?? [])], selectedEdge.type)}
              </h3>
              {selectedEdgeParticipants ? (
                <p className="mt-3 text-sm leading-7 text-slate-400">
                  {selectedEdgeParticipants.source} {"->"} {selectedEdgeParticipants.target}
                </p>
              ) : null}
            </div>

            <InspectorSection title="Relationship note">
              <p className="text-sm leading-7 text-slate-300">
                {selectedEdge.description || "No explicit relationship note has been saved yet."}
              </p>
            </InspectorSection>

            <InspectorSection title="Network detail">
              <div className="space-y-3 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-300">Primary type</span>
                  <span className="font-semibold text-white">{relationshipFacetLabel(selectedEdge.type)}</span>
                </div>
                {typeof selectedEdge.from_chapter === "number" ? <InspectorMetric label="First tracked" value={selectedEdge.from_chapter} /> : null}
                {typeof selectedEdge.to_chapter === "number" ? <InspectorMetric label="Ends chapter" value={selectedEdge.to_chapter} /> : null}
                {selectedEdge.status ? (
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-slate-300">Status</span>
                    <span className="font-semibold capitalize text-white">{selectedEdge.status}</span>
                  </div>
                ) : null}
                {sentimentLabel(selectedEdge.sentiment) ? (
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-slate-300">Emotional direction</span>
                    <span className="font-semibold text-white">{sentimentLabel(selectedEdge.sentiment)}</span>
                  </div>
                ) : null}
              </div>
            </InspectorSection>

            {authorMode && selectedEdge.relationshipId ? (
              <InspectorSection title="Author correction">
                <p className="text-sm leading-6 text-slate-400">
                  Correct the extracted relationship if the manuscript context is clearer than the model guess.
                </p>

                <div className="mt-4 space-y-3">
                  <label className="block">
                    <span className="mb-1 block text-xs text-slate-400">Type</span>
                    <select
                      value={edgeDraft.relType}
                      onChange={(event) => setEdgeDraft((value) => ({ ...value, relType: event.target.value }))}
                      className="w-full rounded-xl border border-white/10 bg-[#0b1020] px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                    >
                      {edgeDraft.relType && !PRIMARY_RELATIONSHIP_TYPE_OPTIONS.includes(edgeDraft.relType as (typeof PRIMARY_RELATIONSHIP_TYPE_OPTIONS)[number]) ? (
                        <option value={edgeDraft.relType}>{relationshipLabel(edgeDraft.relType)}</option>
                      ) : null}
                      {PRIMARY_RELATIONSHIP_TYPE_OPTIONS.map((type) => (
                        <option key={type} value={type}>
                          {relationshipFacetLabel(type)}
                        </option>
                      ))}
                    </select>
                  </label>

                  <RelationshipLabelChecklist
                    label="Shared facets"
                    options={SHARED_RELATIONSHIP_LABEL_OPTIONS}
                    selected={edgeDraft.sharedLabels}
                    onChange={(labels) => setEdgeDraft((value) => ({ ...value, sharedLabels: labels }))}
                  />

                  {selectedEdgeParticipants ? (
                    <div className="grid gap-3 lg:grid-cols-2">
                      <RelationshipLabelChecklist
                        label={`${selectedEdgeParticipants.source} to ${selectedEdgeParticipants.target}`}
                        options={DIRECTIONAL_RELATIONSHIP_LABEL_OPTIONS}
                        selected={edgeDraft.sourceToTargetLabels}
                        onChange={(labels) => setEdgeDraft((value) => ({ ...value, sourceToTargetLabels: labels }))}
                      />
                      <RelationshipLabelChecklist
                        label={`${selectedEdgeParticipants.target} to ${selectedEdgeParticipants.source}`}
                        options={DIRECTIONAL_RELATIONSHIP_LABEL_OPTIONS}
                        selected={edgeDraft.targetToSourceLabels}
                        onChange={(labels) => setEdgeDraft((value) => ({ ...value, targetToSourceLabels: labels }))}
                      />
                    </div>
                  ) : null}

                  <label className="block">
                    <span className="mb-1 block text-xs text-slate-400">Relationship note</span>
                    <textarea
                      value={edgeDraft.description}
                      onChange={(event) => setEdgeDraft((value) => ({ ...value, description: event.target.value }))}
                      rows={4}
                      className="w-full rounded-xl border border-white/10 bg-[#0b1020] px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                    />
                  </label>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <label className="block">
                      <span className="mb-1 block text-xs text-slate-400">Sentiment</span>
                      <input
                        type="number"
                        min={-1}
                        max={1}
                        step={0.1}
                        value={edgeDraft.sentiment}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, sentiment: event.target.value }))}
                        className="w-full rounded-xl border border-white/10 bg-[#0b1020] px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-xs text-slate-400">From chapter</span>
                      <input
                        type="number"
                        min={1}
                        value={edgeDraft.fromChapter}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, fromChapter: event.target.value }))}
                        className="w-full rounded-xl border border-white/10 bg-[#0b1020] px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-xs text-slate-400">Ends chapter</span>
                      <input
                        type="number"
                        min={1}
                        value={edgeDraft.toChapter}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, toChapter: event.target.value }))}
                        className="w-full rounded-xl border border-white/10 bg-[#0b1020] px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                      />
                      <span className="mt-1 block text-xs text-slate-500">Leave blank if ongoing.</span>
                    </label>
                  </div>

                  {edgeMessage ? (
                    <p className={cn("text-sm", edgeMessage.includes("saved") || edgeMessage.includes("removed") ? "text-emerald-400" : "text-rose-300")}>
                      {edgeMessage}
                    </p>
                  ) : null}

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={savingEdge}
                      onClick={() => void saveEdgeCorrection()}
                      className={cn(controlButtonClass(true), savingEdge && "opacity-60")}
                    >
                      <CheckIcon className="h-4 w-4" />
                      <span>{savingEdge ? "Saving..." : "Save correction"}</span>
                    </button>
                    <button
                      type="button"
                      disabled={savingEdge}
                      onClick={() => void deleteSelectedRelationship()}
                      className={cn(
                        "inline-flex items-center justify-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-100 transition",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/70",
                        savingEdge && "opacity-60"
                      )}
                    >
                      <TrashIcon className="h-4 w-4" />
                      <span>Delete relationship</span>
                    </button>
                  </div>
                </div>
              </InspectorSection>
            ) : null}
          </div>
        ) : (
          <EmptyInspector edgeCount={graphStats.edgeCount} nodeCount={graphStats.nodeCount} />
        )}
      </aside>
    </div>
  )
})

function ArrangeIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h4v4H7zM13 7h4v4h-4zM7 13h4v4H7zM13 13h4v4h-4z" />
    </svg>
  )
}

function CheckIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12.5l4.2 4.2L19 7" />
    </svg>
  )
}

function ChevronDownIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
    </svg>
  )
}

function CursorIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 4l5.5 14 2.3-5.3L18 10 5 4z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12.5 12.7L17 18" />
    </svg>
  )
}

function EyeIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6z" />
      <circle cx="12" cy="12" r="2.8" />
    </svg>
  )
}

function FilterIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16l-6 7v5l-4 2v-7L4 6z" />
    </svg>
  )
}

function FitIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 4H4v4M16 4h4v4M20 16v4h-4M4 16v4h4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l-5-5M15 9l5-5M15 15l5 5M9 15l-5 5" />
    </svg>
  )
}

function GridIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 8h.01M12 8h.01M16 8h.01M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01" />
    </svg>
  )
}

function HandIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 11V6a1.5 1.5 0 013 0v4M11 10V4.8a1.5 1.5 0 013 0V10M14 10V6.4a1.5 1.5 0 013 0v6.8l1.2-.9a1.6 1.6 0 012.3.4c.4.6.3 1.5-.2 2l-4.1 4.5a4 4 0 01-3 1.3h-2.5a4 4 0 01-3.7-2.5L5 13.5A1.7 1.7 0 016.5 11H8z" />
    </svg>
  )
}

function LinksIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 14l4-4M7 17H6a4 4 0 010-8h3M17 7h1a4 4 0 010 8h-3" />
    </svg>
  )
}

function MinusIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
    </svg>
  )
}

function PlusIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
    </svg>
  )
}

function ResetIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M20 11a8 8 0 10-2.34 5.66L20 14M20 14v-5h-5" />
    </svg>
  )
}

function ScopeIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="11" cy="11" r="6" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M20 20l-4.2-4.2" />
    </svg>
  )
}

function TargetIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="7" />
      <circle cx="12" cy="12" r="2.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </svg>
  )
}

function TrashIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M9 7V5h6v2M8 7l.7 11.2A2 2 0 0010.7 20h2.6a2 2 0 001.99-1.8L16 7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 11v5M14 11v5" />
    </svg>
  )
}

function UsersIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 100-6 3 3 0 000 6zM4 19a5 5 0 0110 0M17 11a2.5 2.5 0 100-5M15.5 15.5A4.5 4.5 0 0120 20" />
    </svg>
  )
}

export default RelationshipGraph
