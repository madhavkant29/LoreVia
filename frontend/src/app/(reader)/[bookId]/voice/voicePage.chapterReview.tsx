"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { intelligenceApi } from "@/lib/api/intelligence"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"

export function ChapterVoiceReview({
  bookId,
  chapterNumber,
  onFocusCharacter,
}: {
  bookId: string
  chapterNumber: number | null
  onFocusCharacter: (characterId: string | null, mode: "dialogue" | "first_person_narration", range?: { start: number; end: number }) => void
}) {
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const reviewQuery = useQuery({
    queryKey: ["voice-chapter-review", bookId, chapterNumber],
    queryFn: () => intelligenceApi.latestVoiceChapterReview(bookId, chapterNumber!),
    enabled: chapterNumber !== null,
    retry: false,
    refetchInterval: (query) => {
      const latest = query.state.data
      return latest?.status === "queued" || latest?.status === "running" || (latest?.status === "paused" && !!latest.next_resume_at) ? 5000 : false
    },
  })
  const job = reviewQuery.data
  const result = job?.result
  const active = job?.status === "queued" || job?.status === "running"
  const awaitingAutomaticRetry = job?.status === "paused" && !!job.next_resume_at && Date.parse(job.next_resume_at) > Date.now()
  const reviewChapter = async () => {
    if (chapterNumber === null || starting || active || awaitingAutomaticRetry) return
    setStarting(true)
    setStartError(null)
    try {
      await intelligenceApi.startVoiceChapterReview(
        bookId, chapterNumber, job?.status === "paused", job?.status === "complete" || job?.status === "failed",
      )
      await reviewQuery.refetch()
    } catch (error) {
      setStartError(getApiErrorDetail(error) ?? "Could not start the chapter review. Try again.")
    } finally {
      setStarting(false)
    }
  }

  return (
    <section aria-label="Saved chapter voice review" className="mt-6 border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-5 text-[rgb(var(--foreground))]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Review saved chapter</h2>
          <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Checks identifiable dialogue and first-person narration across the entire saved chapter. Passage review below is for unsaved edits or a focused check.</p>
        </div>
        <button type="button" className="app-button-primary" disabled={chapterNumber === null || starting || active || awaitingAutomaticRetry} onClick={() => void reviewChapter()}>
          {starting ? "Starting…" : awaitingAutomaticRetry ? "Automatic retry scheduled" : job?.status === "paused" ? "Retry chapter review" : job?.status === "failed" || job?.status === "complete" ? "Review chapter again" : "Review chapter"}
        </button>
      </div>
      {chapterNumber === null ? <p className="mt-3 text-sm">Select a saved chapter to start.</p> : null}
      {reviewQuery.isError ? <p role="alert" className="mt-3 text-sm">Could not load the previous chapter review. <button type="button" className="underline" onClick={() => void reviewQuery.refetch()}>Retry status</button></p> : null}
      {startError ? <p role="alert" className="mt-3 text-sm text-rose-700 dark:text-rose-300">{startError}</p> : null}
      {job ? <div className="mt-4 text-sm" role={active ? "status" : undefined}>
        <p className="font-semibold">{job.status === "complete" ? result?.status === "complete" ? "Chapter review complete" : "Chapter review finished with limitations" : job.status === "paused" ? "Chapter review paused" : job.status === "failed" ? "Chapter review stopped" : job.status === "running" ? "Reviewing chapter" : "Chapter review queued"}</p>
        {active || job.status === "paused" ? <p className="mt-1">{job.progress.completed} of {job.progress.total || "pending"} voice sections reviewed. You can leave and return to this page.</p> : null}
        {job.error ? <p className="mt-1">{job.error}</p> : null}
        {job.next_resume_at ? <p className="mt-1">Automatic retry is scheduled for {new Date(job.next_resume_at).toLocaleString()}.</p> : null}
      </div> : null}
      {result ? <div className="mt-5 space-y-4">
        <p className="text-sm">{result.voices.length} voice{result.voices.length === 1 ? "" : "s"} reviewed · {result.coverage.unattributed_quoted_ranges?.length ?? 0} unattributed quote range{result.coverage.unattributed_quoted_ranges?.length === 1 ? "" : "s"}. {result.narrator_identified ? "Narrator identified." : "No narrator was confidently identified."}</p>
        <p className="text-sm text-[rgb(var(--muted-foreground))]">{result.coverage.processed_ranges.length} reviewed source range{result.coverage.processed_ranges.length === 1 ? "" : "s"} across {result.coverage.total_characters.toLocaleString()} saved characters. {result.coverage.unattributed_ranges?.length ?? 0} range{result.coverage.unattributed_ranges?.length === 1 ? "" : "s"} had no reviewed voice.</p>
        {result.narration_present && !result.narrator_identified ? <p className="border-l-2 border-amber-500 pl-3 text-sm">First-person narration was found, but its speaker could not be identified confidently. Choose a narrator in the passage review below.</p> : null}
        {result.voices.length === 0 ? <p className="text-sm">No attributable character voice had enough evidence for a verdict. Use a focused passage review if you know the speaker.</p> : null}
        {result.voices.map((voice) => <article key={`${voice.character_id}:${voice.voice_mode}`} className="border-t border-[rgb(var(--border))] pt-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">{voice.character_name} · {voice.voice_mode === "dialogue" ? "Dialogue" : "Narration"}</h3><button type="button" className="app-button-secondary" onClick={() => onFocusCharacter(voice.character_id, voice.voice_mode, voice.coverage.compared_ranges?.[0] ?? voice.coverage.processed_ranges?.[0])}>{voice.coverage.compared_ranges?.length || voice.coverage.processed_ranges?.length ? "Review focused passage" : "Choose a passage"}</button></div>
          <p className="mt-1">{voice.status === "complete" ? "Reviewed" : voice.status === "insufficient_evidence" ? "Insufficient evidence" : "Partial evidence"} · {voice.coverage.compared_ranges?.length ?? 0} compared source range{voice.coverage.compared_ranges?.length === 1 ? "" : "s"}</p>
          {voice.issues.length ? <div className="mt-2 space-y-3">{voice.issues.map((issue, index) => <div key={issue.finding_key ?? index} className="border-l-2 border-amber-500 pl-3"><p className="font-medium">{issue.title}</p><p>{issue.description}</p>{issue.submitted_excerpt ? <p className="mt-1">Current: {issue.submitted_excerpt}</p> : null}{issue.baseline_excerpt ? <p>Baseline, chapter {issue.baseline_chapter_number}: {issue.baseline_excerpt}</p> : null}</div>)}</div> : <p className="mt-1">{voice.status === "complete" ? "No supported voice shifts found in the compared speech." : "There is not enough supported evidence for a clean voice verdict."}</p>}
          {voice.warnings.length ? <details className="mt-2"><summary className="cursor-pointer">Review limitations ({voice.warnings.length})</summary><ul className="mt-1 list-disc pl-5">{voice.warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul></details> : null}
        </article>)}
        {result.status !== "complete" ? <p className="border-l-2 border-amber-500 pl-3 text-sm">This is not a clean verdict: {result.unreviewed_ranges.length} work range{result.unreviewed_ranges.length === 1 ? "" : "s"} unfinished and {result.coverage.unattributed_quoted_ranges?.length ?? 0} quoted range{result.coverage.unattributed_quoted_ranges?.length === 1 ? "" : "s"} without a supported speaker comparison. Voice and narrator evidence may also be insufficient.</p> : null}
        {(result.coverage.unattributed_quoted_ranges?.length ?? 0) > 0 ? <button type="button" className="app-button-secondary" onClick={() => onFocusCharacter(null, "dialogue", result.coverage.unattributed_quoted_ranges?.[0])}>Choose a speaker in passage review</button> : null}
      </div> : null}
    </section>
  )
}
