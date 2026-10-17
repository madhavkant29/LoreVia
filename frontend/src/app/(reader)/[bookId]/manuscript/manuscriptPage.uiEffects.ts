import { useEffect, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import {
  applyAnnotationHighlights,
  buildAnnotationSelectionAnchor,
  clearAnnotationHighlights,
  type ManuscriptSelectionAnchor,
  scrollAnnotationRangeIntoView,
} from "@/lib/utils/manuscriptAnnotations"
import type {
  ChapterVersion,
  ManuscriptAnnotation,
  ReadabilityMetrics,
} from "@/types/book"
import type { Character } from "@/types/character"
import type { InlineContinuityResponse } from "@/types/intelligence"
import type { SearchResult } from "@/types/reader"
import type { BookDraftMap } from "./manuscriptPage.helpers"
import type { DraftSurfaceMode, EditorMode, RightPane, WorkspaceTab } from "./manuscriptPage.constants"
type SelectionMenu = { text: string; top: number; left: number } | null
type AnnotationAnchorState = {
  quote: string
  anchorContextBefore: string | null
  anchorContextAfter: string | null
  startOffset: number
  endOffset: number
} | null

type UseManuscriptUiEffectsArgs = {
  activeAnnotationId: string | null
  activeChapterNumber: number
  bookDrafts: BookDraftMap
  bookId: string
  chapterAnnotations: ManuscriptAnnotation[]
  chapterRefs: RefObject<Record<number, HTMLDivElement | null>>
  characters: Character[]
  deferredChecksSeedRef: MutableRefObject<{ chapterNumber: number; text: string } | null>
  draftSurfaceMode: DraftSurfaceMode
  editorMode: EditorMode
  focusMode: boolean
  fontSizeLocked: boolean
  html: string
  jumpTarget: number | null
  manuscriptSectionRef: RefObject<HTMLDivElement | null>
  pendingAnnotationJumpIdRef: MutableRefObject<string | null>
  recallQuery: string
  recallResults: SearchResult[]
  searchInputRef: RefObject<HTMLInputElement | null>
  selectedChapter: number | null
  selectionMenuAnchorRef: MutableRefObject<ManuscriptSelectionAnchor | null>
  annotationRangesRef: MutableRefObject<Map<string, Range>>
  showLeftRail: boolean
  statusMessage: string | null
  text: string
  workspaceTab: WorkspaceTab
  setActiveAnnotationId: Dispatch<SetStateAction<string | null>>
  setActiveFindIndex: Dispatch<SetStateAction<number>>
  setActiveRightPane: Dispatch<SetStateAction<RightPane>>
  setAnnotationAnchor: Dispatch<SetStateAction<AnnotationAnchorState>>
  setAnnotationDraft: Dispatch<SetStateAction<string>>
  setChapterVersions: Dispatch<SetStateAction<ChapterVersion[]>>
  setContinuityLoading: Dispatch<SetStateAction<boolean>>
  setFontSize: Dispatch<SetStateAction<number>>
  setInlineContinuity: Dispatch<SetStateAction<InlineContinuityResponse | null>>
  setReadability: Dispatch<SetStateAction<ReadabilityMetrics | null>>
  setReadabilityLoading: Dispatch<SetStateAction<boolean>>
  setRecallCharacter: Dispatch<SetStateAction<Character | null>>
  setRecallLoading: Dispatch<SetStateAction<boolean>>
  setRecallResults: Dispatch<SetStateAction<SearchResult[]>>
  setSelectionMenu: Dispatch<SetStateAction<SelectionMenu>>
  setShowLeftRail: Dispatch<SetStateAction<boolean>>
  setShowRightRail: Dispatch<SetStateAction<boolean>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptUiEffects({
  activeAnnotationId,
  activeChapterNumber,
  bookDrafts,
  bookId,
  chapterAnnotations,
  chapterRefs,
  characters,
  deferredChecksSeedRef,
  draftSurfaceMode,
  editorMode,
  focusMode,
  fontSizeLocked,
  html,
  jumpTarget,
  manuscriptSectionRef,
  pendingAnnotationJumpIdRef,
  recallQuery,
  recallResults,
  searchInputRef,
  selectedChapter,
  selectionMenuAnchorRef,
  annotationRangesRef,
  showLeftRail,
  statusMessage,
  text,
  workspaceTab,
  setActiveAnnotationId,
  setActiveFindIndex,
  setActiveRightPane,
  setAnnotationAnchor,
  setAnnotationDraft,
  setChapterVersions,
  setContinuityLoading,
  setFontSize,
  setInlineContinuity,
  setReadability,
  setReadabilityLoading,
  setRecallCharacter,
  setRecallLoading,
  setRecallResults,
  setSelectionMenu,
  setShowLeftRail,
  setShowRightRail,
  setStatusMessage,
}: UseManuscriptUiEffectsArgs) {
  useEffect(() => {
    if (!statusMessage) return
    const handle = window.setTimeout(() => setStatusMessage(null), 3200)
    return () => window.clearTimeout(handle)
  }, [statusMessage, setStatusMessage])

  useEffect(() => {
    if (!showLeftRail || selectedChapter === null) {
      setChapterVersions([])
    }
  }, [selectedChapter, showLeftRail, setChapterVersions])

  useEffect(() => {
    if (editorMode !== "book" || jumpTarget === null) return
    const handle = window.setTimeout(() => {
      const node = chapterRefs.current[jumpTarget]
      if (node) {
        node.scrollIntoView({ behavior: "smooth", block: "start" })
      }
    }, 150)
    return () => window.clearTimeout(handle)
  }, [editorMode, jumpTarget, bookDrafts, chapterRefs])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        if (!searchInputRef.current) return
        event.preventDefault()
        searchInputRef.current?.focus()
        searchInputRef.current?.select()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [searchInputRef])

  useEffect(() => {
    if (fontSizeLocked) return

    const updateFontSize = () => {
      const width = manuscriptSectionRef.current?.clientWidth ?? window.innerWidth
      if (width <= 900) {
        setFontSize(12)
      } else if (width <= 1200) {
        setFontSize(13)
      } else if (width <= 1600) {
        setFontSize(14)
      } else {
        setFontSize(15)
      }
    }

    updateFontSize()
    window.addEventListener("resize", updateFontSize)
    return () => window.removeEventListener("resize", updateFontSize)
  }, [fontSizeLocked, manuscriptSectionRef, setFontSize])

  useEffect(() => {
    const trimmed = recallQuery.trim()
    if (trimmed.length < 2) {
      setRecallResults([])
      setRecallCharacter(null)
      setRecallLoading(false)
      return
    }

    const normalized = trimmed.toLowerCase()
    const exact = characters.find((character) =>
      character.name.toLowerCase() === normalized || character.aliases.some((alias) => alias.toLowerCase() === normalized)
    ) || null
    setRecallCharacter(exact)

    const handle = window.setTimeout(() => {
      setRecallLoading(true)
      readerApi.search(bookId, trimmed)
        .then((results) => setRecallResults(results.slice(0, 6)))
        .catch(() => setRecallResults([]))
        .finally(() => setRecallLoading(false))
    }, 250)

    return () => window.clearTimeout(handle)
  }, [bookId, characters, recallQuery, setRecallCharacter, setRecallLoading, setRecallResults])

  useEffect(() => {
    setActiveFindIndex(0)
  }, [recallResults.length, recallQuery, setActiveFindIndex])

  useEffect(() => {
    setAnnotationAnchor(null)
    setAnnotationDraft("")
    selectionMenuAnchorRef.current = null
  }, [activeChapterNumber, selectionMenuAnchorRef, setAnnotationAnchor, setAnnotationDraft])

  useEffect(() => {
    if (focusMode) return
    if (workspaceTab === "write") {
      setShowLeftRail(false)
      setShowRightRail(false)
      setActiveRightPane((current) => current === "insights" ? "context" : current)
      return
    }
    if (workspaceTab === "plan") {
      setShowLeftRail(false)
      setShowRightRail(false)
      return
    }
    if (workspaceTab === "analysis") {
      setShowLeftRail(false)
      setShowRightRail(true)
      setActiveRightPane((current) => current === "character" ? "character" : "insights")
    }
  }, [focusMode, workspaceTab, setActiveRightPane, setShowLeftRail, setShowRightRail])

  useEffect(() => {
    if (workspaceTab !== "write" || editorMode !== "chapter" || draftSurfaceMode !== "edit") {
      setSelectionMenu(null)
      return
    }

    const syncSelectionMenu = () => {
      const selection = window.getSelection()
      const selectedText = selection?.toString().trim() ?? ""
      const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
      const anchorNode = selection?.anchorNode

      if (!selection || !selectedText || !editor || !anchorNode || !editor.contains(anchorNode) || selection.rangeCount === 0) {
        selectionMenuAnchorRef.current = null
        setSelectionMenu(null)
        return
      }

      const rect = selection.getRangeAt(0).getBoundingClientRect()
      if (!rect.width && !rect.height) {
        selectionMenuAnchorRef.current = null
        setSelectionMenu(null)
        return
      }

      const anchor = buildAnnotationSelectionAnchor(editor)
      if (!anchor) {
        selectionMenuAnchorRef.current = null
        setSelectionMenu(null)
        return
      }

      selectionMenuAnchorRef.current = anchor
      setSelectionMenu({
        text: selectedText,
        top: rect.top + window.scrollY - 56,
        left: rect.left + window.scrollX + (rect.width / 2),
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
  }, [activeChapterNumber, draftSurfaceMode, editorMode, selectionMenuAnchorRef, setSelectionMenu, workspaceTab])

  useEffect(() => {
    if (editorMode !== "chapter") {
      clearAnnotationHighlights()
      annotationRangesRef.current = new Map()
      return
    }

    const frame = window.requestAnimationFrame(() => {
      const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
      const nextRanges = applyAnnotationHighlights(editor, chapterAnnotations, activeAnnotationId)
      annotationRangesRef.current = nextRanges

      const pendingId = pendingAnnotationJumpIdRef.current
      if (!pendingId) return
      const pendingRange = nextRanges.get(pendingId)
      if (!pendingRange) return
      scrollAnnotationRangeIntoView(pendingRange)
      pendingAnnotationJumpIdRef.current = null
    })

    return () => {
      window.cancelAnimationFrame(frame)
      clearAnnotationHighlights()
      annotationRangesRef.current = new Map()
    }
  }, [activeAnnotationId, activeChapterNumber, annotationRangesRef, chapterAnnotations, editorMode, html, pendingAnnotationJumpIdRef])

  useEffect(() => {
    if (!activeAnnotationId) return
    if (chapterAnnotations.some((annotation) => annotation.id === activeAnnotationId)) return
    setActiveAnnotationId(null)
  }, [activeAnnotationId, chapterAnnotations, setActiveAnnotationId])

  useEffect(() => {
    const trimmed = text.trim()
    if (!trimmed) {
      setReadability(null)
      setInlineContinuity(null)
      setReadabilityLoading(false)
      setContinuityLoading(false)
      return
    }
    if (
      deferredChecksSeedRef.current?.chapterNumber === activeChapterNumber
      && deferredChecksSeedRef.current.text === trimmed
    ) {
      deferredChecksSeedRef.current = null
      return
    }
    const handle = window.setTimeout(() => {
      setReadabilityLoading(true)
      setContinuityLoading(false)
      booksApi.getReadability(bookId, trimmed)
        .then(setReadability)
        .catch(() => setReadability(null))
        .finally(() => setReadabilityLoading(false))
    }, 3000)
    return () => window.clearTimeout(handle)
  }, [
    activeChapterNumber,
    bookId,
    deferredChecksSeedRef,
    setContinuityLoading,
    setInlineContinuity,
    setReadability,
    setReadabilityLoading,
    text,
  ])
}
