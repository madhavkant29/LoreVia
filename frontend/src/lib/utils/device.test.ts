import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { getOrCreateDeviceId } from "./device"

describe("device utilities", () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    storage.clear()
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
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
      },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("returns a server fallback when window is unavailable", () => {
    vi.stubGlobal("window", undefined)

    expect(getOrCreateDeviceId()).toBe("lv-server-fallback-0000")
  })

  it("creates and persists a device id in local storage", () => {
    const randomUuid = vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue("uuid-123")

    const first = getOrCreateDeviceId()
    const second = getOrCreateDeviceId()

    expect(first).toBe("lv-uuid-123")
    expect(second).toBe("lv-uuid-123")
    expect(storage.get("lorevia-device-id")).toBe("lv-uuid-123")
    expect(randomUuid).toHaveBeenCalledTimes(1)
  })
})
