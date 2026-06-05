"use client"

import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState, type DragEvent as ReactDragEvent, type ReactNode } from "react"
import dynamic from "next/dynamic"

import { booksApi } from "@/lib/api/books"
import Link from "next/link"
import {
  buildUniqueWorkspacePath,
  buildUniqueWorkspacePathFromCandidate,
  buildWorkspaceFolderTree,
  normalizeWorkspaceFolderPath,
  sanitizeWorkspaceTitle,
  workspaceFileTitle,
  workspaceFolderFromPath,
  type WorkspaceFolderNode,
} from "@/lib/utils/workspacePaths"
import type { ManuscriptWorkspaceTree, VaultGraph, VaultNoteRelations, VaultNote } from "@/types/book"
import type { Character } from "@/types/character"
import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"
import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { Skeleton } from "@/components/ui/Skeleton"
import { Tooltip } from "@/components/ui/Tooltip"
import { migrateVaultStorage } from "@/lib/utils/vaultStorageMigration"

const WhatsTheWordPanel = dynamic(
  () => import("@/components/intelligence/WhatsTheWordPanel").then((module) => module.WhatsTheWordPanel),
  { ssr: false }
)

const GraphViewer = dynamic(
  () => import("./GraphViewer").then((module) => module.GraphViewer),
  {
    ssr: false,
    loading: () => <Skeleton variant="card" className="min-h-[34rem] rounded-lg" />,
  }
)

const MarkdownPreview = dynamic(
  () => import("./MarkdownPreview").then((module) => module.MarkdownPreview),
  {
    ssr: false,
    loading: () => <Skeleton variant="card" className="min-h-[32rem] rounded-md" />,
  }
)

const FAVORITES_STORAGE_KEY = "vault-note-favorites:v1"
const FOLDERS_STORAGE_KEY_PREFIX = "vault-note-folders:v1:"
const CORE_NOTE_FOLDERS = ["Characters", "Plot Threads", "Story Advisor", "Manual Editor", "Worldbuilding", "Timeline", "Themes", "Templates", "Custom"]

type NotesView = "recent" | "favorites"
type EditorMode = "edit" | "preview" | "split"

type FolderNode = WorkspaceFolderNode
type NotesDragItem = { kind: "note"; path: string }

const TOOLBAR_BUTTON_DEFS = [
  { key: "bold", label: "B", title: "Bold", kind: "wrap" as const, open: "**", close: "**", placeholder: "bold text" },
  { key: "italic", label: "I", title: "Italic", className: "italic", kind: "wrap" as const, open: "*", close: "*", placeholder: "italic text" },
  { key: "strike", label: "S", title: "Strikethrough", className: "line-through", kind: "wrap" as const, open: "~~", close: "~~", placeholder: "crossed text" },
  { key: "underline", label: "U", title: "Underline helper", className: "underline", kind: "wrap" as const, open: "<u>", close: "</u>", placeholder: "underlined text" },
  { key: "h1", label: "H1", title: "Heading 1", kind: "prefix" as const, prefix: "# ", placeholder: "Heading" },
  { key: "h2", label: "H2", title: "Heading 2", kind: "prefix" as const, prefix: "## ", placeholder: "Section heading" },
  { key: "h3", label: "H3", title: "Heading 3", kind: "prefix" as const, prefix: "### ", placeholder: "Subsection" },
  { key: "bullets", label: "-", title: "Bullet list", kind: "prefix" as const, prefix: "- ", placeholder: "List item" },
  { key: "numbers", label: "1.", title: "Numbered list", kind: "prefix" as const, prefix: "1. ", placeholder: "Numbered item" },
  { key: "check", label: "[ ]", title: "Checklist", kind: "prefix" as const, prefix: "- [ ] ", placeholder: "Checklist item" },
  { key: "quote", label: '"', title: "Blockquote", kind: "prefix" as const, prefix: "> ", placeholder: "Quoted note" },
  { key: "code", label: "</>", title: "Code", kind: "wrap" as const, open: "`", close: "`", placeholder: "code" },
  { key: "link", label: "[[]]", title: "Wiki link", kind: "wrap" as const, open: "[[", close: "]]", placeholder: "Linked note" },
  { key: "divider", label: "---", title: "Divider", kind: "snippet" as const, snippet: "\n---\n" },
  { key: "scene-break", label: "***", title: "Scene break", kind: "snippet" as const, snippet: "\n***\n" },
  { key: "bookmark", label: "#", title: "Bookmark / anchor", kind: "snippet" as const, snippet: "\n^anchor-name\n" },
  { key: "template", label: "Tpl", title: "Scene note template", kind: "snippet" as const, snippet: "\n## Scene note\n- POV:\n- Location:\n- Timeline:\n- Tags:\n- Continuity risk:\n\n" },
  { key: "table", label: "tbl", title: "Table", kind: "snippet" as const, snippet: "\n| Column | Detail |\n| --- | --- |\n| Item | Note |\n" },
] as const

function noteTitle(path: string) {
  return workspaceFileTitle(path)
}

function noteFolder(path: string) {
  return workspaceFolderFromPath(path)
}

function matchesReference(path: string, reference: string) {
  const cleanedReference = reference.replace(/\.md$/i, "").trim().toLowerCase()
  const cleanedPath = path.toLowerCase()
  return cleanedPath === reference.toLowerCase() || noteTitle(path).toLowerCase() === cleanedReference
}

function fileWordCount(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed.split(/\s+/).length : 0
}

function fileCharacterCount(value: string) {
  return value.trim().length
}

function countMarkdownHeadings(value: string) {
  return value.match(/^#{1,6}\s+/gm)?.length ?? 0
}

function countWikiLinks(value: string) {
  return value.match(/\[\[[^\]]+\]\]/g)?.length ?? 0
}

function buildFolderTree(paths: string[], seededFolders: string[] = []) {
  const root = buildWorkspaceFolderTree(paths, seededFolders)
  root.name = "All notes"
  return root
}

function buildUniqueNotePath(notes: VaultNote[], folder: string | null, baseTitle: string) {
  return buildUniqueWorkspacePath(notes.map((note) => note.path), folder, baseTitle)
}

function loadFavoriteMap() {
  if (typeof window === "undefined") return {}
  try {
    return JSON.parse(window.localStorage.getItem(FAVORITES_STORAGE_KEY) || "{}") as Record<string, boolean>
  } catch {
    return {}
  }
}

function loadCustomFolders(bookId: string) {
  if (typeof window === "undefined") return [] as string[]
  try {
    const raw = window.localStorage.getItem(`${FOLDERS_STORAGE_KEY_PREFIX}${bookId}`)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.map((value) => normalizeWorkspaceFolderPath(String(value))).filter(Boolean) : []
  } catch {
    return []
  }
}

