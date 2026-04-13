"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import axios from "axios"

import { authApi } from "@/lib/api/auth"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/lib/stores/authStore"

export default function AuthCallbackPage() {
  const router = useRouter()
  const setAuth = useAuthStore((state) => state.setAuth)
  const setUser = useAuthStore((state) => state.setUser)

  useEffect(() => {
    let active = true
    const fail = (reason: string) => {
      router.replace(`/login?error=${encodeURIComponent(reason)}`)
    }

    const finishSignIn = async () => {
      try {
        if (!supabase) {
          fail("Google sign-in is not configured.")
          return
        }
        const url = new URL(window.location.href)
        const oauthError = url.searchParams.get("error_description") || url.searchParams.get("error")
        const code = url.searchParams.get("code")

        if (oauthError) {
          fail(oauthError)
          return
        }

        let session = (await supabase.auth.getSession()).data.session

        if (!session && code) {
          const { data, error } = await supabase.auth.exchangeCodeForSession(code)
          if (error) {
            fail(error.message || "Could not complete Google sign-in.")
            return
          }
          session = data.session
        }

        if (!session) {
          fail("No OAuth session was returned by Supabase.")
          return
        }

        const acceptedTerms = window.sessionStorage.getItem("lorevia-oauth-accepted-terms") === "true"
        window.sessionStorage.removeItem("lorevia-oauth-accepted-terms")
        const tokens = await authApi.loginWithSupabaseToken(session.access_token, acceptedTerms)
        if (!active) return

        setAuth(tokens.access_token, tokens.refresh_token)
        const me = await authApi.me()
        if (!active) return
        setUser(me)
        router.replace("/library")
      } catch (error) {
        if (axios.isAxiosError(error)) {
          const message =
            typeof error.response?.data?.detail === "string"
              ? error.response.data.detail
              : error.message
          fail(message || "OAuth sign-in failed.")
          return
        }
        if (error instanceof Error) {
          fail(error.message || "OAuth sign-in failed.")
          return
        }
        fail("OAuth sign-in failed.")
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
