import { useEffect, useRef } from "react"
import type { GraphEdgeView } from "./RelationshipGraph.controls"

export type RelationshipDraft = {
  relType: string; description: string; sentiment: string; fromChapter: string; toChapter: string
  sharedLabels: string[]; sourceToTargetLabels: string[]; targetToSourceLabels: string[]
}

export function relationshipDraft(edge: GraphEdgeView | null): RelationshipDraft {
  return {
    relType: edge?.type || "", description: edge?.description || "",
    sentiment: typeof edge?.sentiment === "number" ? String(edge.sentiment) : "0",
    fromChapter: typeof edge?.from_chapter === "number" ? String(edge.from_chapter) : "",
    toChapter: typeof edge?.to_chapter === "number" ? String(edge.to_chapter) : "",
    sharedLabels: edge?.shared_labels ?? [], sourceToTargetLabels: edge?.character_a_to_b_labels ?? [], targetToSourceLabels: edge?.character_b_to_a_labels ?? [],
  }
}

export function relationshipDraftError(draft: RelationshipDraft) {
  if (!draft.relType.trim()) return "Choose a relationship type."
  if (draft.sentiment.trim() && (!Number.isFinite(Number(draft.sentiment)) || Number(draft.sentiment) < -1 || Number(draft.sentiment) > 1)) return "Sentiment must be between −1 and 1, or blank."
  for (const value of [draft.fromChapter, draft.toChapter]) if (value.trim() && (!Number.isInteger(Number(value)) || Number(value) < 1)) return "Chapter numbers must be positive whole numbers, or blank."
  if (draft.fromChapter.trim() && draft.toChapter.trim() && Number(draft.toChapter) < Number(draft.fromChapter)) return "The end chapter cannot come before the first chapter."
  return null
}

export function useRelationshipDraftGuard(dirty: boolean, busy: boolean) {
  const state = useRef({ dirty, busy })
  state.current = { dirty, busy }
  const canLeave = useRef(() => !state.current.busy && (!state.current.dirty || window.confirm("Discard the unsaved relationship correction?"))).current
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => { if (state.current.dirty || state.current.busy) { event.preventDefault(); event.returnValue = "" } }
    const beforeNavigation = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null
      if (link && !canLeave()) { event.preventDefault(); event.stopPropagation() }
    }
    const beforeScopeChange = (event: Event) => {
      if (event.target instanceof HTMLSelectElement && event.target.matches("[data-graph-scope]") && !canLeave()) { event.target.value = event.target.dataset.graphCurrent ?? ""; event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", beforeUnload)
    document.addEventListener("click", beforeNavigation, true)
    document.addEventListener("change", beforeScopeChange, true)
    return () => { window.removeEventListener("beforeunload", beforeUnload); document.removeEventListener("click", beforeNavigation, true); document.removeEventListener("change", beforeScopeChange, true) }
  }, [canLeave])
  return canLeave
}