function parseNotesDragItem(event: Pick<DragEvent, "dataTransfer"> | Pick<ReactDragEvent, "dataTransfer">) {
  const raw = event.dataTransfer?.getData("application/lorevia-note-item")
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as NotesDragItem
    return value.kind === "note" && value.path ? value : null
  } catch {
    return null
  }
}

function formatRelativeTime(value: string) {
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return "Unknown"
  const diffMs = timestamp - Date.now()
  const diffMinutes = Math.round(diffMs / 60000)
  if (Math.abs(diffMinutes) < 1) return "just now"
  if (Math.abs(diffMinutes) < 60) return `${Math.abs(diffMinutes)}m ago`
  const diffHours = Math.round(diffMinutes / 60)
  if (Math.abs(diffHours) < 24) return `${Math.abs(diffHours)}h ago`
  const diffDays = Math.round(diffHours / 24)
  if (Math.abs(diffDays) === 1) return "Yesterday"
  if (Math.abs(diffDays) < 7) return `${Math.abs(diffDays)}d ago`
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value))
}

function formatTimestamp(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) return "Unknown"
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp)
}

function inferNoteType(path: string) {
  const lower = path.toLowerCase()
  if (lower.includes("character")) return "Character"
  if (lower.includes("plot")) return "Plot"
  if (lower.includes("world")) return "World"
  if (lower.includes("timeline")) return "Timeline"
  if (lower.includes("theme")) return "Theme"
  if (lower.includes("template")) return "Template"
  return "Note"
}

