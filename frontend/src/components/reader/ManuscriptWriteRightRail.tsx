"use client"

import Link from "next/link"

import type { BookNote, EmotionalArcOverview } from "@/types/book"
import type { Character } from "@/types/character"
import type { AdvisorSuggestion, EditorialReview } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"

type ContextCharacter = {
  id: string
  name: string
  role?: string | null
}

type ActiveThreadItem = {
  title: string
}

type RecentEventItem = {
  chapter_number: number
  detail: string
}

type WarningItem = {
  title: string
}

type ManuscriptWriteRightRailProps = {
  isDark: boolean
  bookId: string
  activeRightPane: "context" | "advisor" | "notes" | "arcs" | "insights" | "character"
  onOpenRightPane: (pane: "context" | "advisor" | "notes" | "arcs" | "insights" | "character") => void
  selectedCharCard: Character | null
  onClearSelectedCharCard: () => void
  activeChapterContextCharacters: ContextCharacter[]
  characters: Character[]
  onOpenCharCard: (character: Character) => void
  activeThreadSummary: ActiveThreadItem[]
  plotThreads: PlotThread[]
  recentEventSummary: RecentEventItem[]
  warningSummary: WarningItem[]
  review: EditorialReview | null
  onTightenSelectedText: () => void
  suggestions: AdvisorSuggestion[]
  chapterAnnotationsCount: number
  chapterManualNotes: BookNote[]
  generalNotes: BookNote[]
  activeChapterNumber: number
  arcSummaryCharacter: EmotionalArcOverview["characters"][number] | null
}

