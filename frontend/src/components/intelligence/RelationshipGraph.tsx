"use client"

import Link from "next/link"
import { RelationshipGraphInspector } from "./RelationshipGraph.inspector"
import { RelationshipGraphBrowser } from "./RelationshipGraph.browser"
import { relationshipDraft, relationshipDraftError, useRelationshipDraftGuard } from "./RelationshipGraph.editing"
import { memo, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import cytoscape from "cytoscape"

import { booksApi } from "@/lib/api/books"
import { loadRelationshipGraph } from "./RelationshipGraph.loading"
import { RELATIONSHIP_COLORS } from "@/lib/constants"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { cn } from "@/lib/utils/text"
import type { RelationshipGraph as GraphData } from "@/types/character"
import {
  ArrangeIcon,
  CompactSelectionSummary,
  EyeIcon,
  FilterSelect,
  FitIcon,
  GridIcon,
  GraphToolbarButton,
  MinusIcon,
  PlusIcon,
  ResetIcon,
  type GraphEdgeView,
  type GraphNodeView,
} from "./RelationshipGraph.controls"
import {
  BASE_LAYOUT,
  buildIsolatedPositions,
  panelClass,
  storedGraphLabels,
  storedGraphPositions,
} from "./RelationshipGraph.helpers"

import {
  graphLabelKey,
  graphStorageKey,
  relationshipFacetSummary,
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
  toolbarLeading?: ReactNode
  inspectorPlacement?: "overlay" | "inline"
}

type Selection =
  | { type: "node"; data: GraphNodeView }
  | { type: "edge"; data: GraphEdgeView }
  | null

type GraphNode = GraphData["nodes"][number]
type InteractionMode = "arrange" | "inspect"
type GraphTestHandle = {
  cy: cytoscape.Core
  selectNode: (id: string) => void
  selectEdge: (id: string) => void
  clearSelection: () => void
}

function graphTestHandleEnabled() {
  // Debug handle stays development-only. Production test builds must use the
  // separately acknowledged admin override path instead of leaking a graph
  // instance onto window for any visitor.
  return typeof window !== "undefined" && process.env.NODE_ENV !== "production"
}

function installGraphTestHandle(cy: cytoscape.Core) {
  if (!graphTestHandleEnabled()) return

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
  if (!graphTestHandleEnabled()) return

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
  toolbarLeading,
  inspectorPlacement = "overlay",
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
  const [edgeDraft, setEdgeDraft] = useState(() => relationshipDraft(null))
  const [savingEdge, setSavingEdge] = useState(false)
  const [edgeMessage, setEdgeMessage] = useState<string | null>(null)
  const savingRef = useRef(false)
  const [storageError, setStorageError] = useState(false)
  const dirty = selection?.type === "edge" && JSON.stringify(edgeDraft) !== JSON.stringify(relationshipDraft(selection.data))
  const canLeave = useRelationshipDraftGuard(dirty, savingEdge)
  const requestSelectionRef = useRef((next: Selection) => { void next })
  requestSelectionRef.current = (next) => {
    if (!canLeave()) return
    setSelection(next)
    setEdgeMessage(null)
    if (next?.type === "node") selectCharacterRef.current?.(next.data.id)
  }

  const { data: graphQueryData = null, isLoading: loading, isError, isFetching, refetch } = useQuery<GraphData | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, `relationships:${upToChapter}:${includeInactive ? "all" : "active"}`)),
    queryFn: () => loadRelationshipGraph(bookId, upToChapter, includeInactive),
  })

  useEffect(() => {
    selectCharacterRef.current = onSelectCharacterId
  }, [onSelectCharacterId])

  useEffect(() => {
    if (typeof window === "undefined") return

    try {
      const raw = window.localStorage.getItem(graphLabelKey(bookId))
      setLabelOverrides(storedGraphLabels(raw))
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

    const visibleNodes = graphData.nodes.filter((node) => connected.has(node.id))
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
          chapter: edge.from_chapter ?? null,
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

  const relationshipStylesheet = useMemo<cytoscape.StylesheetJson>(
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
          "font-size": 14,
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
          opacity: 0.85,
          label: "data(label)",
          "font-size": 12,
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
        return storedGraphPositions(raw)
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
      requestSelectionRef.current(nextSelection)
    })

    cy.on("tap", "edge", (event) => {
      requestSelectionRef.current({ type: "edge", data: event.target.data() as GraphEdgeView })
    })

    cy.on("tap", (event) => {
      if (event.target === cy) {
        requestSelectionRef.current(null)
      }
    })

    cy.on("dragfree", "node", () => {
      const positions = Object.fromEntries(cy.nodes().map((node) => [node.id(), node.position()]))
      if (typeof window !== "undefined") {
        if (layoutPersistTimerRef.current) {
          window.clearTimeout(layoutPersistTimerRef.current)
        }
        layoutPersistTimerRef.current = window.setTimeout(() => {
          try { window.localStorage.setItem(graphStorageKey(bookId, upToChapter), JSON.stringify(positions)) } catch { setStorageError(true) }
          layoutPersistTimerRef.current = null
        }, 180)
      }
    })

    cy.on("zoom", () => {
      setZoomLevel(cy.zoom())
    })

    cyRef.current = cy
    installGraphTestHandle(cy)
    const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
      if (cy.destroyed()) return
      cy.resize()
      cy.fit(undefined, compact ? 72 : 40)
      setZoomLevel(cy.zoom())
    })
    resizeObserver?.observe(containerRef.current)

    return () => {
      resizeObserver?.disconnect()
      if (layoutPersistTimerRef.current) {
        window.clearTimeout(layoutPersistTimerRef.current)
        layoutPersistTimerRef.current = null
      }

      const positions = Object.fromEntries(cy.nodes().map((node) => [node.id(), node.position()]))
      if (typeof window !== "undefined") {
        try { window.localStorage.setItem(graphStorageKey(bookId, upToChapter), JSON.stringify(positions)) } catch { setStorageError(true) }
      }
      clearGraphTestHandle(cy)
      cy.destroy()
      if (cyRef.current === cy) cyRef.current = null
    }
  }, [bookId, compact, filteredGraph, interactionMode, labelOverrides, relationshipStylesheet, theme, upToChapter])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !focusCharacterId) return

    const node = cy.getElementById(focusCharacterId)
    if (node.empty()) return

    cy.elements().unselect()
    node.select()
    requestSelectionRef.current({ type: "node", data: node.data() as GraphNodeView })

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

    setEdgeDraft(relationshipDraft(selectedEdge))
  }, [selectedEdge])

  function updateNodeLabel(nodeId: string, value: string) {
    const next = { ...labelOverrides, [nodeId]: value }
    setLabelOverrides(next)
    if (typeof window !== "undefined") {
      try { window.localStorage.setItem(graphLabelKey(bookId), JSON.stringify(next)) } catch { setStorageError(true) }
    }
  }

  function clearLabelOverride(node: GraphNode) {
    const next = { ...labelOverrides }
    delete next[node.id]
    setLabelOverrides(next)
    if (typeof window !== "undefined") {
      try { window.localStorage.setItem(graphLabelKey(bookId), JSON.stringify(next)) } catch { setStorageError(true) }
    }
  }

  function resetLayout() {
    if (typeof window !== "undefined") {
      try { window.localStorage.removeItem(graphStorageKey(bookId, upToChapter)) } catch { setStorageError(true) }
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
    cyRef.current?.resize()
    cyRef.current?.fit(undefined, compact ? 72 : 40)
  }

  function adjustZoom(direction: "in" | "out") {
    const cy = cyRef.current
    if (!cy) return

    const factor = direction === "in" ? 1.18 : 1 / 1.18
    const nextZoom = Math.max(0.3, Math.min(2.4, cy.zoom() * factor))
    cy.zoom({ level: nextZoom, position: { x: cy.width() / 2, y: cy.height() / 2 } })
    setZoomLevel(cy.zoom())
  }

  function clearSelection() {
    if (!canLeave()) return
    cyRef.current?.elements().unselect()
    setSelection(null)
    selectCharacterRef.current?.(null)
  }

  async function saveEdgeCorrection() {
    if (!selectedEdge?.relationshipId || savingRef.current) return
    const validation = relationshipDraftError(edgeDraft)
    if (validation) { setEdgeMessage(validation); return }
    savingRef.current = true
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
        current?.type === "edge" && current.data.relationshipId === selectedEdge.relationshipId
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
      savingRef.current = false
      setSavingEdge(false)
    }
  }

  async function deleteSelectedRelationship() {
    if (!selectedEdge?.relationshipId || savingRef.current) return
    if (!window.confirm("Delete this relationship? This removes the recorded connection and any unsaved correction.")) return
    savingRef.current = true
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
      savingRef.current = false
      setSavingEdge(false)
    }
  }

  if (loading) {
    return (
      <div role="status" className="py-8 text-sm text-[rgb(var(--muted-foreground))]">
        Building the relationship graph...
      </div>
    )
  }

  if (isError && !graphData) return <div role="alert" className="border-l-2 border-amber-500 p-4 text-sm"><p>The relationship graph could not load.</p><button type="button" className="app-button-secondary mt-3" disabled={isFetching} onClick={() => void refetch()}>Retry graph</button></div>

  if (compact) {
    return (
      <section className="rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-3 text-[rgb(var(--foreground))] ">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[rgb(var(--foreground))]">Relationship graph</h2>
            <p className="mt-1 text-sm leading-5 text-[rgb(var(--muted-foreground))]">
              Zoomed out by default. Tap a node to sync the profile.
            </p>
          </div>
          <div className="rounded-sm border border-[rgb(var(--border))] bg-white/[0.03] px-3 py-1.5 text-sm font-medium text-[rgb(var(--foreground))]">
            {graphStats.nodeCount} cast - {graphStats.edgeCount} ties
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <FilterSelect filterId={filterId} filterType={filterType} relationshipTypes={relationshipTypes} setFilterType={(value) => { if (canLeave()) { setFilterType(value); setSelection(null) } }} />
          <div className="flex flex-wrap gap-2">
            <GraphToolbarButton icon={<FitIcon className="h-4 w-4" />} onClick={fitCanvas}>Fit</GraphToolbarButton>
            <GraphToolbarButton icon={<MinusIcon className="h-4 w-4" />} onClick={() => adjustZoom("out")}>Zoom out</GraphToolbarButton>
            <GraphToolbarButton
              active={showIsolated}
              ariaPressed={showIsolated}
              icon={<EyeIcon className="h-4 w-4" />}
              onClick={() => { if (canLeave()) { setShowIsolated((current) => !current); setSelection(null) } }}
            >
              {showIsolated ? "Hide isolated" : "Show isolated"}
            </GraphToolbarButton>
            <GraphToolbarButton icon={<ResetIcon className="h-4 w-4" />} onClick={resetLayout}>Reset</GraphToolbarButton>
          </div>
        </div>

        {filteredGraph && filteredGraph.nodes.length > 0 ? (
          <div className="relative mt-3 overflow-hidden rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))]">
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
              className="pointer-events-none absolute inset-0 "
            />
            <div
              ref={containerRef}
              className="relative z-10 h-[260px] min-h-[260px]"
              style={{ cursor: interactionMode === "arrange" ? "grab" : "default" }}
            />
          </div>
        ) : (
          <div className="mt-3 flex min-h-[220px] items-center justify-center rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] text-center text-[rgb(var(--muted-foreground))]">
            <div className="max-w-sm space-y-3 px-6">
              <p className="text-base font-semibold text-[rgb(var(--foreground))]">No graphable relationships yet</p>
              <p className="text-sm leading-6">Relationships appear after character extraction has enough scene evidence. Clear filters, open Characters, or retry processing if extraction failed.</p>
              <div className="flex flex-wrap justify-center gap-2 pt-1">
                <Link href={`/${bookId}/characters`} className="rounded-sm border border-[rgb(var(--border))] bg-white/[0.06] px-3 py-2 text-sm font-semibold text-[rgb(var(--foreground))] hover:bg-white/[0.1]">
                  Open characters
                </Link>
                <Link href={`/${bookId}/${authorMode ? "manuscript" : "chapters"}`} className="rounded-sm border border-[rgb(var(--border))] bg-white/[0.06] px-3 py-2 text-sm font-semibold text-[rgb(var(--foreground))] hover:bg-white/[0.1]">
                  {authorMode ? "Open manuscript" : "View chapters"}
                </Link>
              </div>
            </div>
          </div>
        )}

        <div className="mt-3 rounded-sm border border-[rgb(var(--border))] bg-white/[0.03] p-3 text-sm leading-5 text-[rgb(var(--foreground))]">
          <CompactSelectionSummary selectedNode={selectedNode} selectedEdge={selectedEdge} />
        </div>
      </section>
    )
  }

  return (
    <div className={cn("relative min-w-0 [overflow-wrap:anywhere]", selection && inspectorPlacement === "overlay" && "xl:grid xl:grid-cols-[minmax(0,1fr)_380px] xl:items-start xl:gap-4")}>
      {isError ? <div role="alert" className="col-span-full mb-4 border-l-2 border-amber-500 pl-4 text-sm">Graph refresh failed. Previously loaded data remains visible.</div> : null}
      {storageError ? <p role="status" className="col-span-full mb-3 text-sm">Changes to display labels and layout cannot be saved on this device.</p> : null}
      {edgeMessage && !selection ? <p role="status" className="col-span-full mb-3 text-sm">{edgeMessage}</p> : null}
      <section className={cn(panelClass(), "min-w-0 overflow-hidden p-3")}>
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2 border-b border-[rgb(var(--border))] pb-3">
            <div className="min-w-max">
              <FilterSelect filterId={filterId} filterType={filterType} relationshipTypes={relationshipTypes} setFilterType={(value) => { if (canLeave()) { setFilterType(value); setSelection(null) } }} />
            </div>
            {toolbarLeading ? <div className="min-w-max">{toolbarLeading}</div> : null}
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
                onClick={() => { if (canLeave()) { setShowIsolated((current) => !current); setSelection(null) } }}
              >
                {showIsolated ? "Hide isolated" : "Show isolated"}
              </GraphToolbarButton>
              <GraphToolbarButton
                active={showGrid}
                ariaPressed={showGrid}
                icon={<GridIcon className="h-4 w-4" />}
                onClick={() => setShowGrid((current) => !current)}
              >
                Grid
              </GraphToolbarButton>
              <GraphToolbarButton icon={<MinusIcon className="h-4 w-4" />} onClick={() => adjustZoom("out")}>Zoom out</GraphToolbarButton>
              <GraphToolbarButton icon={<PlusIcon className="h-4 w-4" />} onClick={() => adjustZoom("in")}>Zoom in</GraphToolbarButton>
              <GraphToolbarButton icon={<FitIcon className="h-4 w-4" />} onClick={fitCanvas}>Fit</GraphToolbarButton>
              <GraphToolbarButton icon={<ResetIcon className="h-4 w-4" />} onClick={resetLayout}>Reset layout</GraphToolbarButton>
              <button type="button" disabled={isFetching || savingEdge} className="app-button-secondary !rounded-sm" onClick={() => { if (canLeave()) { setSelection(null); void refetch() } }}>{isFetching ? "Refreshing…" : "Refresh graph"}</button>
            </div>
            <div className="ml-auto min-w-max px-2 text-sm text-[rgb(var(--muted-foreground))]">
              {graphStats.nodeCount} characters · {graphStats.edgeCount} connections · {zoomPercentLabel(zoomLevel)}
            </div>
          </div>

          {filteredGraph ? <RelationshipGraphBrowser graph={filteredGraph} disabled={savingEdge} onSelect={(kind, id) => {
            const element = cyRef.current?.getElementById(id)
            if (element?.nonempty()) requestSelectionRef.current(kind === "node" ? { type: "node", data: element.data() as GraphNodeView } : { type: "edge", data: element.data() as GraphEdgeView })
          }} /> : null}
          {filteredGraph && filteredGraph.nodes.length > 0 ? (
            <div className="relative overflow-hidden rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))]">
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
                className="pointer-events-none absolute inset-0 "
              />

              <div
                ref={containerRef}
                className="relative z-10 h-[64vh] min-h-[430px] md:h-[72vh] md:min-h-[600px]"
                style={{ cursor: interactionMode === "arrange" ? "grab" : "default" }}
              />

              <div className="pointer-events-none absolute bottom-4 left-4 z-20 flex max-w-[calc(100%-2rem)] flex-wrap gap-2 text-sm text-[rgb(var(--muted-foreground))]">
                <span>{storageError ? "Layout stays in this session; device storage is unavailable." : "Layout saves on this device."}</span>
                {filteredGraph.edges.length === 0 ? (
                  <span>
                    No relationships extracted yet. Characters remain visible so you can arrange the cast.
                  </span>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="flex h-[40vh] min-h-[340px] items-center justify-center rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] text-center text-[rgb(var(--muted-foreground))]">
              <div className="max-w-sm space-y-3 px-6">
                <p className="text-lg font-semibold text-[rgb(var(--foreground))]">{graphData?.nodes.length ? "No characters match these filters" : "No graphable relationships yet"}</p>
                {graphData?.nodes.length ? <button type="button" className="app-button-secondary" onClick={() => { setFilterType(null); setShowIsolated(true) }}>Clear graph filters</button> : null}
                <p className="text-sm leading-6">Relationship edges appear after character extraction has enough scene evidence. If this manuscript just finished uploading, processing may still be catching up.</p>
                <div className="flex flex-wrap justify-center gap-2 pt-1">
                  <Link href={`/${bookId}/${authorMode ? "manuscript" : "chapters"}`} className="rounded-sm border border-[rgb(var(--border))] bg-white/[0.06] px-3 py-2 text-sm font-semibold text-[rgb(var(--foreground))] hover:bg-white/[0.1]">
                    {authorMode ? "Open manuscript" : "View chapters"}
                  </Link>
                  <Link href={`/${bookId}/characters`} className="rounded-sm bg-violet-500/20 px-3 py-2 text-sm font-semibold text-violet-800 dark:text-violet-100 hover:bg-violet-500/30">
                    Review characters
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {selection ? <RelationshipGraphInspector bookId={bookId} inspectorPlacement={inspectorPlacement} selectedNode={selectedNode} selectedEdge={selectedEdge} selectedEdgeParticipants={selectedEdgeParticipants} selectedNodeConnections={selectedNodeConnections} labelInputId={labelInputId} labelOverrides={labelOverrides} storageError={storageError} updateNodeLabel={updateNodeLabel} clearLabelOverride={clearLabelOverride} clearSelection={clearSelection} focusSelection={focusSelection} authorMode={authorMode} savingEdge={savingEdge} edgeMessage={edgeMessage} edgeDraft={edgeDraft} setEdgeDraft={setEdgeDraft} saveEdgeCorrection={saveEdgeCorrection} deleteSelectedRelationship={deleteSelectedRelationship} /> : null}
    </div>
  )
})

export default RelationshipGraph
