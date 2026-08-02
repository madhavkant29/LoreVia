import type { Dispatch, MutableRefObject, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import {
  buildAnnotationSelectionAnchor,
  type ManuscriptSelectionAnchor,
  scrollAnnotationRangeIntoView,
} from "@/lib/utils/manuscriptAnnotations"
import type { ManuscriptAnnotation, ManuscriptAnnotationCategory } from "@/types/book"

import type { DraftSurfaceMode, EditorMode, RightPane } from "./manuscriptPage.constants"

type ManuscriptAnnotationSaveInput = {
  annotationId?: string | null
  chapterNumber?: number | null
  category?: string | null
  status?: "open" | "resolved" | null
  visibility?: "shared" | "private" | null
  quote?: string | null
  comment?: string | null
  anchorContextBefore?: string | null
  anchorContextAfter?: string | null
  startOffset?: number | null
  endOffset?: number | null
}

type AnnotationSave = {
  save: (input: ManuscriptAnnotationSaveInput) => Promise<ManuscriptAnnotation | null>
}

type UseManuscriptAnnotationActionsArgs = {
  activeAnnotationId: string | null
  activeChapterNumber: number
  annotationAnchor: ManuscriptSelectionAnchor | null
  annotationCategory: ManuscriptAnnotationCategory
  annotationDraft: string
  annotationRangesRef: MutableRefObject<Map<string, Range>>
  annotationSave: AnnotationSave
  annotationVisibility: "shared" | "private"
  bookId: string
  draftSurfaceMode: DraftSurfaceMode
  pendingAnnotationJumpIdRef: MutableRefObject<string | null>
  selectedChapter: number | null
  selectionMenuAnchorRef: MutableRefObject<ManuscriptSelectionAnchor | null>
  openRightPane: (pane: RightPane) => void
  setActiveAnnotationId: Dispatch<SetStateAction<string | null>>
  setAnnotationActionId: Dispatch<SetStateAction<string | null>>
  setAnnotationAnchor: Dispatch<SetStateAction<ManuscriptSelectionAnchor | null>>
  setAnnotationCategory: Dispatch<SetStateAction<ManuscriptAnnotationCategory>>
  setAnnotationDraft: Dispatch<SetStateAction<string>>
  setAnnotationVisibility: Dispatch<SetStateAction<"shared" | "private">>
  setAnnotations: Dispatch<SetStateAction<ManuscriptAnnotation[]>>
  setDraftSurfaceMode: Dispatch<SetStateAction<DraftSurfaceMode>>
  setEditorMode: Dispatch<SetStateAction<EditorMode>>
  setSelectedChapter: Dispatch<SetStateAction<number | null>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptAnnotationActions({
  activeAnnotationId,
  activeChapterNumber,
  annotationAnchor,
  annotationCategory,
  annotationDraft,
  annotationRangesRef,
  annotationSave,
  annotationVisibility,
  bookId,
  draftSurfaceMode,
  openRightPane,
  pendingAnnotationJumpIdRef,
  selectedChapter,
  selectionMenuAnchorRef,
  setActiveAnnotationId,
  setAnnotationActionId,
  setAnnotationAnchor,
  setAnnotationCategory,
  setAnnotationDraft,
  setAnnotationVisibility,
  setAnnotations,
  setDraftSurfaceMode,
  setEditorMode,
  setSelectedChapter,
  setStatusMessage,
}: UseManuscriptAnnotationActionsArgs) {
  function openAnnotationComposer() {
    if (draftSurfaceMode === "paged") {
      setStatusMessage("Switch back to Draft mode to anchor annotations to the manuscript.")
      return
    }
    const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
    if (!editor) {
      setStatusMessage("Open a chapter first, then select the passage you want to annotate.")
      return
    }
    const anchor = buildAnnotationSelectionAnchor(editor) ?? selectionMenuAnchorRef.current
    if (!anchor) {
      setStatusMessage("Select a passage first, then add an annotation.")
      return
    }
    setAnnotationAnchor(anchor)
    setAnnotationDraft("")
    setAnnotationCategory("general")
    setAnnotationVisibility("shared")
    openRightPane("notes")
  }

  async function saveAnnotation() {
    if (!annotationAnchor || !annotationDraft.trim()) return
    setAnnotationActionId("new")
    try {
      await annotationSave.save({
        chapterNumber: activeChapterNumber,
        category: annotationCategory,
        visibility: annotationVisibility,
        status: "open",
        quote: annotationAnchor.quote,
        comment: annotationDraft.trim(),
        anchorContextBefore: annotationAnchor.anchorContextBefore,
        anchorContextAfter: annotationAnchor.anchorContextAfter,
        startOffset: annotationAnchor.startOffset,
        endOffset: annotationAnchor.endOffset,
      })
    } finally {
      setAnnotationActionId(null)
    }
  }

  async function updateAnnotationStatus(annotation: ManuscriptAnnotation, status: "open" | "resolved") {
    setAnnotationActionId(annotation.id)
    try {
      const updated = await booksApi.saveManuscriptAnnotation(bookId, {
        annotationId: annotation.id,
        status,
      })
      setAnnotations((current) => current.map((item) => item.id === updated.id ? updated : item))
      setStatusMessage(status === "resolved" ? "Annotation resolved." : "Annotation reopened.")
    } finally {
      setAnnotationActionId(null)
    }
  }

  async function removeAnnotation(annotationId: string) {
    setAnnotationActionId(annotationId)
    try {
      await booksApi.deleteManuscriptAnnotation(bookId, annotationId)
      setAnnotations((current) => current.filter((annotation) => annotation.id !== annotationId))
      if (activeAnnotationId === annotationId) {
        setActiveAnnotationId(null)
      }
    } finally {
      setAnnotationActionId(null)
    }
  }

  function jumpToAnnotation(annotation: ManuscriptAnnotation) {
    openRightPane("notes")
    setEditorMode("chapter")
    setDraftSurfaceMode("edit")
    setActiveAnnotationId(annotation.id)
    pendingAnnotationJumpIdRef.current = annotation.id
    if (selectedChapter !== annotation.chapter_number) {
      setSelectedChapter(annotation.chapter_number)
      return
    }
    const range = annotationRangesRef.current.get(annotation.id)
    if (range) {
      scrollAnnotationRangeIntoView(range)
      pendingAnnotationJumpIdRef.current = null
    }
  }

  return {
    jumpToAnnotation,
    openAnnotationComposer,
    removeAnnotation,
    saveAnnotation,
    updateAnnotationStatus,
  }
}
