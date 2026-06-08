"use client"

import { Suspense, useEffect, useState } from "react"
import type { Route } from "next"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import axios from "axios"
import { GoogleOAuthButton } from "@/components/auth/GoogleOAuthButton"
import { authApi } from "@/lib/api/auth"
import { normalizeLoginError, shouldShowCreateAccountCta } from "@/lib/auth/loginMessages"
import { resolveSafeAuthNextPath } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { getOrCreateDeviceId } from "@/lib/utils/device"

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  )
}

function LoginInner() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [validatingSession, setValidatingSession] = useState(false)

  const router = useRouter()
  const searchParams = useSearchParams()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    // Verify session is actually valid before redirecting to prevent
    // issues with stale cached user data causing unwanted redirects
    if (user) {
      setValidatingSession(true)
      authApi.me()
        .then((validUser) => {
          if (validUser) {
            router.replace("/library")
          } else {
            // Session expired, clear stale user
            useAuthStore.getState().logout()
            setValidatingSession(false)
          }
        })
        .catch(() => {
          // Session invalid, clear stale user
          useAuthStore.getState().logout()
          setValidatingSession(false)
        })
    }
  }, [user, router])

  useEffect(() => {
    const oauthError = searchParams.get("error")
    if (oauthError) {
      setError(normalizeLoginError(oauthError))
      router.replace("/login")
    }
  }, [router, searchParams])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const user = await authApi.login(email, password, getOrCreateDeviceId())
      if (!user) {
        setError("Could not load your account. Please try again.")
        return
      }
      document.cookie = "lorevia_session_dead=; Max-Age=0; Path=/"
      setUser(user)
      router.push(resolveSafeAuthNextPath(searchParams.get("next")) as Route)
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail
        if (error.response?.status === 401) {
          setError(normalizeLoginError(typeof detail === "string" ? detail : null, 401))
          return
        }
        if (typeof detail === "string" && detail.trim()) {
          setError(normalizeLoginError(detail, error.response?.status))
          return
        }
        if (error.response?.status && error.response.status >= 500) {
          setError(normalizeLoginError(null, error.response.status))
          return
        }
      }
      setError("Could not sign you in right now. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  const inputCls = [
    "w-full rounded-md border px-4 py-3 text-sm transition-colors",
    "focus:outline-none focus:ring-2 focus:ring-offset-0",
    isDark
      ? "border-white/[0.08] bg-white/[0.04] text-slate-100 focus:border-white/20 focus:ring-white/10"
      : "border-stone-200 bg-white text-stone-900 focus:border-stone-300 focus:ring-stone-100",
  ].join(" ")

  // Show loading state while validating existing session
  if (validatingSession) {
    return (
      <main>
        <div className={`rounded-lg border p-8 ${
          isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"
        }`}>
          <div className="flex items-center justify-center py-12">
            <div className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Checking session...
            </div>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main>
      <div className={`rounded-lg border p-8 ${
        isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"
      }`}>
        <div className="mb-8 text-center">
          <h1 className={`text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Sign in</h1>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Enter your email and password to return to your author workspace.
          </p>
        </div>

        <GoogleOAuthButton onError={setError} />
        <p className={`mt-2 text-center text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
          First time with Google? Use <Link href="/register" className="font-medium underline-offset-2 hover:underline">Create one</Link> so you can accept the required terms first.
        </p>

        <div className="relative my-6 flex items-center">
          <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
          <span className={`px-3 text-3xs font-medium uppercase tracking-[0.18em] ${isDark ? "text-slate-600" : "text-stone-400"}`}>
            or
          </span>
          <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls}
              required
              autoComplete="email"
            />
          </label>

          <div className="flex flex-col gap-1.5">
            <label className="flex flex-col gap-1.5">
              <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputCls}
                required
                autoComplete="current-password"
              />
            </label>
            <div className="flex justify-end">
              <Link
                href="/forgot-password"
                className={`text-xs font-medium transition hover:underline ${
                  isDark ? "text-slate-500 hover:text-slate-300" : "text-stone-400 hover:text-stone-700"
                }`}
              >
                Forgot password?
              </Link>
            </div>
          </div>

          {error && (
            <div className={`rounded-md border px-4 py-3 text-sm ${
              isDark
                ? "border-rose-500/25 bg-rose-500/[0.08] text-rose-300"
                : "border-rose-200 bg-rose-50 text-rose-600"
            }`}>
              <p>{error}</p>
              {error.toLowerCase().includes("verify your email") && email ? (
                <Link
                  href={`/verify-email?email=${encodeURIComponent(email)}`}
                  className={`mt-2 inline-flex font-medium underline-offset-2 hover:underline ${
                    isDark ? "text-rose-200" : "text-rose-700"
                  }`}
                >
                  Resend verification email
                </Link>
              ) : null}
              {shouldShowCreateAccountCta(error) ? (
                <Link
                  href="/register"
                  className={`mt-2 inline-flex font-medium underline-offset-2 hover:underline ${
                    isDark ? "text-rose-200" : "text-rose-700"
                  }`}
                >
                  Go to Create one
                </Link>
              ) : null}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className={`mt-1 rounded-md py-3 text-sm font-semibold transition disabled:pointer-events-none disabled:opacity-40 ${
              isDark
                ? "bg-white text-black hover:bg-stone-100"
                : "bg-stone-950 text-white hover:bg-stone-800"
            }`}
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className={`mt-7 text-center text-sm ${isDark ? "text-slate-500" : "text-stone-400"}`}>
          No account?{" "}
          <Link
            href="/register"
            className={`font-medium transition hover:underline ${
              isDark ? "text-slate-200 hover:text-white" : "text-stone-700 hover:text-stone-950"
            }`}
          >
            Create one
          </Link>
        </p>
      </div>
    </main>
  )
}
