"use client"

import { useEffect, useRef, useState, type RefObject } from "react"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { chapterScrollFraction, parseReaderBookmark, type ReaderBookmark } from "@/lib/utils/readerPosition"

export function useReaderPosition({ bookId, chapterNum, chapterTitle, ready, scrollRef, saveProgress }: {
  bookId: string
  chapterNum: number
  chapterTitle: string | null
  ready: boolean
  scrollRef: RefObject<HTMLDivElement | null>
  saveProgress: (fraction: number) => Promise<unknown> | void
}) {
  const [scrollPct, setScrollPct] = useState(0)
  const [storageError, setStorageError] = useState(false)
  const titleRef = useRef(chapterTitle)
  titleRef.current = chapterTitle

  useEffect(() => {
    const container = scrollRef.current
    if (!ready || !container) return
    const chapter = container.querySelector<HTMLElement>("[data-chapter-content]")
    const key = `reader-bookmark:${normalizeBookRouteId(bookId)}`
    let pending: ReaderBookmark | null = null
    try {
      pending = parseReaderBookmark(window.localStorage.getItem(key)
        ?? window.localStorage.getItem(`reader-bookmark:${bookId}`), bookId, chapterNum)
    } catch { setStorageError(true) }

    let timer: number | undefined
    let restoreFrame: number | undefined
    let userScrolled = false
    const contentHeight = () => chapter
      ? chapter.getBoundingClientRect().bottom - container.getBoundingClientRect().top + container.scrollTop
      : container.scrollHeight
    const persist = (fraction: number) => {
      const bookmark: ReaderBookmark = { bookId, chapter: chapterNum, chapterTitle: titleRef.current,
        scrollPct: fraction, selectedText: null, savedAt: new Date().toISOString() }
      try { window.localStorage.setItem(key, JSON.stringify(bookmark)); setStorageError(false) }
      catch { setStorageError(true) }
    }
    const measure = () => {
      if (pending) {
        container.scrollTop = Math.max(0, contentHeight() - container.clientHeight) * pending.scrollPct
      }
      setScrollPct(chapterScrollFraction(container.scrollTop, contentHeight(), container.clientHeight))
    }
    const markInteraction = () => { pending = null; userScrolled = true }
    const onScroll = () => {
      measure()
      if (!userScrolled) return
      const fraction = chapterScrollFraction(container.scrollTop, contentHeight(), container.clientHeight)
      persist(fraction)
      window.clearTimeout(timer)
      timer = window.setTimeout(() => { void saveProgress(fraction) }, 350)
    }
    // Images and font changes can alter the reading surface after the initial render.
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
      if (restoreFrame !== undefined) window.cancelAnimationFrame(restoreFrame)
      restoreFrame = window.requestAnimationFrame(measure)
    })
    observer?.observe(chapter ?? container)
    observer?.observe(container)
    measure()
    container.addEventListener("wheel", markInteraction, { passive: true })
    container.addEventListener("touchstart", markInteraction, { passive: true })
    container.addEventListener("pointerdown", markInteraction)
    container.addEventListener("keydown", markInteraction)
    container.addEventListener("scroll", onScroll, { passive: true })
    return () => {
      observer?.disconnect()
      window.clearTimeout(timer)
      if (restoreFrame !== undefined) window.cancelAnimationFrame(restoreFrame)
      container.removeEventListener("wheel", markInteraction)
      container.removeEventListener("touchstart", markInteraction)
      container.removeEventListener("pointerdown", markInteraction)
      container.removeEventListener("keydown", markInteraction)
      container.removeEventListener("scroll", onScroll)
    }
  }, [bookId, chapterNum, ready, saveProgress, scrollRef])

  return { scrollPct, storageError }
}
