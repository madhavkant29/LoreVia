import Link from "next/link"

import { SaveStatePill } from "@/components/ui/ResponsivenessStatus"
import type { SaveState } from "@/types/book"
import type { Character } from "@/types/character"

import {
  EditorToolbar,
  RichTextEditor,
} from "./manuscriptPage.dynamic"
import type { buildManuscriptInspectorClasses } from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>
type NoteScope = "chapter" | "book"
type NoteSaveStates = {
  book_note?: SaveState
  vault_note?: SaveState
}

type ManuscriptNoteComposerProps = {
  activeChapterNumber: number
  bookId: string
  characters: Character[]
  inspectorClasses: InspectorClasses
  isDark: boolean
  noteBody: string
  noteBodyText: string
  noteScope: NoteScope
  noteTitle: string
  saveStateByTarget: NoteSaveStates
  savingNote: boolean
  onCharacterClick: (characterName: string) => void
  onNoteBodyChange: (html: string, text: string) => void
  onNoteScopeChange: (scope: NoteScope) => void
  onNoteTitleChange: (value: string) => void
  onSaveNote: () => void
  onSaveWorkspaceVaultNote: () => void
}

export function ManuscriptNoteComposer({
  activeChapterNumber,
  bookId,
  characters,
  inspectorClasses,
  isDark,
  noteBody,
  noteBodyText,
  noteScope,
  noteTitle,
  saveStateByTarget,
  savingNote,
  onCharacterClick,
  onNoteBodyChange,
  onNoteScopeChange,
  onNoteTitleChange,
  onSaveNote,
  onSaveWorkspaceVaultNote,
}: ManuscriptNoteComposerProps) {
  return (
    <div className={inspectorClasses.section}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={inspectorClasses.label}>Notes</p>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Save quick author notes for this chapter or for the whole book.
          </p>
        </div>
        <Link href={`/${bookId}/notes`} className={inspectorClasses.secondaryButton}>All notes</Link>
      </div>

      <div className={`mt-4 inline-flex rounded-sm border p-1 ${isDark ? "border-white/[0.08] bg-[#080b0c]" : "border-stone-200 bg-stone-100"}`}>
        <button
          onClick={() => onNoteScopeChange("chapter")}
          className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${noteScope === "chapter" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-white text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
        >
          Chapter {activeChapterNumber}
        </button>
        <button
          onClick={() => onNoteScopeChange("book")}
          className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${noteScope === "book" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-white text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
        >
          Whole book
        </button>
      </div>

      <div className="mt-4 space-y-3">
        <label className="grid gap-1.5">
          <span className={inspectorClasses.label}>Note title</span>
          <input
            value={noteTitle}
            onChange={(event) => onNoteTitleChange(event.target.value)}
            className={`${inspectorClasses.input} w-full px-3 py-2 text-sm`}
          />
        </label>
        <div className={`overflow-hidden rounded-md border ${isDark ? "border-white/[0.08] bg-[#0a0d0f]" : "border-stone-200 bg-white"}`}>
          <EditorToolbar editorKey="note-editor-modal" isDark={isDark} compact characters={characters} />
          <RichTextEditor
            editorKey="note-editor-modal"
            html={noteBody}
            onChange={onNoteBodyChange}
            onCharacterClick={onCharacterClick}
            className={`min-h-[11rem] px-4 py-4 text-sm leading-7 outline-none ${isDark ? "bg-black/40 text-slate-100" : "bg-white text-stone-900"}`}
          />
        </div>
        <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{noteScope === "chapter" ? `Add a note for chapter ${activeChapterNumber}.` : "Add a book-level note."}</p>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={onSaveNote}
            disabled={savingNote || !noteBodyText.trim()}
            className={`${inspectorClasses.primaryButton} px-4 py-3 text-sm`}
          >
            {savingNote ? "Saving..." : `Save ${noteScope === "chapter" ? "chapter" : "book"} note`}
          </button>
          <button
            type="button"
            onClick={onSaveWorkspaceVaultNote}
            disabled={!noteBodyText.trim()}
            className={`${inspectorClasses.secondaryButton} px-4 py-3 text-sm disabled:opacity-40`}
          >
            Save to workspace notes
          </button>
          <Link
            href={`/${bookId}/notes`}
            className={`${inspectorClasses.secondaryButton} inline-flex items-center justify-center px-4 py-3 text-sm`}
          >
            Open notes workspace
          </Link>
          {saveStateByTarget.book_note ? <SaveStatePill state={saveStateByTarget.book_note} /> : null}
          {saveStateByTarget.vault_note ? <SaveStatePill state={saveStateByTarget.vault_note} /> : null}
        </div>
      </div>
    </div>
  )
}
