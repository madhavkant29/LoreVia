import { startTransition, useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import {
  buildUniqueWorkspacePathFromCandidate,
  normalizeWorkspaceFolderPath,
  sanitizeWorkspaceTitle,
} from "@/lib/utils/workspacePaths"
import type { ConfirmDialogConfig, PromptDialogConfig } from "@/types/ux"
import type { VaultGraph, VaultNote } from "@/types/book"

import {
  buildUniqueNotePath,
  matchesReference,
  noteFolder,
  noteTitle,
} from "./VaultNotesEditor.helpers"

type PromptDialog = (config: PromptDialogConfig) => Promise<string | null>
type ConfirmDialog = (config: ConfirmDialogConfig) => Promise<boolean>

interface UseVaultNotesEditorActionsArgs {
  busy: boolean
  bookId: string
  bookTitle: string
  confirm: ConfirmDialog
  drafts: Record<string, string>
  editedFolder: string
  editedTitle: string
  latestDraftRef: MutableRefObject<Record<string, string>>
  noteMap: Map<string, VaultNote>
  notes: VaultNote[]
  prompt: PromptDialog
  selectedContent: string
  selectedFolder: string | null
  selectedNote: VaultNote | null
  selectedPath: string | null
  setBusy: Dispatch<SetStateAction<boolean>>
  setCollapsed: Dispatch<SetStateAction<Record<string, boolean>>>
  setCustomFolders: Dispatch<SetStateAction<string[]>>
  setDrafts: Dispatch<SetStateAction<Record<string, string>>>
  setDropTargetFolder: Dispatch<SetStateAction<string | null>>
  setFavorites: Dispatch<SetStateAction<Record<string, boolean>>>
  setGraph: Dispatch<SetStateAction<VaultGraph>>
  setMode: (value: "edit") => void
  setNotes: Dispatch<SetStateAction<VaultNote[]>>
  settlePath: (path: string) => Promise<void>
  forgetPath: (path: string) => void
  flushAll: () => Promise<boolean>
  setSelectedFolder: Dispatch<SetStateAction<string | null>>
  setSelectedPath: Dispatch<SetStateAction<string | null>>
  setStatus: Dispatch<SetStateAction<string | null>>
}

export function useVaultNotesEditorActions({
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
  settlePath,
  forgetPath,
  flushAll,
  setSelectedFolder,
  setSelectedPath,
  setStatus,
}: UseVaultNotesEditorActionsArgs) {
  const refreshGraph = useCallback(async () => {
    try {
      const nextGraph = await booksApi.getVaultGraph(bookId)
      setGraph(nextGraph)
    } catch {
      setStatus("The note action completed, but the graph could not refresh. Reopen the page to retry.")
    }
  }, [bookId, setGraph, setStatus])

  const openNote = (reference: string) => {
    if (busy) return
    const match = notes.find((note) => matchesReference(note.path, reference))
    if (!match) {
      setStatus("Could not open this linked note. It may have been removed.")
      return
    }
    setSelectedFolder(noteFolder(match.path))
    startTransition(() => setSelectedPath(match.path))
  }

  const rememberFolder = (folderPath: string | null | undefined) => {
    const normalized = normalizeWorkspaceFolderPath(folderPath)
    if (!normalized) return
    setCustomFolders((current) => [...new Set([...current, normalized])].sort())
  }

  const createFolder = async (parentFolder?: string | null) => {
    if (busy) return
    const base = normalizeWorkspaceFolderPath(parentFolder ?? selectedFolder) || "Custom"
    const requestedFolder = await prompt({
      title: "Create vault folder",
      body: "Use / to nest folders in the vault.",
      label: "Folder path",
      initialValue: `${base}/New Folder`,
      confirmLabel: "Create folder",
      validate: (value) => normalizeWorkspaceFolderPath(value) ? null : "Folder path cannot be empty.",
    })
    if (requestedFolder === null) return
    const cleanFolder = normalizeWorkspaceFolderPath(requestedFolder)
    if (!cleanFolder) {
      setStatus("Folder path cannot be empty")
      return
    }
    rememberFolder(cleanFolder)
    setSelectedFolder(cleanFolder)
    setCollapsed((current) => ({ ...current, [cleanFolder]: false }))
    setStatus(`Created folder ${cleanFolder}`)
  }

  const createNote = async (folderOverride?: string | null) => {
    if (busy) return
    const destinationFolder = folderOverride?.trim() || selectedFolder || noteFolder(selectedPath ?? "") || "Custom"
    const path = buildUniqueNotePath(notes, destinationFolder, "Untitled note")
    const title = noteTitle(path)
    setBusy(true)
    try {
      const result = await booksApi.saveVaultNote(bookId, { path, content: `# ${title}\n\n` })
      setNotes((current) =>
        [...current.filter((note) => note.path !== result.path), {
          id: `${result.path}:${Date.now()}`,
          book_id: bookId,
          source: result.source,
          path: result.path,
          content: result.content,
          created_at: result.created_at ?? new Date().toISOString(),
          updated_at: result.updated_at ?? new Date().toISOString(),
        }].sort((a, b) => a.path.localeCompare(b.path))
      )
      setDrafts((current) => ({ ...current, [result.path]: result.content }))
      rememberFolder(noteFolder(result.path))
      setSelectedFolder(noteFolder(result.path))
      setSelectedPath(result.path)
      setMode("edit")
      setStatus(`Created ${result.path}`)
      await refreshGraph()
    } catch {
      setStatus("Could not create this note. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const moveNoteToFolder = async (notePath: string, destinationFolder: string | null) => {
    if (busy) return
    const note = noteMap.get(notePath)
    if (!note) return
    const cleanFolder = normalizeWorkspaceFolderPath(destinationFolder)
    const nextPath = buildUniqueWorkspacePathFromCandidate(
      notes.filter((item) => item.path !== note.path).map((item) => item.path),
      cleanFolder ? `${cleanFolder}/${noteTitle(note.path)}.md` : `${noteTitle(note.path)}.md`
    )
    if (nextPath === note.path) {
      setStatus("That note is already in this folder")
      return
    }

    setBusy(true)
    try {
      await settlePath(note.path)
      const content = drafts[note.path] ?? note.content
      const result = await booksApi.saveVaultNote(bookId, { path: nextPath, content })
      setNotes((current) => [...current.filter((item) => item.path !== result.path), { ...note, id: result.path, path: result.path, content: result.content, updated_at: result.updated_at ?? note.updated_at }])
      await booksApi.deleteVaultNote(bookId, note.path)
      forgetPath(note.path)
      setNotes((current) =>
        current
          .filter((item) => item.path !== note.path && item.path !== result.path)
          .concat({
            ...note,
            path: result.path,
            content: result.content,
            updated_at: result.updated_at ?? note.updated_at,
          })
          .sort((a, b) => a.path.localeCompare(b.path))
      )
      setDrafts((current) => {
        const next = { ...current }
        delete next[note.path]
        next[result.path] = result.content
        return next
      })
      setFavorites((current) => {
        if (!current[note.path]) return current
        const next = { ...current }
        delete next[note.path]
        next[result.path] = true
        return next
      })
      latestDraftRef.current[result.path] = result.content
      delete latestDraftRef.current[note.path]
      rememberFolder(noteFolder(result.path))
      if (selectedPath === note.path) {
        setSelectedFolder(noteFolder(result.path))
        setSelectedPath(result.path)
      }
      setStatus(`Moved note to ${result.path}`)
      await refreshGraph()
    } catch {
      setStatus("Could not finish moving this note. Any created copy is shown alongside the original.")
    } finally {
      setBusy(false)
      setDropTargetFolder(null)
    }
  }

  const deleteCurrent = async () => {
    if (busy) return
    if (!selectedNote) return
    const proceed = await confirm({
      title: "Delete note?",
      body: `Delete ${selectedNote.path}?`,
      confirmLabel: "Delete note",
      tone: "danger",
    })
    if (!proceed) return
    setBusy(true)
    try {
      await settlePath(selectedNote.path)
      await booksApi.deleteVaultNote(bookId, selectedNote.path)
      forgetPath(selectedNote.path)
      const remaining = notes.filter((note) => note.path !== selectedNote.path)
      setNotes(remaining)
      setDrafts((current) => {
        const next = { ...current }
        delete next[selectedNote.path]
        return next
      })
      setFavorites((current) => {
        const next = { ...current }
        delete next[selectedNote.path]
        return next
      })
      setSelectedPath(remaining[0]?.path ?? null)
      setStatus(`Deleted ${selectedNote.path}`)
      await refreshGraph()
    } catch {
      setStatus("Could not delete this note. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const moveCurrent = async () => {
    if (busy) return
    if (!selectedNote) return
    const cleanFolder = normalizeWorkspaceFolderPath(editedFolder)
    const cleanTitle = sanitizeWorkspaceTitle(editedTitle, "")
    if (!cleanTitle) {
      setStatus("Note title cannot be empty")
      return
    }
    const nextPath = cleanFolder ? `${cleanFolder}/${cleanTitle}.md` : `${cleanTitle}.md`
    if (nextPath === selectedNote.path) {
      setStatus("Path already matches this note")
      return
    }

    if (notes.some((note) => note.path.toLowerCase() === nextPath.toLowerCase())) {
      setStatus("A note already uses that path. Choose a different title or folder.")
      return
    }
    setBusy(true)
    try {
      await settlePath(selectedNote.path)
      const result = await booksApi.saveVaultNote(bookId, { path: nextPath, content: selectedContent })
      setNotes((current) => [...current.filter((item) => item.path !== result.path), { ...selectedNote, id: result.path, path: result.path, content: result.content, updated_at: result.updated_at ?? selectedNote.updated_at }])
      await booksApi.deleteVaultNote(bookId, selectedNote.path)
      forgetPath(selectedNote.path)
      setNotes((current) =>
        current
          .filter((note) => note.path !== selectedNote.path && note.path !== result.path)
          .concat({
            ...selectedNote,
            path: result.path,
            content: result.content,
            updated_at: result.updated_at ?? selectedNote.updated_at,
          })
          .sort((a, b) => a.path.localeCompare(b.path))
      )
      setDrafts((current) => {
        const next = { ...current }
        delete next[selectedNote.path]
        next[result.path] = result.content
        return next
      })
      setFavorites((current) => {
        if (!current[selectedNote.path]) return current
        const next = { ...current }
        delete next[selectedNote.path]
        next[result.path] = true
        return next
      })
      latestDraftRef.current[result.path] = result.content
      delete latestDraftRef.current[selectedNote.path]
      rememberFolder(noteFolder(result.path))
      setSelectedFolder(noteFolder(result.path))
      setSelectedPath(result.path)
      setStatus(`Moved note to ${result.path}`)
      await refreshGraph()
    } catch {
      setStatus("Could not finish moving this note. Any created copy is shown alongside the original.")
    } finally {
      setBusy(false)
    }
  }

  const duplicateCurrent = async () => {
    if (busy) return
    if (!selectedNote) return
    const folder = noteFolder(selectedNote.path)
    const path = buildUniqueNotePath(notes, folder, `${noteTitle(selectedNote.path)} Copy`)
    setBusy(true)
    try {
      const result = await booksApi.saveVaultNote(bookId, { path, content: selectedContent })
      setNotes((current) =>
        [...current.filter((note) => note.path !== result.path), {
          id: `${result.path}:${Date.now()}`,
          book_id: bookId,
          source: result.source,
          path: result.path,
          content: result.content,
          created_at: result.created_at ?? new Date().toISOString(),
          updated_at: result.updated_at ?? new Date().toISOString(),
        }].sort((a, b) => a.path.localeCompare(b.path))
      )
      setSelectedPath(result.path)
      setStatus(`Duplicated to ${result.path}`)
      await refreshGraph()
    } catch {
      setStatus("Could not duplicate this note. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const copyCurrentReference = async () => {
    if (!selectedNote || typeof navigator === "undefined" || !navigator.clipboard) return
    try {
      await navigator.clipboard.writeText(`[[${noteTitle(selectedNote.path)}]]`)
      setStatus("Copied note reference")
    } catch {
      setStatus("Could not copy note reference")
    }
  }

  const exportNotes = async () => {
    if (busy) return
    setBusy(true)
    try {
      if (!await flushAll()) return
    const blob = await booksApi.exportVaultNotes(bookId)
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `${bookTitle.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-") || "book"}-notes.zip`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(url)
    setStatus("Downloaded notes ZIP")
    } catch {
      setStatus("Could not export notes. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const importNotes = async (file: File) => {
    if (busy) return
    if (!await flushAll()) return
    setBusy(true)
    try {
      await booksApi.importVaultNotes(bookId, file)
      const nextNotes = await booksApi.listVaultNotes(bookId)
      setNotes(nextNotes)
      setDrafts({})
      latestDraftRef.current = {}
      setSelectedPath(nextNotes[0]?.path ?? null)
      setSelectedFolder(noteFolder(nextNotes[0]?.path ?? ""))
      setCustomFolders((current) => [...new Set([...current, ...nextNotes.map((note) => noteFolder(note.path)).filter(Boolean)])].sort())
      setStatus(`Imported ${file.name}`)
      await refreshGraph()
    } catch {
      setStatus("Could not import these notes. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  return {
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
    refreshGraph,
  }
}
