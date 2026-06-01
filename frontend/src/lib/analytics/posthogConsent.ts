export const ANALYTICS_CONSENT_COOKIE = "lorevia_analytics_consent"

export function hasAnalyticsConsent(consentValue: string | undefined) {
  return consentValue === "true"
}

export function getAnalyticsConsentValue(cookieString: string) {
  if (!cookieString) return undefined

  const cookies = new Map<string, string>()
  for (const cookiePair of cookieString.split(";")) {
    const [rawName, ...rawValueParts] = cookiePair.trim().split("=")
    try {
      cookies.set(
        decodeURIComponent(rawName),
        rawValueParts.length ? decodeURIComponent(rawValueParts.join("=")) : "",
      )
    } catch {
      // Ignore malformed cookies just as the previous cookie parser did.
    }
  }

  return cookies.get(ANALYTICS_CONSENT_COOKIE) ?? cookies.get(`${ANALYTICS_CONSENT_COOKIE}-legacy`)
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
