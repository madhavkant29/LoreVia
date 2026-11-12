"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { Info } from "lucide-react"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { useVoiceWorkspace } from "./voicePage.state"
import { ChapterVoiceReview } from "./voicePage.chapterReview"
import { countVoiceSourceCharacters } from "@/lib/utils/voiceWorkspace"

export default function VoiceConsistencyPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <VoiceWorkspace key={bookId} bookId={bookId} />
}

function VoiceWorkspace({ bookId }: { bookId: string }) {
  const workspace = useVoiceWorkspace(bookId)
  const { bookQuery, chaptersQuery, charactersQuery, chapterQuery, selectedChapter, selectChapter, selectedCharacterId, setSelectedCharacterId, selectedCharacter, characters, sceneContext, setSceneContext, voiceMode, setVoiceMode,
    text, setText, chapterTitle, chapterAvailable, draft, resetDraft, focusChapterVoice, focusStatus, result, contextChanged, overLimit, canReview, runReview, reviewLoading, reviewStage, reviewError, saving, saveStatus, saveError, save, decideFinding, decisionSavingKey, decisionError } = workspace
  const book = bookQuery.data
  const chapterOptions = chaptersQuery.data?.chapters ?? []
  const review = result?.review
  const voiceCharacters = result?.characters_reviewed ?? []
  const voiceMatches = result?.character_matches ?? []
  const reviewWarnings = result?.warnings ?? []
  const reviewedSectionCharacters = result?.coverage?.processed_ranges.reduce((total, range) => total + range.end - range.start, 0) ?? 0
  const unattributedCharacters = result?.coverage?.unattributed_ranges?.reduce((total, range) => total + range.end - range.start, 0) ?? 0
  const comparedVoiceCharacters = result?.coverage?.compared_ranges?.reduce((total, range) => total + range.end - range.start, 0)
  const notComparedCharacters = result?.coverage?.not_compared_ranges?.reduce((total, range) => total + range.end - range.start, 0)
  const unattributedQuotedCharacters = result?.coverage?.unattributed_quoted_ranges?.reduce((total, range) => total + range.end - range.start, 0) ?? 0
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
        <details data-voice-help className="mt-2 text-sm text-[rgb(var(--foreground))]">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-sm px-1 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--accent))] [&::-webkit-details-marker]:hidden">
            How voice review works <Info className="h-4 w-4" aria-hidden="true" />
          </summary>
          <div className="mt-3 max-w-3xl border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-4 leading-6">
            <p>Review chapter checks the entire saved chapter, with a separate result for every identifiable speaker and first-person narrator. It compares attributable voice with earlier chapters, shows supporting passages, and reports unknown speakers or missing baseline evidence. The review runs in the background and can resume after a pause.</p>
            <p className="mt-2">For unsaved edits or a focused question, use passage review below: paste up to 12,000 characters or choose a chapter, then optionally select one character. Passage Auto-detect checks up to five known characters. Neither review changes your manuscript.</p>
          </div>
        </details>

        {bookQuery.isLoading ? <p className="mt-5" role="status">Loading book context…</p> : bookQuery.isError || !book ? <div className="mt-5 border-l-2 border-[rgb(var(--border))] pl-4" role="alert"><p>Book context could not be loaded. Your passage stays here; reviewing is unavailable until it loads.</p><button type="button" className="app-button-secondary mt-2" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry book context</button></div> : null}

        <ChapterVoiceReview bookId={bookId} chapterNumber={selectedChapter} onFocusCharacter={(characterId, mode, range) => {
          focusChapterVoice(characterId, mode, range)
          document.getElementById("voice-passage-review")?.scrollIntoView?.({ behavior: "smooth" })
        }} />

        <section id="voice-passage-review" className="mt-6 border-y border-[rgb(var(--border))]">
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
              <span className="mt-2 block text-xs text-[rgb(var(--muted-foreground))]">In dialogue mode, Auto-detect checks up to five known characters with attributable speech. Select one character for a focused comparison or to check someone the automatic review skips.</span>
              <label htmlFor="voice-mode" className="mt-4 block font-semibold">Voice to review</label>
              <select id="voice-mode" value={voiceMode} onChange={(event) => setVoiceMode(event.target.value as "dialogue" | "first_person_narration")} className="app-input mt-2 w-full">
                <option value="dialogue">Character dialogue</option>
                <option value="first_person_narration">First-person narration</option>
              </select>
              {voiceMode === "first_person_narration" ? <p className="mt-2 text-xs text-[rgb(var(--muted-foreground))]">Select the narrator, or use Auto-detect when the passage explicitly names its “I” narrator. We will not guess from “I” alone.</p> : null}
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
              <p id="voice-passage-count" className="mt-2 text-sm">{countVoiceSourceCharacters(text).toLocaleString()} / 12,000 characters{overLimit ? " — shorten the passage before reviewing. Your full text is preserved." : ""}</p>
              {focusStatus ? <p className="mt-2 text-sm" role="status">{focusStatus}</p> : null}
              <p id="voice-passage-help" className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Edits stay on this page while you switch chapters. They do not change your manuscript. Save a snapshot to keep the reviewed passage in Scenes.</p>
              {draft && draft.text !== draft.original ? <button type="button" className="app-button-secondary mt-3" onClick={resetDraft}>Discard passage edits</button> : null}
              <label htmlFor="voice-scene-context" className="mt-5 block text-sm font-semibold">Scene context (optional)</label>
              <textarea id="voice-scene-context" value={sceneContext} maxLength={500} onChange={(event) => setSceneContext(event.target.value)} className="app-input mt-2 min-h-20 w-full resize-y px-3 py-2 text-sm" placeholder="For example: fear, anger, deception, injury, code-switching, or earned growth." />
              <p className="mt-1 text-xs text-[rgb(var(--muted-foreground))]">Context helps distinguish an intentional change from an unexplained voice shift.</p>
              {draft && chapterQuery.isError && selectedChapter !== null ? <p className="mt-3 text-sm" role="status">The chapter could not refresh. Your existing passage is retained.</p> : null}
              {reviewError ? <div className="mt-4 border-l-2 border-rose-500 py-1 pl-3 text-sm" role="alert"><p>{reviewError}</p><p className="mt-2">Your passage{result ? " and previous review remain" : " remains"} available. Run voice review to try again.</p></div> : null}
            </div>

            <div className="min-w-0 border-t border-[rgb(var(--border))] py-5 sm:p-6 xl:border-t-0">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[rgb(var(--border))] pb-5">
                <div><p className="text-sm font-medium text-[rgb(var(--muted-foreground))]">Review type</p><h2 id="voice-result" tabIndex={-1} className="mt-1 scroll-mt-6 text-2xl font-semibold">{voiceMode === "first_person_narration" ? "Narrator voice" : "Character voice"}</h2></div>
                {review ? <div className="flex flex-wrap gap-2"><button type="button" disabled={saving || reviewLoading} onClick={() => void save("review")} className="app-button-secondary">Save review note</button><button type="button" disabled={saving || reviewLoading} onClick={() => void save("snapshot")} className="app-button-secondary">Save snapshot</button></div> : null}
              </div>

              {saving ? <p className="mt-4 text-sm" role="status">Saving review…</p> : null}
              {saveStatus ? <div className="mt-4 border-l-2 border-emerald-500 pl-3 text-sm" role="status"><p>{saveStatus}</p><div className="mt-2 flex flex-wrap gap-3"><Link className="app-button-secondary" href={`/${bookId}/notes`}>Open notes</Link><Link className="app-button-secondary" href={`/${bookId}/scenes`}>Open scenes</Link></div></div> : null}
              {saveError ? <p className="mt-4 border-l-2 border-rose-500 pl-3 text-sm" role="alert">{saveError}</p> : null}
              {reviewLoading ? <div className="py-5" role="status"><p className="font-semibold">{reviewStage || "Comparing the submitted passage with manuscript voice evidence…"}</p><p className="app-copy mt-2">You can keep editing. The result will refer to the passage submitted when you started.</p></div> : null}
              {result ? <div className="border-b border-[rgb(var(--border))] py-4 text-sm"><p>Reviewed source: {result.source.chapterNumber === null ? "Custom passage" : `Chapter ${result.source.chapterNumber} — ${result.source.chapterTitle}`}</p><p className="mt-1">Character focus: {result.source.characterName} · {countVoiceSourceCharacters(result.source.text).toLocaleString()} characters</p>{contextChanged ? <p className="mt-3 font-semibold" role="status">The editor or character focus has changed. This review and its save actions still use the submitted passage.</p> : null}<details className="mt-3"><summary className="cursor-pointer py-2">Read the reviewed passage</summary><p className="mt-2 whitespace-pre-wrap leading-7">{result.source.text}</p></details></div> : null}

              {!review ? (
                !reviewLoading ? <div className="py-8"><p className="font-semibold">Review a passage against character voice evidence.</p><p className="app-copy mt-2">Select a chapter or paste text, optionally focus on one character, then run the review. Results stay here until you leave; save a note or snapshot to keep them.</p></div> : null
              ) : (
                <div>
                  <section className="border-b border-[rgb(var(--border))] py-5">
                    <h3 className="font-semibold">{review.status === "insufficient_evidence" ? "Insufficient voice evidence" : review.status === "partial_evidence" ? "Partial voice review" : "Verdict"}</h3>
                    <p className="mt-2 leading-7">{review.overall_verdict}</p>
                    {voiceCharacters.length ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Reviewed voices: {voiceCharacters.join(", ")}</p> : null}
                    {result.characters_detected?.length ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Voice baselines compared: {result.characters_reviewed.length} of {result.characters_detected.length} detected characters.</p> : null}
                    {result.coverage ? <div className="mt-2 text-sm text-[rgb(var(--muted-foreground))]"><p>Source coverage: {result.coverage.processed_ranges.length ? `${reviewedSectionCharacters.toLocaleString()} of ${result.coverage.total_characters.toLocaleString()} source characters were in reviewed sections; only ${result.voice_mode === "first_person_narration" ? "identified narrator prose" : "attributed voice samples"} were compared${unattributedCharacters ? `; ${unattributedCharacters.toLocaleString()} characters had no attributable voice in any reviewed section` : ""}` : `no source sections reviewed; a reliable baseline or attributable passage voice is needed`}</p>{comparedVoiceCharacters !== undefined ? <p className="mt-1">Exact voice comparison: {comparedVoiceCharacters.toLocaleString()} characters compared with the baseline; {(notComparedCharacters ?? 0).toLocaleString()} source characters were not voice-compared (including narration, speaker labels, or uncertain speech).</p> : null}{result.coverage_by_character?.map((item) => <p key={item.character_name} className="mt-1">{item.character_name}: {item.processed_ranges.length} overlapping section(s) compared; {item.unattributed_ranges?.length ?? 0} section(s) had no attributable voice and were not compared.{item.compared_ranges ? ` ${item.compared_ranges.reduce((total, range) => total + range.end - range.start, 0).toLocaleString()} attributed voice characters compared.` : ""}</p>)}</div> : null}
                    {unattributedQuotedCharacters > 0 ? <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">{unattributedQuotedCharacters.toLocaleString()} quoted characters were not attributed to a reviewed voice. This is a partial review; select the speaker for a focused check if known.</p> : null}
                  </section>
                  {result.characters_detected?.length ? <p className="mt-4 text-sm">Detected characters: {result.characters_detected.join(", ")}</p> : null}
                  {result.baseline_evidence?.length ? <div className="mt-3 text-sm"><p className="font-semibold">Voice evidence</p>{result.baseline_evidence.map((item) => <p key={item.character_name} className="mt-1">{item.character_name}: {item.sample_count} {result.voice_mode === "first_person_narration" ? "first-person narrative" : "attributed dialogue"} baseline excerpts, {item.word_count} words{item.chapters.length ? ` from chapter${item.chapters.length === 1 ? "" : "s"} ${item.chapters.join(", ")}` : ""}. {item.baseline_attribution_confidence ? `Baseline attribution: ${item.baseline_attribution_confidence.replace(/_/g, " ")}. ` : ""}Current passage attribution: {item.attribution_confidence.replace(/_/g, " ")}.</p>)}</div> : null}
                  {reviewWarnings.length ? <div className="my-5 border-l-2 border-amber-500 py-1 pl-3 text-sm"><p className="mb-2 font-semibold">Review limitations</p>{reviewWarnings.map((warning, index) => <p key={`${warning}-${index}`}>{warning}</p>)}</div> : null}

                  <section className="border-b border-[rgb(var(--border))] pb-5">
                    <h3 className="mb-3 font-semibold">Findings</h3>
                    {decisionError ? <p role="alert" className="mb-3 border-l-2 border-rose-500 pl-3 text-sm">{decisionError}</p> : null}
                    {review.issues.length ? <div className="divide-y divide-[rgb(var(--border))]">{review.issues.map((issue, index) => (
                      <article key={`${issue.character_name}-${issue.title}-${index}`} className="border-l-2 border-rose-500 py-4 pl-4 first:pt-2">
                        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-medium text-[rgb(var(--muted-foreground))]">{issue.classification?.replace(/_/g, " ") ?? issue.severity} · {issue.character_name}{typeof issue.confidence === "number" ? ` · ${Math.round(issue.confidence * 100)}% evidence strength` : ""}</p><h4 className="mt-1 font-semibold">{issue.title}</h4></div><button type="button" aria-label={`Save note: ${issue.title}`} disabled={saving || reviewLoading} onClick={() => void save("issue", issue)} className="app-button-secondary">Save note</button></div>
                        <p className="mt-2 text-sm leading-6">{issue.description}</p>{issue.submitted_excerpt ? <blockquote className="mt-3 border-l-2 border-[rgb(var(--border))] pl-3 text-sm"><strong>Submitted passage:</strong> {issue.submitted_excerpt}</blockquote> : null}{issue.baseline_excerpt ? <blockquote className="mt-2 border-l-2 border-[rgb(var(--border))] pl-3 text-sm"><strong>Baseline, chapter {issue.baseline_chapter_number}:</strong> {issue.baseline_excerpt}</blockquote> : issue.evidence ? <p className="mt-2 text-sm"><strong>Evidence:</strong> {issue.evidence}</p> : null}{issue.revision_direction || issue.suggestion ? <p className="mt-2 text-sm"><strong>Revision direction:</strong> {issue.revision_direction || issue.suggestion}</p> : null}
                        {issue.intentionality_prompt ? <details className="mt-3 text-sm"><summary className="cursor-pointer py-2">If this change is intentional</summary><p className="mt-2 leading-6">{issue.intentionality_prompt}</p></details> : null}
                        {issue.finding_key ? <div className="mt-3 flex flex-wrap gap-2" aria-label={`Review finding: ${issue.title}`}>
                          <button type="button" className="app-button-secondary" disabled={!!decisionSavingKey || reviewLoading} onClick={() => void decideFinding(issue, "intentional")}>Mark intentional</button>
                          <button type="button" className="app-button-secondary" disabled={!!decisionSavingKey || reviewLoading} onClick={() => void decideFinding(issue, "incorrect")}>Mark incorrect</button>
                          <button type="button" className="app-button-secondary" disabled={!!decisionSavingKey || reviewLoading} onClick={() => void decideFinding(issue, "resolved")}>Mark resolved</button>
                          {decisionSavingKey === issue.finding_key ? <span role="status">Saving decision…</span> : null}
                        </div> : null}
                      </article>
                    ))}</div> : <p className="text-sm text-[rgb(var(--muted-foreground))]">{review.status === "insufficient_evidence" ? "No verdict was made because attributed baseline evidence is insufficient." : review.status === "partial_evidence" ? "No supported issue was found, but this is not a complete verdict: speaker attribution, the baseline, or current passage evidence may be too limited." : result.suppressed_findings?.length ? "All findings from this review have recorded decisions; they are not being presented as new issues." : "No supported character voice issues were found in the reviewed passage."}</p>}
                    {result.suppressed_findings?.length ? <details className="mt-4 text-sm"><summary className="cursor-pointer py-2">Previously reviewed findings ({result.suppressed_findings.length})</summary>{result.suppressed_findings.map((issue) => <p key={issue.finding_key ?? issue.title} className="mt-2">{issue.title} — marked {issue.decision ?? "reviewed"}</p>)}</details> : null}
                  </section>

                  <section className="pt-5">
                    <h3 className="font-semibold">Baseline matches</h3>
                    <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Similarity estimates depend on available {result.voice_mode === "first_person_narration" ? "first-person narration" : "dialogue"}. Use the evidence and sample counts to judge the result; a score is not a verdict on writing quality.</p>
                    {!voiceMatches.length ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">No reliable match scores were available for this passage.</p> : <div className="mt-3 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">{voiceMatches.map((match) => (
                      <article key={match.character_name} className="py-4"><div className="flex items-baseline justify-between gap-3"><h4 className="font-semibold">{match.character_name}</h4><strong>{match.match_score}% match</strong></div><p className="mt-1 text-xs text-[rgb(var(--muted-foreground))]">Baseline {match.baseline_sample_size} samples · current passage {match.sample_dialogue_count} excerpts</p>{match.strongest_signals.length ? <p className="mt-2 text-sm">{match.strongest_signals.join(". ")}.</p> : null}{match.closest_other_character ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Closest alternate voice: {match.closest_other_character}{typeof match.closest_other_score === "number" ? ` (${match.closest_other_score}% stylistic similarity)` : ""}. This is supporting evidence, not proof of speaker identity.</p> : null}</article>
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
