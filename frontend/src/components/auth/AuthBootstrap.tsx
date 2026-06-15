"use client"

import { useEffect, useRef } from "react"
import { usePathname, useRouter } from "next/navigation"
import { authApi } from "@/lib/api/auth"
import { captureTiming } from "@/lib/analytics/posthog"
import { shouldSkipAuthBootstrap } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

function debug(label: string, ...args: unknown[]) {
  if (process.env.NODE_ENV === "production") return
  console.log(`[auth-bootstrap] ${label}`, ...args)
}

export function AuthBootstrap() {
  const { user, setUser, setHydrated, logout } = useAuthStore()
  const ran = useRef(false)
  const startedAt = useRef(typeof performance !== "undefined" ? performance.now() : 0)
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    if (shouldSkipAuthBootstrap(pathname)) {
      debug("skipped", pathname)
      setHydrated()
      captureTiming("auth_ready_ms", startedAt.current, { skipped: true })
      return
    }

    if (ran.current) return
    ran.current = true

    const redirectLogin = () => {
      debug("redirect to login")
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
    }

    const restoreSession = async ({ cachedUser }: { cachedUser: boolean }) => {
      debug(cachedUser ? "validate cached user via session" : "restore via session")
      try {
        const me = await authApi.session()
        debug("session result", me ? "has user" : "null")
        if (me) {
          debug("setting user", me.id)
          document.cookie = "lorevia_session_dead=; Max-Age=0; Path=/"
          setUser(me)
          captureTiming("auth_ready_ms", startedAt.current, { cached_user: cachedUser })
          return
        }
      } catch {
        debug("session failed")
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
      debug("cached user found, validating", user.id)
      void restoreSession({ cachedUser: true })
      return
    }

    void restoreSession({ cachedUser: false })
  }, [pathname, user, setHydrated, setUser, logout, router])

  return null
}
