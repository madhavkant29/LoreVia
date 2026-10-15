export const ANALYTICS_CONSENT_COOKIE = "lorevia_analytics_consent"
export const ANALYTICS_CONSENT_EVENT = "lorevia:analytics-consent-changed"

export function writeAnalyticsConsentCookie(value: "true" | "false") {
  document.cookie = `${ANALYTICS_CONSENT_COOKIE}=${value}; Max-Age=31536000; Path=/; SameSite=Lax`
  window.dispatchEvent(new Event(ANALYTICS_CONSENT_EVENT))
}

export function hasAnalyticsConsent(consentValue: string | undefined) {
  return consentValue === "true"
}

export function hasAnalyticsConsentChoice(consentValue: string | undefined) {
  return consentValue === "true" || consentValue === "false"
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

  return !hasAnalyticsConsentChoice(consentValue)
}
