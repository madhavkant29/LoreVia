"use client"

import { useEffect, useRef } from "react"
import { usePathname } from "next/navigation"
import { authApi } from "@/lib/api/auth"
import { shouldSkipAuthBootstrap } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

export function AuthBootstrap() {
  const { user, setUser, setHydrated, logout } = useAuthStore()
  const ran = useRef(false)
  const pathname = usePathname()

  useEffect(() => {
    if (ran.current) return
    ran.current = true

    if (shouldSkipAuthBootstrap(pathname)) {
      setHydrated()
      return
    }

    if (user) return

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
        }
      } catch {
        logout()
      }
    }

    restore()
  }, [pathname, user, setHydrated, setUser, logout])

  return null
}
