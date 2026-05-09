export const ANALYTICS_CONSENT_COOKIE = "lorevia_analytics_consent"

export function hasAnalyticsConsent(consentValue: string | undefined) {
  return consentValue === "true"
}

export function shouldShowAnalyticsConsentBanner({
  analyticsKey,
  consentValue,
  pathname,
  hydrated,
}: {
  analyticsKey: string | undefined
  consentValue: string | undefined
  pathname: string | null
  hydrated: boolean
}) {
  if (!hydrated || !analyticsKey || pathname === "/privacy") {
    return false
  }

  return !hasAnalyticsConsent(consentValue)
}
