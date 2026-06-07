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
      // Clear any stale dead-session flag from a previous failed attempt
      // before doing any OAuth work, so new login cookies won't be nuked.
      document.cookie = "lorevia_session_dead=; Max-Age=0; Path=/"
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
          setStatus("Checking your session...")
        }
        let session = (await withTimeout(supabase.auth.getSession(), "Checking your session")).data.session

        if (!session && code) {
          if (active) {
            setStatus("Completing sign-in...")
          }
          const { data, error } = await withTimeout(
            supabase.auth.exchangeCodeForSession(code),
            "Completing sign-in",
          )
          if (error) {
            fail("Could not complete Google sign-in.")
            return
          }
          session = data.session
        }

        if (!session) {
          fail("No session was returned. Please try signing in again.")
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
        document.cookie = "lorevia_session_dead=; Max-Age=0; Path=/"
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
          const status = error.response?.status
          
          console.error("OAuth sign-in failed:", {
            status,
            detail,
            hasSession: !!session,
            email: session?.user?.email,
          })
          
          if (typeof detail === "string" && detail.trim()) {
            fail(normalizeLoginError(detail, status) ?? "OAuth sign-in failed.")
            return
          }
          if (status && status >= 500) {
            fail(normalizeLoginError(null, status) ?? "OAuth sign-in failed.")
            return
          }
        }
        if (error instanceof Error) {
          console.error("OAuth error:", error)
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
