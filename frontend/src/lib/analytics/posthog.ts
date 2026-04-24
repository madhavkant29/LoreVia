import posthog from "posthog-js"

export type AnalyticsProps = Record<string, unknown>

export function capture(event: string, properties?: AnalyticsProps) {
  try {
    const loaded = Boolean((posthog as any).__loaded)
    if (!loaded) return
    posthog.capture(event, properties)
  } catch {
    // never block UX on analytics
  }
}