function markdownButtonClass(isDark: boolean) {
  return `flex h-9 min-w-9 items-center justify-center rounded-xl border px-2 text-sm font-semibold transition ${
    isDark
      ? "border-white/8 bg-white/[0.03] text-slate-300 hover:bg-white/[0.08] hover:text-white"
      : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
  }`
}

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
  const [sceneSending, setSceneSending] = useState(false)
  const [findWithinNote, setFindWithinNote] = useState("")
  const [replaceWithinNote, setReplaceWithinNote] = useState("")
  const [secondaryPanelsEnabled, setSecondaryPanelsEnabled] = useState(false)
  const [notesSelectionMenu, setNotesSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)
  const [addCharacterOpen, setAddCharacterOpen] = useState(false)
  const [addCharacterText, setAddCharacterText] = useState("")
  const notesSelectionRef = useRef("")
  const deferredQuery = useDeferredValue(query)
  const saveTimersRef = useRef<Record<string, number>>({})
  const latestDraftRef = useRef<Record<string, string>>({})
  const importInputRef = useRef<HTMLInputElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const confirm = useConfirmDialog()

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
    if (typeof window === "undefined") return
    const id = window.requestIdleCallback
      ? window.requestIdleCallback(() => {
          window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favorites))
        })
      : window.setTimeout(() => {
          window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favorites))
        }, 0)
    return () => {
      if (typeof id === "number") window.clearTimeout(id)
      else if (window.cancelIdleCallback) window.cancelIdleCallback(id as number)
    }
  }, [favorites])

  useEffect(() => {
    if (typeof window === "undefined") return
    const id = window.requestIdleCallback
      ? window.requestIdleCallback(() => {
          window.localStorage.setItem(
            `${FOLDERS_STORAGE_KEY_PREFIX}${bookId}`,
            JSON.stringify([...new Set(customFolders.map((folder) => normalizeWorkspaceFolderPath(folder)).filter(Boolean))].sort())
          )
        })
      : window.setTimeout(() => {
          window.localStorage.setItem(
            `${FOLDERS_STORAGE_KEY_PREFIX}${bookId}`,
            JSON.stringify([...new Set(customFolders.map((folder) => normalizeWorkspaceFolderPath(folder)).filter(Boolean))].sort())
          )
        }, 0)
    return () => {
      if (typeof id === "number") window.clearTimeout(id)
      else if (window.cancelIdleCallback) window.cancelIdleCallback(id as number)
    }
  }, [bookId, customFolders])

  useEffect(() => {
    return () => {
      for (const timer of Object.values(saveTimersRef.current)) {
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

  const noteMap = useMemo(() => new Map(notes.map((note) => [note.path, note])), [notes])
  const folderTree = useMemo(
    () => buildFolderTree(notes.map((note) => note.path), [...CORE_NOTE_FOLDERS, ...customFolders]),
    [customFolders, notes]
  )
  const selectedNote = selectedPath ? noteMap.get(selectedPath) ?? null : null
  const selectedContent = selectedNote ? drafts[selectedNote.path] ?? selectedNote.content : ""
  const selectedOutgoingLinks = useMemo(
    () => graph.edges.filter((edge) => edge.source === selectedPath),
    [graph.edges, selectedPath]
  )

  const filteredNotes = useMemo(() => {
    const term = deferredQuery.trim().toLowerCase()
    return [...notes]
      .filter((note) => {
        const draft = drafts[note.path] ?? note.content
        const folder = noteFolder(note.path)
        const folderMatches = !selectedFolder || folder === selectedFolder || folder.startsWith(`${selectedFolder}/`)
        if (!folderMatches) return false
        if (!term) return true
        return (
          note.path.toLowerCase().includes(term) ||
          folder.toLowerCase().includes(term) ||
          noteTitle(note.path).toLowerCase().includes(term) ||
          draft.toLowerCase().includes(term)
        )
      })
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
  }, [deferredQuery, drafts, notes, selectedFolder])

  const favoriteNotes = useMemo(
    () => filteredNotes.filter((note) => favorites[note.path]),
    [favorites, filteredNotes]
  )
  const displayedNotes = notesView === "favorites" ? favoriteNotes : filteredNotes
  const availablePaths = filteredNotes.map((note) => note.path)

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
  }, [bookId, secondaryPanelsEnabled, selectedNote?.path])

  useEffect(() => {
    if (!selectedNote) {
      setEditedFolder("")
      setEditedTitle("")
      return
    }
    setEditedFolder(noteFolder(selectedNote.path))
    setEditedTitle(noteTitle(selectedNote.path))
  }, [selectedNote?.path])

  const refreshGraph = async () => {
    const nextGraph = await booksApi.getVaultGraph(bookId)
    setGraph(nextGraph)
  }

  const saveNote = async (path: string, content: string) => {
    latestDraftRef.current[path] = content
    try {
      const result = await booksApi.saveVaultNote(bookId, { path, content })
      if (latestDraftRef.current[path] !== result.content) return
      setNotes((current) =>
        current
          .map((note) =>
            note.path === path ? { ...note, content: result.content, updated_at: result.updated_at ?? note.updated_at } : note
          )
          .sort((a, b) => a.path.localeCompare(b.path))
      )
      setDrafts((current) => ({ ...current, [path]: result.content }))
      setStatus("Saved just now")
      void refreshGraph()
      if (selectedPath === path) {
        void booksApi.getVaultNoteRelations(bookId, path).then((value) => setRelations(value))
      }
    } catch {
      setStatus(`Could not save ${path}`)
    }
  }

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
  }, [drafts, selectedNote])

  const updateDraft = (path: string, value: string) => {
    latestDraftRef.current[path] = value
    setDrafts((current) => ({ ...current, [path]: value }))
    setStatus(null)
  }

  const openNote = (reference: string) => {
    const match = notes.find((note) => matchesReference(note.path, reference))
    if (!match) return
    setSelectedFolder(noteFolder(match.path))
    startTransition(() => setSelectedPath(match.path))
  }

  const rememberFolder = (folderPath: string | null | undefined) => {
    const normalized = normalizeWorkspaceFolderPath(folderPath)
    if (!normalized) return
    setCustomFolders((current) => [...new Set([...current, normalized])].sort())
  }

  const createFolder = (parentFolder?: string | null) => {
    if (typeof window === "undefined") return
    const base = normalizeWorkspaceFolderPath(parentFolder ?? selectedFolder) || "Custom"
    const requestedFolder = window.prompt(
      "Create a folder path. Use / to nest folders.",
      `${base}/New Folder`
    )
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
    const destinationFolder = folderOverride?.trim() || selectedFolder || noteFolder(selectedPath ?? "") || "Custom"
    const path = buildUniqueNotePath(notes, destinationFolder, "Untitled note")
    const title = noteTitle(path)
    setBusy(true)
    try {
      const result = await booksApi.saveVaultNote(bookId, { path, content: `# ${title}\n\n` })
      setNotes((current) =>
        [...current, {
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
    } finally {
      setBusy(false)
    }
  }

  const moveNoteToFolder = async (notePath: string, destinationFolder: string | null) => {
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
      const content = drafts[note.path] ?? note.content
      const result = await booksApi.saveVaultNote(bookId, { path: nextPath, content })
      await booksApi.deleteVaultNote(bookId, note.path)
      setNotes((current) =>
        current
          .filter((item) => item.path !== note.path)
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
      setStatus("Could not move this note")
    } finally {
      setBusy(false)
      setDropTargetFolder(null)
    }
  }

  const deleteCurrent = async () => {
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
      await booksApi.deleteVaultNote(bookId, selectedNote.path)
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
    } finally {
      setBusy(false)
    }
  }

  const moveCurrent = async () => {
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

    setBusy(true)
    try {
      const result = await booksApi.saveVaultNote(bookId, { path: nextPath, content: selectedContent })
      await booksApi.deleteVaultNote(bookId, selectedNote.path)
      setNotes((current) =>
        current
          .filter((note) => note.path !== selectedNote.path)
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
      setStatus("Could not move this note")
    } finally {
      setBusy(false)
    }
  }

  const duplicateCurrent = async () => {
    if (!selectedNote) return
    const folder = noteFolder(selectedNote.path)
    const path = buildUniqueNotePath(notes, folder, `${noteTitle(selectedNote.path)} Copy`)
    setBusy(true)
    try {
      const result = await booksApi.saveVaultNote(bookId, { path, content: selectedContent })
      setNotes((current) =>
        [...current, {
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
  }

  const importNotes = async (file: File) => {
    setBusy(true)
    try {
      await booksApi.importVaultNotes(bookId, file)
      const [nextNotes, nextGraph] = await Promise.all([booksApi.listVaultNotes(bookId), booksApi.getVaultGraph(bookId)])
      setNotes(nextNotes)
      setGraph(nextGraph)
      setSelectedPath(nextNotes[0]?.path ?? null)
      setSelectedFolder(noteFolder(nextNotes[0]?.path ?? ""))
      setCustomFolders((current) => [...new Set([...current, ...nextNotes.map((note) => noteFolder(note.path)).filter(Boolean)])].sort())
      setStatus(`Imported ${file.name}`)
    } finally {
      setBusy(false)
    }
  }

  const replaceSelectedText = (before: string, after = before, fallback = "") => {
    const textarea = textareaRef.current
    if (!textarea || !selectedNote) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const currentValue = drafts[selectedNote.path] ?? selectedNote.content
    const selection = currentValue.slice(start, end)
    const body = selection || fallback
    const nextValue = `${currentValue.slice(0, start)}${before}${body}${after}${currentValue.slice(end)}`
    updateDraft(selectedNote.path, nextValue)
    requestAnimationFrame(() => {
      textarea.focus()
      const cursorStart = start + before.length
      const cursorEnd = cursorStart + body.length
      textarea.setSelectionRange(cursorStart, cursorEnd)
    })
  }

  const prefixSelectedLines = (prefix: string, fallback: string) => {
    const textarea = textareaRef.current
    if (!textarea || !selectedNote) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const currentValue = drafts[selectedNote.path] ?? selectedNote.content
    const selection = currentValue.slice(start, end)
    const source = selection || fallback
    const nextChunk = source
      .split("\n")
      .map((line) => `${prefix}${line}`)
      .join("\n")
    const nextValue = `${currentValue.slice(0, start)}${nextChunk}${currentValue.slice(end)}`
    updateDraft(selectedNote.path, nextValue)
    requestAnimationFrame(() => {
      textarea.focus()
      textarea.setSelectionRange(start, start + nextChunk.length)
    })
  }

  const insertSnippet = (snippet: string) => {
    const textarea = textareaRef.current
    if (!textarea || !selectedNote) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const currentValue = drafts[selectedNote.path] ?? selectedNote.content
    const nextValue = `${currentValue.slice(0, start)}${snippet}${currentValue.slice(end)}`
    updateDraft(selectedNote.path, nextValue)
    requestAnimationFrame(() => {
      textarea.focus()
      const cursor = start + snippet.length
      textarea.setSelectionRange(cursor, cursor)
    })
  }

  const toolbarButtons = useMemo(
    () =>
      TOOLBAR_BUTTON_DEFS.map((def) => ({
        key: def.key,
        label: def.label,
        title: def.title,
        className: "className" in def ? def.className : undefined,
        action: () => {
          if (def.kind === "wrap") replaceSelectedText(def.open, def.close, def.placeholder)
          else if (def.kind === "prefix") prefixSelectedLines(def.prefix, def.placeholder)
          else insertSnippet(def.snippet)
        },
      })),
    [replaceSelectedText, prefixSelectedLines, insertSnippet],
  )

  const isFavorite = selectedNote ? Boolean(favorites[selectedNote.path]) : false
  const sceneChapters = workspaceTree?.chapters ?? []
  const recentMentions = useMemo(
    () =>
      [...(relations?.backlinks ?? [])]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 3),
    [relations?.backlinks],
  )
  const previewNodes = useMemo(() => {
    const unique = new Map<string, { id: string; label: string }>()
    for (const link of selectedOutgoingLinks.slice(0, 2)) {
      unique.set(link.target, { id: link.target, label: noteTitle(link.target) })
    }
    for (const link of recentMentions.slice(0, 2)) {
      if (!unique.has(link.source_note_path)) {
        unique.set(link.source_note_path, { id: link.source_note_path, label: noteTitle(link.source_note_path) })
      }
    }
    return [...unique.values()].slice(0, 4)
  }, [recentMentions, selectedOutgoingLinks])

  const sendToScene = async () => {
    if (!selectedNote) return
    setSceneSending(true)
    try {
      const scene = await booksApi.saveScene(bookId, {
        title: noteTitle(selectedNote.path),
        description: `Sent from note: ${selectedNote.path}`,
        body: selectedContent,
        chapter_number: sceneChapterNumber,
        status: "planned",
      })
      setStatus(`Sent to scenes: ${scene.title}`)
    } catch {
      setStatus("Could not send this note to scenes")
    } finally {
      setSceneSending(false)
    }
  }

  const replaceInSelectedNote = () => {
    if (!selectedNote || !findWithinNote.trim()) return
    const currentValue = drafts[selectedNote.path] ?? selectedNote.content
    updateDraft(selectedNote.path, currentValue.split(findWithinNote).join(replaceWithinNote))
    setStatus("Updated note draft with replacements")
  }

  const syncNotesSelectionMenu = (mouseEvent?: Pick<MouseEvent, "clientX" | "clientY">) => {
    const textarea = textareaRef.current
    if (!textarea) return
    const selectedText = textarea.value.slice(textarea.selectionStart, textarea.selectionEnd).trim()
    if (!selectedText) {
      setNotesSelectionMenu(null)
      return
    }
    notesSelectionRef.current = selectedText
    if (mouseEvent) {
      setNotesSelectionMenu({
        text: selectedText.slice(0, 100),
        top: mouseEvent.clientY - 48,
        left: mouseEvent.clientX,
      })
    } else {
      const rect = textarea.getBoundingClientRect()
      setNotesSelectionMenu({
        text: selectedText.slice(0, 100),
        top: rect.top + window.scrollY + 60,
        left: rect.left + window.scrollX + (rect.width / 2),
      })
    }
  }

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (target.closest('[data-notes-add-character]')) return
      setNotesSelectionMenu(null)
    }
    document.addEventListener("click", handleClick)
    return () => document.removeEventListener("click", handleClick)
  }, [])

  const openAddCharacterFromNotes = () => {
    const text = notesSelectionRef.current.trim()
    if (!text) return
    setAddCharacterText(text)
    setAddCharacterOpen(true)
    setNotesSelectionMenu(null)
  }

  const handleCharacterCreated = (character: Character) => {
    setStatus(`Character "${character.name}" added to the story bible.`)
  }

  return (
    <div
      className={`rounded-lg border p-4 sm:p-5 ${
        isDark
          ? "border-white/8 bg-[#071211]"
          : "border-stone-200 bg-white"
      }`}
    >
      <div className="flex flex-col gap-4 border-b border-white/8 pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className={`font-serif text-[2rem] tracking-[-0.04em] ${isDark ? "text-white" : "text-stone-950"}`}>Vault notes workspace</h2>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>A book-native vault for character notes, links, themes, and evolving story context.</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void createNote()} disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-[#1f615d] px-4 py-3 text-sm font-semibold text-white disabled:opacity-60">
            <IconPlus />
            New note
          </button>
          <button type="button" onClick={() => importInputRef.current?.click()} disabled={busy} className={`inline-flex items-center gap-2 rounded-md border px-4 py-3 text-sm font-medium ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
            <IconUpload />
            Import ZIP
          </button>
          <button type="button" onClick={exportNotes} disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-[#1f615d] px-4 py-3 text-sm font-semibold text-white">
            <IconUpload className="rotate-180" />
            Export ZIP
          </button>
          <Tooltip content="Duplicate selected note">
            <button type="button" aria-label="Duplicate selected note" onClick={() => void duplicateCurrent()} disabled={!selectedNote || busy} className={`inline-flex h-[3rem] w-[3rem] items-center justify-center rounded-md border ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              <IconMore />
            </button>
          </Tooltip>
          <input
            ref={importInputRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void importNotes(file)
              event.currentTarget.value = ""
            }}
          />
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(18rem,20rem)_minmax(0,1fr)_minmax(16rem,18rem)]">
        <aside className={`overflow-hidden rounded-lg border ${isDark ? "border-white/8 bg-[#07101d]/90" : "border-stone-200 bg-white/90"}`}>
          <div className={`border-b px-5 py-5 ${isDark ? "border-white/8" : "border-stone-200"}`}>
            <div className="flex items-center gap-3">
              <div className={`flex h-12 w-12 items-center justify-center rounded-md ${isDark ? "bg-emerald-500/12 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>
                <IconDocument />
              </div>
              <div className="min-w-0">
                <h3 className={`truncate text-xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{bookTitle}</h3>
                <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Vault notes workspace</p>
              </div>
            </div>
          </div>

          <div className="p-4">
            <div className="flex gap-2">
              <label className={`flex min-w-0 flex-1 items-center gap-2 rounded-md border px-3 py-3 ${isDark ? "border-white/8 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
                <IconSearch />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search notes"
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-inherit"
                />
              </label>
              <Tooltip content="Show all folders">
                <button type="button" aria-label="Show all folders" onClick={() => setSelectedFolder(null)} className={`flex h-12 w-12 items-center justify-center rounded-md border ${isDark ? "border-white/8 bg-white/[0.03] text-slate-300 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
                  <IconSliders />
                </button>
              </Tooltip>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Folders</p>
              <Tooltip content="Create folder">
                <button type="button" aria-label="Create folder" onClick={() => createFolder()} className={`rounded-full p-1.5 ${isDark ? "text-slate-400 hover:bg-white/[0.06] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}>
                  <IconPlus />
                </button>
              </Tooltip>
            </div>

            <div className="mt-3 max-h-[23rem] overflow-auto pr-1">
              <button
                type="button"
                onClick={() => setSelectedFolder(null)}
                onDragOver={(event) => {
                  if (!parseNotesDragItem(event)) return
                  event.preventDefault()
                  setDropTargetFolder("")
                }}
                onDragLeave={() => setDropTargetFolder((current) => (current === "" ? null : current))}
                onDrop={(event) => {
                  const dragItem = parseNotesDragItem(event)
                  if (!dragItem) return
                  event.preventDefault()
                  void moveNoteToFolder(dragItem.path, null)
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
                <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{notes.length}</span>
              </button>
              <FolderList
                node={folderTree}
                activePath={selectedFolder}
                collapsed={collapsed}
                onToggleFolder={(path) => setCollapsed((current) => ({ ...current, [path]: !current[path] }))}
                onSelect={(path) => setSelectedFolder(path)}
                onCreateFolder={(path) => createFolder(path)}
                onDropNote={(notePath, folderPath) => void moveNoteToFolder(notePath, folderPath)}
                dropTargetPath={dropTargetFolder}
                onDropTargetChange={setDropTargetFolder}
                isDark={isDark}
              />
            </div>

            <div className="mt-6">
              <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Notes</p>
              <div className="mt-3 flex gap-2" role="tablist" aria-label="Notes view">
                <button type="button" role="tab" aria-selected={notesView === "recent"} onClick={() => setNotesView("recent")} className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${notesView === "recent" ? "bg-emerald-500/16 text-emerald-200" : isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}>
                  Recent
                </button>
                <button type="button" role="tab" aria-selected={notesView === "favorites"} onClick={() => setNotesView("favorites")} className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${notesView === "favorites" ? "bg-emerald-500/16 text-emerald-200" : isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}>
                  Favorites
                </button>
              </div>

              <div className="mt-3 max-h-[18rem] space-y-1 overflow-auto pr-1">
                {displayedNotes.length === 0 ? (
                  <div className={`rounded-md border border-dashed px-4 py-8 text-center text-sm ${isDark ? "border-white/8 text-slate-500" : "border-stone-300 text-stone-500"}`}>
                    {notesView === "favorites" ? "Star a note to keep it here." : "No notes match that search."}
                  </div>
                ) : (
                  displayedNotes.map((note) => {
                    const active = note.path === selectedPath
                    return (
                      <button
                        key={note.path}
                        type="button"
                        onClick={() => setSelectedPath(note.path)}
                        draggable
                        onDragStart={(event) => {
                          const payload: NotesDragItem = { kind: "note", path: note.path }
                          event.dataTransfer.effectAllowed = "move"
                          event.dataTransfer.setData("application/lorevia-note-item", JSON.stringify(payload))
                        }}
                        className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-3 text-left transition ${
                          active
                            ? isDark
                              ? "bg-white/[0.06] text-white"
                              : "bg-stone-100 text-stone-950"
                            : isDark
                              ? "text-slate-300 hover:bg-white/[0.04]"
                              : "text-stone-700 hover:bg-stone-100"
                        }`}
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <IconDocument small />
                            <span className="truncate text-sm font-medium">{noteTitle(note.path)}</span>
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className={`text-xs ${active ? (isDark ? "text-slate-300" : "text-stone-600") : isDark ? "text-slate-500" : "text-stone-400"}`}>{formatRelativeTime(note.updated_at)}</span>
                          {active ? <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> : null}
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </div>
          </div>

          <div className={`border-t px-4 py-4 ${isDark ? "border-white/8" : "border-stone-200"}`}>
            <button type="button" onClick={() => void createNote()} disabled={busy} className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${isDark ? "text-sky-200 hover:bg-white/[0.04]" : "text-sky-700 hover:bg-stone-100"}`}>
              <IconPlus />
              New note
            </button>
          </div>
        </aside>

        <section className={`overflow-hidden rounded-lg border ${isDark ? "border-white/8 bg-[#08111e]/95" : "border-stone-200 bg-white"}`}>
          {selectedNote ? (
            <>
              <div className={`flex flex-col gap-5 border-b px-5 py-4 ${isDark ? "border-white/8" : "border-stone-200"} lg:flex-row lg:items-start lg:justify-between`}>
                <div className="min-w-0">
                  <div className={`flex flex-wrap items-center gap-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    {selectedNote.path.split("/").slice(0, -1).map((segment, index, array) => (
                      <div key={`${segment}-${index}`} className="flex items-center gap-2">
                        <span className={index === 0 ? "inline-flex items-center gap-2" : ""}>
                          {index === 0 ? <IconDocument small /> : null}
                          {segment}
                        </span>
                        {index < array.length - 1 ? <span>&gt;</span> : null}
                      </div>
                    ))}
                    {selectedNote.path.includes("/") ? <span>&gt;</span> : <IconDocument small />}
                    <span className={`font-medium ${isDark ? "text-slate-200" : "text-stone-800"}`}>{noteTitle(selectedNote.path)}</span>
                  </div>

                  <div className="mt-5 flex items-start gap-3">
                    <div className="min-w-0">
                      <h3 className={`truncate font-serif text-5xl tracking-[-0.05em] ${isDark ? "text-white" : "text-stone-950"}`}>{noteTitle(selectedNote.path)}</h3>
                    </div>
                    <Tooltip content={isFavorite ? "Remove from favorites" : "Add to favorites"}>
                      <button
                        type="button"
                        aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
                        onClick={() => setFavorites((current) => ({ ...current, [selectedNote.path]: !current[selectedNote.path] }))}
                        className={`mt-1 rounded-full p-2 transition ${isFavorite ? "text-amber-300" : isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-white" : "text-stone-400 hover:bg-stone-100 hover:text-stone-900"}`}
                      >
                        <IconStar filled={isFavorite} />
                      </button>
                    </Tooltip>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Note editor mode">
                    {(["edit", "preview", "split"] as EditorMode[]).map((value) => (
                      <button
                        key={value}
                        type="button"
                        role="tab"
                        aria-selected={mode === value}
                        onClick={() => setMode(value)}
                        className={`rounded-md px-4 py-2 text-sm font-medium capitalize transition ${
                          mode === value
                            ? "bg-emerald-500/16 text-emerald-200"
                            : isDark
                              ? "bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]"
                              : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                        }`}
                      >
                        {value}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                  <span className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{status || `Saved ${formatRelativeTime(selectedNote.updated_at)}`}</span>
                  <button type="button" onClick={() => void saveNote(selectedNote.path, selectedContent)} className={`rounded-md border px-3 py-2 text-sm font-medium ${isDark ? "border-white/8 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
                    <span className="inline-flex items-center gap-2"><IconCheck />Save now</span>
                  </button>
                  <Tooltip content="Copy note reference">
                    <button type="button" aria-label="Copy note reference" onClick={() => void copyCurrentReference()} className={`rounded-md border p-2.5 ${isDark ? "border-white/8 bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
                      <IconCopy />
                    </button>
                  </Tooltip>
                  <Tooltip content="Open full graph">
                    <button type="button" aria-label="Open full graph" onClick={() => setGraphExpanded(true)} className={`rounded-md border p-2.5 ${isDark ? "border-white/8 bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
                      <IconExpand />
                    </button>
                  </Tooltip>
                </div>
              </div>

              <div className="p-5">
                <WhatsTheWordPanel bookId={bookId} isDark={isDark} className="mb-4" />
                <div className={`overflow-hidden rounded-lg border ${isDark ? "border-white/8 bg-[#0a1323]" : "border-stone-200 bg-stone-50"}`}>
                  {(mode === "edit" || mode === "split") ? (
                    <div className={`border-b px-3 py-3 ${isDark ? "border-white/8 bg-white/[0.02]" : "border-stone-200 bg-white/80"}`}>
                      <div className="flex flex-wrap gap-2">
                        {toolbarButtons.map((button) => (
                          <Tooltip key={button.key} content={button.title}>
                            <button
                              type="button"
                              aria-label={button.title}
                              onClick={button.action}
                              className={`${markdownButtonClass(isDark)} ${button.className ?? ""}`}
                            >
                              {button.label}
                            </button>
                          </Tooltip>
                        ))}
                      </div>
                      <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                        <input
                          value={findWithinNote}
                          onChange={(event) => setFindWithinNote(event.target.value)}
                          placeholder="Find in this note"
                          className={`rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/8 bg-[#08111d] text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                        />
                        <input
                          value={replaceWithinNote}
                          onChange={(event) => setReplaceWithinNote(event.target.value)}
                          placeholder="Replace with"
                          className={`rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/8 bg-[#08111d] text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                        />
                        <button type="button" onClick={replaceInSelectedNote} disabled={!findWithinNote.trim()} className={`rounded-xl px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
                          Replace all
                        </button>
                      </div>
                    </div>
                  ) : null}

                  <div className={`${mode === "split" ? "grid gap-px xl:grid-cols-2" : ""} ${isDark && mode === "split" ? "bg-white/8" : ""}`}>
                    {mode !== "preview" ? (
                      <textarea
                        ref={textareaRef}
                        value={selectedContent}
                        onChange={(event) => updateDraft(selectedNote.path, event.target.value)}
                        onMouseUp={(event) => syncNotesSelectionMenu(event)}
                        onKeyUp={() => syncNotesSelectionMenu()}
                        spellCheck={false}
                        className={`min-h-[42rem] w-full resize-none border-0 px-4 py-5 font-mono text-base leading-8 outline-none ${
                          isDark
                            ? "bg-[#0a1323] text-slate-100 placeholder:text-slate-500"
                            : "bg-white text-stone-900 placeholder:text-stone-400"
                        } ${mode === "split" ? "xl:min-h-[48rem]" : ""}`}
                      />
                    ) : null}

                    {mode !== "edit" ? (
                      <div className={`${mode === "split" ? (isDark ? "bg-[#08111d]" : "bg-white") : "p-4"}`}>
                        <MarkdownPreview
                          content={selectedContent}
                          isDark={isDark}
                          notes={notes}
                          currentPath={selectedNote.path}
                          onOpenNote={openNote}
                        />
                      </div>
                    ) : null}
                  </div>

                  <div className={`flex flex-wrap items-center gap-4 border-t px-4 py-3 text-sm ${isDark ? "border-white/8 bg-[#09111f] text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
                    <span>{fileWordCount(selectedContent).toLocaleString()} words</span>
                    <span>{fileCharacterCount(selectedContent).toLocaleString()} characters</span>
                    <span>{countMarkdownHeadings(selectedContent)} headings</span>
                    <span>{countWikiLinks(selectedContent)} links</span>
                    <span>{Math.max(1, Math.ceil(fileWordCount(selectedContent) / 250))} min read</span>
                    <span className="ml-auto">Markdown</span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className={`flex min-h-[42rem] items-center justify-center px-6 text-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Create or select a note to begin.</div>
          )}
        </section>

        <aside className="space-y-4">
          <PanelCard
            isDark={isDark}
            title="Properties"
            action={(
              <button
                type="button"
                onClick={() => setMode("edit")}
                className={`inline-flex h-8 w-8 items-center justify-center rounded-xl ${isDark ? "bg-white/[0.05] text-slate-300 hover:bg-white/[0.08] hover:text-white" : "bg-stone-100 text-stone-700 hover:bg-stone-200"}`}
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
                <span className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Folder path</span>
                <input
                  value={editedFolder}
                  onChange={(event) => setEditedFolder(event.target.value)}
                  placeholder="Characters"
                  className={`w-full rounded-md border px-3 py-2.5 text-sm outline-none ${isDark ? "border-white/8 bg-white/[0.03] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                />
              </label>
              <label className="space-y-2">
                <span className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>File title</span>
                <input
                  value={editedTitle}
                  onChange={(event) => setEditedTitle(event.target.value)}
                  placeholder="Note title"
                  className={`w-full rounded-md border px-3 py-2.5 text-sm outline-none ${isDark ? "border-white/8 bg-white/[0.03] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                />
              </label>
              <div className="flex gap-2">
                <button type="button" onClick={() => void moveCurrent()} disabled={busy || !selectedNote} className="min-w-0 flex-1 rounded-md bg-[#1f615d] px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
                  Update path
                </button>
                <button type="button" onClick={() => void deleteCurrent()} disabled={busy || !selectedNote} className={`shrink-0 rounded-md px-3 py-2.5 text-sm font-medium ${isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"}`}>
                  Delete
                </button>
              </div>
              <div className={`overflow-hidden rounded-md border p-3 ${isDark ? "border-white/8 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Send to scenes</p>
                <div className="mt-3 flex gap-2">
                  <select
                    value={sceneChapterNumber ?? ""}
                    onChange={(event) => setSceneChapterNumber(event.target.value ? Number(event.target.value) : null)}
                    className={`min-w-0 flex-1 rounded-md border px-3 py-2.5 text-sm outline-none ${isDark ? "border-white/8 bg-[#09111f] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
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
                    onClick={() => void sendToScene()}
                    disabled={!selectedNote || sceneSending}
                    className="shrink-0 rounded-md bg-[#1f615d] px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
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

          <PanelCard isDark={isDark} title="Backlinks" count={relations?.backlinks.length ?? 0}>
            <RelationStack
              items={(relations?.backlinks ?? []).map((link) => ({ id: link.id, label: noteTitle(link.source_note_path), secondary: "Mentions", reference: link.source_note_path }))}
              onOpen={openNote}
              emptyLabel="No backlinks yet."
              isDark={isDark}
            />
            {Boolean(relations?.backlinks.length) ? <PanelLink isDark={isDark}>View all backlinks</PanelLink> : null}
          </PanelCard>

          <PanelCard isDark={isDark} title="Outgoing links" count={selectedOutgoingLinks.length}>
            <RelationStack
              items={selectedOutgoingLinks.map((link, index) => ({ id: `${link.source}-${link.target}-${index}`, label: noteTitle(link.target), secondary: "Linked", reference: link.target }))}
              onOpen={openNote}
              emptyLabel="No outgoing links yet."
              isDark={isDark}
            />
            {selectedOutgoingLinks.length ? <PanelLink isDark={isDark}>View all outgoing links</PanelLink> : null}
          </PanelCard>

          <PanelCard isDark={isDark} title="Tags">
            {relations?.tags.length ? (
              <div className="flex flex-wrap items-center gap-2">
                {relations.tags.map((tag) => (
                  <span key={tag.id} className={`rounded-xl px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {tag.tag_name}
                  </span>
                ))}
                <Tooltip content="Add tag">
                  <button type="button" aria-label="Add tag" className={`inline-flex h-8 w-8 items-center justify-center rounded-xl ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-stone-100 text-stone-700"}`}>
                    <IconPlus />
                  </button>
                </Tooltip>
              </div>
            ) : (
              <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No tags found for this note.</p>
            )}
          </PanelCard>

          <PanelCard isDark={isDark} title="Recent mentions" count={recentMentions.length}>
            <RelationStack
              items={recentMentions.map((link) => ({
                id: link.id,
                label: noteTitle(link.source_note_path),
                secondary: formatRelativeTime(link.created_at),
                reference: link.source_note_path,
              }))}
              onOpen={openNote}
              emptyLabel="No recent mentions."
              isDark={isDark}
            />
          </PanelCard>

          <PanelCard
            isDark={isDark}
            title="Graph preview"
            action={(
              <button
                type="button"
                onClick={() => setGraphExpanded(true)}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${isDark ? "border-white/8 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
              >
                Open full graph
                <IconArrowUpRight />
              </button>
            )}
          >
            <MiniGraphPreview
              currentLabel={selectedNote ? noteTitle(selectedNote.path) : "Current note"}
              nodes={previewNodes}
              isDark={isDark}
            />
          </PanelCard>
        </aside>
      </div>

      {graphExpanded ? (
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
                  onClick={() => setGraphExpanded(false)}
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
                  onOpenNote={(path) => {
                    setSelectedPath(path)
                    setGraphExpanded(false)
                  }}
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
                      onClick={() => setGraphExpanded(false)}
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
      ) : null}

      {notesSelectionMenu ? (
        <div
          className="pointer-events-none fixed z-50 hidden -translate-x-1/2 xl:block"
          style={{ top: notesSelectionMenu.top, left: notesSelectionMenu.left }}
        >
          <div className={`pointer-events-auto flex items-center gap-2 rounded-full border px-2 py-2 ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`} data-notes-add-character>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => openAddCharacterFromNotes()}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-violet-700/30 text-violet-200" : "bg-violet-100 text-violet-800"}`}
            >
              Add as character
            </button>
          </div>
        </div>
      ) : null}

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

function FolderList({
  node,
  activePath,
  collapsed,
  onToggleFolder,
  onSelect,
  onCreateFolder,
  onDropNote,
  dropTargetPath,
  onDropTargetChange,
  isDark,
  depth = 0,
}: {
  node: FolderNode
  activePath: string | null
  collapsed: Record<string, boolean>
  onToggleFolder: (path: string) => void
  onSelect: (path: string) => void
  onCreateFolder: (path: string) => void
  onDropNote: (notePath: string, folderPath: string) => void
  dropTargetPath: string | null
  onDropTargetChange: (path: string | null) => void
  isDark: boolean
  depth?: number
}) {
  return (
    <div className="space-y-1">
      {[...node.folders.values()].map((child) => {
        const isCollapsed = Boolean(collapsed[child.path])
        const active = child.path === activePath
        return (
          <div key={child.path}>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onToggleFolder(child.path)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-slate-200" : "text-stone-400 hover:bg-stone-100 hover:text-stone-700"}`}
                style={{ marginLeft: `${depth * 12}px` }}
              >
                <IconChevron open={!isCollapsed} />
              </button>
              <button
                type="button"
                onClick={() => onSelect(child.path)}
                onDragOver={(event) => {
                  if (!parseNotesDragItem(event)) return
                  event.preventDefault()
                  onDropTargetChange(child.path)
                }}
                onDragLeave={() => onDropTargetChange(null)}
                onDrop={(event) => {
                  const dragItem = parseNotesDragItem(event)
                  if (!dragItem) return
                  event.preventDefault()
                  onDropNote(dragItem.path, child.path)
                }}
                className={`flex min-w-0 flex-1 items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
                  active
                    ? isDark
                      ? "bg-emerald-500/12 text-emerald-100"
                      : "bg-emerald-50 text-emerald-800"
                    : isDark
                      ? "text-slate-300 hover:bg-white/[0.04]"
                      : "text-stone-700 hover:bg-stone-100"
                } ${dropTargetPath === child.path ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-300") : ""}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <IconFolder />
                  <span className="truncate font-medium">{child.name}</span>
                </span>
                <span className={`text-xs ${active ? (isDark ? "text-emerald-200/80" : "text-emerald-700/80") : isDark ? "text-slate-500" : "text-stone-400"}`}>{child.itemCount}</span>
              </button>
              <button
                type="button"
                onClick={() => onCreateFolder(child.path)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-white" : "text-stone-400 hover:bg-stone-100 hover:text-stone-800"}`}
                title={`Create a folder inside ${child.name}`}
              >
                <IconPlus />
              </button>
            </div>
            {!isCollapsed ? (
              <div className="mt-1">
                <FolderList
                  node={child}
                  activePath={activePath}
                  collapsed={collapsed}
                  onToggleFolder={onToggleFolder}
                  onSelect={onSelect}
                  onCreateFolder={onCreateFolder}
                  onDropNote={onDropNote}
                  dropTargetPath={dropTargetPath}
                  onDropTargetChange={onDropTargetChange}
                  isDark={isDark}
                  depth={depth + 1}
                />
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function PanelCard({
  title,
  count,
  action,
  isDark,
  children,
}: {
  title: string
  count?: number
  action?: ReactNode
  isDark: boolean
  children: ReactNode
}) {
  return (
    <section className={`overflow-hidden rounded-lg border p-4 ${isDark ? "border-white/8 bg-[#07101d]/88" : "border-stone-200 bg-white/90"}`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{title}</p>
        <div className="flex items-center gap-2 shrink-0">
          {typeof count === "number" ? (
            <span className={`inline-flex h-6 min-w-6 items-center justify-center rounded-full px-2 text-xs font-semibold ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-stone-100 text-stone-700"}`}>
              {count}
            </span>
          ) : null}
          {action}
        </div>
      </div>
      {children}
    </section>
  )
}

function PanelLink({ children, isDark }: { children: ReactNode; isDark: boolean }) {
  return (
    <button
      type="button"
      className={`mt-3 inline-flex items-center gap-2 text-sm font-medium ${isDark ? "text-sky-300 hover:text-sky-200" : "text-sky-700 hover:text-sky-800"}`}
    >
      {children}
      <IconArrowRight />
    </button>
  )
}

function InfoLine({
  label,
  value,
  isDark,
  tone,
  activeDot,
}: {
  label: string
  value: string
  isDark: boolean
  tone?: boolean
  activeDot?: boolean
}) {
  const valueClass = tone
    ? isDark
      ? "rounded-full bg-sky-500/14 px-2.5 py-1 text-sky-200"
      : "rounded-full bg-sky-50 px-2.5 py-1 text-sky-700"
    : isDark
      ? "text-slate-100"
      : "text-stone-900"

  return (
    <div className="mb-3 flex items-start justify-between gap-3 text-sm">
      <span className={isDark ? "text-slate-400" : "text-stone-500"}>{label}</span>
      <span className={`max-w-[10rem] text-right ${valueClass} ${activeDot ? "inline-flex items-center gap-2" : ""}`}>
        {activeDot ? <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> : null}
        {value}
      </span>
    </div>
  )
}

function RelationStack({
  items,
  emptyLabel,
  onOpen,
  isDark,
}: {
  items: { id: string; label: string; secondary?: string | null; reference: string }[]
  emptyLabel: string
  onOpen: (reference: string) => void
  isDark: boolean
}) {
  if (!items.length) {
    return <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>{emptyLabel}</p>
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onOpen(item.reference)}
          className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-2.5 text-left text-sm transition ${isDark ? "bg-white/[0.03] text-slate-100 hover:bg-white/[0.06]" : "bg-stone-50 text-stone-800 hover:bg-stone-100"}`}
        >
          <span className="truncate">{item.label}</span>
          {item.secondary ? <span className={`shrink-0 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{item.secondary}</span> : null}
        </button>
      ))}
    </div>
  )
}

function MiniGraphPreview({
  currentLabel,
  nodes,
  isDark,
}: {
  currentLabel: string
  nodes: { id: string; label: string }[]
  isDark: boolean
}) {
  const positions = [
    { left: 20, top: 23, tone: "border-teal-400/20 bg-teal-500/12 text-teal-200" },
    { left: 80, top: 23, tone: "border-violet-400/20 bg-violet-500/12 text-violet-200" },
    { left: 18, top: 76, tone: "border-sky-400/20 bg-sky-500/12 text-sky-200" },
    { left: 82, top: 77, tone: "border-amber-400/20 bg-amber-500/12 text-amber-100" },
  ] as const

  if (!nodes.length) {
    return (
      <div className={`flex min-h-[13rem] items-center justify-center rounded-md border border-dashed text-sm ${isDark ? "border-white/8 text-slate-500" : "border-stone-300 text-stone-500"}`}>
        Link a few notes to see the mini graph preview.
      </div>
    )
  }

  return (
    <div className={`relative min-h-[13rem] overflow-hidden rounded-md border ${isDark ? "border-white/8 bg-[#091321]" : "border-stone-200 bg-stone-50"}`}>
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {nodes.map((node, index) => {
          const position = positions[index]
          return (
            <line
              key={node.id}
              x1="50"
              y1="54"
              x2={String(position.left)}
              y2={String(position.top)}
              stroke={isDark ? "rgba(56,189,248,0.28)" : "rgba(59,130,246,0.24)"}
              strokeWidth="0.7"
            />
          )
        })}
      </svg>

      <div className="absolute left-1/2 top-[54%] z-10 -translate-x-1/2 -translate-y-1/2">
        <div className={`flex h-[5.3rem] w-[5.3rem] items-center justify-center rounded-full border text-center ${isDark ? "border-emerald-400/55 bg-emerald-500/18 text-white" : "border-emerald-300 bg-emerald-50 text-emerald-900"}`}>
          <span className="max-w-[4rem] text-xs font-medium leading-4">{currentLabel}</span>
        </div>
      </div>

      {nodes.map((node, index) => {
        const position = positions[index]
        return (
          <div
            key={node.id}
            className="absolute z-10"
            style={{ left: `${position.left}%`, top: `${position.top}%`, transform: "translate(-50%, -50%)" }}
          >
            <div className={`max-w-[8rem] rounded-full border px-3 py-2 text-xs font-medium leading-4 ${isDark ? position.tone : "border-stone-200 bg-white text-stone-700"}`}>
              {node.label}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function IconSearch() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
}

function IconSliders() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h8M16 6h4M10 6a2 2 0 11-4 0 2 2 0 014 0zM4 12h4M12 12h8M14 12a2 2 0 11-4 0 2 2 0 014 0zM4 18h10M18 18h2M16 18a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
}

function IconPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
}

function IconCheck() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 12.5l4 4L19 7.5" /></svg>
}

function IconCopy() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 9h10v11H9z" /><path strokeLinecap="round" strokeLinejoin="round" d="M5 15H4V5h10v1" /></svg>
}

function IconUpload({ className = "" }: { className?: string }) {
  return <svg className={`h-4 w-4 ${className}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4M7 9l5-5 5 5M5 20h14" /></svg>
}

function IconDocument({ small = false }: { small?: boolean }) {
  return <svg className={small ? "h-4 w-4 shrink-0" : "h-5 w-5"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 4v4h4M9 13h6M9 16h4" /></svg>
}

function IconFolder() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h6l2 2h8v9a2 2 0 01-2 2H6a2 2 0 01-2-2V7z" /></svg>
}

function IconChevron({ open }: { open: boolean }) {
  return <svg className={`h-4 w-4 transition ${open ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 6l6 6-6 6" /></svg>
}

function IconStar({ filled }: { filled: boolean }) {
  return filled
    ? <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M11.2 3.6a.85.85 0 011.6 0l2 4.78 5.17.44a.85.85 0 01.48 1.5l-3.93 3.4 1.19 5.04a.85.85 0 01-1.27.92L12 16.92l-4.44 2.76a.85.85 0 01-1.27-.92l1.19-5.04-3.93-3.4a.85.85 0 01.48-1.5l5.17-.44 2-4.78z" /></svg>
    : <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11.2 3.6a.85.85 0 011.6 0l2 4.78 5.17.44a.85.85 0 01.48 1.5l-3.93 3.4 1.19 5.04a.85.85 0 01-1.27.92L12 16.92l-4.44 2.76a.85.85 0 01-1.27-.92l1.19-5.04-3.93-3.4a.85.85 0 01.48-1.5l5.17-.44 2-4.78z" /></svg>
}

function IconExpand() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M15 4h5v5M9 20H4v-5M20 9V4h-5M4 15v5h5" /></svg>
}

function IconArrowUpRight() {
  return <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M7 17L17 7M9 7h8v8" /></svg>
}

function IconArrowRight() {
  return <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" /></svg>
}

function IconMore() {
  return <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.8" /><circle cx="12" cy="12" r="1.8" /><circle cx="19" cy="12" r="1.8" /></svg>
}

function IconPencil() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20l4.5-1 9-9a2.2 2.2 0 10-3.1-3.1l-9 9L4 20z" /><path strokeLinecap="round" strokeLinejoin="round" d="M13 6l5 5" /></svg>
}
