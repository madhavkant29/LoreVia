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
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className={`w-full max-w-md rounded-lg border p-5 ${isDark ? "border-white/10 bg-[#0f1117] text-slate-100" : "border-stone-200 bg-white text-stone-950"}`}>
        <h2 className="text-lg font-semibold">Reprocess manuscript?</h2>
        <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          Reprocessing rebuilds the Character Bible, relationships, plot threads, summaries, world/lore data, and continuity signals from the saved manuscript. This will consume 1 book upload. Continue?
        </p>
        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button
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
            {reprocessing ? "Starting..." : "Reprocess and use 1 upload"}
          </button>
        </div>
      </div>
    </div>
  )
}
