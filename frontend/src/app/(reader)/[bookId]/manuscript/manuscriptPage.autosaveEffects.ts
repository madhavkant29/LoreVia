import { useEffect, type Dispatch, type SetStateAction } from "react"

import {
  buildManuscriptAutosaveKey,
  serializeAutosaveDraft,
  serializeSceneAutosaveDraft,
} from "@/lib/utils/manuscriptEditor"
import type { NovelScene } from "@/types/book"
import {
  buildSceneDraftStorageKey,
  type BookDraftMap,
} from "./manuscriptPage.helpers"

type AutosaveState = Record<number, { status: "pending" | "saved" | "error"; updatedAt?: string }>

type UseManuscriptAutosaveEffectsArgs = {
  activeChapterNumber: number
  bookDrafts: BookDraftMap
  bookId: string
  dirtyDrafts: number[]
  editingScene: NovelScene | null
  hasPendingEdits: boolean
  sceneBodyDraft: string
  sceneChapterDraft: number | null
  sceneDescriptionDraft: string
  sceneDraftDirty: boolean
  sceneEditorOpen: boolean
  sceneTitleDraft: string
  setAutosaveState: Dispatch<SetStateAction<AutosaveState>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptAutosaveEffects({
  activeChapterNumber,
  bookDrafts,
  bookId,
  dirtyDrafts,
  editingScene,
  hasPendingEdits,
  sceneBodyDraft,
  sceneChapterDraft,
  sceneDescriptionDraft,
  sceneDraftDirty,
  sceneEditorOpen,
  sceneTitleDraft,
  setAutosaveState,
  setStatusMessage,
}: UseManuscriptAutosaveEffectsArgs) {
  useEffect(() => {
    if (typeof window === "undefined" || dirtyDrafts.length === 0) return

    setAutosaveState((current) => {
      const next = { ...current }
      for (const chapterNumber of dirtyDrafts) {
        next[chapterNumber] = {
          ...next[chapterNumber],
          status: "pending",
        }
      }
      return next
    })

    const handle = window.setTimeout(() => {
      try {
        const updatedAt = new Date().toISOString()
        for (const chapterNumber of dirtyDrafts) {
          const draft = bookDrafts[chapterNumber]
          if (!draft) continue
          window.localStorage.setItem(
            buildManuscriptAutosaveKey(bookId, chapterNumber),
            serializeAutosaveDraft({
              title: draft.title,
              text: draft.text,
              html: draft.html,
              updatedAt,
            })
          )
        }
        setAutosaveState((current) => {
          const next = { ...current }
          for (const chapterNumber of dirtyDrafts) {
            if (!(chapterNumber in next)) continue
            next[chapterNumber] = {
              status: "saved",
              updatedAt,
            }
          }
          return next
        })
      } catch {
        setAutosaveState((current) => {
          const next = { ...current }
          for (const chapterNumber of dirtyDrafts) {
            next[chapterNumber] = {
              ...next[chapterNumber],
              status: "error",
            }
          }
          return next
        })
      }
    }, 900)

    return () => window.clearTimeout(handle)
  }, [bookDrafts, bookId, dirtyDrafts, setAutosaveState])

  useEffect(() => {
    if (typeof window === "undefined" || !sceneEditorOpen || !sceneDraftDirty) return

    const handle = window.setTimeout(() => {
      try {
        window.localStorage.setItem(
          buildSceneDraftStorageKey(bookId, editingScene, sceneChapterDraft),
          serializeSceneAutosaveDraft({
            title: sceneTitleDraft,
            description: sceneDescriptionDraft,
            body: sceneBodyDraft,
            chapterNumber: sceneChapterDraft,
            updatedAt: new Date().toISOString(),
          })
        )
      } catch {
        setStatusMessage("Local scene autosave failed.")
      }
    }, 900)

    return () => window.clearTimeout(handle)
  }, [
    bookId,
    editingScene,
    sceneBodyDraft,
    sceneChapterDraft,
    sceneDescriptionDraft,
    sceneDraftDirty,
    sceneEditorOpen,
    sceneTitleDraft,
    setStatusMessage,
  ])

  useEffect(() => {
    if (typeof window === "undefined" || !hasPendingEdits) return

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ""
    }

    const handlePageHide = () => {
      const draft = bookDrafts[activeChapterNumber]
      if (!draft?.text?.trim()) return
      const formData = new FormData()
      formData.append("text", draft.text)
      formData.append("html", draft.html ?? "")
      formData.append("title", (draft.title ?? "").trim() || "")
      formData.append("chapter_number", String(activeChapterNumber))
      formData.append("replace_existing", "true")
      navigator.sendBeacon(
        `/api/v1/books/${bookId}/manuscript/import`,
        formData,
      )
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    window.addEventListener("pagehide", handlePageHide)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
      window.removeEventListener("pagehide", handlePageHide)
    }
  }, [hasPendingEdits, bookDrafts, activeChapterNumber, bookId])
}
