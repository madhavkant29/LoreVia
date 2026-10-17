import { startTransition, useCallback, type Dispatch, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { useAdaptivePolling } from "@/lib/hooks/useAdaptivePolling"
import type { Book, WriterWorkspace } from "@/types/book"
import { MANUSCRIPT_PROCESSING_POLL_INTERVAL_MS } from "./manuscriptPage.constants"

type UseManuscriptProcessingPollArgs = {
  bookId: string
  isBookProcessing: boolean
  setBook: Dispatch<SetStateAction<Book | null>>
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
}

export function useManuscriptProcessingPoll({
  bookId,
  isBookProcessing,
  setBook,
  setWriterWorkspace,
}: UseManuscriptProcessingPollArgs) {
  const pollProcessing = useCallback(async () => {
    const [nextBook, nextWorkspace] = await Promise.all([
      booksApi.get(bookId),
      booksApi.getWriterWorkspace(bookId),
    ])
    startTransition(() => {
      setBook(nextBook)
      setWriterWorkspace((current) => {
        if (!current) return nextWorkspace
        return {
          ...current,
          processing: nextWorkspace.processing,
          reprocess: nextWorkspace.reprocess,
        }
      })
    })
    return { nextBook, nextWorkspace }
  }, [bookId, setBook, setWriterWorkspace])

  useAdaptivePolling({
    enabled: isBookProcessing,
    poll: pollProcessing,
    getProgress: ({ nextBook, nextWorkspace }) => JSON.stringify({
      status: nextBook.status,
      processing: nextWorkspace.processing,
      reprocess: nextWorkspace.reprocess,
    }),
    isTerminal: ({ nextBook }) => !["processing", "queued"].includes(nextBook.status),
    initialDelayMs: MANUSCRIPT_PROCESSING_POLL_INTERVAL_MS,
    maxDelayMs: 30_000,
    timeoutMs: 30 * 60 * 1_000,
    resetKey: bookId,
  })
}
