import { useRef } from "react"

import { Dialog } from "@/components/ui/Dialog"

type ManuscriptReprocessDialogProps = {
  isDark: boolean
  reprocessing: boolean
  onCancel: () => void
  onConfirm: () => void
}

export function ManuscriptReprocessDialog({
  isDark,
  reprocessing,
  onCancel,
  onConfirm,
}: ManuscriptReprocessDialogProps) {
  const cancelRef = useRef<HTMLButtonElement | null>(null)

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
      size="sm"
      className={isDark ? "border-white/10 bg-[#0f1117] text-slate-100" : "border-stone-200 bg-white text-stone-950"}
      footer={(
        <div className="flex flex-wrap justify-end gap-3">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={reprocessing}
            className={`rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50 ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-700"}`}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={reprocessing}
            className="rounded-md bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {reprocessing ? "Starting..." : "Reserve words and reprocess"}
          </button>
        </div>
      )}
    />
  )
}
