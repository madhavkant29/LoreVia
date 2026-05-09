import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("zustand/middleware", () => ({
  persist: (initializer: unknown) => initializer,
}))

import { useAuthStore } from "./authStore"
import { useBookModeStore } from "./bookModeStore"
import { usePreferencesStore } from "./preferencesStore"

describe("zustand stores", () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    storage.clear()
    const storageApi = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value)
      },
      removeItem: (key: string) => {
        storage.delete(key)
      },
      clear: () => {
        storage.clear()
      },
    }
    vi.stubGlobal("localStorage", storageApi)
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: storageApi,
    })
    document.documentElement.className = ""
    document.documentElement.dataset.theme = ""

    useAuthStore.setState({ user: null, hydrated: false })
    useBookModeStore.setState({ modesByBookId: {} })
    usePreferencesStore.setState({
      theme: "light",
      timelineCollapsedSections: { characters: true, plotThreads: true, relationships: true },
    })
  })

  it("starts the auth store with no user", () => {
    expect(useAuthStore.getState().user).toBeNull()
  })

  it("starts the auth store as not hydrated", () => {
    expect(useAuthStore.getState().hydrated).toBe(false)
  })

  it("sets the auth user and marks the store hydrated", () => {
    useAuthStore.getState().setUser({ id: "1", email: "reader@example.com", username: "reader", tier: "reader" } as never)

    expect(useAuthStore.getState().user?.username).toBe("reader")
    expect(useAuthStore.getState().hydrated).toBe(true)
  })

  it("marks the auth store hydrated without a user", () => {
    useAuthStore.getState().setHydrated()

    expect(useAuthStore.getState().hydrated).toBe(true)
    expect(useAuthStore.getState().user).toBeNull()
  })

  it("logs out by clearing the user and keeping hydration", () => {
    useAuthStore.setState({ user: { id: "2" } as never, hydrated: true })
    useAuthStore.getState().logout()

    expect(useAuthStore.getState().user).toBeNull()
    expect(useAuthStore.getState().hydrated).toBe(true)
  })

  it("returns reader as the default book mode", () => {
    expect(useBookModeStore.getState().getMode("book-1")).toBe("reader")
  })

  it("sets a book mode for a specific book", () => {
    useBookModeStore.getState().setMode("book-1", "author")

    expect(useBookModeStore.getState().getMode("book-1")).toBe("author")
  })

  it("overwrites an existing book mode", () => {
    useBookModeStore.getState().setMode("book-1", "author")
    useBookModeStore.getState().setMode("book-1", "reader")

    expect(useBookModeStore.getState().getMode("book-1")).toBe("reader")
  })

  it("clears a book mode back to the default", () => {
    useBookModeStore.getState().setMode("book-1", "author")
    useBookModeStore.getState().clearMode("book-1")

    expect(useBookModeStore.getState().getMode("book-1")).toBe("reader")
  })

  it("starts the preferences store in light theme", () => {
    expect(usePreferencesStore.getState().theme).toBe("light")
  })

  it("sets the theme to dark and mirrors it to the document", () => {
    usePreferencesStore.getState().setTheme("dark")

    expect(usePreferencesStore.getState().theme).toBe("dark")
    expect(storage.get("app-theme")).toBe("dark")
    expect(document.documentElement.dataset.theme).toBe("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("sets the theme to light and removes the dark class", () => {
    document.documentElement.classList.add("dark")
    usePreferencesStore.getState().setTheme("light")

    expect(usePreferencesStore.getState().theme).toBe("light")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("toggles from light to dark", () => {
    usePreferencesStore.getState().toggleTheme()

    expect(usePreferencesStore.getState().theme).toBe("dark")
  })

  it("updates a single timeline collapsed section", () => {
    usePreferencesStore.getState().setTimelineCollapsedSection("characters", false)

    expect(usePreferencesStore.getState().timelineCollapsedSections.characters).toBe(false)
    expect(usePreferencesStore.getState().timelineCollapsedSections.plotThreads).toBe(true)
  })

  it("collapses all timeline sections together", () => {
    usePreferencesStore.getState().setTimelineAllCollapsed(true)

    expect(usePreferencesStore.getState().timelineCollapsedSections).toEqual({
      characters: true,
      plotThreads: true,
      relationships: true,
    })
  })

  it("expands all timeline sections together", () => {
    usePreferencesStore.getState().setTimelineAllCollapsed(false)

    expect(usePreferencesStore.getState().timelineCollapsedSections).toEqual({
      characters: false,
      plotThreads: false,
      relationships: false,
    })
  })
})
