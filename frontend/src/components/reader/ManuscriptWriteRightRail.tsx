"use client"

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react"
import Link from "next/link"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { BookNote, EmotionalArcOverview, VaultNote } from "@/types/book"
import type { Character } from "@/types/character"
import type { AdvisorMessage, AdvisorSuggestion, EditorialReview } from "@/types/intelligence"
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

const ADVISOR_STARTERS = [
  "What continuity risks should I watch in this chapter?",
  "How can I make this scene transition stronger?",
  "What should I foreshadow from here?",
]

export function buildManuscriptRailAdvisorStorageKey(bookId: string) {
  return `lorevia:manuscript-rail-advisor:${bookId}`
}

export function getNotePreview(content: string, limit = 140) {
  const plain = content
    .replace(/^#\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\s+/g, " ")
    .trim()
  if (plain.length <= limit) return plain
  return `${plain.slice(0, limit).trim()}...`
}

export function buildQuickVaultNoteFolder(scope: "chapter" | "book", chapterNumber: number) {
  return scope === "chapter" ? [`Chapter ${chapterNumber}`] : ["Whole Book"]
}

type ManuscriptWriteRightRailProps = {
  isDark: boolean
  bookId: string
  totalChapters: number | null
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
  vaultNotes: VaultNote[]
  activeChapterNumber: number
  arcSummaryCharacter: EmotionalArcOverview["characters"][number] | null
  onBookNoteSaved?: (note: BookNote) => void
  onVaultNoteSaved?: () => void
}

export function ManuscriptWriteRightRail({
  isDark,
  bookId,
  totalChapters,
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
  vaultNotes,
  activeChapterNumber,
  arcSummaryCharacter,
  onBookNoteSaved,
  onVaultNoteSaved,
}: ManuscriptWriteRightRailProps) {
  const [noteScope, setNoteScope] = useState<"chapter" | "book">("chapter")
  const [noteTitle, setNoteTitle] = useState("")
  const [noteBody, setNoteBody] = useState("")
  const [noteStatus, setNoteStatus] = useState<string | null>(null)
  const [savingNote, setSavingNote] = useState(false)
  const [advisorMessages, setAdvisorMessages] = useState<AdvisorMessage[]>([])
  const [advisorInput, setAdvisorInput] = useState("")
  const [advisorLoading, setAdvisorLoading] = useState(false)
  const [advisorError, setAdvisorError] = useState<string | null>(null)
  const advisorBottomRef = useRef<HTMLDivElement>(null)

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

  const storageKey = useMemo(() => buildManuscriptRailAdvisorStorageKey(bookId), [bookId])
  const recentVaultNotes = useMemo(
    () => [...vaultNotes].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()),
    [vaultNotes],
  )

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey)
      if (!raw) {
        setAdvisorMessages([])
        return
      }
      const parsed = JSON.parse(raw) as AdvisorMessage[]
      setAdvisorMessages(Array.isArray(parsed) ? parsed.filter((message) => message.role && message.content).slice(-12) : [])
    } catch {
      setAdvisorMessages([])
    }
  }, [storageKey])

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(advisorMessages.slice(-12)))
    } catch {
      // localStorage can be unavailable in tests or private browsing contexts.
    }
  }, [advisorMessages, storageKey])

  useEffect(() => {
    if (typeof advisorBottomRef.current?.scrollIntoView === "function") {
      advisorBottomRef.current.scrollIntoView({ block: "nearest" })
    }
  }, [advisorMessages, advisorLoading])

  const saveQuickNote = useCallback(async () => {
    const body = noteBody.trim()
    if (!body) return
    const title = noteTitle.trim() || (noteScope === "chapter" ? `Chapter ${activeChapterNumber} note` : "Book note")
    setSavingNote(true)
    setNoteStatus(null)
    try {
      const savedBookNote = await booksApi.saveBookNote(bookId, {
        chapterNumber: noteScope === "chapter" ? activeChapterNumber : null,
        title,
        body,
      })
      onBookNoteSaved?.(savedBookNote)
      await saveContextualVaultNote({
        bookId,
        title,
        content: body,
        context: "manual_editor",
        folderSegments: buildQuickVaultNoteFolder(noteScope, activeChapterNumber),
      })
      onVaultNoteSaved?.()
      setNoteTitle("")
      setNoteBody("")
      setNoteStatus("Saved to manuscript notes and the notes workspace.")
    } catch {
      setNoteStatus("Could not save note. Try again.")
    } finally {
      setSavingNote(false)
    }
  }, [activeChapterNumber, bookId, noteBody, noteScope, noteTitle, onBookNoteSaved, onVaultNoteSaved])

  const sendAdvisorMessage = useCallback(async (text: string) => {
    const question = text.trim()
    if (!question || advisorLoading) return
    const nextMessages: AdvisorMessage[] = [...advisorMessages, { role: "user", content: question }]
    setAdvisorMessages(nextMessages)
    setAdvisorInput("")
    setAdvisorError(null)
    setAdvisorLoading(true)
    try {
      const response = await intelligenceApi.advisorMessageStream(
        bookId,
        nextMessages,
        totalChapters ?? Math.max(activeChapterNumber, 1),
        {
          onDelta: (content) => {
            if (!content) return
            setAdvisorMessages((current) => {
              const last = current[current.length - 1]
              if (last?.role === "assistant") {
                return [...current.slice(0, -1), { ...last, content: `${last.content}${content}` }]
              }
              return [...current, { role: "assistant", content }]
            })
          },
        },
      )
      setAdvisorMessages((current) => {
        const last = current[current.length - 1]
        if (last?.role === "assistant") {
          return [...current.slice(0, -1), { role: "assistant", content: response.reply }]
        }
        return [...current, { role: "assistant", content: response.reply }]
      })
    } catch (err) {
      console.error("Advisor stream failed:", err)
      setAdvisorError("The advisor could not respond from the drafting panel.")
    } finally {
      setAdvisorLoading(false)
    }
  }, [activeChapterNumber, advisorLoading, advisorMessages, bookId, totalChapters])

  const handleAdvisorKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      void sendAdvisorMessage(advisorInput)
    }
  }

  return (
    <aside className={`min-w-0 xl:sticky xl:top-[8.25rem] xl:max-h-[calc(100vh-8.25rem)] xl:overflow-y-auto ${isDark ? "border-white/10" : "border-stone-200"}`}>
      <div className={`border-b px-4 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
        <div className="flex items-center gap-7" role="tablist" aria-label="Writing context panels">
          {([
            ["context", "Context"],
            ["advisor", "Advisor"],
            ["notes", "Notes"],
            ["arcs", "Arcs"],
          ] as const).map(([pane, label]) => (
            <button
              key={pane}
              type="button"
              role="tab"
              aria-selected={activeRightPane === pane}
              onClick={() => onOpenRightPane(pane)}
              className={`border-b-2 py-4 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-teal-300/40 ${
                activeRightPane === pane
                  ? isDark
                    ? "border-teal-300 text-white"
                    : "border-teal-600 text-stone-950"
                  : isDark
                    ? "border-transparent text-slate-400 hover:text-slate-200"
                    : "border-transparent text-stone-600 hover:text-stone-900"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {activeRightPane === "character" && selectedCharCard ? (
        <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
          <button
            type="button"
            onClick={onClearSelectedCharCard}
            className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}
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
          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Active characters</p>
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
                  className="flex w-full items-center justify-between gap-3 rounded-sm px-1 py-1 text-left transition hover:bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-teal-300/30"
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

          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Unresolved threads</p>
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

          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Recent events</p>
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

          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Continuity warnings</p>
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

          <div className={`p-5 ${isDark ? "bg-[#151a1a]" : "bg-sky-50/80"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Ask LoreVia</p>
              <span className={`rounded-sm px-2 py-0.5 text-3xs font-semibold ${isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-100 text-sky-700"}`}>Beta</span>
            </div>
            <p className={`mt-4 rounded-sm border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
              Ask LoreVia about continuity, rewrites, or the selected passage using the actions below.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => onOpenRightPane("context")} className={`rounded-sm border px-3 py-1.5 text-xs font-medium ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>Check continuity</button>
              <button type="button" onClick={onTightenSelectedText} className={`rounded-sm border px-3 py-1.5 text-xs font-medium ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>Tighten selection</button>
              <button type="button" onClick={() => onOpenRightPane("advisor")} className={`rounded-sm border px-3 py-1.5 text-xs font-medium ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>Suggest rewrite</button>
            </div>
          </div>
        </>
      ) : null}

      {activeRightPane === "advisor" ? (
        <>
          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter advisor</p>
              <Link href={`/${bookId}/advisor`} className={`text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>Full advisor -&gt;</Link>
            </div>
            <div className={`mt-4 flex max-h-[28rem] flex-col gap-3 overflow-y-auto rounded-sm border p-3 ${isDark ? "border-white/10 bg-black/15" : "border-stone-200 bg-stone-50"}`}>
              {advisorMessages.length === 0 ? (
                <div className={`rounded-sm border p-3 ${isDark ? "border-violet-400/20 bg-violet-400/10 text-slate-200" : "border-violet-100 bg-violet-50 text-stone-700"}`}>
                  <p className="text-sm leading-6">Ask LoreVia from the drafting panel. Recent messages stay here for this book.</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {ADVISOR_STARTERS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => void sendAdvisorMessage(prompt)}
                        className={`rounded-sm border px-2.5 py-1.5 text-left text-xs font-medium ${isDark ? "border-white/10 bg-white/[0.05] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {advisorMessages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`rounded-sm border px-3 py-2.5 ${
                    message.role === "assistant"
                      ? isDark
                        ? "border-white/10 bg-white/[0.04]"
                        : "border-stone-200 bg-white"
                      : isDark
                        ? "ml-6 border-teal-400/25 bg-teal-400/10"
                        : "ml-6 border-teal-100 bg-teal-50"
                  }`}
                >
                  <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${message.role === "assistant" ? isDark ? "text-violet-300" : "text-violet-700" : isDark ? "text-teal-300" : "text-teal-700"}`}>
                    {message.role === "assistant" ? "Advisor" : "You"}
                  </p>
                  <p className={`mt-2 whitespace-pre-wrap text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{message.content}</p>
                </div>
              ))}
              {advisorLoading ? <p className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>Advisor is thinking...</p> : null}
              {advisorError ? <p className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-amber-400/20 bg-amber-400/10 text-amber-200" : "border-amber-200 bg-amber-50 text-amber-700"}`}>{advisorError}</p> : null}
              <div ref={advisorBottomRef} />
            </div>
            <div className={`mt-3 rounded-sm border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
              <textarea
                value={advisorInput}
                onChange={(event) => setAdvisorInput(event.target.value)}
                onKeyDown={handleAdvisorKeyDown}
                rows={3}
                disabled={advisorLoading}
                aria-label="Ask advisor from manuscript"
                placeholder="Ask about this chapter, continuity, transitions, or foreshadowing..."
                className={`w-full resize-none bg-transparent text-sm leading-6 outline-none placeholder:text-slate-500 ${isDark ? "text-slate-100" : "text-stone-800"}`}
              />
              <div className="mt-2 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setAdvisorMessages([])}
                  disabled={advisorMessages.length === 0 || advisorLoading}
                  className={`rounded-sm border px-3 py-1.5 text-xs font-medium disabled:opacity-40 ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={() => void sendAdvisorMessage(advisorInput)}
                  disabled={!advisorInput.trim() || advisorLoading}
                  className={`rounded-sm px-3 py-1.5 text-xs font-semibold disabled:opacity-40 ${isDark ? "bg-violet-500 text-white" : "bg-violet-600 text-white"}`}
                >
                  {advisorLoading ? "Sending..." : "Send"}
                </button>
              </div>
            </div>
          </div>

          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Review data</p>
            <div className="mt-4 space-y-3">
              {suggestions.slice(0, 3).map((suggestion, index) => (
                <div key={`${suggestion.title}-${index}`} className={`rounded-sm border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{suggestion.title}</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{suggestion.description}</p>
                </div>
              ))}
              {suggestions.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Advisor suggestions will appear here after review passes run.</p> : null}
            </div>
          </div>
        </>
      ) : null}

      {activeRightPane === "notes" ? (
        <>
          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>New note</p>
              <Link href={`/${bookId}/notes`} className={`text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>All notes -&gt;</Link>
            </div>
            <div className="mt-4 space-y-3">
              <div className={`grid grid-cols-2 overflow-hidden rounded-sm border p-1 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
                {(["chapter", "book"] as const).map((scope) => (
                  <button
                    key={scope}
                    type="button"
                    onClick={() => setNoteScope(scope)}
                    className={`rounded-sm px-3 py-2 text-xs font-semibold capitalize transition ${
                      noteScope === scope
                        ? isDark
                          ? "bg-teal-400/15 text-teal-100"
                          : "bg-white text-stone-950 shadow-sm"
                        : isDark
                          ? "text-slate-400 hover:text-slate-200"
                          : "text-stone-500 hover:text-stone-800"
                    }`}
                  >
                    {scope === "chapter" ? `Chapter ${activeChapterNumber}` : "Whole book"}
                  </button>
                ))}
              </div>
              <input
                value={noteTitle}
                onChange={(event) => setNoteTitle(event.target.value)}
                placeholder={noteScope === "chapter" ? `Chapter ${activeChapterNumber} note title` : "Book note title"}
                className={`w-full rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/20 text-slate-100 placeholder:text-slate-600 focus:border-teal-300/50" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400 focus:border-teal-500"}`}
              />
              <textarea
                value={noteBody}
                onChange={(event) => setNoteBody(event.target.value)}
                rows={5}
                placeholder="Capture a beat, fix, continuity concern, or draft thought..."
                className={`w-full resize-none rounded-sm border px-3 py-2 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black/20 text-slate-100 placeholder:text-slate-600 focus:border-teal-300/50" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400 focus:border-teal-500"}`}
              />
              <div className="flex items-center justify-between gap-3">
                <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Saves into manuscript notes and the notes workspace.</p>
                <button
                  type="button"
                  onClick={() => void saveQuickNote()}
                  disabled={!noteBody.trim() || savingNote}
                  className={`rounded-sm px-3 py-2 text-xs font-semibold disabled:opacity-40 ${isDark ? "bg-teal-500 text-slate-950" : "bg-teal-600 text-white"}`}
                >
                  {savingNote ? "Saving..." : "Save note"}
                </button>
              </div>
              {noteStatus ? <p role="status" className={`text-xs ${noteStatus.startsWith("Could") ? isDark ? "text-amber-300" : "text-amber-700" : isDark ? "text-teal-200" : "text-teal-700"}`}>{noteStatus}</p> : null}
            </div>
          </div>

          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Notes workspace</p>
              <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{vaultNotes.length}</span>
            </div>
            <div className="mt-4 space-y-3">
              {recentVaultNotes.slice(0, 8).map((note) => (
                <article key={note.id || note.path} className={`rounded-sm border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <p className={`min-w-0 truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.path.split("/").pop()?.replace(/\.md$/i, "") || note.path}</p>
                    <span className={`shrink-0 text-3xs ${isDark ? "text-slate-600" : "text-stone-400"}`}>{new Date(note.updated_at).toLocaleDateString()}</span>
                  </div>
                  <p className={`mt-1 truncate text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{note.path}</p>
                  <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{getNotePreview(note.content)}</p>
                </article>
              ))}
              {vaultNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No notes workspace files saved yet.</p> : null}
            </div>
          </div>

          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter notes</p>
              <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{chapterManualNotes.length}</span>
            </div>
            {chapterAnnotationsCount > 0 ? <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterAnnotationsCount} annotation{chapterAnnotationsCount === 1 ? "" : "s"} anchored to this chapter.</p> : null}
            <div className="mt-4 space-y-3">
              {chapterManualNotes.slice(0, 4).map((note) => (
                <div key={note.id} className={`rounded-sm border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || `Chapter ${activeChapterNumber} note`}</p>
                  <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{getNotePreview(note.body, 110)}</p>
                  <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                </div>
              ))}
              {chapterManualNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No notes saved for this chapter yet.</p> : null}
            </div>
          </div>

          <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Book notes</p>
              <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{generalNotes.length}</span>
            </div>
            <div className="mt-4 space-y-3">
              {generalNotes.slice(0, 3).map((note) => (
                <div key={note.id} className={`rounded-sm border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || "Book note"}</p>
                  <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{getNotePreview(note.body, 110)}</p>
                  <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                </div>
              ))}
              {generalNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No book-level notes saved yet.</p> : null}
            </div>
          </div>
        </>
      ) : null}

      {activeRightPane === "arcs" ? (
        <div className={`border-b p-5 ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Character emotional arc</p>
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
