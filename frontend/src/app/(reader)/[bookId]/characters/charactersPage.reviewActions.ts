import { useState, type Dispatch, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type { Character, CharacterCandidate, CharacterRelationshipCandidate } from "@/types/character"
import { relationshipReviewProposal } from "./charactersPage.helpers"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type UseCharacterReviewActionsArgs = {
  bookId: string
  refreshCharacters: () => Promise<Character[]>
  refreshGraph: () => Promise<void>
  refetchCharacterReview: () => Promise<unknown>
  selectedCharacter: Character | null
  setActionError: Dispatch<SetStateAction<string | null>>
  setSelectedId: Dispatch<SetStateAction<string>>
  setWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>
}

export function useCharacterReviewActions({
  bookId,
  refreshCharacters,
  refreshGraph,
  refetchCharacterReview,
  selectedCharacter,
  setActionError,
  setSelectedId,
  setWorkspaceMode,
}: UseCharacterReviewActionsArgs) {
  const [candidateActionId, setCandidateActionId] = useState<string | null>(null)
  const [relationshipCandidateActionId, setRelationshipCandidateActionId] = useState<string | null>(null)

  async function handlePromoteCandidate(candidate: CharacterCandidate) {
    setCandidateActionId(candidate.id)
    setActionError(null)
    try {
      const response = await booksApi.promoteCharacterCandidate(bookId, candidate.id)
      const refreshed = await refreshCharacters()
      setWorkspaceMode("profile")
      setSelectedId(response.promoted || refreshed[0]?.id || "")
      await refreshGraph()
    } catch {
      setActionError("Could not promote this candidate into the cast.")
    } finally {
      setCandidateActionId(null)
    }
  }

  async function handleAttachCandidate(candidate: CharacterCandidate) {
    if (!selectedCharacter) {
      setActionError("Select a character profile first, then attach this candidate.")
      return
    }
    setCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.attachCharacterCandidate(bookId, candidate.id, selectedCharacter.id)
      await refreshCharacters()
      await refreshGraph()
    } catch {
      setActionError("Could not attach this candidate to the selected character.")
    } finally {
      setCandidateActionId(null)
    }
  }

  async function handleRejectCandidate(candidate: CharacterCandidate) {
    setCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.rejectCharacterCandidate(bookId, candidate.id)
      await refetchCharacterReview()
    } catch {
      setActionError("Could not reject this candidate.")
    } finally {
      setCandidateActionId(null)
    }
  }

  async function handleMarkCandidatePlace(candidate: CharacterCandidate) {
    setCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.markCharacterCandidatePlace(bookId, candidate.id)
      await refetchCharacterReview()
    } catch {
      setActionError("Could not mark this candidate as a place.")
    } finally {
      setCandidateActionId(null)
    }
  }

  async function handleAttachRelationshipCandidate(
    candidate: CharacterRelationshipCandidate,
    side: "a" | "b",
  ) {
    if (!selectedCharacter) {
      setActionError("Select a character profile first, then attach the unresolved side.")
      return
    }
    setRelationshipCandidateActionId(candidate.id)
    setActionError(null)
    try {
      if (side === "a") {
        await booksApi.attachRelationshipCandidateA(bookId, candidate.id, selectedCharacter.id)
      } else {
        await booksApi.attachRelationshipCandidateB(bookId, candidate.id, selectedCharacter.id)
      }
      await refetchCharacterReview()
    } catch {
      setActionError("Could not attach that relationship endpoint.")
    } finally {
      setRelationshipCandidateActionId(null)
    }
  }

  async function handleAcceptRelationshipCandidate(candidate: CharacterRelationshipCandidate) {
    const proposal = relationshipReviewProposal(candidate)
    const leftId = candidate.matched_character_a_id ?? selectedCharacter?.id ?? null
    const rightId = candidate.matched_character_b_id ?? selectedCharacter?.id ?? null
    if (!leftId || !rightId || leftId === rightId) {
      setActionError("Attach both sides to real characters before creating this relationship.")
      return
    }
    setRelationshipCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.acceptRelationshipCandidate(bookId, candidate.id, {
        characterAId: leftId,
        characterBId: rightId,
        relType: proposal?.relType ?? candidate.rel_type ?? "connection",
        sentiment: candidate.sentiment ?? null,
        description: candidate.reason_codes.includes("generated_relationship_requires_review") ? null : candidate.description ?? null,
        fromChapter: candidate.chapter_number,
        ...(proposal ? { labelEvidence: { quote: proposal.quote, source_start: proposal.sourceStart, source_end: proposal.sourceEnd } } : {}),
      })
      await refreshGraph()
      await refetchCharacterReview()
    } catch {
      setActionError("Could not turn this review item into a relationship.")
    } finally {
      setRelationshipCandidateActionId(null)
    }
  }

  async function handleResolveRelationshipCandidate(candidate: CharacterRelationshipCandidate) {
    setRelationshipCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.resolveRelationshipCandidate(bookId, candidate.id)
      await refetchCharacterReview()
    } catch {
      setActionError("Could not mark this relationship review item as resolved.")
    } finally {
      setRelationshipCandidateActionId(null)
    }
  }

  async function handleRejectRelationshipCandidate(candidate: CharacterRelationshipCandidate) {
    setRelationshipCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.rejectRelationshipCandidate(bookId, candidate.id)
      await refetchCharacterReview()
    } catch {
      setActionError("Could not reject this relationship review item.")
    } finally {
      setRelationshipCandidateActionId(null)
    }
  }

  return {
    candidateActionId,
    handleAcceptRelationshipCandidate,
    handleAttachCandidate,
    handleAttachRelationshipCandidate,
    handleMarkCandidatePlace,
    handlePromoteCandidate,
    handleRejectCandidate,
    handleRejectRelationshipCandidate,
    handleResolveRelationshipCandidate,
    relationshipCandidateActionId,
  }
}
