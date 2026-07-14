import { startTransition, useEffect, type Dispatch, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
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
  useEffect(() => {
    if (!isBookProcessing) return

    const intervalId = window.setInterval(() => {
      void Promise.all([
        booksApi.get(bookId),
        booksApi.getWriterWorkspace(bookId),
      ]).then(([nextBook, nextWorkspace]) => {
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
      }).catch(() => {})
    }, MANUSCRIPT_PROCESSING_POLL_INTERVAL_MS)

    return () => window.clearInterval(intervalId)
  }, [bookId, isBookProcessing, setBook, setWriterWorkspace])
}
