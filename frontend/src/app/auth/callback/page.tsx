"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { authApi } from "@/lib/api/auth"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/lib/stores/authStore"

export default function AuthCallbackPage() {
  const router = useRouter()
  const setAuth = useAuthStore((state) => state.setAuth)
  const setUser = useAuthStore((state) => state.setUser)

  useEffect(() => {
    let active = true

    const finishSignIn = async () => {
      try {
        const url = new URL(window.location.href)
        const oauthError = url.searchParams.get("error_description") || url.searchParams.get("error")
        const code = url.searchParams.get("code")

        if (oauthError) {
          router.replace("/login?error=oauth_failed")
          return
        }

        let session = (await supabase.auth.getSession()).data.session

        if (!session && code) {
          const { data, error } = await supabase.auth.exchangeCodeForSession(code)
          if (error) {
            router.replace("/login?error=oauth_failed")
            return
          }
          session = data.session
        }

        if (!session) {
          router.replace("/login?error=oauth_failed")
          return
        }

        const tokens = await authApi.loginWithSupabaseToken(session.access_token)
        if (!active) return

        setAuth(tokens.access_token, tokens.refresh_token)
        const me = await authApi.me()
        if (!active) return
        setUser(me)
        router.replace("/library")
      } catch {
        router.replace("/login?error=oauth_failed")
      }
    }

    finishSignIn()
    return () => {
      active = false
    }
  }, [router, setAuth, setUser])

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <p className="text-sm text-gray-500">Signing you in...</p>
    </div>
  )
}
