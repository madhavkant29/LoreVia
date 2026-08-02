export type AnalyticsProps = Record<string, unknown>

type PostHogCaptureClient = {
  capture: (event: string, properties?: AnalyticsProps) => void
  identify: (userId: string, properties?: AnalyticsProps) => void
  reset: () => void
}

declare global {
  interface Window {
    __loreviaPosthog?: PostHogCaptureClient
  }
}

export function capture(event: string, properties?: AnalyticsProps) {
  try {
    if (typeof window === "undefined") return
    window.__loreviaPosthog?.capture(event, properties)
  } catch {
    // never block UX on analytics
  }
}

export function captureTiming(event: string, startedAt: number, properties?: AnalyticsProps) {
  try {
    if (typeof window === "undefined") return
    const durationMs = Math.max(0, Math.round(performance.now() - startedAt))
    capture(event, {
      ...properties,
      duration_ms: durationMs,
    })
  } catch {
    // never block UX on analytics
  }
}

export function identify(userId: string, properties?: AnalyticsProps) {
  try {
    if (typeof window === "undefined" || !userId) return
    window.__loreviaPosthog?.identify(userId, properties)
  } catch {
    // never block UX on analytics
  }
}

