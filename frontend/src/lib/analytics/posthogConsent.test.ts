import { describe, expect, it } from "vitest"

import {
  ANALYTICS_CONSENT_COOKIE,
  hasAnalyticsConsent,
  shouldShowAnalyticsConsentBanner,
} from "./posthogConsent"

describe("posthog consent helpers", () => {
  it("uses the expected analytics consent cookie name", () => {
    expect(ANALYTICS_CONSENT_COOKIE).toBe("lorevia_analytics_consent")
  })

  it("treats only an explicit true value as consent", () => {
    expect(hasAnalyticsConsent("true")).toBe(true)
    expect(hasAnalyticsConsent("false")).toBe(false)
    expect(hasAnalyticsConsent(undefined)).toBe(false)
  })

  it("shows the banner when analytics is configured and consent is missing", () => {
    expect(
      shouldShowAnalyticsConsentBanner({
        analyticsKey: "phc_test",
        consentValue: undefined,
        pathname: "/login",
        hydrated: true,
      })
    ).toBe(true)
  })

  it("shows the banner again after a previous decline", () => {
    expect(
      shouldShowAnalyticsConsentBanner({
        analyticsKey: "phc_test",
        consentValue: "false",
        pathname: "/settings",
        hydrated: true,
      })
    ).toBe(true)
  })

  it("hides the banner after consent has been accepted", () => {
    expect(
      shouldShowAnalyticsConsentBanner({
        analyticsKey: "phc_test",
        consentValue: "true",
        pathname: "/login",
        hydrated: true,
      })
    ).toBe(false)
  })

  it("hides the banner before hydration and on privacy pages", () => {
    expect(
      shouldShowAnalyticsConsentBanner({
        analyticsKey: "phc_test",
        consentValue: undefined,
        pathname: "/login",
        hydrated: false,
      })
    ).toBe(false)

    expect(
      shouldShowAnalyticsConsentBanner({
        analyticsKey: "phc_test",
        consentValue: undefined,
        pathname: "/privacy",
        hydrated: true,
      })
    ).toBe(false)
  })
})
