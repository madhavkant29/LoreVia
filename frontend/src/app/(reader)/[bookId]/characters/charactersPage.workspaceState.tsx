type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type BuildSidebarSummaryArgs = {
  filteredCharCount: number
  filteredMergeSuggestionCount: number
  filteredPendingCandidateCount: number
  filteredRelationshipCandidateCount: number
  isManualMerge: boolean
  plannedDemotionCount: number
  plannedMergeCount: number
  workspaceMode: WorkspaceMode
}

export function buildSidebarSummary({
  filteredCharCount,
  filteredMergeSuggestionCount,
  filteredPendingCandidateCount,
  filteredRelationshipCandidateCount,
  isManualMerge,
  plannedDemotionCount,
  plannedMergeCount,
  workspaceMode,
}: BuildSidebarSummaryArgs) {
  if (workspaceMode === "duplicates") {
    return `${filteredMergeSuggestionCount} suggestions${isManualMerge ? " / manual pair selected" : ""}`
  }
  if (workspaceMode === "review") {
    return `${filteredPendingCandidateCount} candidate items / ${filteredRelationshipCandidateCount} relationship items`
  }
  if (workspaceMode === "repair") {
    return `${plannedMergeCount} planned merges / ${plannedDemotionCount} planned demotions`
  }
  return `${filteredCharCount} characters`
}

type CharacterWorkspaceEmptyStateProps = {
  bookStatus?: string | null
  hasPendingReviewItems: boolean
  isAuthorMode: boolean
  isDark: boolean
  pendingReviewItemCount: number
  onOpenCreateCharacter: () => void
  onOpenReviewQueue: () => void
}

export function CharacterWorkspaceEmptyState({
  bookStatus,
  hasPendingReviewItems,
  isAuthorMode,
  isDark,
  pendingReviewItemCount,
  onOpenCreateCharacter,
  onOpenReviewQueue,
}: CharacterWorkspaceEmptyStateProps) {
  return (
    <div className={`mt-5 rounded-lg border p-6 text-sm ${isDark ? "border-[#202a38] bg-black/20 text-slate-300" : "border-stone-200 bg-white/85 text-stone-600"}`}>
      <p>
        {hasPendingReviewItems
          ? `LoreVia held ${pendingReviewItemCount} extracted ${pendingReviewItemCount === 1 ? "item" : "items"} for review instead of adding them automatically.`
          : bookStatus === "processing"
            ? "No character profiles are ready yet. Processing continues in the background after upload."
            : "No character profiles were saved from this manuscript."}
      </p>
      {isAuthorMode ? (
        <div className="mt-4 flex flex-wrap gap-3">
          {hasPendingReviewItems ? (
            <button
              type="button"
              onClick={onOpenReviewQueue}
              className="rounded-md bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25756f]"
            >
              Review held candidates
            </button>
          ) : null}
          <button
            type="button"
            onClick={onOpenCreateCharacter}
            className="rounded-md bg-violet-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-600"
          >
            Add character manually
          </button>
        </div>
      ) : null}
    </div>
  )
}
