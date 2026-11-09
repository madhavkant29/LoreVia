import type { Character } from "@/types/character"
import type { SearchResult } from "@/types/reader"
import {
  actionButtonClasses,
  SurfaceCard,
} from "./charactersPage.components"
import {
  bookCoverageLabel,
  chapterSpanCount,
} from "./charactersPage.helpers"
import { characterMentionCountKind } from "./charactersPage.mentionLabels"

type CharacterMentionsTabProps = {
  character: Character
  chapterAppearanceText: (chapter: number | null | undefined) => string
  evidence: SearchResult[]
  isDark: boolean
  openQuestions: string[]
  totalChapters?: number | null
  onOpenEvidence: () => void
}

export function CharacterMentionsTab({
  character,
  chapterAppearanceText,
  evidence,
  isDark,
  openQuestions,
  totalChapters,
  onOpenEvidence,
}: CharacterMentionsTabProps) {
  return (
    <div className="mt-5 grid gap-4 xl:grid-cols-2">
      <SurfaceCard title="Mention summary" isDark={isDark}>
        <dl className="grid gap-3 text-sm">
          <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>{characterMentionCountKind(character)}</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{character.mention_count ?? 0}</dd>
          </div>
          <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>First appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Last appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.last_seen_chapter ?? character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Chapter count</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterSpanCount(character)} / {bookCoverageLabel(character, totalChapters)}</dd>
          </div>
        </dl>
        <p className={`mt-3 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
          {character.analysis_metadata?.mention_count_basis === "source_positions"
            ? "Counts explicit names and supported aliases in the manuscript, not pronouns or unnamed references."
            : "This older count is an estimate. Reprocess the stored manuscript to calculate source-backed named mentions."}
        </p>
      </SurfaceCard>

      <SurfaceCard title="Open questions" isDark={isDark}>
        {openQuestions.length > 0 ? (
          <ul className={`space-y-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
            {openQuestions.map((question) => <li key={question}>- {question}</li>)}
          </ul>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No open questions are currently derived for this character.</p>
        )}
      </SurfaceCard>

      <SurfaceCard title="Mention evidence" isDark={isDark} className="xl:col-span-2">
        {evidence.length > 0 ? (
          <div className="space-y-3">
            {evidence.map((result, index) => (
              <div key={`${character.id}-mention-${index}`} className={`rounded-sm border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Chapter {result.chapter_num}{result.chapter_title ? ` / ${result.chapter_title}` : ""}</p>
                <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No evidence snippets are loaded yet.</p>
            <button type="button" onClick={onOpenEvidence} className={actionButtonClasses(isDark)}>Load mention evidence</button>
          </div>
        )}
      </SurfaceCard>
    </div>
  )
}
