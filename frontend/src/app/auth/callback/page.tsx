"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { authApi } from "@/lib/api/auth"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/lib/stores/authStore"

export default function AuthCallbackPage() {
  const router = useRouter()
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
          fail("Google sign-in failed. Please try again.")
          return
        }

        let session = (await supabase.auth.getSession()).data.session

        if (!session && code) {
          const { data, error } = await supabase.auth.exchangeCodeForSession(code)
          if (error) {
            fail("Could not complete Google sign-in.")
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
        const user = await authApi.loginWithSupabaseToken(session.access_token, acceptedTerms)
        if (!active) return

        if (!user) {
          fail("Could not load your profile after Google sign-in.")
          return
        }
        setUser(user)
        router.replace(user.username ? "/library" : "/complete-username")
      } catch (error) {
        if (error instanceof Error) {
          fail("OAuth sign-in failed.")
          return
        }
        fail("OAuth sign-in failed.")
      }
    }

    finishSignIn()
    return () => {
      active = false
    }
  }, [router, setUser])

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <p className="text-sm text-gray-500">Signing you in...</p>
    </div>
  )
}
