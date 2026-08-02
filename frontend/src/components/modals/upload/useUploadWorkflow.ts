"use client"

import { useCallback } from "react"
import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import type { BookWorkType, ChapterConsistencyReport, ImportPreview } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"

type ReviewTarget = { bookId: string; chapterNum?: number; text: string }

type UploadWorkflowOptions = {
  files: File[]
  workType: BookWorkType
  setError: Dispatch<SetStateAction<string | null>>
  setPreviewLoading: Dispatch<SetStateAction<boolean>>
  setImportPreview: Dispatch<SetStateAction<ImportPreview | null>>
  setDismissPreview: Dispatch<SetStateAction<boolean>>
  setPostImportReview: Dispatch<SetStateAction<EditorialReview | null>>
  setPostImportPassages: Dispatch<SetStateAction<EditorialReviewPassage[]>>
  setPostImportSuggestions: Dispatch<SetStateAction<AdvisorSuggestion[]>>
  setPostImportThreads: Dispatch<SetStateAction<PlotThread[]>>
  setPostImportSynopsis: Dispatch<SetStateAction<ManuscriptSynopsis | null>>
  setChapterReports: Dispatch<SetStateAction<ChapterConsistencyReport[]>>
  setReportReady: Dispatch<SetStateAction<ReviewTarget | null>>
  getApiErrorDetail: (error: unknown) => string | null
}

export function useUploadWorkflow({
  files,
  workType,
  setError,
  setPreviewLoading,
  setImportPreview,
  setDismissPreview,
  setPostImportReview,
  setPostImportPassages,
  setPostImportSuggestions,
  setPostImportThreads,
  setPostImportSynopsis,
  setChapterReports,
  setReportReady,
  getApiErrorDetail,
}: UploadWorkflowOptions) {
  const resetImportFeedback = useCallback(() => {
    setError(null)
    setPostImportReview(null)
    setPostImportPassages([])
    setPostImportSuggestions([])
    setPostImportThreads([])
    setPostImportSynopsis(null)
    setChapterReports([])
    setReportReady(null)
  }, [
    setChapterReports,
    setError,
    setPostImportPassages,
    setPostImportReview,
    setPostImportSuggestions,
    setPostImportSynopsis,
    setPostImportThreads,
    setReportReady,
  ])

  const fetchPreview = useCallback(async () => {
    if (files.length === 0) return
    setPreviewLoading(true)
    setError(null)
    try {
      const preview = await booksApi.previewUpload(files[0], workType)
      setImportPreview(preview)
      setDismissPreview(false)
    } catch (error) {
      setError(getApiErrorDetail(error) || "Failed to analyze manuscript structure.")
    } finally {
      setPreviewLoading(false)
    }
  }, [files, getApiErrorDetail, setDismissPreview, setError, setImportPreview, setPreviewLoading, workType])

  const loadPostImportReview = useCallback(async (
    bookId: string,
    chapterNum: number | undefined,
    content: string,
  ) => {
    if (!content.trim()) {
      setError("Chapter imported, but there was no text available to review inline.")
      return
    }
    const [editorial, suggestions, threads, synopsis] = await Promise.all([
      intelligenceApi.editorialReview(bookId, content, chapterNum),
      intelligenceApi.advisorSuggestions(bookId),
      readerApi.getPlotThreads(bookId, chapterNum ?? 9999),
      intelligenceApi.synopsis(bookId, "minimal").catch(() => null),
    ])
    setPostImportReview(editorial.review)
    setPostImportPassages(editorial.retrieved_passages)
    setPostImportSuggestions(
      suggestions.suggestions
        .filter((item) => item.chapter_ref === null || item.chapter_ref <= (chapterNum ?? Number.MAX_SAFE_INTEGER))
        .slice(0, 5),
    )
    setPostImportThreads(threads.filter((thread) => thread.status !== "resolved").slice(0, 6))
    setPostImportSynopsis(synopsis)
    setReportReady({ bookId, chapterNum, text: content })
  }, [
    setError,
    setPostImportPassages,
    setPostImportReview,
    setPostImportSuggestions,
    setPostImportSynopsis,
    setPostImportThreads,
    setReportReady,
  ])

  return { fetchPreview, loadPostImportReview, resetImportFeedback }
}
