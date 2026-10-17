"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { useVoiceWorkspace } from "./voicePage.state"

export default function VoiceConsistencyPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <VoiceWorkspace key={bookId} bookId={bookId} />
}

function VoiceWorkspace({ bookId }: { bookId: string }) {
  const workspace = useVoiceWorkspace(bookId)
  const { bookQuery, chaptersQuery, charactersQuery, chapterQuery, selectedChapter, selectChapter, selectedCharacterId, setSelectedCharacterId, selectedCharacter, characters,
    text, setText, chapterTitle, chapterAvailable, draft, resetDraft, result, contextChanged, overLimit, canReview, runReview, reviewLoading, reviewError, saving, saveStatus, saveError, save } = workspace
  const book = bookQuery.data
  const chapterOptions = chaptersQuery.data?.chapters ?? []
  const review = result?.review
  const voiceCharacters = result?.characters_reviewed ?? []
  const voiceMatches = result?.character_matches ?? []
  const reviewWarnings = result?.warnings ?? []
  return (
    <WorkspacePage><div data-voice-workspace>
      <div className="mx-auto max-w-7xl px-0 pb-20 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="voice"
          bookId={bookId}
          family="review-center"
          title={`${book?.title || "Book"} voice consistency`}
          description="Review one chapter or passage against established character voices, then save only the evidence you need."
          actions={<><Link href={`/${bookId}/manuscript`} className="app-button-secondary">Open manuscript</Link><button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))}>Help</button></>}
        />

        {bookQuery.isLoading ? <p className="mt-5" role="status">Loading book context…</p> : bookQuery.isError || !book ? <div className="mt-5 border-l-2 border-[rgb(var(--border))] pl-4" role="alert"><p>Book context could not be loaded. Your passage stays here; reviewing is unavailable until it loads.</p><button type="button" className="app-button-secondary mt-2" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry book context</button></div> : null}

        <section className="mt-6 border-y border-[rgb(var(--border))]">
          <div className="grid border-b border-[rgb(var(--border))] md:grid-cols-2 md:divide-x md:divide-[rgb(var(--border))]">
            <div className="min-w-0 p-5 text-sm">
              <label htmlFor="voice-chapter" className="font-semibold">Chapter or passage</label>
              <select id="voice-chapter" value={selectedChapter ?? ""} onChange={(event) => selectChapter(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full">
                <option value="">Paste custom passage</option>
                {!chapterAvailable ? <option value={selectedChapter ?? ""}>Chapter {selectedChapter} — unavailable</option> : null}
                {chapterOptions.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}{chapter.title ? ` — ${chapter.title}` : ""}</option>)}
              </select>
              {!chapterAvailable ? <p className="mt-2" role="status">This chapter is no longer in the chapter list. Your passage is retained; choose an available chapter or copy it into a custom passage to review.</p> : null}
              {chaptersQuery.isLoading ? <span className="mt-2 block" role="status">Loading chapters. You can paste a custom passage.</span> : chaptersQuery.isError ? <span className="mt-2 block" role="alert">Chapters could not be refreshed. Existing drafts are retained.<button type="button" className="app-button-secondary mt-2" disabled={chaptersQuery.isFetching} onClick={() => void chaptersQuery.refetch()}>Retry chapter list</button></span> : chapterOptions.length === 0 ? <span className="mt-2 block">No chapters yet. Paste a passage to review it.</span> : null}
            </div>
            <div className="min-w-0 border-t border-[rgb(var(--border))] p-5 text-sm md:border-t-0">
              <label htmlFor="voice-character" className="font-semibold">Character focus</label>
              <select id="voice-character" value={selectedCharacterId ?? ""} onChange={(event) => setSelectedCharacterId(event.target.value || null)} className="app-input mt-2 w-full">
                <option value="">Auto-detect from passage</option>
                {selectedCharacterId && !selectedCharacter ? <option value={selectedCharacterId}>Previously selected character — unavailable</option> : null}
                {characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}
              </select>
              {selectedCharacterId && !selectedCharacter ? <p className="mt-2" role="status">Select an available character or auto-detect before reviewing.</p> : null}
              <span className="mt-2 block text-xs text-[rgb(var(--muted-foreground))]">Choose a character only when you need a targeted baseline comparison.</span>
              {charactersQuery.isLoading ? <span className="mt-2 block" role="status">Loading character choices…</span> : charactersQuery.isError ? <span className="mt-2 block" role="alert">Character choices could not be refreshed. Auto-detect is still available.<button type="button" className="app-button-secondary mt-2" disabled={charactersQuery.isFetching} onClick={() => void charactersQuery.refetch()}>Retry characters</button></span> : characters.length === 0 ? <span className="mt-2 block">No character choices yet. Auto-detect uses the submitted passage.</span> : null}
            </div>
          </div>

          <div className="grid xl:grid-cols-2 xl:divide-x xl:divide-[rgb(var(--border))]">
            <div className="min-w-0 py-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-[rgb(var(--muted-foreground))]">Source passage</p>
                  <h2 className="mt-1 text-2xl font-semibold">{chapterTitle || "Custom passage"}</h2>
                  {selectedCharacter ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Focused review: {selectedCharacter.name}</p> : null}
                </div>
                <div className="flex flex-wrap items-center gap-2"><button type="button" onClick={() => void runReview()} disabled={reviewLoading || saving || !canReview} className="app-button-primary">
                  {reviewLoading ? "Reviewing..." : "Run voice review"}
                </button>{result ? <a href="#voice-result" className="app-button-secondary">View review</a> : null}</div>
              </div>
              {!draft && chapterQuery.isFetching ? <p className="mt-5 text-sm text-[rgb(var(--muted-foreground))]" role="status">Loading chapter text...</p> : !draft ? <div className="mt-5" role="alert"><p>Chapter text could not be loaded. Choose another chapter or paste a custom passage.</p><button type="button" className="app-button-secondary mt-2" onClick={() => void chapterQuery.refetch()}>Retry chapter text</button></div> : (
                <textarea value={text} onChange={(event) => setText(event.target.value)} aria-label="Dialogue or chapter text for voice review" aria-describedby="voice-passage-help voice-passage-count" aria-invalid={overLimit} className="app-input mt-5 min-h-[18rem] w-full resize-y px-4 py-3 text-base leading-7 lg:min-h-[26rem]" />
              )}
              <p id="voice-passage-count" className="mt-2 text-sm">{text.trim().length.toLocaleString()} / 12,000 characters{overLimit ? " — shorten the passage before reviewing. Your full text is preserved." : ""}</p>
              <p id="voice-passage-help" className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Edits stay on this page while you switch chapters. They do not change your manuscript. Save a snapshot to keep the reviewed passage in Scenes.</p>
              {draft && draft.text !== draft.original ? <button type="button" className="app-button-secondary mt-3" onClick={resetDraft}>Discard passage edits</button> : null}
              {draft && chapterQuery.isError && selectedChapter !== null ? <p className="mt-3 text-sm" role="status">The chapter could not refresh. Your existing passage is retained.</p> : null}
              {reviewError ? <div className="mt-4 border-l-2 border-rose-500 py-1 pl-3 text-sm" role="alert"><p>{reviewError}</p><p className="mt-2">Your passage{result ? " and previous review remain" : " remains"} available. Run voice review to try again.</p></div> : null}
            </div>

            <div className="min-w-0 border-t border-[rgb(var(--border))] py-5 sm:p-6 xl:border-t-0">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[rgb(var(--border))] pb-5">
                <div><p className="text-sm font-medium text-[rgb(var(--muted-foreground))]">Review type</p><h2 id="voice-result" tabIndex={-1} className="mt-1 scroll-mt-6 text-2xl font-semibold">Character voice</h2></div>
                {review ? <div className="flex flex-wrap gap-2"><button type="button" disabled={saving || reviewLoading} onClick={() => void save("review")} className="app-button-secondary">Save review note</button><button type="button" disabled={saving || reviewLoading} onClick={() => void save("snapshot")} className="app-button-secondary">Save snapshot</button></div> : null}
              </div>

              {saving ? <p className="mt-4 text-sm" role="status">Saving review…</p> : null}
              {saveStatus ? <div className="mt-4 border-l-2 border-emerald-500 pl-3 text-sm" role="status"><p>{saveStatus}</p><div className="mt-2 flex flex-wrap gap-3"><Link className="app-button-secondary" href={`/${bookId}/notes`}>Open notes</Link><Link className="app-button-secondary" href={`/${bookId}/scenes`}>Open scenes</Link></div></div> : null}
              {saveError ? <p className="mt-4 border-l-2 border-rose-500 pl-3 text-sm" role="alert">{saveError}</p> : null}
              {reviewLoading ? <div className="py-5" role="status"><p className="font-semibold">Comparing the submitted passage with manuscript voice evidence…</p><p className="app-copy mt-2">You can keep editing. The result will refer to the passage submitted when you started.</p></div> : null}
              {result ? <div className="border-b border-[rgb(var(--border))] py-4 text-sm"><p>Reviewed source: {result.source.chapterNumber === null ? "Custom passage" : `Chapter ${result.source.chapterNumber} — ${result.source.chapterTitle}`}</p><p className="mt-1">Character focus: {result.source.characterName} · {result.source.text.length.toLocaleString()} characters</p>{contextChanged ? <p className="mt-3 font-semibold" role="status">The editor or character focus has changed. This review and its save actions still use the submitted passage.</p> : null}<details className="mt-3"><summary className="cursor-pointer py-2">Read the reviewed passage</summary><p className="mt-2 whitespace-pre-wrap leading-7">{result.source.text}</p></details></div> : null}

              {!review ? (
                !reviewLoading ? <div className="py-8"><p className="font-semibold">Review a passage against character voice evidence.</p><p className="app-copy mt-2">Select a chapter or paste text, optionally focus on one character, then run the review. Results stay here until you leave; save a note or snapshot to keep them.</p></div> : null
              ) : (
                <div>
                  <section className="border-b border-[rgb(var(--border))] py-5"><h3 className="font-semibold">Verdict</h3><p className="mt-2 leading-7">{review.overall_verdict}</p>{voiceCharacters.length ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Reviewed: {voiceCharacters.join(", ")}</p> : null}</section>
                  {reviewWarnings.length ? <div className="my-5 border-l-2 border-amber-500 py-1 pl-3 text-sm"><p className="mb-2 font-semibold">Review limitations</p>{reviewWarnings.map((warning, index) => <p key={`${warning}-${index}`}>{warning}</p>)}</div> : null}

                  <section className="border-b border-[rgb(var(--border))] pb-5">
                    <h3 className="mb-3 font-semibold">Findings</h3>
                    {review.issues.length ? <div className="divide-y divide-[rgb(var(--border))]">{review.issues.map((issue, index) => (
                      <article key={`${issue.character_name}-${issue.title}-${index}`} className="border-l-2 border-rose-500 py-4 pl-4 first:pt-2">
                        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-medium text-[rgb(var(--muted-foreground))]">{issue.severity} · {issue.character_name}</p><h4 className="mt-1 font-semibold">{issue.title}</h4></div><button type="button" aria-label={`Save note: ${issue.title}`} disabled={saving || reviewLoading} onClick={() => void save("issue", issue)} className="app-button-secondary">Save note</button></div>
                        <p className="mt-2 text-sm leading-6">{issue.description}</p>{issue.evidence ? <p className="mt-2 text-sm"><strong>Evidence:</strong> {issue.evidence}</p> : null}{issue.suggestion ? <p className="mt-2 text-sm"><strong>Revision direction:</strong> {issue.suggestion}</p> : null}
                        {issue.intentionality_prompt ? <details className="mt-3 text-sm"><summary className="cursor-pointer py-2">If this change is intentional</summary><p className="mt-2 leading-6">{issue.intentionality_prompt}</p></details> : null}
                      </article>
                    ))}</div> : <p className="text-sm text-[rgb(var(--muted-foreground))]">No character voice issues were flagged in this pass.</p>}
                  </section>

                  <section className="pt-5">
                    <h3 className="font-semibold">Baseline matches</h3>
                    <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Similarity estimates depend on available dialogue. Use the evidence and sample counts to judge the result; a score is not a verdict on writing quality.</p>
                    {!voiceMatches.length ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">No reliable match scores were available for this passage.</p> : <div className="mt-3 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">{voiceMatches.map((match) => (
                      <article key={match.character_name} className="py-4"><div className="flex items-baseline justify-between gap-3"><h4 className="font-semibold">{match.character_name}</h4><strong>{match.match_score}% match</strong></div><p className="mt-1 text-xs text-[rgb(var(--muted-foreground))]">Baseline {match.baseline_sample_size} samples · current passage {match.sample_dialogue_count} excerpts</p>{match.strongest_signals.length ? <p className="mt-2 text-sm">{match.strongest_signals.join(". ")}.</p> : null}{match.closest_other_character ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Closest alternate voice: {match.closest_other_character}{typeof match.closest_other_score === "number" ? ` (${match.closest_other_score}% match)` : ""}</p> : null}</article>
                    ))}</div>}
                  </section>
                  <details className="mt-5 border-t border-[rgb(var(--border))] pt-3">
                    <summary className="cursor-pointer py-2 font-semibold">Manuscript evidence ({result?.retrieved_passages?.length ?? 0} {result?.retrieved_passages?.length === 1 ? "passage" : "passages"})</summary>
                    {result?.retrieved_passages?.length ? <div className="divide-y divide-[rgb(var(--border))]">{result.retrieved_passages.map((passage, index) => <article key={`${passage.chapter_num}-${index}`} className="py-4"><h4 className="font-semibold">Chapter {passage.chapter_num}{passage.chapter_title ? ` — ${passage.chapter_title}` : ""}</h4><p className="mt-2 whitespace-pre-wrap text-sm leading-7">{passage.excerpt || "No excerpt was supplied for this source."}</p>{chapterOptions.some((chapter) => chapter.number === passage.chapter_num) ? <Link href={`/${bookId}/manuscript?chapter=${passage.chapter_num}`} className="app-button-secondary mt-3">Open chapter {passage.chapter_num}</Link> : <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">This chapter is not available in the current chapter list.</p>}</article>)}</div> : <p className="py-3 text-sm text-[rgb(var(--muted-foreground))]">No manuscript excerpts were supplied with this review.</p>}
                  </details>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div></WorkspacePage>
  )
}
