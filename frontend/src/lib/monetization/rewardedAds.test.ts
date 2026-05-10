import { beforeEach, describe, expect, it, vi } from "vitest"

import { playRewardedAd } from "./rewardedAds"

function installGoogletagMock() {
  const listeners = new Map<string, Array<(event: unknown) => void>>()
  const slot = {
    addService: vi.fn(() => slot),
    getSlotElementId: vi.fn(() => "rewarded-slot"),
  }

  const pubads = {
    addEventListener: vi.fn((eventType: string, listener: (event: unknown) => void) => {
      const current = listeners.get(eventType) ?? []
      current.push(listener)
      listeners.set(eventType, current)
    }),
    removeEventListener: vi.fn((eventType: string, listener: (event: unknown) => void) => {
      listeners.set(
        eventType,
        (listeners.get(eventType) ?? []).filter((candidate) => candidate !== listener)
      )
    }),
  }

  const googletag = {
    apiReady: true,
    cmd: [] as Array<() => void>,
    enums: { OutOfPageFormat: { REWARDED: "rewarded" } },
    pubads: () => pubads,
    defineOutOfPageSlot: vi.fn(() => slot),
    enableServices: vi.fn(),
    display: vi.fn(() => {
      const readyListeners = listeners.get("rewardedSlotReady") ?? []
      const grantedListeners = listeners.get("rewardedSlotGranted") ?? []
      readyListeners.forEach((listener) =>
        listener({
          slot,
          makeRewardedVisible: () => {
            grantedListeners.forEach((grantedListener) =>
              grantedListener({
                slot,
                payload: { type: "points", amount: 1 },
              })
            )
          },
        })
      )
    }),
    destroySlots: vi.fn(() => true),
  }

  Object.defineProperty(window, "googletag", {
    configurable: true,
    value: googletag,
    writable: true,
  })

  return { googletag }
}

describe("playRewardedAd", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    document.head.innerHTML = ""
    Object.defineProperty(window, "googletag", {
      configurable: true,
      value: undefined,
      writable: true,
    })
  })

  it("returns unsupported when the rewarded slot is unavailable", async () => {
    const googletag = {
      apiReady: true,
      cmd: [] as Array<() => void>,
      enums: { OutOfPageFormat: { REWARDED: "rewarded" } },
      pubads: () => ({
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
      defineOutOfPageSlot: vi.fn(() => null),
      enableServices: vi.fn(),
      display: vi.fn(),
      destroySlots: vi.fn(() => true),
    }
    Object.defineProperty(window, "googletag", {
      configurable: true,
      value: googletag,
      writable: true,
    })

    const result = await playRewardedAd("/1234567/lorevia/rewarded")

    expect(result.outcome).toBe("unsupported")
  })

  it("returns rewarded when GPT grants the reward", async () => {
    const { googletag } = installGoogletagMock()

    const result = await playRewardedAd("/1234567/lorevia/rewarded")

    expect(result.outcome).toBe("rewarded")
    expect(result.rewardType).toBe("points")
    expect(result.rewardAmount).toBe(1)
    expect(googletag.display).toHaveBeenCalled()
  })
})
