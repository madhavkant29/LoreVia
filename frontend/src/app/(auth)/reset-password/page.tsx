"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { authApi } from "@/lib/api/auth"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

function ResetPasswordInner() {
  const params = useSearchParams()
  const token = params.get("token") ?? ""
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!token || !password) return
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      await authApi.resetPassword(token, password)
      setMessage("Password updated. You can sign in with the new password now.")
      setPassword("")
    } catch {
      setError("Could not reset password. The link may be expired or the password may not meet requirements.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <form onSubmit={submit} className={`border-y py-8 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <p className={`text-sm font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>Account recovery</p>
        <h1 className="mt-2 text-3xl font-semibold">Choose a new password</h1>
        <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
          Use at least 12 characters with upper and lower case letters, a number, and a symbol.
        </p>

        <label className="mt-6 block space-y-2">
          <span className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>New password</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            className={`w-full rounded-md border px-4 py-3 text-sm outline-none ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-stone-50 text-stone-950"}`}
          />
        </label>

        {!token ? <p className={`mt-4 border-l-2 px-4 py-2 text-sm ${isDark ? "border-rose-400 text-rose-300" : "border-rose-700 text-rose-700"}`}>This reset link is missing a token.</p> : null}
        {message ? <p className={`mt-4 border-l-2 px-4 py-2 text-sm ${isDark ? "border-emerald-400 text-emerald-300" : "border-emerald-700 text-emerald-700"}`}>{message}</p> : null}
        {error ? <p className={`mt-4 border-l-2 px-4 py-2 text-sm ${isDark ? "border-rose-400 text-rose-300" : "border-rose-700 text-rose-700"}`}>{error}</p> : null}

        <button type="submit" disabled={loading || !token || !password} className={`mt-6 w-full rounded-md px-4 py-3 text-sm font-semibold disabled:opacity-50 ${isDark ? "bg-white text-stone-950" : "bg-stone-950 text-white"}`}>
          {loading ? "Updating..." : "Update password"}
        </button>
        <Link href="/login" className={`mt-4 block text-center text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>
          Back to login
        </Link>
      </form>
    </main>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordInner />
    </Suspense>
  )
}
