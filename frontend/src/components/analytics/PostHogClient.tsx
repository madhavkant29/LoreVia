"use client"

import posthog from "posthog-js"
import { PostHogProvider } from "posthog-js/react"
import React from "react"
import CookieConsent, { getCookieConsentValue } from "react-cookie-consent"

function isEnabled() {
  return typeof window !== "undefined" && Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY)
}

function initPostHog() {
  if (!isEnabled()) return
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY as string, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://eu.posthog.com",
    ip: false,
    capture_pageview: true,
    capture_pageleave: true,
    persistence: "localStorage",
    disable_session_recording: true,
  })
}

export function PostHogClientProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = React.useState(false)

  React.useEffect(() => {
    if (!isEnabled()) return
    const consent = getCookieConsentValue("lorevia_analytics_consent")
    if (consent === "true") {
      initPostHog()
      setReady(true)
    }
  }, [])

  const enable = () => {
    initPostHog()
    setReady(true)
  }

  return (
    <>
      {ready ? <PostHogProvider client={posthog}>{children}</PostHogProvider> : <>{children}</>}
      {isEnabled() ? (
        <CookieConsent
          cookieName="lorevia_analytics_consent"
          enableDeclineButton
          declineButtonText="Not now"
          buttonText="Yes, for analytics"
          onAccept={enable}
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
          Want to allow cookies for analytics? We use them to see which features people use and to improve the app. See our{" "}
          <a href="/privacy" className="underline underline-offset-4">
            Privacy Policy
          </a>
          .
        </CookieConsent>
      ) : null}
    </>
  )
}

