"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import axios from "axios"

import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const PENDING_OAUTH_USER_KEY = "lorevia-pending-oauth-user"

export default function CompleteUsernamePage() {
  const router = useRouter()
  const user = useAuthStore((state) => state.user)
  const setUser = useAuthStore((state) => state.setUser)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [username, setUsername] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [checkingSession, setCheckingSession] = useState(false)

  useEffect(() => {
    if (!user) {
      const pendingUser = typeof window !== "undefined" ? window.sessionStorage.getItem(PENDING_OAUTH_USER_KEY) : null
      setCheckingSession(true)
      void authApi.me().then((me) => {
        if (!me) {
          if (!pendingUser) {
            router.replace("/login")
            return
          }
          setError("Finish choosing a username to complete Google sign-in. If this page refreshes again, start from Google sign-in once more.")
          return
        }
        setUser(me)
        if (me.username) {
          router.replace("/library")
        }
      }).catch(() => {
        if (!pendingUser) {
          router.replace("/login")
          return
        }
        setError("Finish choosing a username to complete Google sign-in. If this page refreshes again, start from Google sign-in once more.")
      }).finally(() => {
        setCheckingSession(false)
      })
      return
    }

    if (user.username) {
      router.replace("/library")
    }
  }, [router, setUser, user])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedUsername = username.trim()

    if (!trimmedUsername) {
      setError("Username is required to continue.")
      return
    }

    setLoading(true)
    setError(null)
    try {
      const updatedUser = await authApi.setUsername(trimmedUsername)
      if (typeof window !== "undefined") {
        window.sessionStorage.removeItem(PENDING_OAUTH_USER_KEY)
      }
      setUser(updatedUser)
      router.replace("/library")
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail
        if (typeof detail === "string" && detail.trim()) {
          setError(detail)
          return
        }
      }
      setError("That username is unavailable or invalid.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className={`rounded-lg border p-8 ${
        isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"
      }`}
    >
      <div className="mb-8 text-center">
        <h1 className={`text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Choose a username</h1>
        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          OAuth accounts need a username before you can continue.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Username</span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            minLength={3}
            maxLength={32}
            required
            className={`rounded-md border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-700/30 ${
              isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-300 bg-white text-stone-900"
            }`}
          />
        </label>

        {checkingSession && !error ? (
          <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Reconnecting your session...
          </p>
        ) : null}

        {error && (
          <p
            className={`rounded-md border px-4 py-3 text-sm ${
              isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className={`rounded-md py-3 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
            isDark ? "bg-[#1f615d] hover:bg-[#174c49]" : "bg-stone-950 hover:bg-stone-800"
          }`}
        >
          {loading ? "Saving..." : "Continue"}
        </button>
      </form>
    </div>
  )
}
