// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  getGlobal: vi.fn(),
  patchGlobal: vi.fn(),
  getBook: vi.fn(),
  patchBook: vi.fn(),
}))

vi.mock("@/lib/api/uiPreferences", () => ({
  uiPreferencesApi: {
    ...api,
    exportPreferences: vi.fn(),
    importPreferences: vi.fn(),
    getBookVisibilitySummary: vi.fn(),
  },
}))

import {
  UI_PREFERENCES_CACHE_PREFIX,
  defaultBookUiPreference,
  defaultUserUiPreference,
  parseUiPreferenceCache,
  useUiPreferencesStore,
} from "./uiPreferencesStore"

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.useFakeTimers()
  const values = new Map<string, string>()
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      removeItem: (key: string) => values.delete(key),
      setItem: (key: string, value: string) => values.set(key, value),
    },
  })
  Object.values(api).forEach((mock) => mock.mockReset())
  useUiPreferencesStore.getState().clearActiveUser()
})

describe("ui preferences store isolation and replay", () => {
  it("reports an unavailable book load when no account is active", async () => {
    expect(await useUiPreferencesStore.getState().hydrateBook("book-1")).toBe(false)
    expect(api.getBook).not.toHaveBeenCalled()
  })

  it("does not confirm a book load belonging to a previous account", async () => {
    api.getGlobal.mockResolvedValue(defaultUserUiPreference("standard"))
    await useUiPreferencesStore.getState().hydrateForUser("user-a")
    const request = deferred<ReturnType<typeof defaultBookUiPreference>>()
    api.getBook.mockReturnValue(request.promise)
    const pending = useUiPreferencesStore.getState().hydrateBook("book-1")
    useUiPreferencesStore.getState().clearActiveUser()
    request.resolve(defaultBookUiPreference("book-1"))
    expect(await pending).toBe(false)
    expect(useUiPreferencesStore.getState().bookPreferences).toEqual({})
  })

  it("rejects malformed caches and canonicalizes valid book keys", () => {
    expect(parseUiPreferenceCache("{broken")).toBeNull()
    expect(parseUiPreferenceCache(JSON.stringify({ preferences: { schema_version: 99 } }))).toBeNull()

    const preference = defaultUserUiPreference("standard")
    const bookPreference = defaultBookUiPreference("draft--11111111-1111-4111-8111-111111111111", "standard")
    const parsed = parseUiPreferenceCache(JSON.stringify({
      preferences: preference,
      bookPreferences: { "draft--11111111-1111-4111-8111-111111111111": bookPreference },
      pendingGlobalOperations: [{ op: "set", path: "invalid", value: true }],
      pendingBookOperations: {},
    }))

    expect(parsed?.bookPreferences["11111111-1111-4111-8111-111111111111"]?.book_preset).toBe("all")
    expect(parsed?.pendingGlobalOperations).toEqual([])
  })

  it("ignores a stale hydration response after an account switch", async () => {
    const first = deferred<ReturnType<typeof defaultUserUiPreference>>()
    const second = deferred<ReturnType<typeof defaultUserUiPreference>>()
    api.getGlobal.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise)

    const firstHydration = useUiPreferencesStore.getState().hydrateForUser("user-a")
    const secondHydration = useUiPreferencesStore.getState().hydrateForUser("user-b")

    second.resolve({ ...defaultUserUiPreference("power"), revision: 4 })
    await secondHydration
    first.resolve({ ...defaultUserUiPreference("standard"), revision: 7 })
    await firstHydration

    expect(useUiPreferencesStore.getState().activeUserId).toBe("user-b")
    expect(useUiPreferencesStore.getState().preferences.complexity_mode).toBe("power")
    expect(window.localStorage.getItem(`${UI_PREFERENCES_CACHE_PREFIX}:user-a`)).toBeNull()
  })

  it("normalizes canonical book ids before hydration and storage", async () => {
    api.getGlobal.mockResolvedValue(defaultUserUiPreference("focused"))
    api.getBook.mockResolvedValue({
      ...defaultBookUiPreference("11111111-1111-4111-8111-111111111111"),
      revision: 3,
    })
    await useUiPreferencesStore.getState().hydrateForUser("user-a")
    expect(await useUiPreferencesStore.getState().hydrateBook("draft--11111111-1111-4111-8111-111111111111")).toBe(true)

    expect(api.getBook).toHaveBeenCalledWith("11111111-1111-4111-8111-111111111111")
    expect(useUiPreferencesStore.getState().bookPreferences["11111111-1111-4111-8111-111111111111"]?.revision).toBe(3)
    expect(useUiPreferencesStore.getState().bookPreferences["draft--11111111-1111-4111-8111-111111111111"]).toBeUndefined()
  })

  it("falls back to focused book preferences when uncached preference hydration fails", async () => {
    const global = deferred<ReturnType<typeof defaultUserUiPreference>>()
    api.getGlobal.mockReturnValueOnce(global.promise)
    api.getBook.mockRejectedValueOnce(new Error("offline"))

    const userHydration = useUiPreferencesStore.getState().hydrateForUser("user-a")
    expect(await useUiPreferencesStore.getState().hydrateBook("book-1")).toBe(false)

    expect(useUiPreferencesStore.getState().bookPreferences["book-1"]?.book_preset).toBe("draft")

    global.reject(new Error("offline"))
    await userHydration

    expect(useUiPreferencesStore.getState().preferences.complexity_mode).toBe("focused")
    expect(useUiPreferencesStore.getState().bookPreferences["book-1"]?.book_preset).toBe("draft")
    expect(useUiPreferencesStore.getState().syncState).toBe("api_unavailable")
    expect(useUiPreferencesStore.getState().syncMessage).toBe("Using the focused layout until preferences load.")
  })

  it("retains failed offline operations and clears them only after retry succeeds", async () => {
    api.getGlobal.mockResolvedValue(defaultUserUiPreference("standard"))
    api.patchGlobal.mockRejectedValueOnce(new Error("offline"))
    await useUiPreferencesStore.getState().hydrateForUser("user-a")

    await useUiPreferencesStore.getState().patchGlobal([
      { op: "set", path: "/complexity_mode", value: "power" },
    ])
    await vi.advanceTimersByTimeAsync(WRITE_DELAY)

    expect(useUiPreferencesStore.getState().pendingGlobalOperations).toHaveLength(1)
    expect(useUiPreferencesStore.getState().syncState).toBe("sync_pending")

    api.patchGlobal.mockResolvedValueOnce({ ...defaultUserUiPreference("power"), revision: 2 })
    await useUiPreferencesStore.getState().retrySync()

    expect(useUiPreferencesStore.getState().pendingGlobalOperations).toEqual([])
    expect(useUiPreferencesStore.getState().preferences.complexity_mode).toBe("power")
    expect(useUiPreferencesStore.getState().syncState).toBe("idle")
  })
})

const WRITE_DELAY = 300
