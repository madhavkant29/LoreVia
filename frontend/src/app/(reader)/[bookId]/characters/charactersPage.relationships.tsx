import type { ReactNode } from "react"

import type { ConnectedRelationship } from "@/components/reader/CharacterProfileRightRail"
import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import {
  RELATIONSHIP_TYPE_OPTIONS,
  formatRelationshipType,
  graphVisibilityReasonCopy,
  relationshipStrengthColor,
  sentimentLabel,
  strengthValue,
  type RelationshipComposerDraft,
} from "./charactersPage.helpers"
import { SurfaceCard } from "./charactersPage.components"

type HiddenGraphNode = NonNullable<RelationshipGraphData["hidden_nodes"]>[number]

type CharacterRelationshipsTabProps = {
  children: ReactNode
  connections: ConnectedRelationship[]
  counterpartOptions: Character[]
  createRelationshipBusy: boolean
  hiddenGraphNodes: HiddenGraphNode[]
  isAuthorMode: boolean
  isDark: boolean
  relationshipDraft: RelationshipComposerDraft
  onCreateRelationship: () => void
  onDraftChange: (updater: (value: RelationshipComposerDraft) => RelationshipComposerDraft) => void
  onReviewHiddenNode: (nodeId: string) => void
}

export function CharacterRelationshipsTab({
  children,
  connections,
  counterpartOptions,
  createRelationshipBusy,
  hiddenGraphNodes,
  isAuthorMode,
  isDark,
  relationshipDraft,
  onCreateRelationship,
  onDraftChange,
  onReviewHiddenNode,
}: CharacterRelationshipsTabProps) {
  const inputClass = `w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-[#202a38] bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`
  const labelClass = `text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`

  return (
    <div className="mt-5 space-y-4">
      {children}

      {isAuthorMode ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <SurfaceCard title="Create relationship" isDark={isDark}>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="space-y-1 md:col-span-2">
                <span className={labelClass}>Counterpart</span>
                <select
                  value={relationshipDraft.counterpartId}
                  onChange={(event) => onDraftChange((value) => ({ ...value, counterpartId: event.target.value }))}
                  className={inputClass}
                >
                  <option value="">Choose a character</option>
                  {counterpartOptions.map((character) => (
                    <option key={character.id} value={character.id}>{character.name}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Type</span>
                <select
                  value={relationshipDraft.relType}
                  onChange={(event) => onDraftChange((value) => ({ ...value, relType: event.target.value as RelationshipComposerDraft["relType"] }))}
                  className={inputClass}
                >
                  {RELATIONSHIP_TYPE_OPTIONS.map((type) => (
                    <option key={type} value={type}>{formatRelationshipType(type)}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Sentiment</span>
                <input
                  type="number"
                  min={-1}
                  max={1}
                  step={0.1}
                  value={relationshipDraft.sentiment}
                  onChange={(event) => onDraftChange((value) => ({ ...value, sentiment: event.target.value }))}
                  className={inputClass}
                />
              </label>
              <label className="space-y-1">
                <span className={labelClass}>From chapter</span>
                <input
                  value={relationshipDraft.fromChapter}
                  onChange={(event) => onDraftChange((value) => ({ ...value, fromChapter: event.target.value }))}
                  inputMode="numeric"
                  className={inputClass}
                />
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Ends chapter</span>
                <input
                  value={relationshipDraft.toChapter}
                  onChange={(event) => onDraftChange((value) => ({ ...value, toChapter: event.target.value }))}
                  inputMode="numeric"
                  className={inputClass}
                />
              </label>
              <label className="space-y-1 md:col-span-2">
                <span className={labelClass}>Relationship note</span>
                <textarea
                  value={relationshipDraft.description}
                  onChange={(event) => onDraftChange((value) => ({ ...value, description: event.target.value }))}
                  rows={3}
                  className={inputClass}
                />
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" disabled={createRelationshipBusy} onClick={onCreateRelationship} className="rounded-md bg-[#1f615d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
                {createRelationshipBusy ? "Saving..." : "Create relationship"}
              </button>
            </div>
          </SurfaceCard>

          <SurfaceCard title="Hidden from graph" isDark={isDark}>
            {hiddenGraphNodes.length > 0 ? (
              <div className="space-y-3">
                {hiddenGraphNodes.slice(0, 8).map((node) => (
                  <div key={node.id} className={`rounded-xl border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{node.name}</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Score {node.visibility_score} • {node.connected_relationship_count} relationship signals</p>
                      </div>
                      <button type="button" onClick={() => onReviewHiddenNode(node.id)} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/[0.06] text-white" : "bg-stone-100 text-stone-800"}`}>
                        Review
                      </button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {node.visibility_reasons.map((reason) => (
                        <span key={`${node.id}-${reason}`} className={`rounded-full px-3 py-1 text-3xs ${isDark ? "bg-white/[0.05] text-slate-300" : "border border-stone-200 bg-stone-50 text-stone-600"}`}>
                          {graphVisibilityReasonCopy(reason)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No cast members are currently being filtered out of the graph.</p>
            )}
          </SurfaceCard>
        </div>
      ) : null}

      <SurfaceCard title="Relationship table" isDark={isDark}>
        {connections.length > 0 ? (
          <div className="space-y-3">
            <div className={`hidden grid-cols-[minmax(0,1fr)_120px_minmax(120px,1fr)_120px_96px] gap-2 px-3 text-xs font-semibold uppercase tracking-wide md:grid ${isDark ? "text-slate-500" : "text-stone-400"}`}>
              <span>Character</span>
              <span>Relationship</span>
              <span>Dynamics</span>
              <span>Strength</span>
              <span>Evidence</span>
            </div>
            {connections.map((edge, index) => (
              <div key={`${edge.source}-${edge.target}-${edge.type}-${index}`} className={`grid gap-2 rounded-xl border px-3 py-3 md:grid-cols-[minmax(0,1fr)_120px_minmax(120px,1fr)_120px_96px] ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                <div className="min-w-0">
                  <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{edge.counterpartName}</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{typeof edge.from_chapter === "number" ? `Chapter ${edge.from_chapter}` : "Chapter evidence pending"} / {Math.max(1, Math.round(strengthValue(edge.sentiment) / 10))} mentions</p>
                </div>
                <div className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{formatRelationshipType(edge.type)}</div>
                <div className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{edge.description || sentimentLabel(edge.sentiment)}</div>
                <div className="flex items-center gap-2">
                  <span className={`h-2 flex-1 rounded-full ${isDark ? "bg-white/10" : "bg-stone-100"}`}>
                    <span className={`block h-2 rounded-full ${relationshipStrengthColor(edge.sentiment, isDark)}`} style={{ width: `${strengthValue(edge.sentiment)}%` }} />
                  </span>
                </div>
                <div className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{typeof edge.from_chapter === "number" ? `Ch. ${edge.from_chapter}` : "No ch."}{edge.status === "ended" ? " • ended" : ""}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No relationship links are visible for this character yet.</p>
        )}
      </SurfaceCard>
    </div>
  )
}
