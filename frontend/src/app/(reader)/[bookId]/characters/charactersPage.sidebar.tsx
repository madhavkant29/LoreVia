import { candidateAdjudicationBadges } from "@/lib/utils/characterAdjudication"
import type { Character, CharacterCandidate, CharacterRelationshipCandidate } from "@/types/character"
import {
  actionButtonClasses,
} from "./charactersPage.components"
import {
  characterInitial,
  chapterSpanCount,
  formatRelationshipType,
  formatRole,
  reviewStatusLabel,
  type MergeSuggestion,
} from "./charactersPage.helpers"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type CharactersSidebarBodyProps = {
  candidateActionId: string | null
  charById: Map<string, Character>
  charsCount: number
  filteredChars: Character[]
  filteredMergeSuggestions: MergeSuggestion[]
  filteredPendingCandidates: CharacterCandidate[]
  filteredRelationshipCandidates: CharacterRelationshipCandidate[]
  flagsByCharacter: Map<string, string[]>
  isAuthorMode: boolean
  isDark: boolean
  relationshipCandidateActionId: string | null
  relationshipCounts: Map<string, number>
  selectedCharacter: Character | null
  selectedMergeSuggestion: MergeSuggestion | undefined
  showAllCast: boolean
  visibleCastChars: Character[]
  workspaceMode: WorkspaceMode
  onAcceptRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => void
  onAttachCandidate: (candidate: CharacterCandidate) => void
  onAttachRelationshipCandidate: (candidate: CharacterRelationshipCandidate, side: "a" | "b") => void
  onMarkCandidatePlace: (candidate: CharacterCandidate) => void
  onOpenCreateCharacter: () => void
  onPromoteCandidate: (candidate: CharacterCandidate) => void
  onRejectCandidate: (candidate: CharacterCandidate) => void
  onRejectRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => void
  onResolveRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => void
  onSelectCharacter: (characterId: string) => void
  onSelectMergeSuggestion: (suggestionKey: string) => void
  onShowAllCastChange: (value: boolean | ((current: boolean) => boolean)) => void
}

