import type {
  buildManuscriptInspectorClasses,
  FullBookPageMapItem,
  ManuscriptReferenceItem,
} from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>

type ManuscriptReferencesProps = {
  fullBookPageMap: FullBookPageMapItem[]
  fullBookReferenceItems: ManuscriptReferenceItem[]
  inspectorClasses: InspectorClasses
  isDark: boolean
  onJumpToChapter: (chapterNumber: number) => void
}

export function ManuscriptReferences({
  fullBookPageMap,
  fullBookReferenceItems,
  inspectorClasses,
  isDark,
  onJumpToChapter,
}: ManuscriptReferencesProps) {
  return (
    <div className={inspectorClasses.section}>
      <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>References</p>
      <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
        {fullBookReferenceItems.length > 0 ? fullBookReferenceItems.map((item) => {
          const pageRef = fullBookPageMap.find((entry) => entry.chapter === item.chapter)
          return (
            <button
              key={item.id}
              onClick={() => onJumpToChapter(item.chapter)}
              className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold">Page {pageRef?.startPage ?? "?"}</p>
                <span className={`text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{item.source}</span>
              </div>
              <p className="mt-1 text-xs opacity-75">Chapter {item.chapter} · {item.title}</p>
              <p className="mt-2 text-xs opacity-80">{item.excerpt}</p>
            </button>
          )
        }) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Search hits, continuity passages, and insertion references will appear here.</p>}
      </div>
    </div>
  )
}
