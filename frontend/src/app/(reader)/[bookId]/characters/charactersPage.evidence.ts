import { useCallback, useEffect, useState } from "react"

import type { SidebarTab } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import { readerApi } from "@/lib/api/reader"
import type { Character, CharacterCandidate } from "@/types/character"
import type { SearchResult } from "@/types/reader"
import { buildCandidateEvidenceQuery, buildCharacterEvidenceQuery } from "./charactersPage.helpers"

export type EvidenceCacheEntry = {
  chapter: number
  results: SearchResult[]
}

type UseCharacterEvidenceArgs = {
  bookId: string
  relationshipChapter: number
}

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type UseCharacterEvidenceAutoLoadArgs = {
  activeTab: CharacterProfileTab
  sidebarTab: SidebarTab
  workspaceMode: WorkspaceMode
  selectedCharacter: Character | null | undefined
  selectedMergePrimary: Character | null | undefined
  selectedMergeSecondary: Character | null | undefined
  loadCharacterEvidence: (character: Character, force?: boolean) => Promise<SearchResult[]>
}

export function useCharacterEvidence({
  bookId,
  relationshipChapter,
}: UseCharacterEvidenceArgs) {
  const [evidenceCache, setEvidenceCache] = useState<Record<string, EvidenceCacheEntry>>({})
  const [evidenceLoadingId, setEvidenceLoadingId] = useState<string | null>(null)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)

  const loadCharacterEvidence = useCallback(async (character: Character, force = false) => {
    const cached = evidenceCache[character.id]
    if (!force && cached && cached.chapter === relationshipChapter) return cached.results

    setEvidenceLoadingId(character.id)
    setEvidenceError(null)
    try {
      const query = buildCharacterEvidenceQuery(character)
      const results = await readerApi.search(bookId, query || character.name, relationshipChapter)
      setEvidenceCache((current) => ({
        ...current,
        [character.id]: {
          chapter: relationshipChapter,
          results: results.slice(0, 8),
        },
      }))
      return results
    } catch {
      setEvidenceError("Could not pull grounded evidence right now.")
      return []
    } finally {
      setEvidenceLoadingId((current) => current === character.id ? null : current)
    }
  }, [bookId, evidenceCache, relationshipChapter])

  const loadCandidateEvidence = useCallback(async (candidate: CharacterCandidate) => {
    setEvidenceLoadingId(candidate.id)
    setEvidenceError(null)
    try {
      const results = await readerApi.search(bookId, buildCandidateEvidenceQuery(candidate), candidate.chapter_number)
      setEvidenceCache((current) => ({
        ...current,
        [candidate.id]: {
          chapter: candidate.chapter_number,
          results,
        },
      }))
    } catch {
      setEvidenceError("Could not load candidate evidence.")
    } finally {
      setEvidenceLoadingId(null)
    }
  }, [bookId])

  return {
    evidenceCache,
    evidenceError,
    evidenceLoadingId,
    loadCandidateEvidence,
    loadCharacterEvidence,
  }
}

export function useCharacterEvidenceAutoLoad({
  activeTab,
  loadCharacterEvidence,
  selectedCharacter,
  selectedMergePrimary,
  selectedMergeSecondary,
  sidebarTab,
  workspaceMode,
}: UseCharacterEvidenceAutoLoadArgs) {
  useEffect(() => {
    if (!selectedCharacter || workspaceMode !== "profile") return
    if (activeTab !== "evidence" && sidebarTab !== "evidence") return
    void loadCharacterEvidence(selectedCharacter)
  }, [activeTab, loadCharacterEvidence, selectedCharacter, sidebarTab, workspaceMode])

  useEffect(() => {
    if (workspaceMode !== "duplicates" || !selectedMergePrimary || !selectedMergeSecondary) return
    void loadCharacterEvidence(selectedMergePrimary)
    void loadCharacterEvidence(selectedMergeSecondary)
  }, [loadCharacterEvidence, selectedMergePrimary, selectedMergeSecondary, workspaceMode])
}
