import { describe, expect, it } from "vitest"

import {
  ANALYTICS_CONSENT_COOKIE,
  getAnalyticsConsentValue,
  hasAnalyticsConsentChoice,
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

  it("treats explicit true and false values as remembered choices", () => {
    expect(hasAnalyticsConsentChoice("true")).toBe(true)
    expect(hasAnalyticsConsentChoice("false")).toBe(true)
    expect(hasAnalyticsConsentChoice(undefined)).toBe(false)
  })

  it("reads the analytics consent value from a browser cookie string", () => {
    expect(getAnalyticsConsentValue("other=value; lorevia_analytics_consent=true; theme=dark")).toBe("true")
    expect(getAnalyticsConsentValue("lorevia_analytics_consent=false")).toBe("false")
    expect(getAnalyticsConsentValue("other=value")).toBeUndefined()
  })

  it("falls back to legacy analytics consent and ignores malformed cookies", () => {
    expect(getAnalyticsConsentValue("lorevia_analytics_consent-legacy=true")).toBe("true")
    expect(getAnalyticsConsentValue("bad=%E0%A4%A; lorevia_analytics_consent=true")).toBe("true")
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

  it("hides the banner after a previous decline", () => {
    expect(
      shouldShowAnalyticsConsentBanner({
        analyticsKey: "phc_test",
        consentValue: "false",
        pathname: "/settings",
        hydrated: true,
      })
    ).toBe(false)
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
