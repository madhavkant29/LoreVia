import { useState, useEffect } from "react"
import { readerApi } from "@/lib/api/reader"

export function useRecall(bookId: string) {
  const [recall, setRecall] = useState<string | null>(null)
  const [lastChapter, setLastChapter] = useState<number | null>(null)
  const [show, setShow] = useState(false)

  useEffect(() => {
    readerApi.getRecall(bookId).then((data) => {
      if (data.recall) {
        setRecall(data.recall)
        setLastChapter(data.last_chapter)
        setShow(true)
      }
    }).catch(() => {})
  }, [bookId])

  return { recall, lastChapter, show, dismiss: () => setShow(false) }
}
