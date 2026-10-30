import type { ConnectedRelationship } from "@/components/reader/CharacterProfileRightRail"
import type { Character, CharacterRelationshipCandidate } from "@/types/character"
import type { SearchResult } from "@/types/reader"
import { characterMentionCountLabel } from "./charactersPage.mentionLabels"
import { actionButtonClasses, QuickActionTile, SurfaceCard } from "./charactersPage.components"
import {
  characterInitial,
  flagClasses,
  formatChapterRange,
  formatPercent,
  formatRelationshipType,
  formatRole,
  formatStatus,
  isCuratedCharacter,
  isProtectedCharacter,
  qualityFlags,
  type MergeSuggestion,
} from "./charactersPage.helpers"

type CharacterDuplicateWorkspaceProps = {
  connectionsByCharacter: Map<string, ConnectedRelationship[]>
  isDark: boolean
  isManualMerge: boolean
  mergeBusy: boolean
  mergeSuggestionIds: Set<string>
  mergeableCharacters: Character[]
  primaryCharacter: Character | null
  primaryEvidence: SearchResult[]
  relationshipCounts: Map<string, number>
  secondaryCharacter: Character | null
  secondaryEvidence: SearchResult[]
  selectedMergeSuggestion: MergeSuggestion | undefined
  onClearManualMerge: () => void
  onCompareEvidence: (primaryCharacterId: string) => void
  onDismissSuggestion: (suggestion: MergeSuggestion) => void
  onMergeCharacters: (primaryId: string, secondaryId: string, suggestionId?: string) => void
  onSetManualPrimary: (characterId: string) => void
  onSetManualSecondary: (characterId: string) => void
  onStartManualMerge: (primaryId?: string, secondaryId?: string) => void
}

