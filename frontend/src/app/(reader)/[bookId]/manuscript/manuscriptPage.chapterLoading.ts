import type { Route } from "next"
import type { QueryClient } from "@tanstack/react-query"
import { startTransition, useCallback, useEffect, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { MANUSCRIPT_CHAPTER_INCLUDE, readerApi } from "@/lib/api/reader"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { captureTiming } from "@/lib/analytics/posthog"
import { bookCacheKey } from "@/lib/query/cacheKeys"
import {
  buildManuscriptAutosaveKey,
  parseAutosaveDraft,
} from "@/lib/utils/manuscriptEditor"
import type {
  Book,
  ManuscriptWorkspaceTree,
  WriterWorkspace,
} from "@/types/book"
import type { Character } from "@/types/character"
import type { EditorialReview, EditorialReviewPassage } from "@/types/intelligence"
import type { ChapterListResponse } from "@/types/reader"
import {
  hydrateChapterMediaHtml,
  textToHtml,
  type BookDraftMap,
} from "./manuscriptPage.helpers"

type AutosaveState = Record<number, { status: "pending" | "saved" | "error"; updatedAt?: string }>
type ManuscriptRouter = Pick<
  ReturnType<(typeof import("next/navigation"))["useRouter"]>,
  "replace"
>

type UseManuscriptChapterLoadingArgs = {
  authHydrated: boolean
  bookDrafts: BookDraftMap
  bookId: string
  chapterList: ChapterListResponse | null
  editorMode: "chapter" | "book"
  nextChapterNumber: number
  queryClient: QueryClient
  router: ManuscriptRouter
  selectedChapter: number | null
  userTier: string | null | undefined
  deferredChecksSeedRef: MutableRefObject<{ chapterNumber: number; text: string } | null>
  firstChapterLoadedCapturedRef: MutableRefObject<boolean>
  initialChapterLoadedRef: MutableRefObject<number | null>
  manuscriptLoadStartedAtRef: MutableRefObject<number | null>
  refetchWorkspaceTree: () => Promise<{ data?: ManuscriptWorkspaceTree | null }>
  setAutosaveState: Dispatch<SetStateAction<AutosaveState>>
  setBook: Dispatch<SetStateAction<Book | null>>
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setChapterList: Dispatch<SetStateAction<ChapterListResponse | null>>
  setChapterTitle: Dispatch<SetStateAction<string>>
  setCharacters: Dispatch<SetStateAction<Character[]>>
  setCollapsedSceneGroups: Dispatch<SetStateAction<Record<string, boolean>>>
  setContentVersionByChapter: Dispatch<SetStateAction<Record<number, number>>>
  setDirtyDrafts: Dispatch<SetStateAction<number[]>>
  setDraftChapterNumber: Dispatch<SetStateAction<number | null>>
  setFullBookLoading: Dispatch<SetStateAction<boolean>>
  setHtml: Dispatch<SetStateAction<string>>
  setLoading: Dispatch<SetStateAction<boolean>>
  setReview: Dispatch<SetStateAction<EditorialReview | null>>
  setReviewPassages: Dispatch<SetStateAction<EditorialReviewPassage[]>>
  setSelectedChapter: Dispatch<SetStateAction<number | null>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setText: Dispatch<SetStateAction<string>>
  setWorkspaceTree: Dispatch<SetStateAction<ManuscriptWorkspaceTree | null>>
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
}

export function useManuscriptChapterLoading({
  authHydrated,
  bookDrafts,
  bookId,
  chapterList,
  deferredChecksSeedRef,
  editorMode,
  firstChapterLoadedCapturedRef,
  initialChapterLoadedRef,
  manuscriptLoadStartedAtRef,
  nextChapterNumber,
  queryClient,
  refetchWorkspaceTree,
  router,
  selectedChapter,
  setAutosaveState,
  setBook,
  setBookDrafts,
  setChapterList,
  setChapterTitle,
  setCharacters,
  setCollapsedSceneGroups,
  setContentVersionByChapter,
  setDirtyDrafts,
  setDraftChapterNumber,
  setFullBookLoading,
  setHtml,
  setLoading,
  setReview,
  setReviewPassages,
  setSelectedChapter,
  setStatusMessage,
  setText,
  setWorkspaceTree,
  setWriterWorkspace,
  userTier,
}: UseManuscriptChapterLoadingArgs) {
  const [loadError, setLoadError] = useState<string | null>(null)
  const selectedChapterRef = useRef(selectedChapter)
  selectedChapterRef.current = selectedChapter

  const markDraftDirty = useCallback((chapterNumber: number) => {
    setDirtyDrafts((current) => (current.includes(chapterNumber) ? current : [...current, chapterNumber]))
  }, [setDirtyDrafts])

  const clearDraftDirty = (chapterNumber: number) => {
    setDirtyDrafts((current) => current.filter((value) => value !== chapterNumber))
    setAutosaveState((current) => {
      const next = { ...current }
      delete next[chapterNumber]
      return next
    })
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(buildManuscriptAutosaveKey(bookId, chapterNumber))
    }
  }

  const getRecoveredDraft = useCallback((chapterNumber: number, fallbackDraft: { title: string; text: string; html: string }) => {
    if (typeof window === "undefined") {
      return { draft: fallbackDraft, recovered: false as const }
    }

    const recovered = parseAutosaveDraft(window.localStorage.getItem(buildManuscriptAutosaveKey(bookId, chapterNumber)))
    if (!recovered?.text.trim()) {
      return { draft: fallbackDraft, recovered: false as const }
    }

    return {
      draft: {
        title: recovered.title.trim() || fallbackDraft.title,
        text: recovered.text,
        html: recovered.html || fallbackDraft.html,
      },
      recovered,
    }
  }, [bookId])

  const syncLocalChapterFromServer = async (chapterNumber: number) => {
    const chapterMeta = chapterList?.chapters.find((item) => item.number === chapterNumber)
    const chapter = await readerApi.getChapter(bookId, chapterNumber, { include: MANUSCRIPT_CHAPTER_INCLUDE })
    const nextTitle = chapter.chapter_title || chapterMeta?.title || `Chapter ${chapterNumber}`
    const nextText = chapter.text_content || ""
    const nextHtml = hydrateChapterMediaHtml(chapter)
    const nextContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
    if (selectedChapter === chapterNumber) {
      setDraftChapterNumber(null)
      setChapterTitle(nextTitle)
      setText(nextText)
      setHtml(nextHtml)
    }
    setBookDrafts((current) => ({
      ...current,
      [chapterNumber]: {
        title: nextTitle,
        text: nextText,
        html: nextHtml,
      },
    }))
    setContentVersionByChapter((current) => ({ ...current, [chapterNumber]: nextContentVersion }))
    clearDraftDirty(chapterNumber)
  }

  const refreshChapterVersionToken = async (chapterNumber: number) => {
    const chapter = await readerApi.getChapter(bookId, chapterNumber, {
      include: [],
      fields: ["content_version"],
    })
    const nextContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
    setContentVersionByChapter((current) => ({ ...current, [chapterNumber]: nextContentVersion }))
    return nextContentVersion
  }

  const loadWorkspaceTree = async () => {
    try {
      const { data: tree } = await refetchWorkspaceTree()
      if (!tree) {
        setWorkspaceTree(null)
        return
      }
      setWorkspaceTree(tree)
      setCollapsedSceneGroups((current) => {
        const next = { ...current }
        for (const group of tree.scene_groups) {
          if (!(group.id in next)) next[group.id] = !!group.collapsed_by_default
        }
        return next
      })
    } catch {
      setWorkspaceTree(null)
    }
  }

  const loadBase = useCallback(async () => {
    const requestedChapter = selectedChapterRef.current
    const [bootstrap, chapters] = await Promise.all([
      booksApi.getManuscriptBootstrap(bookId, { activeChapterNumber: requestedChapter, profile: "critical" }),
      readerApi.getChapterList(bookId),
    ])
    const bookData = bootstrap.book
    const fullBootstrap = bootstrap.profile !== "critical"
    const isOwnerAuthorBook = bookData.mode === "author" && bookData.access_class === "owner"
    if (authHydrated && isOwnerAuthorBook && !canUseAuthorFeatures(userTier)) {
      router.replace(`/${bookId}` as Route)
      return
    }
    queryClient.setQueryData([`manuscript:${bookId}:characters`], bootstrap.characters)
    queryClient.setQueryData([bookCacheKey(bookId, "writer-workspace")], bootstrap.writer_workspace)
    queryClient.setQueryData([bookCacheKey(bookId, "workspace-tree")], bootstrap.workspace_tree)
    if (fullBootstrap) {
      queryClient.setQueryData([bookCacheKey(bookId, "emotional-arc")], bootstrap.emotional_arc)
      queryClient.setQueryData([`manuscript:${bookId}:notes`], bootstrap.notes)
      queryClient.setQueryData([bookCacheKey(bookId, "vault-notes")], bootstrap.vault_notes)
      if (requestedChapter !== null) {
        queryClient.setQueryData([`manuscript:${bookId}:chapter-versions:${requestedChapter}`], bootstrap.chapter_versions)
      }
      if (bootstrap.prewriting_check) {
        queryClient.setQueryData([`manuscript:${bookId}:prewriting:${bootstrap.prewriting_check.upcoming_chapter}`], bootstrap.prewriting_check)
      }
    }
    setBook(bookData)
    setCharacters(bootstrap.characters)
    setWriterWorkspace(bootstrap.writer_workspace)
    setWorkspaceTree(bootstrap.workspace_tree)
    setChapterList(chapters)
    setLoadError(null)
    const initialChapterNumber = chapters.chapters.some((item) => item.number === requestedChapter)
      ? requestedChapter
      : chapters.chapters[chapters.chapters.length - 1]?.number ?? null
    if (initialChapterNumber === null) {
      setSelectedChapter(null)
      return
    }
    if (requestedChapter !== initialChapterNumber) setSelectedChapter(initialChapterNumber)

    const chapterMeta = chapters.chapters.find((item) => item.number === initialChapterNumber)
    try {
      const chapter = await readerApi.getChapter(bookId, initialChapterNumber, { include: MANUSCRIPT_CHAPTER_INCLUDE })
      const title = chapter.chapter_title || chapterMeta?.title || `Chapter ${initialChapterNumber}`
      const chapterText = chapter.text_content || ""
      const chapterHtml = hydrateChapterMediaHtml(chapter)
      const chapterContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
      const recoveredDraft = getRecoveredDraft(initialChapterNumber, {
        title,
        text: chapterText,
        html: chapterHtml,
      })
      const nextDraft = recoveredDraft.draft
      deferredChecksSeedRef.current = {
        chapterNumber: initialChapterNumber,
        text: nextDraft.text.trim(),
      }
      initialChapterLoadedRef.current = initialChapterNumber
      if (!firstChapterLoadedCapturedRef.current) {
        firstChapterLoadedCapturedRef.current = true
        captureTiming("first_chapter_loaded_ms", manuscriptLoadStartedAtRef.current ?? 0, {
          book_id: bookId,
          chapter_number: initialChapterNumber,
        })
      }
      setDraftChapterNumber(null)
      setChapterTitle(nextDraft.title)
      setText(nextDraft.text)
      setHtml(nextDraft.html)
      setBookDrafts((current) => ({
        ...current,
        [initialChapterNumber]: {
          title: nextDraft.title,
          text: nextDraft.text,
          html: nextDraft.html,
        },
      }))
      setContentVersionByChapter((current) => ({
        ...current,
        [initialChapterNumber]: chapterContentVersion,
      }))
      if (recoveredDraft.recovered) {
        markDraftDirty(initialChapterNumber)
        setAutosaveState((current) => ({
          ...current,
          [initialChapterNumber]: {
            status: "saved",
            updatedAt: recoveredDraft.recovered.updatedAt,
          },
        }))
        setStatusMessage(`Recovered a local autosave for chapter ${initialChapterNumber}.`)
      }
    } catch {
      setLoadError(`Chapter ${initialChapterNumber} could not be loaded. Check your connection and try again.`)
    }
  }, [
    authHydrated,
    bookId,
    deferredChecksSeedRef,
    firstChapterLoadedCapturedRef,
    getRecoveredDraft,
    initialChapterLoadedRef,
    manuscriptLoadStartedAtRef,
    markDraftDirty,
    queryClient,
    router,
    setAutosaveState,
    setBook,
    setBookDrafts,
    setChapterList,
    setChapterTitle,
    setCharacters,
    setContentVersionByChapter,
    setDraftChapterNumber,
    setHtml,
    setSelectedChapter,
    setStatusMessage,
    setText,
    setWorkspaceTree,
    setWriterWorkspace,
    userTier,
  ])

  const retryLoad = useCallback(async () => {
    setLoading(true)
    try {
      await loadBase()
    } catch {
      setLoadError("Your manuscript could not be loaded. Check your connection and try again.")
    } finally {
      setLoading(false)
    }
  }, [loadBase, setLoading])

  useEffect(() => {
    void retryLoad()
  }, [retryLoad])

  useEffect(() => {
    if (selectedChapter === null) {
      setDraftChapterNumber(nextChapterNumber)
      setChapterTitle(`Chapter ${nextChapterNumber}`)
      setText("")
      setHtml(textToHtml(""))
      setReview(null)
      setReviewPassages([])
      return
    }
    if (initialChapterLoadedRef.current === selectedChapter) {
      initialChapterLoadedRef.current = null
      return
    }
    const chapterMeta = chapterList?.chapters.find((item) => item.number === selectedChapter)
    readerApi.getChapter(bookId, selectedChapter, { include: MANUSCRIPT_CHAPTER_INCLUDE }).then((chapter) => {
      setLoadError(null)
      const title = chapter.chapter_title || chapterMeta?.title || `Chapter ${selectedChapter}`
      const chapterText = chapter.text_content || ""
      const chapterHtml = hydrateChapterMediaHtml(chapter)
      const chapterContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
      const recoveredDraft = getRecoveredDraft(selectedChapter, {
        title,
        text: chapterText,
        html: chapterHtml,
      })
      const nextDraft = recoveredDraft.draft
      deferredChecksSeedRef.current = {
        chapterNumber: selectedChapter,
        text: nextDraft.text.trim(),
      }
      setDraftChapterNumber(null)
      setChapterTitle(nextDraft.title)
      setText(nextDraft.text)
      setHtml(nextDraft.html)
      setBookDrafts((current) => ({
        ...current,
        [selectedChapter]: {
          title: nextDraft.title,
          text: nextDraft.text,
          html: nextDraft.html,
        },
      }))
      setContentVersionByChapter((current) => ({
        ...current,
        [selectedChapter]: chapterContentVersion,
      }))
      if (recoveredDraft.recovered) {
        markDraftDirty(selectedChapter)
        setAutosaveState((current) => ({
          ...current,
          [selectedChapter]: {
            status: "saved",
            updatedAt: recoveredDraft.recovered.updatedAt,
          },
        }))
        setStatusMessage(`Recovered a local autosave for chapter ${selectedChapter}.`)
      } else {
        setStatusMessage(null)
      }
      setReview(null)
      setReviewPassages([])
    }).catch(() => {
      setLoadError(`Chapter ${selectedChapter} could not be loaded. Check your connection and try again.`)
    })
  }, [
    bookId,
    chapterList,
    deferredChecksSeedRef,
    getRecoveredDraft,
    initialChapterLoadedRef,
    markDraftDirty,
    nextChapterNumber,
    selectedChapter,
    setAutosaveState,
    setBookDrafts,
    setChapterTitle,
    setContentVersionByChapter,
    setDraftChapterNumber,
    setHtml,
    setReview,
    setReviewPassages,
    setStatusMessage,
    setText,
  ])

  useEffect(() => {
    if (editorMode !== "book" || !chapterList?.chapters.length) return
    const missingNumbers = chapterList.chapters
      .map((chapter) => chapter.number)
      .filter((number) => !(number in bookDrafts))
    if (!missingNumbers.length) return

    setFullBookLoading(true)
    Promise.all(missingNumbers.map((number) => readerApi.getChapter(bookId, number, { include: MANUSCRIPT_CHAPTER_INCLUDE })))
      .then((chapters) => {
        const nextDrafts: BookDraftMap = {}
        const nextContentVersions: Record<number, number> = {}
        const recoveredAutosaves: Array<{ chapterNumber: number; updatedAt: string }> = []

        for (const chapter of chapters) {
          const fallbackDraft = {
            title: chapter.chapter_title || `Chapter ${chapter.chapter_number}`,
            text: chapter.text_content || "",
            html: hydrateChapterMediaHtml(chapter),
          }
          const recoveredDraft = getRecoveredDraft(chapter.chapter_number, fallbackDraft)
          nextDrafts[chapter.chapter_number] = recoveredDraft.draft
          nextContentVersions[chapter.chapter_number] = typeof chapter.content_version === "number" ? chapter.content_version : 1
          if (recoveredDraft.recovered) {
            recoveredAutosaves.push({
              chapterNumber: chapter.chapter_number,
              updatedAt: recoveredDraft.recovered.updatedAt,
            })
          }
        }

        startTransition(() => {
          setBookDrafts((current) => {
            return { ...current, ...nextDrafts }
          })
          setContentVersionByChapter((current) => {
            return { ...current, ...nextContentVersions }
          })
          if (recoveredAutosaves.length > 0) {
            setDirtyDrafts((current) => {
              const next = new Set(current)
              for (const draft of recoveredAutosaves) next.add(draft.chapterNumber)
              return Array.from(next)
            })
            setAutosaveState((current) => {
              const next = { ...current }
              for (const draft of recoveredAutosaves) {
                next[draft.chapterNumber] = {
                  status: "saved",
                  updatedAt: draft.updatedAt,
                }
              }
              return next
            })
          }
        })
      })
      .catch(() => setLoadError("Some chapters could not be loaded. Your drafts are still held in this workspace. Try again to open the full book."))
      .finally(() => setFullBookLoading(false))
  }, [
    bookDrafts,
    bookId,
    chapterList,
    editorMode,
    getRecoveredDraft,
    setAutosaveState,
    setBookDrafts,
    setContentVersionByChapter,
    setDirtyDrafts,
    setFullBookLoading,
  ])

  return {
    loadError,
    retryLoad,
    clearDraftDirty,
    loadBase,
    loadWorkspaceTree,
    markDraftDirty,
    refreshChapterVersionToken,
    syncLocalChapterFromServer,
  }
}