export function CharactersSidebarBody({
  candidateActionId,
  charById,
  charsCount,
  filteredChars,
  filteredMergeSuggestions,
  filteredPendingCandidates,
  filteredRelationshipCandidates,
  flagsByCharacter,
  isAuthorMode,
  isDark,
  relationshipCandidateActionId,
  relationshipCounts,
  selectedCharacter,
  selectedMergeSuggestion,
  showAllCast,
  visibleCastChars,
  workspaceMode,
  onAcceptRelationshipCandidate,
  onAttachCandidate,
  onAttachRelationshipCandidate,
  onMarkCandidatePlace,
  onOpenCreateCharacter,
  onPromoteCandidate,
  onRejectCandidate,
  onRejectRelationshipCandidate,
  onResolveRelationshipCandidate,
  onSelectCharacter,
  onSelectMergeSuggestion,
  onShowAllCastChange,
}: CharactersSidebarBodyProps) {
  if (workspaceMode === "profile") {
    return (
      <div className="px-3 py-2">
        <p className={`px-3 pb-2 pt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{filteredChars.length} characters</p>
        {visibleCastChars.map((char) => {
          const isActive = selectedCharacter?.id === char.id
          const flags = flagsByCharacter.get(char.id) ?? []
          const statusLabel = reviewStatusLabel(char, flags)
          const statusTone = statusLabel === "Reviewed" ? "teal" : statusLabel === "Flagged" ? "amber" : "rose"
          return (
            <button
              key={char.id}
              type="button"
              aria-pressed={isActive}
              onClick={() => onSelectCharacter(char.id)}
              style={{ contentVisibility: "auto", containIntrinsicSize: "62px" }}
              className={`w-full px-3 py-2.5 text-left transition-colors ${isActive
                ? isDark ? "border-l-2 border-violet-300 bg-violet-500/10" : "border-l-2 border-violet-700 bg-violet-50"
                : isDark ? "border-b border-[#17202c] hover:bg-white/[0.03]" : "border-b border-stone-200 hover:bg-stone-50/80"
              }`}
            >
              <div className="flex items-start gap-2.5">
                <div className={`flex h-7 w-7 shrink-0 items-center justify-center text-xs font-semibold ${isActive
                  ? isDark ? "text-violet-100" : "text-violet-700"
                  : isDark ? "text-slate-400" : "text-stone-600"
                }`}>
                  {characterInitial(char.name)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className={`break-words text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{char.name}</p>
                        {char.is_manual ? (
                          <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                            Manual
                          </span>
                        ) : null}
                      </div>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{formatRole(char.role)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${statusTone === "teal"
                        ? isDark ? "text-teal-200" : "text-teal-700"
                        : statusTone === "amber"
                          ? isDark ? "text-amber-200" : "text-amber-700"
                          : isDark ? "text-rose-200" : "text-rose-700"
                      }`}>
                        <span aria-hidden="true">•</span>
                        {statusLabel}
                      </span>
                    </div>
                  </div>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                    {chapterSpanCount(char)} {chapterSpanCount(char) === 1 ? "chapter" : "chapters"} / {relationshipCounts.get(char.id) ?? 0} ties
                  </p>
                </div>
              </div>
            </button>
          )
        })}

        {filteredChars.length === 0 ? (
          <div className="px-3 py-6">
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>
              {charsCount === 0 ? "No characters yet. Add one manually to start the bible." : "No characters match the current filters."}
            </p>
            {charsCount === 0 && isAuthorMode ? (
              <button
                type="button"
                onClick={onOpenCreateCharacter}
                className="mt-3 rounded-sm bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white"
              >
                Add character
              </button>
            ) : null}
          </div>
        ) : null}
        {filteredChars.length > 8 ? (
          <div className="px-3 py-4 text-center">
            <button
              type="button"
              onClick={() => onShowAllCastChange((current) => !current)}
              className={`text-sm font-medium ${isDark ? "text-slate-400 hover:text-white" : "text-stone-600 hover:text-stone-950"}`}
            >
              {showAllCast ? "Show less" : "Show more"}
            </button>
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="px-3 py-2">
      {workspaceMode === "duplicates" ? filteredMergeSuggestions.map((suggestion) => {
        const primary = charById.get(suggestion.primaryId)
        const secondary = charById.get(suggestion.secondaryId)
        const active = selectedMergeSuggestion?.key === suggestion.key
        if (!primary || !secondary) return null
        return (
          <button
            key={suggestion.key}
            type="button"
            onClick={() => onSelectMergeSuggestion(suggestion.key)}
            style={{ contentVisibility: "auto", containIntrinsicSize: "82px" }}
            className={`w-full rounded-md border px-3 py-3 text-left transition ${active
              ? isDark ? "border-violet-400/40 bg-violet-500/12" : "border-violet-300 bg-violet-50"
              : isDark ? "border-[#17202c] bg-white/[0.02] hover:bg-white/[0.04]" : "border-stone-200 bg-white hover:bg-stone-50"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className={`break-words text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{primary.name}</p>
                <p className={`mt-1 break-words text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Possible duplicate: {secondary.name}</p>
                <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{suggestion.reasons[0]}</p>
              </div>
              <span className={`rounded-sm px-2 py-1 text-xs font-semibold ${isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"}`}>
                {suggestion.confidence}%
              </span>
            </div>
          </button>
        )
      }) : null}

      {workspaceMode === "duplicates" && filteredMergeSuggestions.length === 0 ? (
        <div className="px-3 py-6">
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No duplicate suggestions match the current search. Use the manual merge tools in the main panel to compare any two records directly.</p>
        </div>
      ) : null}

      {workspaceMode === "review" ? (
        <div className="px-3 py-6">
          <div className={`rounded-md border px-4 py-5 ${isDark ? "border-[#17202c] bg-white/[0.02]" : "border-stone-200 bg-white"}`}>
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>Duplicate comparison stays in the dedicated review workspace. Focus this queue on held candidates, resolver reasons, and promotion blockers.</p>
          </div>
        </div>
      ) : null}

      {workspaceMode === "repair" ? (
        <div className="px-3 py-6">
          <div className={`rounded-md border px-4 py-5 ${isDark ? "border-[#17202c] bg-white/[0.02]" : "border-stone-200 bg-white"}`}>
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>Repair preview lists safe merges, obvious-noise demotions, and protected skips in the main workspace. Search here to narrow the queue before reprocessing.</p>
          </div>
        </div>
      ) : null}

      {filteredPendingCandidates.length > 0 ? (
        <div className={`mt-5 border-t px-3 pt-4 ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Quarantine queue</p>
          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{filteredPendingCandidates.length} candidates waiting for review</p>
          <div className="mt-3 space-y-3">
            {filteredPendingCandidates.slice(0, 8).map((candidate) => (
              <div key={candidate.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-[#17202c] bg-white/[0.02]" : "border-stone-200 bg-white"}`}>
                <p className={`break-words text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{candidate.proposed_name}</p>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Chapter {candidate.chapter_number} · {candidate.confidence}%</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {candidateAdjudicationBadges(candidate).slice(0, 3).map((badge) => (
                    <span key={`${candidate.id}-${badge}`} className={`rounded-sm px-2 py-1 text-[0.68rem] font-semibold ${isDark ? "bg-amber-400/12 text-amber-100" : "bg-amber-50 text-amber-700"}`}>
                      {badge}
                    </span>
                  ))}
                </div>
                <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{candidate.reason_codes[0] ?? "Needs review"}</p>
                {workspaceMode !== "repair" ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={candidateActionId === candidate.id || candidate.status !== "pending"}
                      onClick={() => onPromoteCandidate(candidate)}
                      className={actionButtonClasses(isDark)}
                    >
                      {candidateActionId === candidate.id ? "Working..." : "Promote"}
                    </button>
                    <button
                      type="button"
                      disabled={candidateActionId === candidate.id || candidate.status !== "pending" || !selectedCharacter}
                      onClick={() => onAttachCandidate(candidate)}
                      className={actionButtonClasses(isDark)}
                    >
                      Attach to selected
                    </button>
                    <button
                      type="button"
                      disabled={candidateActionId === candidate.id}
                      onClick={() => onMarkCandidatePlace(candidate)}
                      className={actionButtonClasses(isDark)}
                    >
                      Mark as place
                    </button>
                    <button
                      type="button"
                      disabled={candidateActionId === candidate.id}
                      onClick={() => onRejectCandidate(candidate)}
                      className={actionButtonClasses(isDark)}
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {(workspaceMode === "review" || workspaceMode === "duplicates") && filteredRelationshipCandidates.length > 0 ? (
        <div className={`mt-5 border-t px-3 pt-4 ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Relationship review</p>
          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{filteredRelationshipCandidates.length} unresolved relationships waiting for review</p>
          <div className="mt-3 space-y-3">
            {filteredRelationshipCandidates.slice(0, 8).map((candidate) => (
              <div key={candidate.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-[#17202c] bg-white/[0.02]" : "border-stone-200 bg-white"}`}>
                <p className={`break-words text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{candidate.raw_character_a} {"<->"} {candidate.raw_character_b}</p>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Chapter {candidate.chapter_number}{candidate.rel_type ? ` · ${formatRelationshipType(candidate.rel_type)}` : ""}</p>
                <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{candidate.reason_codes[0] ?? "Needs relationship review"}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={relationshipCandidateActionId === candidate.id || !selectedCharacter}
                    onClick={() => onAttachRelationshipCandidate(candidate, "a")}
                    className={actionButtonClasses(isDark)}
                  >
                    Attach A to selected
                  </button>
                  <button
                    type="button"
                    disabled={relationshipCandidateActionId === candidate.id || !selectedCharacter}
                    onClick={() => onAttachRelationshipCandidate(candidate, "b")}
                    className={actionButtonClasses(isDark)}
                  >
                    Attach B to selected
                  </button>
                  <button
                    type="button"
                    disabled={relationshipCandidateActionId === candidate.id}
                    onClick={() => onAcceptRelationshipCandidate(candidate)}
                    className={actionButtonClasses(isDark)}
                  >
                    {relationshipCandidateActionId === candidate.id ? "Working..." : "Create relationship"}
                  </button>
                  <button
                    type="button"
                    disabled={relationshipCandidateActionId === candidate.id}
                    onClick={() => onResolveRelationshipCandidate(candidate)}
                    className={actionButtonClasses(isDark)}
                  >
                    Mark resolved
                  </button>
                  <button
                    type="button"
                    disabled={relationshipCandidateActionId === candidate.id}
                    onClick={() => onRejectRelationshipCandidate(candidate)}
                    className={actionButtonClasses(isDark)}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
