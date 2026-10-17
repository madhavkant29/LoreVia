"use client"

import Link from "next/link"
import type { Dispatch, SetStateAction } from "react"
import { WorkspaceSidePanel } from "@/components/ui/WorkspaceSidePanel"
import { cn } from "@/lib/utils/text"
import { CheckIcon, InspectorMetric, InspectorSection, RelationshipLabelChecklist, TargetIcon, TrashIcon, UsersIcon, type GraphNodeView, type GraphEdgeView } from "./RelationshipGraph.controls"
import { controlButtonClass, panelClass } from "./RelationshipGraph.helpers"
import { DIRECTIONAL_RELATIONSHIP_LABEL_OPTIONS, PRIMARY_RELATIONSHIP_TYPE_OPTIONS, SHARED_RELATIONSHIP_LABEL_OPTIONS, relationshipFacetLabel, relationshipFacetSummary, relationshipLabel, sentimentLabel } from "./relationshipGraphDisplay"
import type { RelationshipDraft } from "./RelationshipGraph.editing"

type Props = {
  bookId: string
  inspectorPlacement: "overlay" | "inline"
  selectedNode: GraphNodeView | null
  selectedEdge: GraphEdgeView | null
  selectedEdgeParticipants: { source: string; target: string } | null
  selectedNodeConnections: { id: string; label: string; name: string; chapter: number | null }[]
  labelInputId: string
  labelOverrides: Record<string, string>
  storageError: boolean
  updateNodeLabel: (id: string, value: string) => void
  clearLabelOverride: (node: GraphNodeView) => void
  clearSelection: () => void
  focusSelection: () => void
  authorMode: boolean
  savingEdge: boolean
  edgeMessage: string | null
  edgeDraft: RelationshipDraft
  setEdgeDraft: Dispatch<SetStateAction<RelationshipDraft>>
  saveEdgeCorrection: () => Promise<void>
  deleteSelectedRelationship: () => Promise<void>
}

