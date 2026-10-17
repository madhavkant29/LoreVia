import type { WorldBuildingDocument } from "@/types/world-building"

import { EmptyState, LoadingState } from "./WorldbuildingWorkspace.components"
import {
  eyebrowClass,
  mutedTextClass,
  panelClass,
  secondaryButtonClass,
} from "./WorldbuildingWorkspace.helpers"

export function WorldbuildingDocumentSidebar({
  documentsLoading,
  documents,
  visibleDocuments,
  selectedDocumentId,
  showAllDocuments,
  isDark,
  onNewDocument,
  onSelectDocument,
  onToggleShowAllDocuments,
}: {
  documentsLoading: boolean
  documents: WorldBuildingDocument[]
  visibleDocuments: WorldBuildingDocument[]
  selectedDocumentId: string | null
  showAllDocuments: boolean
  isDark: boolean
  onNewDocument: () => void
  onSelectDocument: (documentId: string) => void
  onToggleShowAllDocuments: () => void
}) {
  return (
    <aside className={`overflow-hidden rounded-lg border ${panelClass(isDark)}`}>
      <div className={`flex items-center justify-between border-b px-5 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div>
          <p className={eyebrowClass(isDark)}>Documents</p>
          <p className={`mt-2 text-sm ${mutedTextClass(isDark)}`}>Reference docs stay separate from the manuscript.</p>
        </div>
        <button
          type="button"
          onClick={onNewDocument}
          className={`${secondaryButtonClass(isDark)} shrink-0 whitespace-nowrap`}
        >
          New
        </button>
      </div>
      <div className="p-4">
        {documentsLoading ? <LoadingState label="Loading world documents..." isDark={isDark} /> : null}
        {!documentsLoading && documents.length === 0 ? (
          <EmptyState
            title="No world documents yet."
            description="Reference material is missing. Upload a world guide, bible, or notes file so LoreVia can compare canon against the manuscript."
            isDark={isDark}
            action={(
              <button
                type="button"
                onClick={onNewDocument}
                className={secondaryButtonClass(isDark)}
              >
                Start a reference doc
              </button>
            )}
          />
        ) : null}
        <div className="space-y-2">
          <div className="space-y-2 xl:max-h-[1080px] xl:overflow-y-auto xl:pr-1">
            {visibleDocuments.map((document) => {
              const active = document.id === selectedDocumentId
              return (
                <button
                  key={document.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onSelectDocument(document.id)}
                  className={`w-full rounded-md border px-4 py-3 text-left transition ${active
                    ? isDark
                      ? "border-teal-400/35 bg-teal-500/12 text-white"
                      : "border-teal-300 bg-teal-50 text-stone-950"
                    : isDark
                      ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]"
                      : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                >
                  <p className="break-words text-sm font-semibold">{document.title}</p>
                  <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>
                    {(document.word_count ?? 0).toLocaleString()} words - {new Date(document.updated_at).toLocaleDateString()}
                  </p>
                </button>
              )
            })}
          </div>
          {!documentsLoading && (showAllDocuments || documents.length > visibleDocuments.length) ? (
            <button
              type="button"
              onClick={onToggleShowAllDocuments}
              className={`${secondaryButtonClass(isDark)} w-full`}
            >
              {showAllDocuments ? "Show fewer documents" : `Show all ${documents.length} documents`}
            </button>
          ) : null}
        </div>
      </div>
    </aside>
  )
}
