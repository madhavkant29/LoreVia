import type { QueryClient } from "@tanstack/react-query"
import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { MANUSCRIPT_CHAPTER_INCLUDE, readerApi } from "@/lib/api/reader"
import { readerCacheKey } from "@/lib/query/cacheKeys"
import type { SearchResult } from "@/types/reader"
import {
  findChapterForPage,
  type FullBookPageMapItem,
} from "./manuscriptPage.helpers"
import type { EditorMode } from "./manuscriptPage.constants"

type UseManuscriptNavigationArgs = {
  bookId: string
  fullBookPageMap: FullBookPageMapItem[]
  queryClient: QueryClient
  recallResults: SearchResult[]
  setActiveFindIndex: Dispatch<SetStateAction<number>>
  setEditorMode: Dispatch<SetStateAction<EditorMode>>
  setGotoPageInput: Dispatch<SetStateAction<string>>
  setJumpTarget: Dispatch<SetStateAction<number | null>>
  setSelectedChapter: Dispatch<SetStateAction<number | null>>
}

export function useManuscriptNavigation({
  bookId,
  fullBookPageMap,
  queryClient,
  recallResults,
  setActiveFindIndex,
  setEditorMode,
  setGotoPageInput,
  setJumpTarget,
  setSelectedChapter,
}: UseManuscriptNavigationArgs) {
  function prefetchManuscriptChapter(chapterNum: number) {
    if (!chapterNum || chapterNum < 1) return
    void queryClient.prefetchQuery({
      queryKey: [readerCacheKey(bookId, chapterNum)],
      queryFn: () => readerApi.getChapter(bookId, chapterNum, { include: MANUSCRIPT_CHAPTER_INCLUDE }),
      staleTime: 30_000,
    })
    void queryClient.prefetchQuery({
      queryKey: [`manuscript:${bookId}:chapter-versions:${chapterNum}`],
      queryFn: () => booksApi.getChapterVersions(bookId, chapterNum),
      staleTime: 30_000,
    })
  }

  function jumpToChapter(chapterNum: number) {
    prefetchManuscriptChapter(chapterNum - 1)
    prefetchManuscriptChapter(chapterNum + 1)
    setEditorMode("book")
    setSelectedChapter(chapterNum)
    setJumpTarget(chapterNum)
  }

  function jumpToSearchResult(index: number) {
    const result = recallResults[index]
    if (!result) return
    setActiveFindIndex(index)
    jumpToChapter(result.chapter_num)
  }

  function jumpToPage(page: number) {
    const match = findChapterForPage(fullBookPageMap, page)
    if (!match) return
    setGotoPageInput(String(page))
    jumpToChapter(match.chapter)
  }

  return {
    jumpToChapter,
    jumpToPage,
    jumpToSearchResult,
    prefetchManuscriptChapter,
  }
}
