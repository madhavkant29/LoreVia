"use client"

import { useEffect, useRef } from "react"
import { usePathname, useRouter } from "next/navigation"
import { authApi } from "@/lib/api/auth"
import { shouldSkipAuthBootstrap } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

function debug(label: string, ...args: unknown[]) {
  if (process.env.NODE_ENV === "production") return
  console.log(`[auth-bootstrap] ${label}`, ...args)
}

export function AuthBootstrap() {
  const { user, setUser, setHydrated, logout } = useAuthStore()
  const ran = useRef(false)
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    if (shouldSkipAuthBootstrap(pathname)) {
      debug("skipped", pathname)
      setHydrated()
      return
    }

    if (ran.current) return
    ran.current = true

    const redirectLogin = () => {
      debug("redirect to login")
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
    }

    const restore = async () => {
      debug("restore — no cached user")
      try {
        let me = await authApi.me()
        debug("me result", me ? "has user" : "null")
        if (!me) {
          debug("trying refresh")
          await authApi.refresh()
          me = await authApi.me()
          debug("me after refresh", me ? "has user" : "null")
        }
        if (me) {
          debug("setting user", me.id)
          document.cookie = "lorevia_session_dead=; Max-Age=0; Path=/"
          setUser(me)
        } else {
          debug("no session — hydrating then redirecting")
          setHydrated()
          redirectLogin()
        }
      } catch {
        debug("restore threw — logout + redirect")
        logout()
        redirectLogin()
      }
    }

    const validateExistingSession = async () => {
      debug("validate — cached user exists", user?.id)
      try {
        let me = await authApi.me()
        debug("me result", me ? "has user" : "null")
        if (!me) {
          debug("trying refresh")
          await authApi.refresh()
          me = await authApi.me()
          debug("me after refresh", me ? "has user" : "null")
        }
        if (me) {
          debug("user still valid", me.id)
          setUser(me)
          return
        }
        debug("session dead — logout + redirect")
        logout()
        redirectLogin()
      } catch {
        debug("validate threw — logout + redirect")
        logout()
        redirectLogin()
      }
    }

    if (user) {
      setHydrated()
      debug("cached user found, validating", user.id)
      void validateExistingSession()
      return
    }

    void restore()
  }, [pathname, user, setHydrated, setUser, logout, router])

  return null
}
