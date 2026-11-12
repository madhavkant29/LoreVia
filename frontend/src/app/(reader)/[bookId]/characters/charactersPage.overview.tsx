import type { Character } from "@/types/character"
import { SurfaceCard } from "./charactersPage.components"
import {
  bookCoverageLabel,
  chapterSpanCount,
  currentProfileClaims,
  formatRole,
  formatTraitLabel,
  groupAliasRecordsByKind,
  visibleTraitEntries,
} from "./charactersPage.helpers"

type CharacterOverviewIdentityCardsProps = {
  character: Character
  chapterAppearanceText: (chapter: number | null | undefined) => string
  evidenceCount: number
  growthEventCount: number
  isDark: boolean
  knownFacts: string[]
  reviewStatus: string
  summary: string
  totalChapters?: number | null
  onOpenEvidence: () => void
  onAcceptNarratorClaim?: (index: number) => void
  acceptingNarratorClaimIndex?: number | null
}

export function CharacterOverviewIdentityCards({
  character,
  chapterAppearanceText,
  evidenceCount,
  isDark,
  knownFacts,
  reviewStatus,
  summary,
  totalChapters,
  onOpenEvidence,
  onAcceptNarratorClaim,
  acceptingNarratorClaimIndex,
}: CharacterOverviewIdentityCardsProps) {
  const aliasGroups = groupAliasRecordsByKind(character)
  const traitEntries = visibleTraitEntries(character)
  const profileClaims = currentProfileClaims(character)
  const profileReview = character.analysis_metadata?.character_profile_review
  const narratorProposals = profileReview?.proposals ?? character.analysis_metadata?.narrator_profile_review?.proposals ?? []
  const confirmedNarrator = profileReview?.subject_mode === "confirmed_narrator" || character.analysis_metadata?.narrator_profile_review?.author_confirmed_identity === true

  return (
    <>
      <SurfaceCard title="Profile summary" isDark={isDark}>
        <p className={`text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          {summary || "LoreVia is still building a concise grounded profile from the manuscript."}
        </p>
        <div className={`mt-4 flex items-center justify-between border-y py-2 text-sm ${isDark ? "border-[#202a38] text-slate-300" : "border-stone-200 text-stone-600"}`}>
          <span>{evidenceCount ? `${evidenceCount} loaded passages` : "Open Evidence to search passages"}</span>
          <button type="button" onClick={onOpenEvidence} className={`text-xs font-semibold ${isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-700 hover:text-teal-900"}`}>
            View evidence
          </button>
        </div>
      </SurfaceCard>

      <SurfaceCard title="Identity" isDark={isDark}>
        <dl className="grid gap-4 text-sm">
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Role</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{formatRole(character.role)}</dd>
          </div>
          {character.analysis_metadata?.first_person_self_identification?.excerpt && (
            <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Narrator evidence</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>
                <span className="block text-xs">Possible first-person self-identification, {chapterAppearanceText(character.analysis_metadata.first_person_self_identification.chapter_number)}</span>
                <q className="mt-1 block text-sm">{character.analysis_metadata.first_person_self_identification.excerpt}</q>
              </dd>
            </div>
          )}
          {!character.analysis_metadata?.first_person_self_identification?.excerpt && character.analysis_metadata?.first_person_addressed_as?.excerpt && (
            <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Narrator clue</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>
                <span className="block text-xs">Addressed by name in {chapterAppearanceText(character.analysis_metadata.first_person_addressed_as.chapter_number)}. This alone does not confirm the first-person narrator.</span>
                <q className="mt-1 block text-sm">{character.analysis_metadata.first_person_addressed_as.excerpt}</q>
              </dd>
            </div>
          )}
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Aliases</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{character.aliases.length > 0 ? character.aliases.join(", ") : "None recorded"}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Alias records</dt>
            <dd className="space-y-2">
              {aliasGroups.length > 0 ? aliasGroups.map(([kind, aliases]) => (
                <div key={kind} className={`border-b pb-2 last:border-b-0 ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
                  <p className={`text-xs font-medium capitalize ${isDark ? "text-slate-400" : "text-stone-600"}`}>{kind.replaceAll("_", " ")}</p>
                  <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                    {aliases.map((alias) => `${alias.alias_text} (${Math.round((alias.confidence ?? 0) * 100)}%, ${alias.source})`).join(", ")}
                  </p>
                </div>
              )) : (
                <span className={isDark ? "text-slate-400" : "text-stone-600"}>No structured alias records yet.</span>
              )}
            </dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>First appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Last appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.last_seen_chapter ?? character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Chapter count</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterSpanCount(character)} / {bookCoverageLabel(character, totalChapters)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Status</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{reviewStatus}</dd>
          </div>
        </dl>
      </SurfaceCard>

      <SurfaceCard title="Traits and motivations" isDark={isDark}>
        <div className="space-y-4">
          <div>
            <p className={`text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>Traits</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
              {[
                ...traitEntries.flatMap(([key, trait]) => trait ? [`${formatTraitLabel(key)}: ${trait.value}`] : []),
                ...(character.personality_tags ?? []),
              ].join(", ") || "Traits not recorded"}
            </p>
          </div>
          <div>
            <p className={`text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>Motivations</p>
            {(character.motivations?.length ?? 0) > 0 ? (
              <ul className={`mt-2 space-y-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
                {character.motivations.map((motivation) => <li key={motivation}>- {motivation}</li>)}
              </ul>
            ) : (
              <p className={isDark ? "mt-2 text-sm text-slate-400" : "mt-2 text-sm text-stone-600"}>Motivations not recorded</p>
            )}
          </div>
        </div>
      </SurfaceCard>

      <SurfaceCard title="Known facts" isDark={isDark}>
        {knownFacts.length > 0 ? (
          <ul className={`space-y-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
            {knownFacts.map((fact) => <li key={fact}>- {fact}</li>)}
          </ul>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>Durable facts not recorded</p>
        )}
      </SurfaceCard>

      <SurfaceCard title="Source-backed profile claims" isDark={isDark}>
        {profileClaims.length > 0 ? (
          <div className="space-y-3">
            <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
              Quotes are present in the manuscript; check that each interpretation fits its context.
            </p>
            {profileClaims.slice(0, 12).map((claim, index) => (
              <div key={`${claim.field}-${claim.value}-${claim.chapter_number}-${index}`} className={`border-l-2 pl-3 text-sm ${isDark ? "border-teal-600" : "border-teal-500"}`}>
                <p className={isDark ? "text-slate-200" : "text-stone-800"}>
                  {formatTraitLabel(claim.field.replace("trait:", ""))}: {claim.value}
                  {claim.chapter_number ? ` · Chapter ${claim.chapter_number}` : ""}
                </p>
                <blockquote className={`mt-1 italic ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                  “{claim.quote}”
                </blockquote>
              </div>
            ))}
            {profileClaims.length > 12 && <p className="text-xs">{profileClaims.length - 12} more source-backed claims</p>}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>
            No current profile claims have traceable source quotes yet. Existing profile text may need review.
          </p>
        )}
      </SurfaceCard>

      {narratorProposals.some((proposal) => proposal.status !== "accepted") && (
        <SurfaceCard title={confirmedNarrator ? "Narrator profile suggestions" : "Character profile suggestions"} isDark={isDark}>
          <p className={`mb-3 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
            {confirmedNarrator ? "First-person identity was confirmed by the author. " : ""}These AI interpretations have source quotes; review each before adding it to the profile.
          </p>
          <div className="space-y-3">
            {narratorProposals.map((proposal, index) => proposal.status === "accepted" ? null : (
              <div key={`${proposal.field}-${proposal.value}-${index}`} className={`border-l-2 pl-3 text-sm ${isDark ? "border-amber-700" : "border-amber-500"}`}>
                <p className={isDark ? "text-slate-200" : "text-stone-800"}>{formatTraitLabel(proposal.field.replace("trait:", ""))}: {proposal.value} · Chapter {proposal.chapter_number}</p>
                <blockquote className={`mt-1 italic ${isDark ? "text-slate-400" : "text-stone-600"}`}>“{proposal.quote}”</blockquote>
                {onAcceptNarratorClaim && (
                  <button type="button" disabled={acceptingNarratorClaimIndex !== null && acceptingNarratorClaimIndex !== undefined} onClick={() => onAcceptNarratorClaim(index)} className={`mt-2 text-xs font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>
                    {acceptingNarratorClaimIndex === index ? "Adding..." : "Accept claim"}
                  </button>
                )}
              </div>
            ))}
          </div>
        </SurfaceCard>
      )}

      <SurfaceCard title="Notes and audit" isDark={isDark}>
        <div className="space-y-4 text-sm">
          <div>
            <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Notes</p>
            <p className={`mt-1 leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              {character.analysis_metadata?.review_note || character.relationship_summaries?.[0] || "Reviewer note not recorded"}
            </p>
          </div>
          <dl className="grid gap-3 sm:grid-cols-3">
            <div>
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Created</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{character.created_at ? new Date(character.created_at).toLocaleDateString() : "Not recorded"}</dd>
            </div>
            <div>
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Last updated</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{character.approval_updated_at ? new Date(character.approval_updated_at).toLocaleDateString() : "Not tracked"}</dd>
            </div>
            <div>
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Status</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{reviewStatus}</dd>
            </div>
          </dl>
        </div>
      </SurfaceCard>
    </>
  )
}
