"use client"

import { useEffect } from "react"

export function PWARegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return

    const isNetlifyPreview = window.location.hostname.endsWith(".netlify.app")
    const isLocalhost =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1" ||
      window.location.hostname === "[::1]"

    if (isNetlifyPreview || isLocalhost || process.env.NODE_ENV !== "production") {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        void Promise.all(registrations.map((registration) => registration.unregister()))
      }).catch(() => {})
      return
    }

    navigator.serviceWorker.register("/sw.js").catch(() => {})
  }, [])

  return null
}
