import type { BookNote } from "@/types/book"
import { renderRichTextHtml } from "@/lib/utils/richText"

import { InlineLoadingRows } from "./manuscriptPage.loading"
import type { buildManuscriptInspectorClasses } from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>

type ManuscriptNoteListsProps = {
  chapterNotes: BookNote[]
  editNoteBody: string
  editNoteTitle: string
  editingNoteId: string | null
  editingNoteSaving: boolean
  generalNotes: BookNote[]
  inspectorClasses: InspectorClasses
  isDark: boolean
  notesLoading: boolean
  onCancelEditingNote: () => void
  onEditNoteBodyChange: (value: string) => void
  onEditNoteTitleChange: (value: string) => void
  onRemoveNote: (noteId: string) => void
  onSaveEditedNote: () => void
  onStartEditingNote: (note: BookNote) => void
}

type NoteCardProps = {
  editNoteBody: string
  editNoteTitle: string
  editingNoteId: string | null
  editingNoteSaving: boolean
  fallbackTitle: string
  inspectorClasses: InspectorClasses
  isDark: boolean
  note: BookNote
  onCancelEditingNote: () => void
  onEditNoteBodyChange: (value: string) => void
  onEditNoteTitleChange: (value: string) => void
  onRemoveNote: (noteId: string) => void
  onSaveEditedNote: () => void
  onStartEditingNote: (note: BookNote) => void
}

function NoteCard({
  editNoteBody,
  editNoteTitle,
  editingNoteId,
  editingNoteSaving,
  fallbackTitle,
  inspectorClasses,
  isDark,
  note,
  onCancelEditingNote,
  onEditNoteBodyChange,
  onEditNoteTitleChange,
  onRemoveNote,
  onSaveEditedNote,
  onStartEditingNote,
}: NoteCardProps) {
  return (
    <div className={`rounded-md border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
      {editingNoteId === note.id ? (
        <div className="space-y-3">
          <label className="grid gap-1.5">
            <span className={inspectorClasses.label}>Note title</span>
            <input
              value={editNoteTitle}
              onChange={(event) => onEditNoteTitleChange(event.target.value)}
              className={`${inspectorClasses.input} w-full px-3 py-2 text-sm`}
            />
          </label>
          <label className="grid gap-1.5">
            <span className={inspectorClasses.label}>Note content</span>
            <textarea
              value={editNoteBody}
              onChange={(event) => onEditNoteBodyChange(event.target.value)}
              rows={4}
              className={`${inspectorClasses.input} w-full px-3 py-2 text-sm`}
            />
            <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Markdown is supported.</span>
          </label>
          <div className="flex gap-2">
            <button
              onClick={onSaveEditedNote}
              disabled={editingNoteSaving}
              className={inspectorClasses.primaryButton}
            >
              {editingNoteSaving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={onCancelEditingNote}
              className={inspectorClasses.secondaryButton}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{note.title || fallbackTitle}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => onStartEditingNote(note)} className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}>Edit</button>
              <button onClick={() => onRemoveNote(note.id)} className={inspectorClasses.dangerButton}>Delete</button>
            </div>
          </div>
          <div
            className={`note-rich-content mt-3 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}
            dangerouslySetInnerHTML={{ __html: renderRichTextHtml(note.body) }}
          />
        </>
      )}
    </div>
  )
}

export function ManuscriptNoteLists({
  chapterNotes,
  editNoteBody,
  editNoteTitle,
  editingNoteId,
  editingNoteSaving,
  generalNotes,
  inspectorClasses,
  isDark,
  notesLoading,
  onCancelEditingNote,
  onEditNoteBodyChange,
  onEditNoteTitleChange,
  onRemoveNote,
  onSaveEditedNote,
  onStartEditingNote,
}: ManuscriptNoteListsProps) {
  return (
    <>
      <div className={inspectorClasses.section}>
        <p className={inspectorClasses.label}>Chapter-linked notes</p>
        <div className="mt-3 space-y-2">
          {notesLoading ? <InlineLoadingRows label="Loading notes" isDark={isDark} rows={3} /> : null}
          {!notesLoading && chapterNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No notes saved for this chapter yet.</p> : null}
          {chapterNotes.map((note) => (
            <NoteCard
              key={note.id}
              editNoteBody={editNoteBody}
              editNoteTitle={editNoteTitle}
              editingNoteId={editingNoteId}
              editingNoteSaving={editingNoteSaving}
              fallbackTitle={`Chapter ${note.chapter_number} note`}
              inspectorClasses={inspectorClasses}
              isDark={isDark}
              note={note}
              onCancelEditingNote={onCancelEditingNote}
              onEditNoteBodyChange={onEditNoteBodyChange}
              onEditNoteTitleChange={onEditNoteTitleChange}
              onRemoveNote={onRemoveNote}
              onSaveEditedNote={onSaveEditedNote}
              onStartEditingNote={onStartEditingNote}
            />
          ))}
        </div>
      </div>

      <div className={inspectorClasses.section}>
        <p className={inspectorClasses.label}>Whole-book notes</p>
        <div className="mt-3 space-y-2">
          {!notesLoading && generalNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No general notes saved yet.</p> : null}
          {generalNotes.map((note) => (
            <NoteCard
              key={note.id}
              editNoteBody={editNoteBody}
              editNoteTitle={editNoteTitle}
              editingNoteId={editingNoteId}
              editingNoteSaving={editingNoteSaving}
              fallbackTitle="General book note"
              inspectorClasses={inspectorClasses}
              isDark={isDark}
              note={note}
              onCancelEditingNote={onCancelEditingNote}
              onEditNoteBodyChange={onEditNoteBodyChange}
              onEditNoteTitleChange={onEditNoteTitleChange}
              onRemoveNote={onRemoveNote}
              onSaveEditedNote={onSaveEditedNote}
              onStartEditingNote={onStartEditingNote}
            />
          ))}
        </div>
      </div>
    </>
  )
}
