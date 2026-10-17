"use client"

import type { ReactNode } from "react"
import {
  Check as CheckIcon,
  ChevronDown as ChevronDownIcon,
  Eye as EyeIcon,
  Filter as FilterIcon,
  Grip as GridIcon,
  Hand as HandIcon,
  LayoutGrid as ArrangeIcon,
  Link2 as LinksIcon,
  LocateFixed as TargetIcon,
  Maximize as FitIcon,
  Minus as MinusIcon,
  MousePointer2 as CursorIcon,
  Plus as PlusIcon,
  RotateCcw as ResetIcon,
  Search as ScopeIcon,
  Trash2 as TrashIcon,
  Users as UsersIcon,
} from "lucide-react"

import { cn } from "@/lib/utils/text"
import type { RelationshipGraph as GraphData } from "@/types/character"
import { controlButtonClass } from "./RelationshipGraph.helpers"
import { relationshipFacetLabel, relationshipLabel } from "./relationshipGraphDisplay"

type GraphNode = GraphData["nodes"][number]
type GraphEdge = GraphData["edges"][number]
export type GraphNodeView = GraphNode & { label: string; relationshipCount: number }
export type GraphEdgeView = GraphEdge & { id: string; relationshipId?: string | null; label: string }

export {
  ArrangeIcon, CheckIcon, ChevronDownIcon, CursorIcon, EyeIcon, FilterIcon, FitIcon, GridIcon,
  HandIcon, LinksIcon, MinusIcon, PlusIcon, ResetIcon, ScopeIcon, TargetIcon, TrashIcon, UsersIcon,
}

export function GraphToolbarButton({
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

export function GraphStatusPill({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-sm border border-[rgb(var(--border))] bg-white/[0.03] px-3 py-1.5 text-sm text-[rgb(var(--foreground))]">
      <span className="text-[rgb(var(--muted-foreground))]">{icon}</span>
      <span>{children}</span>
    </div>
  )
}

export function FilterSelect({
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
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[rgb(var(--muted-foreground))]">
          <FilterIcon className="h-4 w-4" />
        </span>
        <select
          id={filterId}
          aria-label="Filter relationships"
          value={filterType ?? ""}
          onChange={(event) => setFilterType(event.target.value || null)}
          className="w-full appearance-none rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] py-2 pl-9 pr-9 text-sm text-[rgb(var(--foreground))] transition-colors hover:border-[rgb(var(--border))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
        >
          <option value="">All</option>
          {relationshipTypes.map((type) => (
            <option key={type} value={type}>
              {relationshipLabel(type)}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[rgb(var(--muted-foreground))]">
          <ChevronDownIcon className="h-4 w-4" />
        </span>
      </div>
    </div>
  )
}

export function InspectorMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[rgb(var(--foreground))]">{label}</span>
      <span className="font-semibold text-[rgb(var(--foreground))]">{value}</span>
    </div>
  )
}

export function RelationshipLabelChecklist({
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
    <fieldset className="rounded-sm border border-[rgb(var(--border))] bg-black/15 p-3">
      <legend className="px-1 text-sm text-[rgb(var(--muted-foreground))]">{label}</legend>
      <div className="mt-2 grid max-h-36 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
        {options.map((option) => (
          <label key={option} className="flex min-w-0 items-center gap-2 rounded-sm px-2 py-1 text-sm text-[rgb(var(--foreground))] hover:bg-white/[0.04]">
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
              className="h-3.5 w-3.5 rounded border-[rgb(var(--border))] bg-[rgb(var(--card))] text-violet-500 focus:ring-violet-400"
            />
            <span className="break-words">{relationshipFacetLabel(option)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

export function InspectorSection({
  children,
  title,
}: {
  children: ReactNode
  title: string
}) {
  return (
    <section className="border-b border-[rgb(var(--border))] py-4 last:border-b-0">
      <h4 className="text-sm font-semibold text-[rgb(var(--foreground))]">{title}</h4>
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function EmptyInspector({
  edgeCount,
  nodeCount,
}: {
  edgeCount: number
  nodeCount: number
}) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-violet-700 dark:text-violet-300/85">Inspector</p>
        <h3 className="mt-3 text-[2rem] font-semibold tracking-tight text-[rgb(var(--foreground))]">Read the map</h3>
      </div>

      <p className="text-sm leading-7 text-[rgb(var(--muted-foreground))]">
        Select a character to inspect their role in the network, or select a connection to read the relationship note. Arrange mode is best when you want to cluster the cast your own way.
      </p>

      <InspectorSection title="Visible now">
        <div className="space-y-3 text-sm">
          <InspectorMetric label="Visible characters" value={nodeCount} />
          <InspectorMetric label="Visible connections" value={edgeCount} />
        </div>
      </InspectorSection>

      <div className="flex min-h-[220px] flex-col items-center justify-center rounded-sm border border-dashed border-[rgb(var(--border))] bg-white/[0.02] px-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-sm border border-violet-400/40 bg-violet-500/8 text-violet-700 dark:text-violet-200">
          <CursorIcon className="h-7 w-7" />
        </div>
        <p className="mt-5 text-lg font-semibold text-[rgb(var(--foreground))]">Select a character or connection</p>
        <p className="mt-2 max-w-xs text-sm leading-7 text-[rgb(var(--muted-foreground))]">
          Use the graph to explore relationships between characters in your manuscript.
        </p>
      </div>

      <InspectorSection title="Tip">
        <p className="text-sm leading-7 text-[rgb(var(--foreground))]">
          Drag nodes to cluster related characters. Your layout is saved automatically.
        </p>
      </InspectorSection>
    </div>
  )
}

export function CompactSelectionSummary({
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
