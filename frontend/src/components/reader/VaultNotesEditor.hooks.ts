import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react"

import { booksApi } from "@/lib/api/books"
import { normalizeWorkspaceFolderPath } from "@/lib/utils/workspacePaths"
import type { VaultNote } from "@/types/book"
import {
  FAVORITES_STORAGE_KEY,
  FOLDERS_STORAGE_KEY_PREFIX,
  TOOLBAR_BUTTON_DEFS,
  insertTextSnippet,
  noteTitle,
  prefixSelectedTextLines,
  wrapSelectedText,
} from "./VaultNotesEditor.helpers"

type DraftMap = Record<string, string>
type UpdateDraft = (path: string, value: string) => void

export function useVaultNotesLocalStoragePersistence({
  bookId,
  customFolders,
  favorites,
}: {
  bookId: string
  customFolders: string[]
  favorites: Record<string, boolean>
}) {
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
    const serializedFolders = JSON.stringify(
      [...new Set(customFolders.map((folder) => normalizeWorkspaceFolderPath(folder)).filter(Boolean))].sort()
    )
    const id = window.requestIdleCallback
      ? window.requestIdleCallback(() => {
          window.localStorage.setItem(`${FOLDERS_STORAGE_KEY_PREFIX}${bookId}`, serializedFolders)
        })
      : window.setTimeout(() => {
          window.localStorage.setItem(`${FOLDERS_STORAGE_KEY_PREFIX}${bookId}`, serializedFolders)
        }, 0)
    return () => {
      if (typeof id === "number") window.clearTimeout(id)
      else if (window.cancelIdleCallback) window.cancelIdleCallback(id as number)
    }
  }, [bookId, customFolders])
}

export function useVaultNotesMarkdownToolbar({
  drafts,
  selectedNote,
  textareaRef,
  updateDraft,
}: {
  drafts: DraftMap
  selectedNote: VaultNote | null
  textareaRef: RefObject<HTMLTextAreaElement | null>
  updateDraft: UpdateDraft
}) {
  const applyTextEdit = useCallback(
    (edit: (currentValue: string, selectionRange: { start: number; end: number }) => { value: string; start: number; end: number }) => {
      const textarea = textareaRef.current
      if (!textarea || !selectedNote) return
      const start = textarea.selectionStart
      const end = textarea.selectionEnd
      const currentValue = drafts[selectedNote.path] ?? selectedNote.content
      const nextEdit = edit(currentValue, { start, end })
      updateDraft(selectedNote.path, nextEdit.value)
      requestAnimationFrame(() => {
        textarea.focus()
        textarea.setSelectionRange(nextEdit.start, nextEdit.end)
      })
    },
    [drafts, selectedNote, textareaRef, updateDraft],
  )

  const replaceSelectedText = useCallback(
    (before: string, after = before, fallback = "") => {
      applyTextEdit((currentValue, selectionRange) => wrapSelectedText(currentValue, selectionRange, before, after, fallback))
    },
    [applyTextEdit],
  )

  const prefixSelectedLines = useCallback(
    (prefix: string, fallback: string) => {
      applyTextEdit((currentValue, selectionRange) => prefixSelectedTextLines(currentValue, selectionRange, prefix, fallback))
    },
    [applyTextEdit],
  )

  const insertSnippet = useCallback(
    (snippet: string) => {
      applyTextEdit((currentValue, selectionRange) => insertTextSnippet(currentValue, selectionRange, snippet))
    },
    [applyTextEdit],
  )

  return useMemo(
    () =>
      TOOLBAR_BUTTON_DEFS.map((def) => ({
        key: def.key,
        label: def.label,
        title: def.title,
        className: "className" in def ? def.className : undefined,
        action: () => {
          if (def.kind === "wrap") replaceSelectedText(def.open, def.close, def.fallbackText)
          else if (def.kind === "prefix") prefixSelectedLines(def.prefix, def.fallbackText)
          else insertSnippet(def.snippet)
        },
      })),
    [insertSnippet, prefixSelectedLines, replaceSelectedText],
  )
}

export function useVaultNotesSelectionMenu(textareaRef: RefObject<HTMLTextAreaElement | null>) {
  const [notesSelectionMenu, setNotesSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)
  const [addCharacterOpen, setAddCharacterOpen] = useState(false)
  const [addCharacterText, setAddCharacterText] = useState("")
  const notesSelectionRef = useRef("")

  const syncNotesSelectionMenu = useCallback(
    (mouseEvent?: Pick<MouseEvent, "clientX" | "clientY">) => {
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
    },
    [textareaRef],
  )

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (target.closest("[data-notes-add-character]")) return
      setNotesSelectionMenu(null)
    }
    document.addEventListener("click", handleClick)
    return () => document.removeEventListener("click", handleClick)
  }, [])

  const openAddCharacterFromNotes = useCallback(() => {
    const text = notesSelectionRef.current.trim()
    if (!text) return
    setAddCharacterText(text)
    setAddCharacterOpen(true)
    setNotesSelectionMenu(null)
  }, [])

  return {
    addCharacterOpen,
    addCharacterText,
    notesSelectionMenu,
    openAddCharacterFromNotes,
    setAddCharacterOpen,
    syncNotesSelectionMenu,
  }
}

export function useVaultNoteSceneSender({
  bookId,
  sceneChapterNumber,
  selectedContent,
  selectedNote,
  setStatus,
}: {
  bookId: string
  sceneChapterNumber: number | null
  selectedContent: string
  selectedNote: VaultNote | null
  setStatus: (status: string | null) => void
}) {
  const [sceneSending, setSceneSending] = useState(false)

  const sendToScene = useCallback(async () => {
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
  }, [bookId, sceneChapterNumber, selectedContent, selectedNote, setStatus])

  return { sceneSending, sendToScene }
}
