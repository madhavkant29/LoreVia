"use client"

import { useEffect, useRef, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import axios from "axios"
import { authApi } from "@/lib/api/auth"
import { capture, captureTiming, identify } from "@/lib/analytics/posthog"
import { shouldSkipAuthBootstrap } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

export function AuthBootstrap() {
  const { user, setUser, setHydrated, logout } = useAuthStore()
  const ran = useRef(false)
  const [retryCount, setRetryCount] = useState(0)
  const [sessionUnavailable, setSessionUnavailable] = useState(false)
  const startedAt = useRef(typeof performance !== "undefined" ? performance.now() : 0)
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    if (shouldSkipAuthBootstrap(pathname)) {
      setSessionUnavailable(false)
      setHydrated()
      captureTiming("auth_ready_ms", startedAt.current, { skipped: true })
      return
    }

    if (ran.current) return
    ran.current = true

    const redirectLogin = () => {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
    }

    const restoreSession = async ({ cachedUser }: { cachedUser: boolean }) => {
      try {
        const me = await authApi.session()
        if (me) {
          document.cookie = "lorevia_session_dead=; Max-Age=0; Path=/"
          setUser(me)
          identify(me.id, { tier: me.tier, account_created_at: me.created_at })
          const analyticsSessionKey = `lorevia:analytics-session:${me.id}`
          if (!window.sessionStorage.getItem(analyticsSessionKey)) {
            window.sessionStorage.setItem(analyticsSessionKey, "1")
            capture("app_session_started", { tier: me.tier })
          }
          captureTiming("auth_ready_ms", startedAt.current, { cached_user: cachedUser })
          return
        }
      } catch (error) {
        if (!axios.isAxiosError(error) || error.response?.status !== 401) {
          setHydrated()
          setSessionUnavailable(true)
          return
        }
      }

      if (cachedUser) {
        logout()
        redirectLogin()
        return
      }

      setHydrated()
      captureTiming("auth_ready_ms", startedAt.current, { authenticated: false })
      redirectLogin()
    }

    if (user) {
      setHydrated()
      void restoreSession({ cachedUser: true })
      return
    }

    void restoreSession({ cachedUser: false })
  }, [pathname, user, setHydrated, setUser, logout, router, retryCount])

  if (!sessionUnavailable) return null

  return (
    <div role="alert" className="fixed inset-x-4 top-4 z-[100] mx-auto max-w-lg rounded-lg border border-amber-500/40 bg-[rgb(var(--background))] p-4 text-sm text-[rgb(var(--foreground))] shadow-lg">
      <p className="font-semibold">Could not verify your session right now.</p>
      <p className="mt-1">We could not confirm your sign-in. Check your connection and try again.</p>
      <button
        type="button"
        className="app-button-secondary mt-3"
        onClick={() => {
          setSessionUnavailable(false)
          ran.current = false
          setRetryCount((count) => count + 1)
        }}
      >
        Retry session check
      </button>
    </div>
  )
}
