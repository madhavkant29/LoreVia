import type { RewardedAdOutcome } from "@/types/monetization"

const GPT_SCRIPT_SRC = "https://securepubads.g.doubleclick.net/tag/js/gpt.js"

type RewardedAdEventType =
  | "rewardedSlotReady"
  | "rewardedSlotGranted"
  | "rewardedSlotClosed"

type RewardedSlot = {
  addService: (service: GoogletagPubAdsService) => RewardedSlot
  getSlotElementId: () => string
}

type RewardedReadyEvent = {
  slot: RewardedSlot
  makeRewardedVisible: () => void
}

type RewardedGrantedEvent = {
  slot: RewardedSlot
  payload?: {
    type?: string
    amount?: number
  }
}

type RewardedClosedEvent = {
  slot: RewardedSlot
}

type GoogletagPubAdsService = {
  addEventListener: (eventType: RewardedAdEventType, listener: (event: unknown) => void) => void
  removeEventListener: (eventType: RewardedAdEventType, listener: (event: unknown) => void) => void
}

type Googletag = {
  apiReady?: boolean
  cmd: Array<() => void>
  enums: {
    OutOfPageFormat: {
      REWARDED: unknown
    }
  }
  pubads: () => GoogletagPubAdsService
  defineOutOfPageSlot: (adUnitPath: string, format: unknown) => RewardedSlot | null
  enableServices: () => void
  display: (slot: RewardedSlot) => void
  destroySlots: (slots: RewardedSlot[]) => boolean
}

declare global {
  interface Window {
    googletag?: Googletag
  }
}

let gptLoadPromise: Promise<void> | null = null
let gptServicesEnabled = false

function ensureGoogletagBootstrap() {
  if (typeof window === "undefined") {
    throw new Error("Rewarded ads are only available in the browser.")
  }
  window.googletag = window.googletag || ({ cmd: [] } as unknown as Googletag)
  window.googletag.cmd = window.googletag.cmd || []
  return window.googletag
}

function loadGptScript(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Rewarded ads are only available in the browser."))
  }
  const googletag = ensureGoogletagBootstrap()
  if (googletag.apiReady) {
    return Promise.resolve()
  }
  if (gptLoadPromise) {
    return gptLoadPromise
  }

  gptLoadPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GPT_SCRIPT_SRC}"]`)
    if (existing) {
      const timeoutId = window.setTimeout(() => reject(new Error("Timed out waiting for GPT to load.")), 12000)
      googletag.cmd.push(() => {
        window.clearTimeout(timeoutId)
        resolve()
      })
      return
    }

    const script = document.createElement("script")
    script.src = GPT_SCRIPT_SRC
    script.async = true
    script.crossOrigin = "anonymous"
    script.onload = () => {
      const timeoutId = window.setTimeout(() => reject(new Error("Timed out waiting for GPT to initialize.")), 12000)
      googletag.cmd.push(() => {
        window.clearTimeout(timeoutId)
        resolve()
      })
    }
    script.onerror = () => reject(new Error("Failed to load Google Publisher Tag."))
    document.head.appendChild(script)
  })

  return gptLoadPromise
}

function runGptCommand<T>(googletag: Googletag, callback: () => T): Promise<T> {
  if (googletag.apiReady) {
    return Promise.resolve(callback())
  }
  return new Promise<T>((resolve) => {
    googletag.cmd.push(() => resolve(callback()))
  })
}

async function ensureGptReady(): Promise<Googletag> {
  await loadGptScript()
  const googletag = ensureGoogletagBootstrap()
  if (!gptServicesEnabled) {
    await runGptCommand(googletag, () => {
        if (!gptServicesEnabled) {
          googletag.enableServices()
          gptServicesEnabled = true
        }
    })
  }
  return googletag
}

export interface RewardedAdPlaybackResult {
  outcome: RewardedAdOutcome
  rewardType?: string | null
  rewardAmount?: number | null
  errorMessage?: string | null
}

export async function playRewardedAd(adUnitPath: string): Promise<RewardedAdPlaybackResult> {
  try {
    const googletag = await ensureGptReady()
    return await runGptCommand(googletag, () =>
      new Promise<RewardedAdPlaybackResult>((resolve) => {
        const slot = googletag.defineOutOfPageSlot(adUnitPath, googletag.enums.OutOfPageFormat.REWARDED)
        if (!slot) {
          resolve({
            outcome: "unsupported",
            errorMessage: "Rewarded ads are not supported on this page or device.",
          })
          return
        }

        const service = googletag.pubads()
        slot.addService(service)
        let settled = false
        let timeoutId = 0

        const cleanup = () => {
          window.clearTimeout(timeoutId)
          service.removeEventListener("rewardedSlotReady", onReady)
          service.removeEventListener("rewardedSlotGranted", onGranted)
          service.removeEventListener("rewardedSlotClosed", onClosed)
          googletag.destroySlots([slot])
        }

        const settle = (result: RewardedAdPlaybackResult) => {
          if (settled) {
            return
          }
          settled = true
          cleanup()
          resolve(result)
        }

        const onReady = (event: unknown) => {
          const rewardedEvent = event as RewardedReadyEvent
          if (rewardedEvent.slot !== slot) {
            return
          }
          rewardedEvent.makeRewardedVisible()
        }

        const onGranted = (event: unknown) => {
          const rewardedEvent = event as RewardedGrantedEvent
          if (rewardedEvent.slot !== slot) {
            return
          }
          settle({
            outcome: "rewarded",
            rewardType: rewardedEvent.payload?.type ?? null,
            rewardAmount: rewardedEvent.payload?.amount ?? null,
          })
        }

        const onClosed = (event: unknown) => {
          const rewardedEvent = event as RewardedClosedEvent
          if (rewardedEvent.slot !== slot) {
            return
          }
          settle({
            outcome: "dismissed",
            errorMessage: "The rewarded ad was closed before a reward was granted.",
          })
        }

        service.addEventListener("rewardedSlotReady", onReady)
        service.addEventListener("rewardedSlotGranted", onGranted)
        service.addEventListener("rewardedSlotClosed", onClosed)

        timeoutId = window.setTimeout(() => {
          settle({
            outcome: "error",
            errorMessage: "Rewarded ad playback timed out before a reward was granted.",
          })
        }, 30000)

        googletag.display(slot)
      })
    )
  } catch (error) {
    return {
      outcome: "error",
      errorMessage: error instanceof Error ? error.message : "Rewarded ad playback failed.",
    }
  }
}
