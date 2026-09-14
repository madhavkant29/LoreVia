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
  CORE_NOTE_FOLDERS,
  buildFolderTree,
  buildNoteMap,
  filterVaultNotes,
  getAvailableNotePaths,
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
  const [firstLineIndent, setFirstLineIndent] = useState(false)
  const deferredQuery = useDeferredValue(query)
  const saveTimersRef = useRef<Record<string, number>>({})
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
    if (secondaryPanelsEnabled) return

    const schedule =
      typeof window.requestIdleCallback === "function"
        ? window.requestIdleCallback.bind(window)
        : ((callback: IdleRequestCallback) =>
            window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline), 150))
    const cancel =
      typeof window.cancelIdleCallback === "function"
        ? window.cancelIdleCallback.bind(window)
        : window.clearTimeout.bind(window)

    const handle = schedule(() => {
      startTransition(() => setSecondaryPanelsEnabled(true))
    })

    return () => cancel(handle)
  }, [secondaryPanelsEnabled])

  useEffect(() => {
    if (!secondaryPanelsEnabled) return

    let active = true
    void booksApi.getWorkspaceTree(bookId)
      .then((value) => {
        if (!active) return
        setWorkspaceTree(value)
        setSceneChapterNumber((current) => current ?? value.chapters[0]?.chapter_number ?? null)
      })
      .catch(() => {
        if (!active) return
        setWorkspaceTree(null)
      })
    return () => {
      active = false
    }
  }, [bookId, secondaryPanelsEnabled])

  useEffect(() => {
    const saveTimers = saveTimersRef.current
    return () => {
      for (const timer of Object.values(saveTimers)) {
        window.clearTimeout(timer)
      }
    }
  }, [])

  useEffect(() => {
    if (!graphExpanded) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setGraphExpanded(false)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [graphExpanded])

  const noteMap = useMemo(() => buildNoteMap(notes), [notes])
  const folderTree = useMemo(
    () => buildFolderTree(notes.map((note) => note.path), [...CORE_NOTE_FOLDERS, ...customFolders]),
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
  const availablePaths = useMemo(() => getAvailableNotePaths(filteredNotes), [filteredNotes])

  useEffect(() => {
    if (!selectedPath && availablePaths[0]) {
      setSelectedPath(availablePaths[0])
      return
    }
    if (selectedPath && availablePaths.length > 0 && !availablePaths.includes(selectedPath)) {
      setSelectedPath(availablePaths[0])
    }
  }, [availablePaths, selectedPath])

  useEffect(() => {
    if (!selectedNote || !secondaryPanelsEnabled) {
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
    void booksApi.getVaultNoteRelations(bookId, selectedNote.path)
      .then((value) => {
        if (!cancelled) setRelations(value)
      })
      .catch(() => {
        if (!cancelled) setRelations(null)
      })
    return () => {
      cancelled = true
    }
  }, [bookId, secondaryPanelsEnabled, selectedNote])

  useEffect(() => {
    if (!selectedNote) {
      setEditedFolder("")
      setEditedTitle("")
      return
    }
    setEditedFolder(noteFolder(selectedNote.path))
    setEditedTitle(noteTitle(selectedNote.path))
  }, [selectedNote])

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
    saveNote,
    updateDraft,
  } = useVaultNotesEditorActions({
    bookId,
    bookTitle,
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
    setRelations,
    setSelectedFolder,
    setSelectedPath,
    setStatus,
  })

  useEffect(() => {
    if (!selectedNote) return
    const nextValue = drafts[selectedNote.path]
    if (nextValue === undefined || nextValue === selectedNote.content) return
    const existingTimer = saveTimersRef.current[selectedNote.path]
    if (existingTimer) window.clearTimeout(existingTimer)
    saveTimersRef.current[selectedNote.path] = window.setTimeout(() => {
      delete saveTimersRef.current[selectedNote.path]
      void saveNote(selectedNote.path, latestDraftRef.current[selectedNote.path] ?? nextValue)
    }, 700)
  }, [drafts, saveNote, selectedNote])

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
      className={`rounded-lg border p-4 sm:p-5 ${
        isDark
          ? "border-white/[0.08] bg-[#071211]"
          : "border-stone-200 bg-white"
      }`}
    >
      <VaultNotesTopbar
        busy={busy}
        importInputRef={importInputRef}
        isDark={isDark}
        selectedNoteAvailable={Boolean(selectedNote)}
        onCreateNote={() => void createNote()}
        onDuplicateCurrent={() => void duplicateCurrent()}
        onExportNotes={() => void exportNotes()}
        onImportNotes={(file) => void importNotes(file)}
      />

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(18rem,20rem)_minmax(0,1fr)_minmax(16rem,18rem)]">
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
              onSelectNote={setSelectedPath}
              onViewChange={setNotesView}
            />
        </VaultNotesSidebarShell>

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
          status={status}
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

        <aside className="space-y-4">
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
            onSwitchToEdit={() => setMode("edit")}
          />

          <VaultNoteRelatedPanels
            isDark={isDark}
            previewNodes={previewNodes}
            recentMentions={recentMentions}
            relations={relations}
            selectedNote={selectedNote}
            selectedOutgoingLinks={selectedOutgoingLinks}
            onOpenGraph={() => setGraphExpanded(true)}
            onOpenNote={openNote}
          />
        </aside>
      </div>

      {graphExpanded ? (
        <VaultNotesGraphModal
          graph={graph}
          isDark={isDark}
          selectedNote={selectedNote}
          selectedPath={selectedPath}
          onClose={() => setGraphExpanded(false)}
          onOpenPath={(path) => {
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
