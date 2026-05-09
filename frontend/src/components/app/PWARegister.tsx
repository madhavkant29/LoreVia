"use client"

import { useEffect } from "react"

export function PWARegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return

    const isNetlifyPreview = window.location.hostname.endsWith(".netlify.app")
    if (isNetlifyPreview) {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        void Promise.all(registrations.map((registration) => registration.unregister()))
      }).catch(() => {})
      return
    }

    navigator.serviceWorker.register("/sw.js").catch(() => {})
  }, [])

  return null
}
