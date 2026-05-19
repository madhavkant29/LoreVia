"use client"

import { usePathname } from "next/navigation"
import React from "react"
import CookieConsent, { getCookieConsentValue } from "react-cookie-consent"
import {
  ANALYTICS_CONSENT_COOKIE,
  hasAnalyticsConsent,
  shouldShowAnalyticsConsentBanner,
} from "@/lib/analytics/posthogConsent"

function isBrowserAnalyticsEnabled() {
  return typeof window !== "undefined" && Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY)
}

let posthogInitPromise: Promise<void> | null = null

async function initPostHog() {
  if (!isBrowserAnalyticsEnabled()) return
  if (!posthogInitPromise) {
    posthogInitPromise = import("posthog-js").then(({ default: posthog }) => {
      posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY as string, {
        api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://eu.posthog.com",
        ip: false,
        capture_pageview: true,
        capture_pageleave: true,
        persistence: "localStorage",
        disable_session_recording: true,
      })
    })
  }
  await posthogInitPromise
}

export function PostHogClientProvider({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = React.useState(false)
  const [consentValue, setConsentValue] = React.useState<string | undefined>(undefined)
  const pathname = usePathname()
  const analyticsKey = process.env.NEXT_PUBLIC_POSTHOG_KEY

  React.useEffect(() => {
    if (!analyticsKey) {
      setHydrated(true)
      return
    }

    const consent = getCookieConsentValue(ANALYTICS_CONSENT_COOKIE) || undefined
    setConsentValue(consent)
    setHydrated(true)

    if (hasAnalyticsConsent(consent)) {
      void initPostHog()
    }
  }, [analyticsKey])

  const enable = () => {
    void initPostHog()
    setConsentValue("true")
  }

  const dismiss = () => {
    setConsentValue("false")
  }

  const showBanner = shouldShowAnalyticsConsentBanner({
    analyticsKey,
    consentValue,
    pathname,
    hydrated,
  })

  return (
    <>
      {children}
      {showBanner ? (
        <CookieConsent
          visible={showBanner ? "show" : "hidden"}
          cookieName={ANALYTICS_CONSENT_COOKIE}
          enableDeclineButton
          setDeclineCookie
          declineButtonText="Not now"
          buttonText="Yes, for analytics"
          onAccept={enable}
          onDecline={dismiss}
          style={{
            background: "rgba(0,0,0,0.92)",
            color: "white",
            fontSize: "13px",
            lineHeight: "1.6",
          }}
          buttonStyle={{
            background: "linear-gradient(135deg,#4f46e5,#4338ca)",
            color: "white",
            fontSize: "13px",
            borderRadius: "9999px",
            padding: "10px 14px",
          }}
          declineButtonStyle={{
            background: "transparent",
            color: "rgba(255,255,255,0.85)",
            border: "1px solid rgba(255,255,255,0.18)",
            fontSize: "13px",
            borderRadius: "9999px",
            padding: "10px 14px",
          }}
        >
          Want to allow cookies for analytics? We use them to see which features people use and improve the app. See our{" "}
          <a href="/privacy" className="underline underline-offset-4">
            Privacy Policy
          </a>
          .
        </CookieConsent>
      ) : null}
    </>
  )
}

