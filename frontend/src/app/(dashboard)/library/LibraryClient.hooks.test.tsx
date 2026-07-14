// @vitest-environment jsdom

import { createRef, type Dispatch, type SetStateAction } from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { PINNED_STORAGE_KEY } from "./LibraryClient.helpers"
import { useLibrarySearchShortcut, usePinnedLibraryProjects } from "./LibraryClient.hooks"

let root: Root | null = null
let container: HTMLDivElement | null = null
let localStorageStore: Record<string, string> = {}

const localStorageMock = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageStore[key] = value
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageStore[key]
  }),
  clear: vi.fn(() => {
    localStorageStore = {}
  }),
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal("localStorage", localStorageMock)
  localStorageMock.clear()
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  if (root) {
    act(() => root?.unmount())
  }
  container?.remove()
  container = null
  root = null
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("LibraryClient hooks", () => {
  it("hydrates and persists pinned project IDs", () => {
    window.localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify({ "book-1": true }))
    let latestPinnedIds: Record<string, boolean> = {}
    let setPinnedIds: Dispatch<SetStateAction<Record<string, boolean>>> | null = null

    function Harness() {
      const [pinnedIds, updatePinnedIds] = usePinnedLibraryProjects()
      latestPinnedIds = pinnedIds
      setPinnedIds = updatePinnedIds
      return null
    }

    act(() => {
      root?.render(<Harness />)
    })
    expect(latestPinnedIds).toEqual({ "book-1": true })

    act(() => {
      vi.runOnlyPendingTimers()
    })
    act(() => {
      setPinnedIds?.({ "book-2": true })
    })
    act(() => {
      vi.runOnlyPendingTimers()
    })

    expect(window.localStorage.getItem(PINNED_STORAGE_KEY)).toBe(JSON.stringify({ "book-2": true }))
  })

  it("focuses search on slash outside typing targets", () => {
    const searchInputRef = createRef<HTMLInputElement>()

    function Harness() {
      useLibrarySearchShortcut(searchInputRef)
      return <input ref={searchInputRef} aria-label="Search projects" />
    }

    act(() => {
      root?.render(<Harness />)
    })

    const event = new KeyboardEvent("keydown", { key: "/", bubbles: true, cancelable: true })
    act(() => {
      window.dispatchEvent(event)
    })

    expect(document.activeElement).toBe(searchInputRef.current)
    expect(event.defaultPrevented).toBe(true)
  })
})
