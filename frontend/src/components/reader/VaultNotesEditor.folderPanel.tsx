import { Tooltip } from "@/components/ui/Tooltip"

import { FolderList } from "./VaultNotesEditor.components"
import { parseNotesDragItem, type FolderNode } from "./VaultNotesEditor.helpers"
import { IconPlus, IconSearch, IconSliders } from "./VaultNotesEditor.icons"

export function VaultNotesFolderPanel({
  collapsed,
  dropTargetFolder,
  folderTree,
  isDark,
  notesCount,
  query,
  selectedFolder,
  onCreateFolder,
  onDropNote,
  onDropTargetChange,
  onQueryChange,
  onRootDropTargetLeave,
  onSelectFolder,
  onToggleFolder,
}: {
  collapsed: Record<string, boolean>
  dropTargetFolder: string | null
  folderTree: FolderNode
  isDark: boolean
  notesCount: number
  query: string
  selectedFolder: string | null
  onCreateFolder: (path?: string | null) => void
  onDropNote: (notePath: string, folderPath: string | null) => void
  onDropTargetChange: (path: string | null) => void
  onQueryChange: (value: string) => void
  onRootDropTargetLeave: () => void
  onSelectFolder: (path: string | null) => void
  onToggleFolder: (path: string) => void
}) {
  return (
    <>
      <div className="flex gap-2">
        <label className={`flex min-w-0 flex-1 items-center gap-2 rounded-md border px-3 py-3 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
          <IconSearch />
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            aria-label="Search notes"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
        </label>
        <Tooltip content="Show all folders">
          <button type="button" aria-label="Show all folders" onClick={() => onSelectFolder(null)} className={`flex h-12 w-12 items-center justify-center rounded-md border ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-300 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
            <IconSliders />
          </button>
        </Tooltip>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Folders</p>
        <Tooltip content="Create folder">
          <button type="button" aria-label="Create folder" onClick={() => onCreateFolder()} className={`rounded-full p-1.5 ${isDark ? "text-slate-400 hover:bg-white/[0.06] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}>
            <IconPlus />
          </button>
        </Tooltip>
      </div>

      <div className="mt-3 max-h-[23rem] overflow-auto pr-1">
        <button
          type="button"
          onClick={() => onSelectFolder(null)}
          onDragOver={(event) => {
            if (!parseNotesDragItem(event)) return
            event.preventDefault()
            onDropTargetChange("")
          }}
          onDragLeave={onRootDropTargetLeave}
          onDrop={(event) => {
            const dragItem = parseNotesDragItem(event)
            if (!dragItem) return
            event.preventDefault()
            onDropNote(dragItem.path, null)
          }}
          className={`mb-2 flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
            !selectedFolder
              ? isDark
                ? "bg-emerald-500/12 text-emerald-100"
                : "bg-emerald-50 text-emerald-800"
              : isDark
                ? "text-slate-300 hover:bg-white/[0.04]"
                : "text-stone-700 hover:bg-stone-100"
          } ${dropTargetFolder === "" ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-300") : ""}`}
        >
          <span className="font-medium">All notes</span>
          <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{notesCount}</span>
        </button>
        <FolderList
          node={folderTree}
          activePath={selectedFolder}
          collapsed={collapsed}
          onToggleFolder={onToggleFolder}
          onSelect={onSelectFolder}
          onCreateFolder={(path) => onCreateFolder(path)}
          onDropNote={(notePath, folderPath) => onDropNote(notePath, folderPath)}
          dropTargetPath={dropTargetFolder}
          onDropTargetChange={onDropTargetChange}
          isDark={isDark}
        />
      </div>
    </>
  )
}
