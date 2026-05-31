"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import axios from "axios"

import { authApi } from "@/lib/api/auth"
import { normalizeLoginError } from "@/lib/auth/loginMessages"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/lib/stores/authStore"
import { getOrCreateDeviceId } from "@/lib/utils/device"

const PENDING_OAUTH_USER_KEY = "lorevia-pending-oauth-user"

export default function AuthCallbackPage() {
  const router = useRouter()
  const setUser = useAuthStore((state) => state.setUser)
  const [status, setStatus] = useState("Preparing Google sign-in...")

  useEffect(() => {
    let active = true
    const withTimeout = async <T,>(promise: Promise<T>, label: string, timeoutMs = 15000): Promise<T> => {
      return await Promise.race([
        promise,
        new Promise<T>((_, reject) => {
          window.setTimeout(() => reject(new Error(`${label} timed out.`)), timeoutMs)
        }),
      ])
    }

    const fail = (reason: string) => {
      if (active) {
        setStatus(reason)
      }
      router.replace(`/login?error=${encodeURIComponent(reason)}`)
    }

    const finishSignIn = async () => {
      try {
        if (!supabase) {
          fail("Google sign-in is not configured.")
          return
        }
        if (active) {
          setStatus("Reading Google callback...")
        }
        const url = new URL(window.location.href)
        const oauthError = url.searchParams.get("error_description") || url.searchParams.get("error")
        const code = url.searchParams.get("code")

        if (oauthError) {
          fail("Google sign-in failed. Please try again.")
          return
        }

        if (active) {
          setStatus("Checking Supabase session...")
        }
        let session = (await withTimeout(supabase.auth.getSession(), "Checking Supabase session")).data.session

        if (!session && code) {
          if (active) {
            setStatus("Completing Google sign-in with Supabase...")
          }
          const { data, error } = await withTimeout(
            supabase.auth.exchangeCodeForSession(code),
            "Completing Google sign-in with Supabase",
          )
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
        if (active) {
          setStatus("Signing you into LoreVia...")
        }
        const user = await withTimeout(
          authApi.loginWithSupabaseToken(session.access_token, getOrCreateDeviceId(), acceptedTerms),
          "Signing you into LoreVia",
        )
        if (!active) return

        if (!user) {
          fail("Could not load your profile after Google sign-in.")
          return
        }
        window.sessionStorage.removeItem("lorevia-oauth-accepted-terms")
        setUser(user)
        if (user.username) {
          window.sessionStorage.removeItem(PENDING_OAUTH_USER_KEY)
        } else {
          window.sessionStorage.setItem(
            PENDING_OAUTH_USER_KEY,
            JSON.stringify({
              id: user.id,
              email: user.email,
            }),
          )
        }
        setStatus("Redirecting to your workspace...")
        router.replace(user.username ? "/library" : "/complete-username")
      } catch (error) {
        if (axios.isAxiosError(error)) {
          const detail = error.response?.data?.detail
          if (typeof detail === "string" && detail.trim()) {
            fail(normalizeLoginError(detail, error.response?.status) ?? "OAuth sign-in failed.")
            return
          }
          if (error.response?.status && error.response.status >= 500) {
            fail(normalizeLoginError(null, error.response.status) ?? "OAuth sign-in failed.")
            return
          }
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
  }, [router, setUser])

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <p className="text-sm text-gray-500">{status}</p>
    </div>
  )
}
