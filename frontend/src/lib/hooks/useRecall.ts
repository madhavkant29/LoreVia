import { useEffect, useState } from "react"

import { readerApi } from "@/lib/api/reader"

export function useRecall(bookId: string) {
  const [recall, setRecall] = useState<string | null>(null)
  const [lastChapter, setLastChapter] = useState<number | null>(null)
  const [show, setShow] = useState(false)

  useEffect(() => {
    let active = true

    readerApi.getRecall(bookId).then((data) => {
      if (!active || !data.recall) return
      setRecall(data.recall)
      setLastChapter(data.last_chapter ?? null)
      setShow(true)
    }).catch(() => {})

    return () => {
      active = false
    }
  }, [bookId])

  return { recall, lastChapter, show, dismiss: () => setShow(false) }
}
