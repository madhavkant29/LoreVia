import { useState } from "react"
import type { RelationshipGraph } from "@/types/character"
import { relationshipFacetLabel } from "./relationshipGraphDisplay"

export function RelationshipGraphBrowser({ graph, onSelect, disabled }: { graph: Pick<RelationshipGraph, "nodes" | "edges">; onSelect: (kind: "node" | "edge", id: string) => void; disabled: boolean }) {
  const [query, setQuery] = useState("")
  const [limit, setLimit] = useState(30)
  const lookup = new Map(graph.nodes.map((node) => [node.id, node.name]))
  const needle = query.trim().toLocaleLowerCase()
  const nodes = graph.nodes.filter((node) => node.name.toLocaleLowerCase().includes(needle))
  const edges = graph.edges.map((edge, index) => ({ ...edge, graphId: `${edge.source}-${edge.target}-${edge.type}-${index}`, label: `${lookup.get(edge.source) ?? "Unknown character"} → ${lookup.get(edge.target) ?? "Unknown character"} · ${relationshipFacetLabel(edge.type)}` })).filter((edge) => edge.label.toLocaleLowerCase().includes(needle))
  return <details className="border-y border-[rgb(var(--border))] py-3">
    <summary className="cursor-pointer py-1 text-sm font-semibold">Browse characters and connections</summary>
    <p className="mt-3 text-sm text-[rgb(var(--muted-foreground))]">Select any entry to open its details. This list follows the graph filters.</p>
    <label className="mt-3 block text-sm"><span>Find in this graph</span><input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(30) }} className="mt-1 block min-h-10 w-full max-w-md rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3" /></label>
    <div className="mt-4 grid gap-5 md:grid-cols-2">
      <section><h2 className="text-sm font-semibold">Characters ({nodes.length})</h2><ul className="mt-2 space-y-1">{nodes.slice(0, limit).map((node) => <li key={node.id}><button type="button" disabled={disabled} onClick={() => onSelect("node", node.id)} className="w-full px-2 py-2 text-left text-sm underline underline-offset-4 hover:bg-[rgb(var(--muted))]">{node.name}</button></li>)}</ul>{!nodes.length ? <p className="py-2 text-sm text-[rgb(var(--muted-foreground))]">No characters match.</p> : null}</section>
      <section><h2 className="text-sm font-semibold">Connections ({edges.length})</h2><ul className="mt-2 space-y-1">{edges.slice(0, limit).map((edge) => <li key={edge.graphId}><button type="button" disabled={disabled} onClick={() => onSelect("edge", edge.graphId)} className="w-full px-2 py-2 text-left text-sm underline underline-offset-4 hover:bg-[rgb(var(--muted))]">{edge.label}</button></li>)}</ul>{!edges.length ? <p className="py-2 text-sm text-[rgb(var(--muted-foreground))]">No connections match.</p> : null}</section>
    </div>
    {nodes.length > limit || edges.length > limit ? <button type="button" className="app-button-secondary mt-3" onClick={() => setLimit((value) => value + 30)}>Show more entries</button> : null}
  </details>
}
