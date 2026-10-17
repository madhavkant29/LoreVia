"use client"

import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from "react"

import { booksApi } from "@/lib/api/books"
import type { ManuscriptWorkspaceTree, VaultGraph, VaultNoteRelations, VaultNote } from "@/types/book"
import type { Character } from "@/types/character"
import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"
import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { usePromptDialog } from "@/components/ui/PromptDialog"
import { migrateVaultStorage } from "@/lib/utils/vaultStorageMigration"
import {
  buildFolderTree,
  buildNoteMap,
  filterVaultNotes,
  getDisplayedVaultNotes,
  getFavoriteVaultNotes,
  getRecentVaultMentions,
  getSelectedNoteContent,
  getSelectedOutgoingLinks,
  getSelectedVaultNote,
  getVaultPreviewNodes,
  loadCustomFolders,
  loadFavoriteMap,
  noteFolder,
  noteTitle,
} from "./VaultNotesEditor.helpers"
import { useVaultNoteSceneSender, useVaultNotesLocalStoragePersistence, useVaultNotesMarkdownToolbar, useVaultNotesSelectionMenu } from "./VaultNotesEditor.hooks"
import { WorkspaceSidePanel } from "@/components/ui/WorkspaceSidePanel"
import { useVaultNotesAutosave } from "./VaultNotesEditor.autosave"
import { useVaultNotesEditorActions } from "./VaultNotesEditor.actions"
import { VaultNotesFolderPanel } from "./VaultNotesEditor.folderPanel"
import { VaultNotesGraphModal } from "./VaultNotesEditor.graphModal"
import { VaultNotesList } from "./VaultNotesEditor.notesList"
import { VaultNotePropertiesPanel } from "./VaultNotesEditor.properties"
import { VaultNoteRelatedPanels } from "./VaultNotesEditor.relatedPanels"
import { VaultNotesSelectionMenu } from "./VaultNotesEditor.selectionMenu"
import { VaultNotesSidebarShell } from "./VaultNotesEditor.sidebarShell"
import { VaultNotesTopbar } from "./VaultNotesEditor.topbar"
import { VaultNoteWorkspace } from "./VaultNotesEditor.workspace"

type NotesView = "recent" | "favorites"
type EditorMode = "edit" | "preview" | "split"

