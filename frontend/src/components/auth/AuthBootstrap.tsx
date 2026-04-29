"use client"

import { useEffect, useRef } from "react"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"

export function AuthBootstrap() {
  const { user, setUser, logout } = useAuthStore()
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current || user) return
    ran.current = true

    const restore = async () => {
      try {
        const me = await authApi.me()
        if (me) {
          setUser(me)
          return
        }
        const refreshed = await authApi.refresh()
        if (!refreshed) {
          logout()
          return
        }
        const refreshedMe = await authApi.me()
        if (refreshedMe) {
          setUser(refreshedMe)
        } else {
          logout()
        }
      } catch {
        logout()
      }
    }

    restore()
  }, [user, setUser, logout])

  return null
}
