import { useEffect, useRef, useState } from "react"
import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"
import type { Character } from "@/types/character"

interface SceneSelectionActionsProps {
  bookId: string
  chapterNumber: number | null
  isDark: boolean
  menuPosition: { top: number; left: number } | null
  selectedText: string
  dialogOpen: boolean
  onOpenDialog: () => void
  onCloseDialog: () => void
  onCreated: (character: Character) => void
}

export function SceneSelectionActions({
  bookId,
  chapterNumber,
  isDark,
  menuPosition,
  selectedText,
  dialogOpen,
  onOpenDialog,
  onCloseDialog,
  onCreated,
}: SceneSelectionActionsProps) {
  return (
    <>
      {menuPosition ? (
        <div
          className="pointer-events-none fixed z-50 hidden -translate-x-1/2 xl:block"
          style={{ top: menuPosition.top, left: menuPosition.left }}
        >
          <div className={`pointer-events-auto flex items-center gap-2 rounded-sm border px-2 py-2 ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={onOpenDialog}
              className={`rounded-sm px-3 py-1.5 text-xs font-medium ${isDark ? "bg-violet-700/30 text-violet-200" : "bg-violet-100 text-violet-800"}`}
            >
              Add as character
            </button>
          </div>
        </div>
      ) : null}

      <AddCharacterFromSelection
        bookId={bookId}
        selectedText={selectedText}
        isDark={isDark}
        firstChapter={chapterNumber ?? undefined}
        open={dialogOpen}
        onClose={onCloseDialog}
        onCreated={onCreated}
      />
    </>
  )
}

export function useSceneSelectionMenu(setStatus: (message: string) => void) {
  const [addCharacterOpen, setAddCharacterOpen] = useState(false)
  const [addCharacterText, setAddCharacterText] = useState("")
  const [selectionMenu, setSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)
  const selectionRef = useRef("")
  useEffect(() => {
    const syncSelectionMenu = () => {
      const selection = window.getSelection()
      const selectedText = selection?.toString().trim() ?? ""
      const editor = document.querySelector<HTMLElement>(`[data-editor-key="scene-workspace-editor"]`)
      const anchorNode = selection?.anchorNode

      if (!selection || !selectedText || !editor || !anchorNode || !editor.contains(anchorNode) || selection.rangeCount === 0) {
        setSelectionMenu(null)
        return
      }

      const rect = selection.getRangeAt(0).getBoundingClientRect()
      if (!rect.width && !rect.height) {
        setSelectionMenu(null)
        return
      }

      selectionRef.current = selectedText
      setSelectionMenu({
        text: selectedText.slice(0, 100),
        top: Math.max(8, rect.top - 48),
        left: Math.max(100, Math.min(window.innerWidth - 100, rect.left + rect.width / 2)),
      })
    }

    document.addEventListener("selectionchange", syncSelectionMenu)
    window.addEventListener("resize", syncSelectionMenu)
    window.addEventListener("scroll", syncSelectionMenu, true)
    return () => {
      document.removeEventListener("selectionchange", syncSelectionMenu)
      window.removeEventListener("resize", syncSelectionMenu)
      window.removeEventListener("scroll", syncSelectionMenu, true)
    }
  }, [])

  const openAddCharacterFromSelection = () => {
    const text = selectionRef.current.trim()
    if (!text) {
      setStatus("Select a character name in the scene first.")
      return
    }
    setAddCharacterText(text)
    setAddCharacterOpen(true)
    setSelectionMenu(null)
  }

  const handleCharacterCreated = (character: Character) => {
    setStatus(`Character "${character.name}" added to the story bible.`)
  }

  return { selectionMenu, addCharacterOpen, addCharacterText, setAddCharacterOpen, openAddCharacterFromSelection, handleCharacterCreated }
}
