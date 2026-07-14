import { useEffect, useState, type RefObject } from "react"

import { PINNED_STORAGE_KEY } from "./LibraryClient.helpers"

export function usePinnedLibraryProjects() {
  const [pinnedIds, setPinnedIds] = useState<Record<string, boolean>>({})
  const [pinsReady, setPinsReady] = useState(false)

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PINNED_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, boolean>
        setPinnedIds(parsed)
      }
    } catch {
      // ignore malformed local storage
    } finally {
      setPinsReady(true)
    }
  }, [])

  useEffect(() => {
    if (!pinsReady) return
    const id = window.requestIdleCallback
      ? window.requestIdleCallback(() => {
          window.localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify(pinnedIds))
        })
      : window.setTimeout(() => {
          window.localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify(pinnedIds))
        }, 0)
    return () => {
      if (typeof id === "number") window.clearTimeout(id)
      else if (window.cancelIdleCallback) window.cancelIdleCallback(id as number)
    }
  }, [pinnedIds, pinsReady])

  return [pinnedIds, setPinnedIds] as const
}

export function useLibrarySearchShortcut(searchInputRef: RefObject<HTMLInputElement | null>) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target
      const typingTarget = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement
      if (!typingTarget && event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [searchInputRef])
}
