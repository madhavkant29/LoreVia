import type { Book } from "@/types/book"

export interface EditorProjectCta {
  label: string
  disabled: boolean
  disabledReason: string | null
  saveLocked: boolean
  isProcessing: boolean
}

export function deriveEditorProjectCta(
  book: Book | null | undefined,
  hasUnsavedDrafts: boolean,
): EditorProjectCta {
  if (!book || !book.is_editor_project) {
    return {
      label: "",
      disabled: true,
      disabledReason: null,
      saveLocked: false,
      isProcessing: false,
    }
  }

  const processing = book.processing
  const hasActiveRebuild =
    processing != null &&
    book.status === "processing" &&
    (processing.status === "processing" ||
      processing.stage === "extraction" ||
      processing.stage === "analysis")

  if (hasActiveRebuild) {
    const progress = processing.progress_pct != null ? ` ${Math.round(processing.progress_pct)}%` : ""
    const eta =
      processing.eta_seconds != null && processing.eta_seconds > 0
        ? ` ~${Math.max(1, Math.round(processing.eta_seconds / 60))}min left`
        : ""
    return {
      label: `Processing${progress}${eta}`,
      disabled: true,
      disabledReason: "Reprocessing is already in progress",
      saveLocked: true,
      isProcessing: true,
    }
  }

  const chapters = book.total_chapters ?? 0
  const words = book.total_words ?? 0

  if (chapters === 0 || words === 0) {
    return {
      label: "Reprocess manuscript",
      disabled: true,
      disabledReason: "Save at least one chapter before reprocessing",
      saveLocked: false,
      isProcessing: false,
    }
  }

  if (hasUnsavedDrafts) {
    return {
      label: "Reprocess manuscript",
      disabled: true,
      disabledReason: "Save your changes before reprocessing",
      saveLocked: false,
      isProcessing: false,
    }
  }

  return {
    label: "Reprocess manuscript",
    disabled: false,
    disabledReason: null,
    saveLocked: false,
    isProcessing: false,
  }
}
