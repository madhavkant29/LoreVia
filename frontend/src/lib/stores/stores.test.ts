import { beforeEach, describe, expect, it, vi } from "vitest"

const uiPreferencesStoreMock = vi.hoisted(() => ({
  clearActiveUser: vi.fn(),
  hydrateForUser: vi.fn(),
}))

vi.mock("zustand/middleware", () => ({
  persist: (initializer: unknown) => initializer,
}))

vi.mock("@/lib/stores/uiPreferencesStore", () => ({
  useUiPreferencesStore: {
    getState: () => uiPreferencesStoreMock,
  },
}))

import { useAuthStore } from "./authStore"
import { useBookModeStore } from "./bookModeStore"
import { usePreferencesStore } from "./preferencesStore"
import { queryClient } from "@/lib/query/queryClient"

describe("zustand stores", () => {
  const storage = new Map<string, string>()
  const sessionStorageData = new Map<string, string>()

  beforeEach(() => {
    storage.clear()
    sessionStorageData.clear()
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
    const sessionStorageApi = {
      getItem: (key: string) => sessionStorageData.get(key) ?? null,
      setItem: (key: string, value: string) => {
        sessionStorageData.set(key, value)
      },
      removeItem: (key: string) => {
        sessionStorageData.delete(key)
      },
      clear: () => {
        sessionStorageData.clear()
      },
    }
    vi.stubGlobal("sessionStorage", sessionStorageApi)
    Object.defineProperty(window, "sessionStorage", {
      configurable: true,
      value: sessionStorageApi,
    })
    document.documentElement.className = ""
    document.documentElement.dataset.theme = ""
    uiPreferencesStoreMock.clearActiveUser.mockClear()
    uiPreferencesStoreMock.hydrateForUser.mockClear()

    queryClient.clear()
    useAuthStore.setState({ user: null, hydrated: false })
    useBookModeStore.setState({ modesByBookId: {} })
    usePreferencesStore.setState({
      theme: "light",
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
    expect(useAuthStore.getState().user?.tier).toBe("free")
    expect(useAuthStore.getState().hydrated).toBe(true)
    expect(sessionStorageData.get("lorevia-auth-user")).toContain("\"username\":\"reader\"")
    expect(sessionStorageData.get("lorevia-auth-user")).toContain("\"tier\":\"free\"")
  })

  it("marks the auth store hydrated without a user", () => {
    useAuthStore.getState().setHydrated()

    expect(useAuthStore.getState().hydrated).toBe(true)
    expect(useAuthStore.getState().user).toBeNull()
  })

  it("logs out by clearing the user and keeping hydration", () => {
    useAuthStore.setState({ user: { id: "2" } as never, hydrated: true })
    sessionStorageData.set("lorevia-auth-user", "{\"id\":\"2\"}")
    useAuthStore.getState().logout()

    expect(useAuthStore.getState().user).toBeNull()
    expect(useAuthStore.getState().hydrated).toBe(true)
    expect(sessionStorageData.has("lorevia-auth-user")).toBe(false)
  })

  it("removes the previous user's query cache and book modes on logout", () => {
    useAuthStore.setState({ user: { id: "user-a" } as never, hydrated: true })
    queryClient.setQueryData(["books"], { owner: "user-a" })
    useBookModeStore.getState().setMode("book-a", "author")

    useAuthStore.getState().logout()

    expect(queryClient.getQueryData(["books"])).toBeUndefined()
    expect(useBookModeStore.getState().modesByBookId).toEqual({})
  })

  it("removes user A's query cache and book modes on a direct A-to-B transition", () => {
    useAuthStore.setState({ user: { id: "user-a" } as never, hydrated: true })
    queryClient.setQueryData(["books"], { owner: "user-a" })
    useBookModeStore.getState().setMode("book-a", "author")

    useAuthStore.getState().setUser({
      id: "user-b",
      email: "user-b@example.com",
      username: "user-b",
      tier: "free",
    } as never)

    expect(queryClient.getQueryData(["books"])).toBeUndefined()
    expect(useBookModeStore.getState().modesByBookId).toEqual({})
    expect(useAuthStore.getState().user?.id).toBe("user-b")
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

})
