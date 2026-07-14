import dynamic from "next/dynamic"

import { Skeleton } from "@/components/ui/Skeleton"
import type { VaultGraph, VaultNote } from "@/types/book"

import { noteTitle } from "./VaultNotesEditor.helpers"

const GraphViewer = dynamic(
  () => import("./GraphViewer").then((module) => module.GraphViewer),
  {
    ssr: false,
    loading: () => <Skeleton variant="card" className="min-h-[34rem] rounded-lg" />,
  }
)

export function VaultNotesGraphModal({
  graph,
  isDark,
  selectedNote,
  selectedPath,
  onClose,
  onOpenPath,
}: {
  graph: VaultGraph
  isDark: boolean
  selectedNote: VaultNote | null
  selectedPath: string | null
  onClose: () => void
  onOpenPath: (path: string) => void
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-stretch justify-center bg-black/70 p-3 sm:p-5">
      <div className={`flex h-full w-full max-w-[96rem] flex-col overflow-hidden rounded-lg border ${isDark ? "border-white/10 bg-[#08111d]" : "border-stone-200 bg-[#f4f7fb]"}`}>
        <div className={`flex flex-col gap-3 border-b px-5 py-4 sm:flex-row sm:items-center sm:justify-between ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/70"}`}>
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Vault graph</p>
            <h3 className={`mt-1 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Vault graph view</h3>
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Pan, zoom, drag nodes, and open linked notes directly from the site.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {selectedNote ? (
              <div className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                Current: {noteTitle(selectedNote.path)}
              </div>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white"}`}
            >
              Close
            </button>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-h-0 p-4">
            <GraphViewer
              graph={graph}
              selectedPath={selectedPath}
              onOpenNote={onOpenPath}
              isDark={isDark}
              heightClassName="h-[calc(100vh-13rem)] min-h-[34rem]"
            />
          </div>

          <aside className={`border-l p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/65"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>How it works</p>
            <div className={`mt-4 space-y-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              <p>Drag nodes to shape the map. Your layout stays saved in the browser.</p>
              <p>Hovering a note spotlights its neighborhood so relationships are easier to trace.</p>
              <p>Labels fade as you zoom out, then return when you move back in closer.</p>
              <p>Click any node to jump directly into that note.</p>
            </div>

            {selectedNote ? (
              <div className={`mt-6 rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Selected note</p>
                <h4 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{noteTitle(selectedNote.path)}</h4>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{selectedNote.path}</p>
                <button
                  type="button"
                  onClick={onClose}
                  className={`mt-4 inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}
                >
                  Open in editor
                </button>
              </div>
            ) : null}
          </aside>
        </div>
      </div>
    </div>
  )
}
