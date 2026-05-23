export type AnalyticsProps = Record<string, unknown>

type PostHogCaptureClient = {
  capture: (event: string, properties?: AnalyticsProps) => void
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

