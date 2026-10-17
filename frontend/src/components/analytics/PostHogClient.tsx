"use client"

import dynamic from "next/dynamic"
import { usePathname } from "next/navigation"
import { useReportWebVitals } from "next/web-vitals"
import React from "react"
import {
  captureWebVital,
  installBrowserErrorTelemetry,
} from "@/lib/analytics/browserTelemetry"
import {
  ANALYTICS_CONSENT_COOKIE,
  ANALYTICS_CONSENT_EVENT,
  getAnalyticsConsentValue,
  hasAnalyticsConsent,
  shouldShowAnalyticsConsentBanner,
  writeAnalyticsConsentCookie,
} from "@/lib/analytics/posthogConsent"

const CookieConsent = dynamic(
  () => import("react-cookie-consent").then((module) => module.default),
  { ssr: false, loading: () => null },
)

function isBrowserAnalyticsEnabled() {
  return typeof window !== "undefined" && Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY)
}

let posthogInitPromise: Promise<void> | null = null
let posthogClient: typeof import("posthog-js").default | null = null

async function initPostHog() {
  if (!isBrowserAnalyticsEnabled() || !hasAnalyticsConsent(getAnalyticsConsentValue(document.cookie))) return
  if (!posthogInitPromise) {
    posthogInitPromise = import("posthog-js").then(({ default: posthog }) => {
      // Consent may have been withdrawn while the SDK was loading.
      if (!hasAnalyticsConsent(getAnalyticsConsentValue(document.cookie))) { posthogInitPromise = null; return }
      posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY as string, {
        api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://eu.posthog.com",
        autocapture: false,
        ip: false,
        capture_pageview: true,
        capture_pageleave: true,
        persistence: "localStorage",
        disable_session_recording: true,
      })
      posthogClient = posthog
    }).catch(() => { posthogInitPromise = null })
  }
  await posthogInitPromise
  if (posthogClient && hasAnalyticsConsent(getAnalyticsConsentValue(document.cookie))) {
    posthogClient.opt_in_capturing({ captureEventName: false })
    window.__loreviaPosthog = posthogClient
  } else posthogClient?.opt_out_capturing()
}

export function PostHogClient() {
  const [hydrated, setHydrated] = React.useState(false)
  const [consentValue, setConsentValue] = React.useState<string | undefined>(undefined)
  const pathname = usePathname()
  const analyticsKey = process.env.NEXT_PUBLIC_POSTHOG_KEY
  const useSquareCorners = pathname === "/blog" || pathname.startsWith("/blog/") || pathname === "/answers" || pathname.startsWith("/answers/")

  useReportWebVitals((metric) => {
    if (hasAnalyticsConsent(consentValue)) captureWebVital(metric)
  })

  React.useEffect(() => {
    const updateConsent = () => {
      const consent = getAnalyticsConsentValue(document.cookie)
      setConsentValue(consent)
      if (hasAnalyticsConsent(consent)) {
        if (analyticsKey) void initPostHog()
      } else {
        window.__loreviaPosthog?.opt_out_capturing?.()
        delete window.__loreviaPosthog
      }
    }
    updateConsent()
    setHydrated(true)
    window.addEventListener(ANALYTICS_CONSENT_EVENT, updateConsent)
    return () => window.removeEventListener(ANALYTICS_CONSENT_EVENT, updateConsent)
  }, [analyticsKey])

  React.useEffect(() => {
    if (!analyticsKey || !hasAnalyticsConsent(consentValue)) return
    return installBrowserErrorTelemetry()
  }, [analyticsKey, consentValue])

  const enable = () => {
    writeAnalyticsConsentCookie("true")
  }

  const dismiss = () => {
    writeAnalyticsConsentCookie("false")
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
          containerClasses="lorevia-cookie-consent"
          enableDeclineButton
          setDeclineCookie
          declineButtonText="Not now"
          buttonText="Yes, for analytics"
          onAccept={enable}
          onDecline={dismiss}
          style={{
            background: "rgba(0,0,0,0.92)",
            border: "1px solid rgba(255,255,255,0.16)",
            borderRadius: useSquareCorners ? "0" : "0.75rem",
            bottom: "1rem",
            boxShadow: "0 18px 55px rgba(0,0,0,0.35)",
            color: "white",
            fontSize: "13px",
            left: "50%",
            lineHeight: "1.6",
            maxWidth: "34rem",
            right: "auto",
            transform: "translateX(-50%)",
            width: "calc(100% - 2rem)",
            zIndex: "60",
          }}
          contentStyle={{ flex: "1 1 18rem", margin: "12px 16px" }}
          buttonStyle={{
            background: "#6d28d9",
            color: "white",
            fontSize: "13px",
            borderRadius: useSquareCorners ? "0" : "9999px",
            padding: "10px 14px",
          }}
          declineButtonStyle={{
            background: "transparent",
            color: "rgba(255,255,255,0.85)",
            border: "1px solid rgba(255,255,255,0.18)",
            fontSize: "13px",
            borderRadius: useSquareCorners ? "0" : "0.375rem",
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
