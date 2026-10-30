"use client"

import { useEffect, useState } from "react"
import Link from "next/link"

import { Dialog } from "@/components/ui/Dialog"
import type { Book } from "@/types/book"

export function reviewReadyPromptKey(book: Pick<Book, "id" | "status" | "processing"> | null, hasReviewMaterial: boolean): string | null {
  const runId = book?.processing?.processing_run_id
  if (!hasReviewMaterial || book?.status !== "ready" || book.processing?.is_fully_ready !== true || !runId) return null
  return `lorevia:review-ready:${book.id}:${runId}`
}

export function ReviewReadyDialog({ book, bookId, enabled, hasReviewMaterial }: { book: Book | null; bookId: string; enabled: boolean; hasReviewMaterial: boolean }) {
  const key = enabled ? reviewReadyPromptKey(book, hasReviewMaterial) : null
  const [openKey, setOpenKey] = useState<string | null>(null)

  useEffect(() => {
    if (!key) return
    try {
      if (window.localStorage.getItem(key)) return
    } catch {
      // A privacy setting must not hide the review destinations entirely.
    }
    setOpenKey(key)
  }, [key])

  function markSeen() {
    if (key) {
      try {
        window.localStorage.setItem(key, "dismissed")
      } catch {
        // A blocked storage API should not trap the reader in the dialog.
      }
    }
  }

  function dismiss() {
    markSeen()
    setOpenKey(null)
  }

  return (
    <Dialog
      open={Boolean(key && openKey === key)}
      onClose={dismiss}
      title="Your manuscript is ready to review"
      description="Explore suggested story checks and chapter reports. These are review aids, not proof that something is wrong."
      footer={<div className="flex flex-wrap gap-3">
        <Link className="app-button-primary" href={`/${bookId}/advisor?tab=scan`} onClick={markSeen}>Recommended checks</Link>
        <Link className="app-button-secondary" href={`/${bookId}/analysis?view=chapters`} onClick={markSeen}>Chapter reports</Link>
        <button type="button" className="app-button-secondary" onClick={dismiss}>Maybe later</button>
      </div>}
    />
  )
}
