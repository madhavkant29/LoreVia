import Link from "next/link"

import type { ManuscriptWorkspaceTree, VaultNote } from "@/types/book"

import { InfoLine, PanelCard } from "./VaultNotesEditor.components"
import { formatTimestamp, inferNoteType, noteFolder } from "./VaultNotesEditor.helpers"
import { IconArrowRight, IconPencil } from "./VaultNotesEditor.icons"

export function VaultNotePropertiesPanel({
  bookId,
  busy,
  editedFolder,
  editedTitle,
  isDark,
  sceneChapterNumber,
  sceneChapters,
  sceneSending,
  selectedContent,
  selectedNote,
  onDeleteCurrent,
  onEditedFolderChange,
  onEditedTitleChange,
  onMoveCurrent,
  onSceneChapterNumberChange,
  onSendToScene,
  onSwitchToEdit,
}: {
  bookId: string
  busy: boolean
  editedFolder: string
  editedTitle: string
  isDark: boolean
  sceneChapterNumber: number | null
  sceneChapters: ManuscriptWorkspaceTree["chapters"]
  sceneSending: boolean
  selectedContent: string
  selectedNote: VaultNote | null
  onDeleteCurrent: () => void
  onEditedFolderChange: (value: string) => void
  onEditedTitleChange: (value: string) => void
  onMoveCurrent: () => void
  onSceneChapterNumberChange: (value: number | null) => void
  onSendToScene: () => void
  onSwitchToEdit: () => void
}) {
  return (
    <PanelCard
      isDark={isDark}
      title="Properties"
      action={(
        <button
          type="button"
          onClick={onSwitchToEdit}
          className={`inline-flex h-8 w-8 items-center justify-center rounded-sm ${isDark ? "bg-white/[0.05] text-slate-300 hover:bg-white/[0.08] hover:text-white" : "bg-stone-100 text-stone-700 hover:bg-stone-200"}`}
          title="Edit note"
        >
          <IconPencil />
        </button>
      )}
    >
      <InfoLine label="Folder" value={selectedNote ? noteFolder(selectedNote.path) || "Root" : "-"} isDark={isDark} />
      <InfoLine label="Created" value={selectedNote ? formatTimestamp(selectedNote.created_at) : "-"} isDark={isDark} />
      <InfoLine label="Updated" value={selectedNote ? formatTimestamp(selectedNote.updated_at) : "-"} isDark={isDark} />
      <InfoLine label="Type" value={selectedNote ? inferNoteType(selectedNote.path) : "-"} isDark={isDark} tone />
      <InfoLine label="Status" value={selectedContent.trim() ? "Active" : "Draft"} isDark={isDark} activeDot />

      <div className="mt-4 grid gap-3">
        <label className="space-y-2">
          <span className={`text-xs font-semibold uppercase tracking-wide ${isDark ? "text-slate-400" : "text-stone-600"}`}>Folder path</span>
          <input
            disabled={busy}
            value={editedFolder}
            onChange={(event) => onEditedFolderChange(event.target.value)}
            className={`w-full rounded-sm border px-3 py-2.5 text-sm outline-none ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
          />
        </label>
        <label className="space-y-2">
          <span className={`text-xs font-semibold uppercase tracking-wide ${isDark ? "text-slate-400" : "text-stone-600"}`}>File title</span>
          <input
            disabled={busy}
            value={editedTitle}
            onChange={(event) => onEditedTitleChange(event.target.value)}
            className={`w-full rounded-sm border px-3 py-2.5 text-sm outline-none ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
          />
        </label>
        <div className="flex gap-2">
          <button type="button" onClick={onMoveCurrent} disabled={busy || !selectedNote || !editedTitle.trim()} className="min-w-0 flex-1 rounded-sm bg-[#1f615d] px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
            Update path
          </button>
          <button type="button" onClick={onDeleteCurrent} disabled={busy || !selectedNote} className={`shrink-0 rounded-sm px-3 py-2.5 text-sm font-medium ${isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"}`}>
            Delete
          </button>
        </div>
        <div className={`overflow-hidden rounded-sm border p-3 ${isDark ? "border-white/[0.08] bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
          <p className={`text-xs font-semibold uppercase tracking-wide ${isDark ? "text-slate-400" : "text-stone-600"}`}>Send to scenes</p>
          <div className="mt-3 flex gap-2">
            <select
              aria-label="Scene destination"
              value={sceneChapterNumber ?? ""}
              onChange={(event) => onSceneChapterNumberChange(event.target.value ? Number(event.target.value) : null)}
              className={`min-w-0 flex-1 rounded-sm border px-3 py-2.5 text-sm outline-none ${isDark ? "border-white/[0.08] bg-[#09111f] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            >
              <option value="">Scenes inbox</option>
              {sceneChapters.map((chapter) => (
                <option key={chapter.chapter_number} value={chapter.chapter_number}>
                  Chapter {chapter.chapter_number}: {chapter.title || "Untitled"}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={onSendToScene}
              disabled={!selectedNote || sceneSending}
              className="shrink-0 rounded-sm bg-[#1f615d] px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              {sceneSending ? "Sending..." : "Send"}
            </button>
          </div>
          <Link
            href={`/${bookId}/scenes`}
            className={`mt-3 inline-flex items-center gap-2 text-sm font-medium ${isDark ? "text-sky-300 hover:text-sky-200" : "text-sky-700 hover:text-sky-800"}`}
          >
            Open scene workspace
            <IconArrowRight />
          </Link>
        </div>
      </div>
    </PanelCard>
  )
}