export function ManuscriptWriteRightRail({
  isDark,
  bookId,
  activeRightPane,
  onOpenRightPane,
  selectedCharCard,
  onClearSelectedCharCard,
  activeChapterContextCharacters,
  characters,
  onOpenCharCard,
  activeThreadSummary,
  plotThreads,
  recentEventSummary,
  warningSummary,
  review,
  onTightenSelectedText,
  suggestions,
  chapterAnnotationsCount,
  chapterManualNotes,
  generalNotes,
  activeChapterNumber,
  arcSummaryCharacter,
}: ManuscriptWriteRightRailProps) {
  const characterItems = activeChapterContextCharacters.length
    ? activeChapterContextCharacters
    : characters.slice(0, 4).map((character) => ({
        id: character.id,
        name: character.name,
        role: character.role,
      }))

  const threadItems = activeThreadSummary.length
    ? activeThreadSummary.map((thread) => thread.title)
    : plotThreads.slice(0, 3).map((thread) => thread.title)

  const continuityItems = warningSummary.length
    ? warningSummary
    : (review?.continuity_issues.slice(0, 3) ?? [])

  return (
    <aside className="space-y-4">
      <div className={`rounded-[1.6rem] border p-2 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
        <div className="flex items-center gap-1">
          {([
            ["context", "Context"],
            ["advisor", "Advisor"],
            ["notes", "Notes"],
            ["arcs", "Arcs"],
          ] as const).map(([pane, label]) => (
            <button
              key={pane}
              type="button"
              onClick={() => onOpenRightPane(pane)}
              className={`rounded-full px-3 py-2 text-sm font-medium transition ${
                activeRightPane === pane
                  ? isDark
                    ? "bg-white text-slate-950"
                    : "bg-stone-900 text-white"
                  : isDark
                    ? "text-slate-300 hover:bg-white/10"
                    : "text-stone-600 hover:bg-stone-100"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {activeRightPane === "character" && selectedCharCard ? (
        <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
          <button
            type="button"
            onClick={onClearSelectedCharCard}
            className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}
          >
            Back to context
          </button>
          <div className="mt-4">
            <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{selectedCharCard.name}</p>
            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
              {selectedCharCard.role === "mc" ? "POV" : selectedCharCard.role === "sc" ? "Supporting" : "Background"} - Ch. {selectedCharCard.first_chapter}
              {selectedCharCard.last_seen_chapter ? ` to ${selectedCharCard.last_seen_chapter}` : ""}
            </p>
            {selectedCharCard.description ? <p className={`mt-4 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{selectedCharCard.description}</p> : null}
            {selectedCharCard.arc_summary ? <p className={`mt-4 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{selectedCharCard.arc_summary}</p> : null}
          </div>
        </div>
      ) : null}

      {activeRightPane === "context" ? (
        <>
          <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Active characters</p>
              <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{activeChapterContextCharacters.length || Math.min(4, characters.length)}</span>
            </div>
            <div className="mt-4 space-y-3">
              {characterItems.map((character) => (
                <button
                  key={character.id}
                  type="button"
                  onClick={() => {
                    const match = characters.find((item) => item.id === character.id)
                    if (match) onOpenCharCard(match)
                  }}
                  className="flex w-full items-center justify-between gap-3 text-left"
                >
                  <div className="flex items-center gap-3">
                    <span className="h-2.5 w-2.5 rounded-full bg-sky-400" />
                    <span className={`text-sm ${isDark ? "text-slate-100" : "text-stone-900"}`}>{character.name}</span>
                  </div>
                  <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{character.role === "mc" ? "POV" : character.role === "sc" ? "Major" : "Supporting"}</span>
                </button>
              ))}
              {activeChapterContextCharacters.length === 0 && characters.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No characters loaded yet.</p> : null}
            </div>
            <Link href={`/${bookId}/characters`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>View all characters -&gt;</Link>
          </div>

          <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Unresolved threads</p>
              <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{activeThreadSummary.length || Math.min(3, plotThreads.length)}</span>
            </div>
            <div className="mt-4 space-y-3">
              {threadItems.map((thread) => (
                <div key={thread} className="flex items-start gap-3">
                  <span className="mt-1.5 h-2 w-2 rounded-full bg-amber-400" />
                  <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{thread}</p>
                </div>
              ))}
              {activeThreadSummary.length === 0 && plotThreads.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No unresolved threads loaded yet.</p> : null}
            </div>
            <Link href={`/${bookId}/plot-threads`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>View all threads -&gt;</Link>
          </div>

          <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Recent events</p>
              <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{recentEventSummary.length}</span>
            </div>
            <div className="mt-4 space-y-3">
              {recentEventSummary.map((event) => (
                <div key={`${event.chapter_number}-${event.detail}`} className="flex items-start gap-3">
                  <span className="mt-1.5 h-2 w-2 rounded-full bg-emerald-400" />
                  <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{event.detail}</p>
                </div>
              ))}
              {recentEventSummary.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Recent chapter events will appear here.</p> : null}
            </div>
            <Link href={`/${bookId}/timeline`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>View timeline -&gt;</Link>
          </div>

          <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Continuity warnings</p>
              <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{warningSummary.length || review?.continuity_issues.length || 0}</span>
            </div>
            <div className="mt-4 space-y-3">
              {continuityItems.map((warning, index) => (
                <div key={`${warning.title}-${index}`} className="flex items-start gap-3">
                  <span className="mt-1.5 h-2 w-2 rounded-full bg-amber-400" />
                  <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{warning.title}</p>
                </div>
              ))}
              {warningSummary.length === 0 && !review?.continuity_issues.length ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No continuity warnings surfaced for this chapter.</p> : null}
            </div>
          </div>

          <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-sky-500/30 bg-sky-500/5" : "border-sky-200 bg-sky-50/80"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Ask LoreVia</p>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-100 text-sky-700"}`}>Beta</span>
            </div>
            <div className={`mt-4 rounded-[1rem] border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-500" : "border-stone-200 bg-white text-stone-400"}`}>
              Ask anything about your story...
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => onOpenRightPane("context")} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Check continuity</button>
              <button type="button" onClick={onTightenSelectedText} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Tighten selection</button>
              <button type="button" onClick={() => onOpenRightPane("advisor")} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Suggest rewrite</button>
            </div>
          </div>
        </>
      ) : null}

      {activeRightPane === "advisor" ? (
        <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter advisor</p>
          <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>Use LoreVia while drafting to tighten prose, surface continuity risks, and suggest stronger scene transitions.</p>
          <div className="mt-4 space-y-3">
            {suggestions.slice(0, 3).map((suggestion, index) => (
              <div key={`${suggestion.title}-${index}`} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{suggestion.title}</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{suggestion.description}</p>
              </div>
            ))}
            {suggestions.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Advisor suggestions will appear here after review passes run.</p> : null}
          </div>
          <Link href={`/${bookId}/advisor`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>Open full advisor -&gt;</Link>
        </div>
      ) : null}

      {activeRightPane === "notes" ? (
        <>
          <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter notes</p>
              <Link href={`/${bookId}/notes`} className={`text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>All notes -&gt;</Link>
            </div>
            {chapterAnnotationsCount > 0 ? <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterAnnotationsCount} annotation{chapterAnnotationsCount === 1 ? "" : "s"} anchored to this chapter.</p> : null}
            <div className="mt-4 space-y-3">
              {chapterManualNotes.slice(0, 4).map((note) => (
                <div key={note.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || `Chapter ${activeChapterNumber} note`}</p>
                  <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                </div>
              ))}
              {chapterManualNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No notes saved for this chapter yet.</p> : null}
            </div>
          </div>
          <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Book notes</p>
            <div className="mt-4 space-y-3">
              {generalNotes.slice(0, 3).map((note) => (
                <div key={note.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || "Book note"}</p>
                  <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                </div>
              ))}
              {generalNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No book-level notes saved yet.</p> : null}
            </div>
          </div>
        </>
      ) : null}

      {activeRightPane === "arcs" ? (
        <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Character emotional arc</p>
          {arcSummaryCharacter ? (
            <div className="mt-4">
              <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{arcSummaryCharacter.character_name}</p>
              <div className="mt-4 space-y-3">
                {arcSummaryCharacter.points.slice(-6).map((point) => (
                  <div key={`${point.chapter_number}-${point.label}`} className="grid grid-cols-[auto_1fr] gap-3">
                    <span className={`text-xs font-semibold ${isDark ? "text-slate-500" : "text-stone-500"}`}>Ch. {point.chapter_number}</span>
                    <div className="flex items-center gap-3">
                      <span className={`h-2 w-full rounded-full ${point.sentiment >= 0 ? "bg-emerald-400/60" : "bg-rose-400/60"}`} />
                      <span className={`min-w-[7rem] text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{point.label}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className={`mt-4 text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Character arc tracking will appear once growth events are available.</p>
          )}
        </div>
      ) : null}
    </aside>
  )
}