export function VaultNotesEditor({
  bookId,
  bookTitle,
  initialNotes,
  initialGraph,
  isDark,
}: {
  bookId: string
  bookTitle: string
  initialNotes: VaultNote[]
  initialGraph: VaultGraph
  isDark: boolean
}) {
  migrateVaultStorage(bookId)

  const [notes, setNotes] = useState<VaultNote[]>(initialNotes)
  const [graph, setGraph] = useState<VaultGraph>(initialGraph)
  const [relations, setRelations] = useState<VaultNoteRelations | null>(null)
  const [selectedPath, setSelectedPath] = useState<string | null>(initialNotes[0]?.path ?? null)
  const [selectedFolder, setSelectedFolder] = useState<string | null>(noteFolder(initialNotes[0]?.path ?? ""))
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [favorites, setFavorites] = useState<Record<string, boolean>>(() => loadFavoriteMap())
  const [query, setQuery] = useState("")
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [customFolders, setCustomFolders] = useState<string[]>(() => loadCustomFolders(bookId))
  const [dropTargetFolder, setDropTargetFolder] = useState<string | null>(null)
  const [mode, setMode] = useState<EditorMode>("edit")
  const [notesView, setNotesView] = useState<NotesView>("recent")
  const [status, setStatus] = useState<string | null>(null)
  const [editedFolder, setEditedFolder] = useState("")
  const [editedTitle, setEditedTitle] = useState("")
  const [busy, setBusy] = useState(false)
  const [graphExpanded, setGraphExpanded] = useState(false)
  const [workspaceTree, setWorkspaceTree] = useState<ManuscriptWorkspaceTree | null>(null)
  const [sceneChapterNumber, setSceneChapterNumber] = useState<number | null>(null)
  const [findWithinNote, setFindWithinNote] = useState("")
  const [replaceWithinNote, setReplaceWithinNote] = useState("")
  const [secondaryPanelsEnabled, setSecondaryPanelsEnabled] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [detailsError, setDetailsError] = useState(false)
  const [relationsError, setRelationsError] = useState(false)
  const [detailsRetry, setDetailsRetry] = useState(0)
  const [firstLineIndent, setFirstLineIndent] = useState(false)
  const deferredQuery = useDeferredValue(query)
  const latestDraftRef = useRef<Record<string, string>>({})
  const importInputRef = useRef<HTMLInputElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const confirm = useConfirmDialog()
  const prompt = usePromptDialog()

  useEffect(() => {
    setNotes(initialNotes)
    setSelectedPath((current) => {
      if (current && initialNotes.some((note) => note.path === current)) return current
      return initialNotes[0]?.path ?? null
    })
  }, [initialNotes])

  useEffect(() => {
    setGraph(initialGraph)
  }, [initialGraph])

  useEffect(() => {
    setCustomFolders(loadCustomFolders(bookId))
  }, [bookId])

  useVaultNotesLocalStoragePersistence({
    bookId,
    customFolders,
    favorites,
  })

  useEffect(() => {
    if (!secondaryPanelsEnabled || !inspectorOpen) return

    let active = true
    setDetailsError(false)
    void booksApi.getWorkspaceTree(bookId)
      .then((value) => {
        if (!active) return
        setWorkspaceTree(value)
        setSceneChapterNumber((current) => current ?? value.chapters[0]?.chapter_number ?? null)
      })
      .catch(() => {
        if (!active) return
        setDetailsError(true)
      })
    return () => {
      active = false
    }
  }, [bookId, inspectorOpen, secondaryPanelsEnabled, detailsRetry])

  const noteMap = useMemo(() => buildNoteMap(notes), [notes])
  const folderTree = useMemo(
    () => buildFolderTree(notes.map((note) => note.path), customFolders),
    [customFolders, notes]
  )
  const selectedNote = getSelectedVaultNote(noteMap, selectedPath)
  const selectedContent = getSelectedNoteContent(selectedNote, drafts)
  const selectedOutgoingLinks = useMemo(
    () => getSelectedOutgoingLinks(graph.edges, selectedPath),
    [graph.edges, selectedPath]
  )

  const filteredNotes = useMemo(
    () => filterVaultNotes(notes, drafts, selectedFolder, deferredQuery),
    [deferredQuery, drafts, notes, selectedFolder]
  )

  const favoriteNotes = useMemo(
    () => getFavoriteVaultNotes(filteredNotes, favorites),
    [favorites, filteredNotes]
  )
  const displayedNotes = getDisplayedVaultNotes(notesView, filteredNotes, favoriteNotes)
  useEffect(() => {
    if (!selectedNote || !secondaryPanelsEnabled || !inspectorOpen) {
      setRelations(null)
      return
    }

    const currentFolder = noteFolder(selectedNote.path)
    setSelectedFolder((previous) => {
      if (!previous) return currentFolder
      if (currentFolder === previous || currentFolder.startsWith(`${previous}/`)) return previous
      return currentFolder
    })

    let cancelled = false
    setRelations(null)
    setRelationsError(false)
    void booksApi.getVaultNoteRelations(bookId, selectedNote.path)
      .then((value) => {
        if (!cancelled) setRelations(value)
      })
      .catch(() => {
        if (!cancelled) setRelationsError(true)
      })
    return () => {
      cancelled = true
    }
  }, [bookId, inspectorOpen, secondaryPanelsEnabled, selectedNote, detailsRetry])

  useEffect(() => {
    if (!selectedPath) {
      setEditedFolder("")
      setEditedTitle("")
      return
    }
    setEditedFolder(noteFolder(selectedPath))
    setEditedTitle(noteTitle(selectedPath))
  }, [selectedPath])

  const autosave = useVaultNotesAutosave({ bookId, notes, drafts, latestDraftRef, busy, setNotes, setDrafts })
  const { saveNote, updateDraft } = autosave

  const {
    copyCurrentReference,
    createFolder,
    createNote,
    deleteCurrent,
    duplicateCurrent,
    exportNotes,
    importNotes,
    moveCurrent,
    moveNoteToFolder,
    openNote,
  } = useVaultNotesEditorActions({
    bookId,
    bookTitle,
    busy,
    confirm,
    drafts,
    editedFolder,
    editedTitle,
    latestDraftRef,
    noteMap,
    notes,
    prompt,
    selectedContent,
    selectedFolder,
    selectedNote,
    selectedPath,
    setBusy,
    setCollapsed,
    setCustomFolders,
    setDrafts,
    setDropTargetFolder,
    setFavorites,
    setGraph,
    setMode,
    setNotes,
    settlePath: autosave.settlePath,
    forgetPath: autosave.forgetPath,
    flushAll: autosave.flushAll,
    setSelectedFolder,
    setSelectedPath,
    setStatus,
  })

  const toolbarButtons = useVaultNotesMarkdownToolbar({
    drafts,
    selectedNote,
    textareaRef,
    updateDraft,
  })

  const isFavorite = selectedNote ? Boolean(favorites[selectedNote.path]) : false
  const sceneChapters = workspaceTree?.chapters ?? []
  const recentMentions = useMemo(() => getRecentVaultMentions(relations), [relations])
  const previewNodes = useMemo(
    () => getVaultPreviewNodes(selectedOutgoingLinks, recentMentions),
    [recentMentions, selectedOutgoingLinks],
  )
  const { sceneSending, sendToScene } = useVaultNoteSceneSender({
    bookId,
    sceneChapterNumber,
    selectedContent,
    selectedNote,
    setStatus,
  })

  const replaceInSelectedNote = () => {
    if (!selectedNote || !findWithinNote.trim()) return
    const currentValue = drafts[selectedNote.path] ?? selectedNote.content
    updateDraft(selectedNote.path, currentValue.split(findWithinNote).join(replaceWithinNote))
    setStatus("Updated note draft with replacements")
  }

  const {
    addCharacterOpen,
    addCharacterText,
    notesSelectionMenu,
    openAddCharacterFromNotes,
    setAddCharacterOpen,
    syncNotesSelectionMenu,
  } = useVaultNotesSelectionMenu(textareaRef)

  const handleCharacterCreated = (character: Character) => {
    setStatus(`Character "${character.name}" added to the story bible.`)
  }

  return (
    <div
      className={`border-y py-4 ${
        isDark
          ? "border-white/[0.08] bg-[#071211]"
          : "border-stone-200 bg-white"
      }`}
    >
      <VaultNotesTopbar
        busy={busy || autosave.leaving}
        importInputRef={importInputRef}
        isDark={isDark}
        inspectorOpen={inspectorOpen}
        onOpenLibrary={() => setLibraryOpen(true)}
        selectedNoteAvailable={Boolean(selectedNote)}
        onCreateNote={() => void createNote()}
        onDuplicateCurrent={() => void duplicateCurrent()}
        onExportNotes={() => void exportNotes()}
        onImportNotes={(file) => void importNotes(file)}
        onToggleInspector={() => {
          const nextOpen = !inspectorOpen
          setInspectorOpen(nextOpen)
          if (nextOpen && !secondaryPanelsEnabled) {
            startTransition(() => setSecondaryPanelsEnabled(true))
          }
        }}
      />

      {autosave.recovered && autosave.dirty ? <p role="status" className="mt-3 text-sm">Recovered unsaved notes from this browser tab. Review them, then <button type="button" disabled={busy || autosave.leaving} className="min-h-10 underline" onClick={() => void autosave.flushAll()}>Save recovered notes</button>.</p> : null}
      {autosave.backupUnavailable && autosave.dirty ? <p role="alert" className="mt-3 text-sm">Tab backup is unavailable. Keep this page open until your notes are saved.</p> : null}
      {status ? <p role={/could not|already uses|cannot/i.test(status) ? "alert" : "status"} className="mt-3 break-words text-sm">{status}</p> : null}
      {Object.entries(autosave.errors).map(([path, message]) => <div key={path} role="alert" className="mt-3 flex flex-wrap items-center gap-3 border-l-2 border-rose-400 pl-3 text-sm"><span className="min-w-0 break-words">{message}</span><button type="button" disabled={busy || autosave.saving[path]} onClick={() => void autosave.saveNote(path, latestDraftRef.current[path])} className="min-h-10 underline">Retry save</button></div>)}
      <div className={`mt-5 grid gap-4 ${inspectorOpen ? "xl:grid-cols-[16rem_minmax(0,1fr)_18rem]" : "xl:grid-cols-[18rem_minmax(0,1fr)]"}`}>
        <div className={libraryOpen ? "min-w-0" : "hidden min-w-0 xl:block"}>
        <WorkspaceSidePanel title="Note library" side="left" open={libraryOpen} onClose={() => setLibraryOpen(false)}>
        <fieldset disabled={busy || autosave.leaving} className="min-w-0">
        <VaultNotesSidebarShell
          bookTitle={bookTitle}
          busy={busy}
          isDark={isDark}
          onCreateNote={() => void createNote()}
        >
            <VaultNotesFolderPanel
              collapsed={collapsed}
              dropTargetFolder={dropTargetFolder}
              folderTree={folderTree}
              isDark={isDark}
              notesCount={notes.length}
              query={query}
              selectedFolder={selectedFolder}
              onCreateFolder={(path) => void createFolder(path)}
              onDropNote={(notePath, folderPath) => void moveNoteToFolder(notePath, folderPath)}
              onDropTargetChange={setDropTargetFolder}
              onQueryChange={setQuery}
              onRootDropTargetLeave={() => setDropTargetFolder((current) => (current === "" ? null : current))}
              onSelectFolder={setSelectedFolder}
              onToggleFolder={(path) => setCollapsed((current) => ({ ...current, [path]: !current[path] }))}
            />

            <VaultNotesList
              displayedNotes={displayedNotes}
              isDark={isDark}
              notesView={notesView}
              selectedPath={selectedPath}
              onSelectNote={(path) => { setSelectedPath(path); setLibraryOpen(false) }}
              onViewChange={setNotesView}
            />
        </VaultNotesSidebarShell>
        </fieldset>
        </WorkspaceSidePanel>
        </div>

        <div className="min-w-0">
        <VaultNoteWorkspace
          bookId={bookId}
          findWithinNote={findWithinNote}
          firstLineIndent={firstLineIndent}
          isDark={isDark}
          isFavorite={isFavorite}
          mode={mode}
          notes={notes}
          replaceWithinNote={replaceWithinNote}
          selectedContent={selectedContent}
          selectedNote={selectedNote}
          status={selectedNote ? autosave.errors[selectedNote.path] ? "Save failed" : autosave.saving[selectedNote.path] ? "Saving…" : drafts[selectedNote.path] !== undefined && drafts[selectedNote.path] !== selectedNote.content ? "Unsaved changes" : null : null}
          busy={busy || autosave.leaving}
          textareaRef={textareaRef}
          toolbarButtons={toolbarButtons}
          onCopyReference={() => void copyCurrentReference()}
          onFavoriteToggle={() => selectedNote ? setFavorites((current) => ({ ...current, [selectedNote.path]: !current[selectedNote.path] })) : undefined}
          onFindWithinNoteChange={setFindWithinNote}
          onFirstLineIndentChange={setFirstLineIndent}
          onModeChange={setMode}
          onOpenGraph={() => setGraphExpanded(true)}
          onOpenNote={openNote}
          onReplaceInSelectedNote={replaceInSelectedNote}
          onReplaceWithinNoteChange={setReplaceWithinNote}
          onSaveNow={() => selectedNote ? void saveNote(selectedNote.path, selectedContent) : undefined}
          onSyncSelectionMenu={syncNotesSelectionMenu}
          onUpdateDraft={updateDraft}
        />
        </div>

        {inspectorOpen ? (
          <WorkspaceSidePanel title="Note details" side="right" onClose={() => setInspectorOpen(false)}>
            <div className="space-y-4 p-3 xl:p-0">
              {status ? <p role={/could not|already uses|cannot/i.test(status) ? "alert" : "status"} className="break-words text-sm xl:hidden">{status}</p> : null}
              {Object.values(autosave.errors).length ? <div role="alert" className="text-sm xl:hidden">{Object.values(autosave.errors).map((message) => <p key={message} className="break-words">{message}</p>)}<button type="button" disabled={busy || autosave.leaving} onClick={() => void autosave.flushAll()} className="min-h-10 underline">Retry save</button></div> : null}
              {detailsError || relationsError ? <div role="alert" className="border-l-2 border-amber-400 pl-3 text-sm"><p>Some note details could not load.</p><button type="button" className="min-h-10 underline" onClick={() => setDetailsRetry((value) => value + 1)}>Retry note details</button></div> : null}
              <VaultNotePropertiesPanel
            bookId={bookId}
            busy={busy}
            editedFolder={editedFolder}
            editedTitle={editedTitle}
            isDark={isDark}
            sceneChapterNumber={sceneChapterNumber}
            sceneChapters={sceneChapters}
            sceneSending={sceneSending}
            selectedContent={selectedContent}
            selectedNote={selectedNote}
            onDeleteCurrent={() => void deleteCurrent()}
            onEditedFolderChange={setEditedFolder}
            onEditedTitleChange={setEditedTitle}
            onMoveCurrent={() => void moveCurrent()}
            onSceneChapterNumberChange={setSceneChapterNumber}
            onSendToScene={() => void sendToScene()}
            onSwitchToEdit={() => { setMode("edit"); setInspectorOpen(false) }}
              />

              {!relationsError && relations ? <VaultNoteRelatedPanels
                isDark={isDark}
                previewNodes={previewNodes}
                recentMentions={recentMentions}
                relations={relations}
                selectedNote={selectedNote}
                selectedOutgoingLinks={selectedOutgoingLinks}
                onOpenGraph={() => setGraphExpanded(true)}
                onOpenNote={(path) => { openNote(path); setInspectorOpen(false) }}
              /> : null}
            </div>
          </WorkspaceSidePanel>
        ) : null}
      </div>

      {graphExpanded ? (
        <VaultNotesGraphModal
          graph={graph}
          isDark={isDark}
          selectedNote={selectedNote}
          selectedPath={selectedPath}
          onClose={() => setGraphExpanded(false)}
          onOpenPath={(path) => {
            if (busy || autosave.leaving) return
            setSelectedPath(path)
            setGraphExpanded(false)
          }}
        />
      ) : null}

      <VaultNotesSelectionMenu
        isDark={isDark}
        menu={notesSelectionMenu}
        onAddCharacter={openAddCharacterFromNotes}
      />

      <AddCharacterFromSelection
        bookId={bookId}
        selectedText={addCharacterText}
        isDark={isDark}
        firstChapter={1}
        open={addCharacterOpen}
        onClose={() => setAddCharacterOpen(false)}
        onCreated={handleCharacterCreated}
      />
    </div>
  )
}
