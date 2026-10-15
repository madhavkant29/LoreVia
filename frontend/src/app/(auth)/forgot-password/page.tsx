"use client"

import Link from "next/link"
import { useState } from "react"

import { authApi } from "@/lib/api/auth"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function ForgotPasswordPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = email.trim()
    if (!trimmed) return
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      await authApi.forgotPassword(trimmed)
      setMessage("If an account exists for that email, a reset link has been sent.")
    } catch {
      setError("Could not start password reset. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <form onSubmit={submit} className={`border-y py-8 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <p className={`text-sm font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>Account recovery</p>
        <h1 className="mt-2 text-3xl font-semibold">Reset your password</h1>
        <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
          Enter the email for your LoreVia account and we will send a reset link if the account exists.
        </p>

        <label className="mt-6 block space-y-2">
          <span className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>Email</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            className={`w-full rounded-md border px-4 py-3 text-sm outline-none ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-stone-50 text-stone-950"}`}
          />
        </label>

        {message ? <p className={`mt-4 border-l-2 px-4 py-2 text-sm ${isDark ? "border-emerald-400 text-emerald-300" : "border-emerald-700 text-emerald-700"}`}>{message}</p> : null}
        {error ? <p className={`mt-4 border-l-2 px-4 py-2 text-sm ${isDark ? "border-rose-400 text-rose-300" : "border-rose-700 text-rose-700"}`}>{error}</p> : null}

        <button type="submit" disabled={loading || !email.trim()} className={`mt-6 w-full rounded-md px-4 py-3 text-sm font-semibold disabled:opacity-50 ${isDark ? "bg-white text-stone-950" : "bg-stone-950 text-white"}`}>
          {loading ? "Sending..." : "Send reset link"}
        </button>
        <Link href="/login" className={`mt-4 block text-center text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>
          Back to login
        </Link>
      </form>
    </main>
  )
}
