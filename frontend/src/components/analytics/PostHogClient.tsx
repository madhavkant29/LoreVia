"use client"

import dynamic from "next/dynamic"
import { usePathname } from "next/navigation"
import React from "react"
import {
  ANALYTICS_CONSENT_COOKIE,
  getAnalyticsConsentValue,
  hasAnalyticsConsent,
  shouldShowAnalyticsConsentBanner,
} from "@/lib/analytics/posthogConsent"

const CookieConsent = dynamic(
  () => import("react-cookie-consent").then((module) => module.default),
  { ssr: false, loading: () => null },
)

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
      window.__loreviaPosthog = posthog
    })
  }
  await posthogInitPromise
}

export function PostHogClient() {
  const [hydrated, setHydrated] = React.useState(false)
  const [consentValue, setConsentValue] = React.useState<string | undefined>(undefined)
  const pathname = usePathname()
  const analyticsKey = process.env.NEXT_PUBLIC_POSTHOG_KEY

  React.useEffect(() => {
    if (!analyticsKey) {
      setHydrated(true)
      return
    }

    const consent = getAnalyticsConsentValue(document.cookie)
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
            background: "#6d28d9",
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
            borderRadius: "0.375rem",
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

export function PostHogClientProvider({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <PostHogClient />
    </>
  )
}
