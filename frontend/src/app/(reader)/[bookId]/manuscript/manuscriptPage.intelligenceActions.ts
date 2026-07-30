import type { Dispatch, MutableRefObject, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { capture } from "@/lib/analytics/posthog"
import { readerApi } from "@/lib/api/reader"
import { htmlToPlainText, sanitizeRichTextHtml } from "@/lib/utils/richText"
import type { EmotionalArcOverview } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"
import type { BookDraftMap } from "./manuscriptPage.helpers"

type ManuscriptRouter = {
  replace: (href: string) => void
}

type ManuscriptSearchParams = {
  get: (name: string) => string | null
}

export async function completeEditedFindingDecision(
  bookId: string,
  searchParams: ManuscriptSearchParams,
): Promise<{ findingId: string; source: "continuity" | "revision" } | null> {
  const continuityFindingId = searchParams.get("continuity_finding")
  const findingId = continuityFindingId ?? searchParams.get("finding")
  if (!findingId) return null
  if (continuityFindingId) {
    await booksApi.decideContinuityFinding(bookId, findingId, {
      decision: "resolved",
      action: "manuscript_edit",
      reason: "fixed",
    })
    return { findingId, source: "continuity" }
  }
  await booksApi.decideRevisionFinding(bookId, findingId, {
    decision: "accepted",
    action: "manuscript_edit",
  })
  return { findingId, source: "revision" }
}

type UseManuscriptIntelligenceActionsArgs = {
  activeChapterNumber: number
  bookId: string
  chapterTitle: string
  editorMode: "chapter" | "book"
  html: string
  lastAutoChecksRef: MutableRefObject<Record<number, number>>
  router: ManuscriptRouter
  searchParams: ManuscriptSearchParams
  markDraftDirty: (chapterNumber: number) => void
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setEmotionalArc: Dispatch<SetStateAction<EmotionalArcOverview | null>>
  setHtml: Dispatch<SetStateAction<string>>
  setLogicSelectionText: Dispatch<SetStateAction<string>>
  setPlotThreads: Dispatch<SetStateAction<PlotThread[]>>
  setReview: Dispatch<SetStateAction<EditorialReview | null>>
  setReviewPassages: Dispatch<SetStateAction<EditorialReviewPassage[]>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setSuggestions: Dispatch<SetStateAction<AdvisorSuggestion[]>>
  setSynopsis: Dispatch<SetStateAction<ManuscriptSynopsis | null>>
  setText: Dispatch<SetStateAction<string>>
  setTighteningSelection: Dispatch<SetStateAction<boolean>>
}

export function useManuscriptIntelligenceActions({
  activeChapterNumber,
  bookId,
  chapterTitle,
  editorMode,
  html,
  lastAutoChecksRef,
  markDraftDirty,
  router,
  searchParams,
  setBookDrafts,
  setEmotionalArc,
  setHtml,
  setLogicSelectionText,
  setPlotThreads,
  setReview,
  setReviewPassages,
  setStatusMessage,
  setSuggestions,
  setSynopsis,
  setText,
  setTighteningSelection,
}: UseManuscriptIntelligenceActionsArgs) {
  async function tightenSelectedText() {
    if (editorMode !== "chapter") {
      setStatusMessage("Selected-text tightening is available in chapter view.")
      return
    }
    const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
    if (!editor) {
      setStatusMessage("Click into the chapter editor first, then select the passage you want tightened.")
      return
    }
    const selection = window.getSelection()
    const selectedText = selection?.toString().trim() ?? ""
    if (!selectedText) {
      setStatusMessage("Select the passage you want tightened first.")
      return
    }
    const cachedRange = selection && selection.rangeCount > 0 ? selection.getRangeAt(0).cloneRange() : null
    setLogicSelectionText(selectedText)
    setTighteningSelection(true)
    try {
      const payload = await intelligenceApi.proseTightenStream(
        bookId,
        selectedText,
        activeChapterNumber,
        { onStage: setStatusMessage },
      )
      if (!payload.tightened_text || payload.tightened_text === selectedText) {
        setStatusMessage("No tighter rewrite was needed for the selected passage.")
        return
      }
      if (cachedRange) {
        const liveSelection = window.getSelection()
        liveSelection?.removeAllRanges()
        liveSelection?.addRange(cachedRange)
        document.execCommand("insertText", false, payload.tightened_text)
      }
      const nextHtml = sanitizeRichTextHtml(editor.innerHTML || html)
      const nextText = htmlToPlainText(nextHtml)
      setText(nextText)
      setHtml(nextHtml)
      markDraftDirty(activeChapterNumber)
      setBookDrafts((current) => ({
        ...current,
        [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
      }))
      setStatusMessage(payload.rationale[0] || "Tightened the selected prose.")
    } finally {
      setTighteningSelection(false)
    }
  }

  async function runAutomaticChecks(chapterNum: number, content: string) {
    const now = Date.now()
    const last = lastAutoChecksRef.current[chapterNum] ?? 0
    if (now - last < 300_000) return
    lastAutoChecksRef.current[chapterNum] = now

    const [editorial, suggestionResult, threads, synopsisResult, emotionalArcResult] = await Promise.all([
      intelligenceApi.editorialReview(bookId, content, chapterNum),
      intelligenceApi.advisorSuggestions(bookId),
      readerApi.getPlotThreads(bookId, chapterNum),
      intelligenceApi.synopsis(bookId, "minimal").catch(() => null),
      booksApi.getEmotionalArc(bookId).catch(() => null),
    ])
    setReview(editorial.review)
    setReviewPassages(editorial.retrieved_passages)
    setSuggestions(suggestionResult.suggestions.filter((item) => item.chapter_ref === null || item.chapter_ref <= chapterNum).slice(0, 6))
    setPlotThreads(threads.filter((thread) => thread.status !== "resolved").slice(0, 8))
    if (synopsisResult) setSynopsis(synopsisResult)
    if (emotionalArcResult) setEmotionalArc(emotionalArcResult)
    capture("live_canon_guard_queued", {
      book_id: bookId,
      chapter_number: chapterNum,
      trigger: "meaningful_save",
    })
  }

  async function completeFindingEdit() {
    try {
      const completed = await completeEditedFindingDecision(bookId, searchParams)
      if (!completed) return
      capture("manuscript_edit_from_finding_completed", {
        book_id: bookId,
        finding_id: completed.findingId,
        finding_source: completed.source,
      })
      capture("activation_completed", {
        book_id: bookId,
        finding_id: completed.findingId,
        action: "manuscript_edit",
      })
      router.replace(`/${bookId}/manuscript`)
    } catch {
      // The manuscript save succeeded; attribution must not turn it into a failed save.
    }
  }

  return {
    completeFindingEdit,
    runAutomaticChecks,
    tightenSelectedText,
  }
}
