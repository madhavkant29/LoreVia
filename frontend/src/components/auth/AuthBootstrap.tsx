"use client"

import { useEffect, useRef } from "react"
import { usePathname, useRouter } from "next/navigation"
import { authApi } from "@/lib/api/auth"
import { shouldSkipAuthBootstrap } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

export function AuthBootstrap() {
  const { user, setUser, setHydrated, logout } = useAuthStore()
  const ran = useRef(false)
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    if (shouldSkipAuthBootstrap(pathname)) {
      setHydrated()
      return
    }

    if (ran.current) return
    ran.current = true

    const redirectLogin = () => {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
    }

    const restore = async () => {
      try {
        let me = await authApi.me()
        if (!me) {
          await authApi.refresh()
          me = await authApi.me()
        }
        if (me) {
          setUser(me)
        } else {
          setHydrated()
          redirectLogin()
        }
      } catch {
        logout()
        redirectLogin()
      }
    }

    const validateExistingSession = async () => {
      try {
        let me = await authApi.me()
        if (!me) {
          await authApi.refresh()
          me = await authApi.me()
        }
        if (me) {
          setUser(me)
          return
        }
        logout()
        redirectLogin()
      } catch {
        logout()
        redirectLogin()
      }
    }

    if (user) {
      setHydrated()
      void validateExistingSession()
      return
    }

    void restore()
  }, [pathname, user, setHydrated, setUser, logout, router])

  return null
}
