import type { Dispatch, MutableRefObject, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { useOptimisticSave } from "@/lib/hooks/useOptimisticSave"
import type { ManuscriptSelectionAnchor } from "@/lib/utils/manuscriptAnnotations"
import type { ManuscriptAnnotation } from "@/types/book"

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

type UseManuscriptAnnotationSaveOptions = {
  activeChapterNumber: number
  bookId: string
  pendingAnnotationJumpIdRef: MutableRefObject<string | null>
  setActiveAnnotationId: Dispatch<SetStateAction<string | null>>
  setAnnotationAnchor: Dispatch<SetStateAction<ManuscriptSelectionAnchor | null>>
  setAnnotationDraft: Dispatch<SetStateAction<string>>
  setAnnotations: Dispatch<SetStateAction<ManuscriptAnnotation[]>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptAnnotationSave({
  activeChapterNumber,
  bookId,
  pendingAnnotationJumpIdRef,
  setActiveAnnotationId,
  setAnnotationAnchor,
  setAnnotationDraft,
  setAnnotations,
  setStatusMessage,
}: UseManuscriptAnnotationSaveOptions) {
  return useOptimisticSave<ManuscriptAnnotationSaveInput, ManuscriptAnnotation>({
    storageKey: `lorevia:manuscript-annotation:${bookId}:${activeChapterNumber}`,
    metricProperties: { book_id: bookId, save_target: "manuscript_annotation" },
    getDraftId: (input) => input.annotationId ?? `chapter-${input.chapterNumber ?? activeChapterNumber}`,
    save: (input) => booksApi.saveManuscriptAnnotation(bookId, input),
    onSuccess: (saved) => {
      setAnnotations((current) => [saved, ...current.filter((annotation) => annotation.id !== saved.id)])
      setAnnotationAnchor(null)
      setAnnotationDraft("")
      setActiveAnnotationId(saved.id)
      pendingAnnotationJumpIdRef.current = saved.id
      setStatusMessage(`Saved annotation for chapter ${saved.chapter_number ?? activeChapterNumber}.`)
    },
    onError: () => {
      setStatusMessage("Could not save annotation. Your draft is still kept locally.")
    },
  })
}
