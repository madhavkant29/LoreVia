import { useCallback, useEffect, useRef, useState } from "react"

import { Dialog } from "@/components/ui/Dialog"
import { booksApi } from "@/lib/api/books"
import type { ManuscriptReprocessPreflight } from "@/types/book"

type ManuscriptReprocessDialogProps = {
  bookId: string
  isDark: boolean
  reprocessing: boolean
  onCancel: () => void
  onConfirm: (previewFingerprint: string) => void
}

export function ManuscriptReprocessDialog({
  bookId,
  isDark,
  reprocessing,
  onCancel,
  onConfirm,
}: ManuscriptReprocessDialogProps) {
  const cancelRef = useRef<HTMLButtonElement | null>(null)
  const [preflight, setPreflight] = useState<ManuscriptReprocessPreflight | null>(null)
  const [preflightError, setPreflightError] = useState(false)
  const [preflightLoading, setPreflightLoading] = useState(true)
  const loadPreflight = useCallback(async () => {
    setPreflightLoading(true)
    setPreflightError(false)
    setPreflight(null)
    try {
      setPreflight(await booksApi.previewManuscriptReprocess(bookId))
    } catch {
      setPreflightError(true)
    } finally {
      setPreflightLoading(false)
    }
  }, [bookId])

  useEffect(() => { void loadPreflight() }, [loadPreflight])
  const canStart = Boolean(preflight?.ready && preflight.preview_fingerprint && !preflightLoading && !reprocessing)

  return (
    <Dialog
      open
      onClose={() => {
        if (!reprocessing) onCancel()
      }}
      title="Reprocess manuscript?"
      description="Reprocessing rebuilds the Character Bible, relationships, plot threads, summaries, world/lore data, and continuity signals from the saved manuscript. The manuscript's full word count is reserved first; only chapters that finish successfully are charged, and unused reservations are restored after failure or cancellation. Continue?"
      initialFocusRef={cancelRef}
      closeOnOutside={!reprocessing}
      size="md"
      className={isDark ? "border-white/10 bg-[#0f1117] text-slate-100" : "border-stone-200 bg-white text-stone-950"}
      footer={(
        <div className="flex flex-wrap justify-end gap-3">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={reprocessing} className={`rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50 ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-700"}`}>
            Cancel
          </button>
          <button type="button" onClick={() => { if (canStart && preflight?.preview_fingerprint) onConfirm(preflight.preview_fingerprint) }} disabled={!canStart} className="rounded-md bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {reprocessing ? "Starting..." : "Reserve words and reprocess"}
          </button>
        </div>
      )}
    >
      <div className="space-y-3 text-sm">
        {preflightLoading ? <p role="status">Checking saved chapter sources and protected records...</p> : null}
        {preflightError ? <p role="alert">Preflight could not be loaded. No words were reserved.</p> : null}
        {preflight ? (
          <>
            <p>{preflight.chapters_total} chapters · {preflight.processed_words_to_reserve.toLocaleString()} processed words to reserve</p>
            <p>{preflight.protected_characters} protected characters will be kept; {preflight.replaceable_characters} generated character records may be replaced.</p>
            {preflight.missing_source_chapters.length ? <p role="alert">Stored source missing for chapters {preflight.missing_source_chapters.join(", ")}.</p> : null}
            {preflight.blockers.map((blocker) => <p role="alert" key={blocker}>{blocker}</p>)}
            <p>{preflight.limitation}</p>
          </>
        ) : null}
        <button type="button" onClick={() => void loadPreflight()} disabled={preflightLoading || reprocessing} className={`rounded-md border px-3 py-2 text-sm disabled:opacity-50 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          Refresh preflight
        </button>
      </div>
    </Dialog>
  )
}
