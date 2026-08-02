import type {
  buildManuscriptInspectorClasses,
  FullBookPageMapItem,
} from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>

type ManuscriptPageNavigatorProps = {
  draftSurfaceMode: "edit" | "scroll" | "paged"
  fullBookApproxPages: number
  fullBookPageMap: FullBookPageMapItem[]
  fullBookPageSummaryLabel: string
  gotoPageInput: string
  inspectorClasses: InspectorClasses
  isDark: boolean
  jumpTarget: number | null
  onGotoPageInputChange: (value: string) => void
  onJumpToPage: (page: number) => void
}

export function ManuscriptPageNavigator({
  draftSurfaceMode,
  fullBookApproxPages,
  fullBookPageMap,
  fullBookPageSummaryLabel,
  gotoPageInput,
  inspectorClasses,
  isDark,
  jumpTarget,
  onGotoPageInputChange,
  onJumpToPage,
}: ManuscriptPageNavigatorProps) {
  return (
    <div className={inspectorClasses.section}>
      <div className="flex items-center justify-between gap-3">
        <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Page navigator</p>
        <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{fullBookPageSummaryLabel}</span>
      </div>
      {draftSurfaceMode === "paged" ? <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter jump targets still use draft-length estimates while paged preview is on.</p> : null}
      <div className="mt-3 flex gap-2">
        <input
          type="number"
          min={1}
          max={Math.max(1, fullBookApproxPages)}
          value={gotoPageInput}
          onChange={(event) => onGotoPageInputChange(event.target.value)}
          aria-label="Page number"
          className={`w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
        />
        <button
          onClick={() => {
            const page = parseInt(gotoPageInput)
            if (!Number.isNaN(page)) onJumpToPage(page)
          }}
          className={`rounded-sm px-3 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
        >
          Go
        </button>
      </div>
      <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
        {fullBookPageMap.map((item) => (
          <button
            key={`page-${item.chapter}`}
            onClick={() => onJumpToPage(item.startPage)}
            className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${jumpTarget === item.chapter ? isDark ? "border-teal-400/30 bg-teal-500/10 text-slate-100" : "border-teal-300 bg-teal-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
          >
            <p className="font-semibold">Pages {item.startPage}{item.endPage > item.startPage ? ` to ${item.endPage}` : ""}</p>
            <p className="mt-1 text-xs opacity-75">Chapter {item.chapter} · {item.title}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