export function CharacterDuplicateWorkspace({
  connectionsByCharacter,
  isDark,
  isManualMerge,
  mergeBusy,
  mergeSuggestionIds,
  mergeableCharacters,
  primaryCharacter,
  primaryEvidence,
  relationshipCounts,
  secondaryCharacter,
  secondaryEvidence,
  selectedMergeSuggestion,
  onClearManualMerge,
  onCompareEvidence,
  onDismissSuggestion,
  onMergeCharacters,
  onSetManualPrimary,
  onSetManualSecondary,
  onStartManualMerge,
}: CharacterDuplicateWorkspaceProps) {
  if (!primaryCharacter || !secondaryCharacter) {
    return (
      <div className="p-5">
        <div className="space-y-4">
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No duplicate suggestion is selected right now. Start with a manual pair and compare any two character records directly.</p>
          {mergeableCharacters.length >= 2 ? (
            <button
              type="button"
              onClick={() => onStartManualMerge()}
              className="rounded-md bg-violet-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-600"
            >
              Start manual merge
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  const protectedOrCurated =
    isProtectedCharacter(primaryCharacter) ||
    isProtectedCharacter(secondaryCharacter) ||
    isCuratedCharacter(primaryCharacter) ||
    isCuratedCharacter(secondaryCharacter)

  return (
    <div className="p-5">
      <div className="space-y-5">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-violet-300" : "text-violet-600"}`}>Duplicate review</p>
          <h2 className={`mt-2 text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{isManualMerge ? "Manual merge" : "Merge suggestion"}</h2>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>
            Compare evidence before merging duplicate character records.
          </p>
          {protectedOrCurated ? (
            <div className={`mt-3 rounded-sm border px-3 py-2 text-xs ${isDark ? "border-amber-500/25 bg-amber-500/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              One of these records is protected or curated. Auto-cleanup will skip it, so merge carefully and only if the evidence is strong.
            </div>
          ) : null}
        </div>

        <SurfaceCard title="Manual pair" isDark={isDark}>
          <div className="grid gap-3 xl:grid-cols-2">
            <label className="text-sm">
              <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Primary record</span>
              <select
                value={primaryCharacter.id}
                onChange={(event) => {
                  const nextPrimaryId = event.target.value
                  onSetManualPrimary(nextPrimaryId)
                  if (nextPrimaryId === secondaryCharacter.id) {
                    const fallbackSecondary = mergeableCharacters.find((character) => character.id !== nextPrimaryId)?.id ?? ""
                    onSetManualSecondary(fallbackSecondary)
                  }
                }}
                className={`mt-2 w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-[#202a38] bg-[#0b1220] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              >
                {mergeableCharacters.map((character) => (
                  <option key={`manual-primary-${character.id}`} value={character.id}>{character.name}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Merge into primary</span>
              <select
                value={secondaryCharacter.id}
                onChange={(event) => onSetManualSecondary(event.target.value)}
                className={`mt-2 w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-[#202a38] bg-[#0b1220] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              >
                {mergeableCharacters.filter((character) => character.id !== primaryCharacter.id).map((character) => (
                  <option key={`manual-secondary-${character.id}`} value={character.id}>{character.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => onStartManualMerge(primaryCharacter.id, secondaryCharacter.id)} className={actionButtonClasses(isDark)}>
              Start manual merge
            </button>
            <button type="button" onClick={onClearManualMerge} className={actionButtonClasses(isDark)}>
              Return to suggestions
            </button>
          </div>
        </SurfaceCard>

        <div className="grid gap-4 xl:grid-cols-2">
          {[primaryCharacter, secondaryCharacter].map((character, index) => {
            const evidence = index === 0 ? primaryEvidence : secondaryEvidence
            const connections = connectionsByCharacter.get(character.id) ?? []
            const flags = qualityFlags(character, mergeSuggestionIds, connections)
            return (
              <SurfaceCard key={character.id} title={index === 0 ? "Primary" : "Candidate"} isDark={isDark}>
                <div className="flex items-start gap-3">
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-sm text-sm font-semibold ${isDark ? "bg-violet-500/18 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                    {characterInitial(character.name)}
                  </div>
                  <div className="min-w-0">
                    <h3 className={`text-xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{character.name}</h3>
                    <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                      {formatRole(character.role)} / {formatStatus(character.status)} / {formatChapterRange(character.first_chapter, character.last_seen_chapter ?? null)}
                    </p>
                  </div>
                </div>

                {flags.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {flags.map((flag) => (
                      <span key={flag} className={`rounded-sm px-2.5 py-1 text-xs font-medium ${flagClasses(isDark, flag)}`}>
                        {flag}
                      </span>
                    ))}
                  </div>
                ) : null}

                <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  {character.description || "No concise profile summary is stored yet."}
                </p>

                <div className="mt-4">
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Aliases</p>
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{character.aliases.length > 0 ? character.aliases.join(", ") : "No aliases recorded"}</p>
                </div>

                <div className="mt-4">
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Traits</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {character.personality_tags.length > 0 ? character.personality_tags.slice(0, 6).map((tag) => (
                      <span key={tag} className={`rounded-sm px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>
                        {tag}
                      </span>
                    )) : <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No trait tags yet.</span>}
                  </div>
                </div>

                <div className="mt-4">
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Evidence</p>
                  <div className="mt-2 space-y-2">
                    {evidence.slice(0, 2).map((result, evidenceIndex) => (
                      <div key={`${character.id}-evidence-compare-${evidenceIndex}`} className={`rounded-sm border px-3 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                        <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Chapter {result.chapter_num}</p>
                        <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                      </div>
                    ))}
                    {evidence.length === 0 ? (
                      <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No evidence preview loaded yet.</p>
                    ) : null}
                  </div>
                </div>
              </SurfaceCard>
            )
          })}
        </div>

        <SurfaceCard title="Differences" isDark={isDark}>
          <div className="grid gap-3 md:grid-cols-2">
            <div className={`rounded-sm border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Primary record</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{primaryCharacter.name} / {characterMentionCountLabel(primaryCharacter)} / {relationshipCounts.get(primaryCharacter.id) ?? 0} ties</p>
            </div>
            <div className={`rounded-sm border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Candidate record</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{secondaryCharacter.name} / {characterMentionCountLabel(secondaryCharacter)} / {relationshipCounts.get(secondaryCharacter.id) ?? 0} ties</p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={() => onCompareEvidence(primaryCharacter.id)} className={actionButtonClasses(isDark)}>
              Compare evidence
            </button>
            <button
              type="button"
              onClick={() => onMergeCharacters(primaryCharacter.id, secondaryCharacter.id, selectedMergeSuggestion?.suggestionId)}
              disabled={mergeBusy}
              className="rounded-md bg-violet-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-600 disabled:opacity-60"
            >
              {mergeBusy ? "Merging..." : "Merge"}
            </button>
            {selectedMergeSuggestion && !isManualMerge ? (
              <>
                <button type="button" onClick={() => onDismissSuggestion(selectedMergeSuggestion)} className={actionButtonClasses(isDark)}>
                  Keep separate
                </button>
                <button type="button" onClick={() => onDismissSuggestion(selectedMergeSuggestion)} className={actionButtonClasses(isDark)}>
                  Dismiss
                </button>
              </>
            ) : null}
          </div>
        </SurfaceCard>
      </div>
    </div>
  )
}

type CharacterDuplicateSideRailProps = {
  characterCount: number
  isDark: boolean
  isManualMerge: boolean
  mergeBusy: boolean
  primaryCharacter: Character | null
  relationshipCandidates: CharacterRelationshipCandidate[]
  secondaryCharacter: Character | null
  selectedMergeSuggestion: MergeSuggestion | undefined
  onClearManualMerge: () => void
  onCompareEvidence: (primaryCharacterId: string) => void
  onDismissSuggestion: (suggestion: MergeSuggestion) => void
  onMergeCharacters: (primaryId: string, secondaryId: string, suggestionId?: string) => void
  onStartManualMerge: () => void
}

export function CharacterDuplicateSideRail({
  characterCount,
  isDark,
  isManualMerge,
  mergeBusy,
  primaryCharacter,
  relationshipCandidates,
  secondaryCharacter,
  selectedMergeSuggestion,
  onClearManualMerge,
  onCompareEvidence,
  onDismissSuggestion,
  onMergeCharacters,
  onStartManualMerge,
}: CharacterDuplicateSideRailProps) {
  return (
    <div className="p-4">
      {primaryCharacter && secondaryCharacter ? (
        <div className="space-y-4">
          <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
            <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>{isManualMerge ? "Manual merge" : "Merge suggestion"}</p>
            <p className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{selectedMergeSuggestion && !isManualMerge ? `${selectedMergeSuggestion.confidence}%` : "Manual review"}</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedMergeSuggestion && !isManualMerge ? "Confidence based on name overlap, alias collisions, and shared chapter context." : "Use this when a family-role alias or late rename was missed by automatic duplicate suggestions."}</p>
            {selectedMergeSuggestion && !isManualMerge ? (
              <div className="mt-4 space-y-2">
                {selectedMergeSuggestion.reasons.map((reason) => (
                  <div key={reason} className={`rounded-sm border px-3 py-2.5 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                    {reason}
                  </div>
                ))}
                {selectedMergeSuggestion.sharedClusterKeys.length > 0 ? (
                  <div className={`rounded-sm border px-3 py-2.5 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                    Shared clusters: {selectedMergeSuggestion.sharedClusterKeys.join(", ")}
                  </div>
                ) : null}
                {selectedMergeSuggestion.sharedChapters.length > 0 ? (
                  <div className={`rounded-sm border px-3 py-2.5 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                    Shared chapters: {selectedMergeSuggestion.sharedChapters.join(", ")}
                  </div>
                ) : null}
                {typeof selectedMergeSuggestion.embeddingSimilarity === "number" ? (
                  <div className={`rounded-sm border px-3 py-2.5 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                    Embedding similarity: {formatPercent(selectedMergeSuggestion.embeddingSimilarity)}
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
            <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Quick actions</p>
            <div className="mt-4 space-y-3">
              <QuickActionTile
                isDark={isDark}
                title="Compare evidence"
                description={`Open ${primaryCharacter.name}'s evidence tab.`}
                onClick={() => onCompareEvidence(primaryCharacter.id)}
              />
              <QuickActionTile
                isDark={isDark}
                title={mergeBusy ? "Merging..." : "Merge records"}
                description={`${secondaryCharacter.name} will merge into ${primaryCharacter.name}.`}
                onClick={() => onMergeCharacters(primaryCharacter.id, secondaryCharacter.id, selectedMergeSuggestion?.suggestionId)}
              />
              <QuickActionTile
                isDark={isDark}
                title="Keep separate"
                description="Dismiss this suggestion and leave both records untouched."
                onClick={() => {
                  if (selectedMergeSuggestion && !isManualMerge) {
                    onDismissSuggestion(selectedMergeSuggestion)
                    return
                  }
                  onClearManualMerge()
                }}
              />
            </div>
          </section>

          <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
            <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Relationship queue</p>
            {relationshipCandidates.length > 0 ? (
              <div className="mt-4 space-y-3">
                {relationshipCandidates.slice(0, 4).map((candidate) => (
                  <div key={`duplicate-review-${candidate.id}`} className={`rounded-sm border px-3 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{candidate.raw_character_a} and {candidate.raw_character_b}</p>
                    <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                      Chapter {candidate.chapter_number}{candidate.rel_type ? ` · ${formatRelationshipType(candidate.rel_type)}` : ""}
                    </p>
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                      {candidate.description || candidate.reason_codes[0] || "Needs relationship review."}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                No unresolved relationship candidates match the current filters.
              </p>
            )}
          </section>
        </div>
      ) : (
        <div className="space-y-4">
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>Choose a suggestion or start a manual merge to compare records the detector did not catch yet.</p>
          {characterCount >= 2 ? (
            <button
              type="button"
              onClick={onStartManualMerge}
              className="w-full rounded-md bg-violet-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-600"
            >
              Begin manual merge
            </button>
          ) : null}
        </div>
      )}
    </div>
  )
}
