import { useRef, useState } from "react"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import type { WorldElement, WorldGapResult, WorldIntegrationResult } from "@/types/world-building"

interface UseWorldbuildingElementActionsArgs {
  setAnalysis: (value: (current: WorldGapResult | null) => WorldGapResult | null) => void
  setIntegration: (value: (current: WorldIntegrationResult | null) => WorldIntegrationResult | null) => void
  setStatusMessage: (value: string | null) => void
}

export function useWorldbuildingElementActions({
  setAnalysis,
  setIntegration,
  setStatusMessage,
}: UseWorldbuildingElementActionsArgs) {
  const lock = useRef(false)
  const [accepting, setAccepting] = useState(false)
  const acceptElementSuggestion = async (element: WorldElement, suggestion: Record<string, unknown> | string) => {
    const suggestionId = typeof suggestion === "string" ? suggestion : String(suggestion.id ?? suggestion.title ?? suggestion.name ?? "")
    if (!suggestionId || lock.current) return
    lock.current = true; setAccepting(true)
    try {
      await worldBuildingApi.acceptSuggestion(element.id, { suggestion_id: suggestionId, mark_implemented: true })
    const removeSuggestion = (item: WorldElement) => item.id === element.id
      ? {
          ...item,
          suggestions: item.suggestions.filter((candidate) => {
            const candidateId = typeof candidate === "string" ? candidate : String(candidate.id ?? candidate.title ?? candidate.name ?? "")
            return candidateId !== suggestionId
          }),
        }
      : item
    setIntegration((current) => current ? { ...current, world_elements: current.world_elements.map(removeSuggestion) } : current)
    setAnalysis((current) => current ? { ...current, world_elements: current.world_elements.map(removeSuggestion) } : current)
      setStatusMessage("Marked that world suggestion as implemented. This records your decision; it does not edit the manuscript.")
    } catch (error) { setStatusMessage(`${getApiErrorDetail(error) ?? "Could not mark that suggestion as implemented."} The suggestion is retained. Try again.`) }
    finally { lock.current = false; setAccepting(false) }
  }

  return { acceptElementSuggestion, accepting }
}