export function RelationshipGraphInspector({ bookId, inspectorPlacement, selectedNode, selectedEdge, selectedEdgeParticipants, selectedNodeConnections, labelInputId, labelOverrides, storageError, updateNodeLabel, clearLabelOverride, clearSelection, focusSelection, authorMode, savingEdge, edgeMessage, edgeDraft, setEdgeDraft, saveEdgeCorrection, deleteSelectedRelationship }: Props) {
  const content = <aside data-graph-edit className={cn(panelClass(), "min-w-0 p-5 [overflow-wrap:anywhere]", inspectorPlacement === "inline" ? "mt-4" : "xl:max-h-[calc(100dvh-2rem)] xl:overflow-y-auto")}>
    <div className={cn("mb-4 items-center justify-between border-b border-[rgb(var(--border))] pb-3", inspectorPlacement === "inline" ? "flex" : "hidden xl:flex")}>
      <span className="text-sm font-semibold text-[rgb(var(--foreground))]">Graph details</span>
      <button type="button" onClick={clearSelection} disabled={savingEdge} className={controlButtonClass()}>Close</button>
    </div>
        {selectedNode ? (
          <div className="space-y-5">
            <div className="flex items-start gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-violet-700 dark:text-violet-300">Character</p>
                <h3 className="mt-1 break-words text-2xl font-semibold tracking-tight text-[rgb(var(--foreground))]">{selectedNode.name}</h3>
                <div className="mt-2 flex flex-wrap gap-3 text-sm text-[rgb(var(--muted-foreground))]">
                  {selectedNode.role ? (
                    <span>{selectedNode.role}</span>
                  ) : null}
                  {selectedNode.is_manual ? (
                    <span className="text-amber-800 dark:text-amber-200">Manual</span>
                  ) : null}
                  {selectedNode.graph_visibility_override === "include" ? (
                    <span className="text-teal-700 dark:text-teal-200">Forced visible</span>
                  ) : null}
                  {typeof selectedNode.visibility_score === "number" ? (
                    <span>Score {selectedNode.visibility_score}</span>
                  ) : null}
                </div>
              </div>
            </div>

            <InspectorSection title="Quick view">
              <div className="space-y-3 text-sm text-[rgb(var(--foreground))]">
                {typeof selectedNode.mention_count === "number" ? <InspectorMetric label="Mentions" value={selectedNode.mention_count} /> : null}
                <InspectorMetric label="Connections in view" value={selectedNode.relationshipCount ?? 0} />
                <InspectorMetric label="First chapter" value={selectedNode.first_chapter} />
                {Number.isInteger(selectedNode.first_chapter) && selectedNode.first_chapter > 0 ? <Link className="block underline underline-offset-4" href={`/${bookId}/chapter/${selectedNode.first_chapter}`}>Open first chapter</Link> : null}
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
              <p className="mb-2 text-sm text-[rgb(var(--muted-foreground))]">{storageError ? "Display labels stay in this session; device storage is unavailable." : "Saved on this device."} The character’s canonical name is unchanged.</p>
              <label htmlFor={labelInputId} className="sr-only">Display label</label>
              <input
                id={labelInputId}
                value={labelOverrides[selectedNode.id] ?? selectedNode.name}
                onChange={(event) => updateNodeLabel(selectedNode.id, event.target.value)}
                className="w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
              />
              <button
                type="button"
                onClick={() => clearLabelOverride(selectedNode)}
                className="mt-3 text-sm font-medium text-[rgb(var(--muted-foreground))] transition hover:text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
              >
                Reset to canonical name
              </button>
            </InspectorSection>

            <InspectorSection title="Reading note">
              <p className="text-sm leading-7 text-[rgb(var(--foreground))]">
                {selectedNode.description || "No narrative summary has been saved yet."}
              </p>
            </InspectorSection>

            {"arc_summary" in selectedNode && selectedNode.arc_summary ? (
              <InspectorSection title="Arc summary">
                <p className="text-sm leading-7 text-[rgb(var(--foreground))]">{selectedNode.arc_summary}</p>
              </InspectorSection>
            ) : null}

            {selectedNode.aliases?.length ? (
              <InspectorSection title="Aliases">
                <div className="flex flex-wrap gap-2">
                  {selectedNode.aliases.map((alias) => (
                    <span key={alias} className="rounded-sm border border-[rgb(var(--border))] bg-white/[0.03] px-3 py-1.5 text-sm text-[rgb(var(--foreground))]">
                      {alias}
                    </span>
                  ))}
                </div>
              </InspectorSection>
            ) : null}

            {selectedNode.personality_tags?.length ? (
              <InspectorSection title="Disposition">
                <p className="text-sm leading-7 text-[rgb(var(--foreground))]">{selectedNode.personality_tags.join(", ")}</p>
              </InspectorSection>
            ) : null}

            {selectedNode.motivations?.length ? (
              <InspectorSection title="Motivations">
                <p className="text-sm leading-7 text-[rgb(var(--foreground))]">{selectedNode.motivations.join(", ")}</p>
              </InspectorSection>
            ) : null}

            {selectedNode.fears?.length ? (
              <InspectorSection title="Fears">
                <p className="text-sm leading-7 text-[rgb(var(--foreground))]">{selectedNode.fears.join(", ")}</p>
              </InspectorSection>
            ) : null}

            {selectedNodeConnections.length > 0 ? (
              <InspectorSection title="Visible connections">
                <div className="space-y-3">
                  {selectedNodeConnections.map((connection) => (
                    <div key={connection.id} className="flex items-start justify-between gap-3 border-b border-[rgb(var(--border))] py-2 text-sm last:border-b-0">
                      <div>
                        <p className="font-medium text-[rgb(var(--foreground))]">{connection.name}</p>
                        <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">{connection.label}</p>
                      </div>
                      {typeof connection.chapter === "number" ? (
                        <span className="text-sm text-[rgb(var(--muted-foreground))]">Ch. {connection.chapter}</span>
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
              <p className="text-sm font-medium text-violet-700 dark:text-violet-300">Connection</p>
              <h3 className="mt-1 text-2xl font-semibold tracking-tight text-[rgb(var(--foreground))]">
                {relationshipFacetSummary([...(selectedEdge.character_a_to_b_labels ?? []), ...(selectedEdge.character_b_to_a_labels ?? []), ...(selectedEdge.shared_labels ?? [])], selectedEdge.type)}
              </h3>
              {selectedEdgeParticipants ? (
                <p className="mt-3 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                  {selectedEdgeParticipants.source} {"->"} {selectedEdgeParticipants.target}
                </p>
              ) : null}
            </div>

            <InspectorSection title="Relationship note">
              <p className="text-sm leading-7 text-[rgb(var(--foreground))]">
                {selectedEdge.description || "No explicit relationship note has been saved yet."}
              </p>
            </InspectorSection>

            <InspectorSection title="Network detail">
              <div className="space-y-3 text-sm text-[rgb(var(--foreground))]">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[rgb(var(--foreground))]">Primary type</span>
                  <span className="font-semibold text-[rgb(var(--foreground))]">{relationshipFacetLabel(selectedEdge.type)}</span>
                </div>
                {typeof selectedEdge.from_chapter === "number" ? <InspectorMetric label="First tracked" value={selectedEdge.from_chapter} /> : null}
                {typeof selectedEdge.from_chapter === "number" && Number.isInteger(selectedEdge.from_chapter) && selectedEdge.from_chapter > 0 ? <Link className="block underline underline-offset-4" href={`/${bookId}/chapter/${selectedEdge.from_chapter}`}>Open source chapter {selectedEdge.from_chapter}</Link> : null}
                {typeof selectedEdge.to_chapter === "number" ? <InspectorMetric label="Ends chapter" value={selectedEdge.to_chapter} /> : null}
                {selectedEdge.status ? (
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[rgb(var(--foreground))]">Status</span>
                    <span className="font-semibold capitalize text-[rgb(var(--foreground))]">{selectedEdge.status}</span>
                  </div>
                ) : null}
                {sentimentLabel(selectedEdge.sentiment) ? (
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[rgb(var(--foreground))]">Emotional direction</span>
                    <span className="font-semibold text-[rgb(var(--foreground))]">{sentimentLabel(selectedEdge.sentiment)}</span>
                  </div>
                ) : null}
              </div>
            </InspectorSection>

            {authorMode && selectedEdge.relationshipId ? (
              <InspectorSection title="Author correction">
                <p className="text-sm leading-6 text-[rgb(var(--muted-foreground))]">
                  Correct the extracted relationship if the manuscript context is clearer than the model guess.
                </p>

                <fieldset disabled={savingEdge} className="mt-4 space-y-3">
                  <label className="block">
                    <span className="mb-1 block text-sm text-[rgb(var(--muted-foreground))]">Type</span>
                    <select
                      value={edgeDraft.relType}
                      onChange={(event) => setEdgeDraft((value) => ({ ...value, relType: event.target.value }))}
                      className="w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
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
                    <div className="grid gap-3">
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
                    <span className="mb-1 block text-sm text-[rgb(var(--muted-foreground))]">Relationship note</span>
                    <textarea
                      value={edgeDraft.description}
                      onChange={(event) => setEdgeDraft((value) => ({ ...value, description: event.target.value }))}
                      rows={4}
                      className="w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                    />
                  </label>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <label className="block">
                      <span className="mb-1 block text-sm text-[rgb(var(--muted-foreground))]">Sentiment</span>
                      <input
                        type="number"
                        min={-1}
                        max={1}
                        step={0.1}
                        value={edgeDraft.sentiment}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, sentiment: event.target.value }))}
                        className="w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm text-[rgb(var(--muted-foreground))]">From chapter</span>
                      <input
                        type="number"
                        min={1}
                        value={edgeDraft.fromChapter}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, fromChapter: event.target.value }))}
                        className="w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm text-[rgb(var(--muted-foreground))]">Ends chapter</span>
                      <input
                        type="number"
                        min={1}
                        value={edgeDraft.toChapter}
                        onChange={(event) => setEdgeDraft((value) => ({ ...value, toChapter: event.target.value }))}
                        className="w-full rounded-sm border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
                      />
                      <span className="mt-1 block text-sm text-[rgb(var(--muted-foreground))]">Leave blank if ongoing.</span>
                    </label>
                  </div>

                  {edgeMessage ? (
                    <p role="status" className={cn("text-sm", edgeMessage.includes("saved") || edgeMessage.includes("removed") ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-300")}>
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
                        "inline-flex items-center justify-center gap-2 rounded-sm border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-800 dark:text-rose-100 transition-colors",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/70",
                        savingEdge && "opacity-60"
                      )}
                    >
                      <TrashIcon className="h-4 w-4" />
                      <span>Delete relationship</span>
                    </button>
                  </div>
                </fieldset>
              </InspectorSection>
            ) : null}
          </div>
        ) : null}
  </aside>
  return inspectorPlacement === "inline" ? content : <WorkspaceSidePanel title="Graph details" side="right" onClose={clearSelection}>{content}</WorkspaceSidePanel>
}
