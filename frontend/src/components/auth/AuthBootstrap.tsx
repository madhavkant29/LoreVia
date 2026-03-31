"use client"

import { useEffect, useRef } from "react"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"

export function AuthBootstrap() {
  const { user, setAuth, setUser, logout } = useAuthStore()
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true

    const accessToken = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    const refreshToken = typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null
    if (!accessToken && !refreshToken) return
    if (user) return

    const restore = async () => {
      try {
        if (!accessToken && refreshToken) {
          const refreshed = await authApi.refresh(refreshToken)
          setAuth(refreshed.access_token, refreshed.refresh_token)
        }
        const me = await authApi.me()
        setUser(me)
      } catch {
        if (refreshToken) {
          try {
            const refreshed = await authApi.refresh(refreshToken)
            setAuth(refreshed.access_token, refreshed.refresh_token)
            const me = await authApi.me()
            setUser(me)
            return
          } catch {
            logout()
          }
        } else {
          logout()
        }
      }
    }

    restore()
  }, [user, setAuth, setUser, logout])

  return null
}
