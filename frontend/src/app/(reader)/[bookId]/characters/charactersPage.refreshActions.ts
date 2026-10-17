import { useCallback, useState, type Dispatch, type SetStateAction } from "react"

import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type QueryRefetch<T> = () => Promise<{ data?: T; error?: unknown }>

type UseCharacterRefreshActionsArgs = {
  refetchCharacterReview: QueryRefetch<unknown>
  refetchCharacters: QueryRefetch<Character[]>
  refetchRelationshipGraph: QueryRefetch<RelationshipGraphData | null>
  refetchRepairPreview: QueryRefetch<unknown>
  workspaceMode: WorkspaceMode
  setActionError: Dispatch<SetStateAction<string | null>>
  setChars: Dispatch<SetStateAction<Character[]>>
  setGraphData: Dispatch<SetStateAction<RelationshipGraphData | null>>
}

export function useCharacterRefreshActions({
  refetchCharacterReview,
  refetchCharacters,
  refetchRelationshipGraph,
  refetchRepairPreview,
  workspaceMode,
  setActionError,
  setChars,
  setGraphData,
}: UseCharacterRefreshActionsArgs) {
  const [refreshingGraph, setRefreshingGraph] = useState(false)

  const refreshCharacters = useCallback(async () => {
    const { data: refreshed, error } = await refetchCharacters()
    if (error || !refreshed) throw new Error("Could not refresh characters.")
    await refetchCharacterReview()
    if (workspaceMode === "repair") {
      await refetchRepairPreview()
    }
    setChars(refreshed)
    return refreshed
  }, [refetchCharacterReview, refetchCharacters, refetchRepairPreview, setChars, workspaceMode])

  const refreshGraph = useCallback(async () => {
    setRefreshingGraph(true)
    try {
      const { data: refreshed = null, error } = await refetchRelationshipGraph()
      if (error || !refreshed) {
        setActionError("Could not rebuild the relationship graph.")
        return
      }
      setGraphData(refreshed)
    } catch {
      setActionError("Could not rebuild the relationship graph.")
    } finally {
      setRefreshingGraph(false)
    }
  }, [refetchRelationshipGraph, setActionError, setGraphData])

  return {
    refreshingGraph,
    refreshCharacters,
    refreshGraph,
  }
}
