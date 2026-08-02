"use client"

import { useEffect, useRef } from "react"
import { usePathname, useRouter } from "next/navigation"
import { authApi } from "@/lib/api/auth"
import { capture, captureTiming, identify } from "@/lib/analytics/posthog"
import { shouldSkipAuthBootstrap } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

export function AuthBootstrap() {
  const { user, setUser, setHydrated, logout } = useAuthStore()
  const ran = useRef(false)
  const startedAt = useRef(typeof performance !== "undefined" ? performance.now() : 0)
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    if (shouldSkipAuthBootstrap(pathname)) {
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
      } catch {}

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
  }, [pathname, user, setHydrated, setUser, logout, router])

  return null
}
