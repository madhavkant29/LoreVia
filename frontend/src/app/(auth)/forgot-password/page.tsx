"use client"

import { useState } from "react"
import Link from "next/link"
import { authApi } from "@/lib/api/auth"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [resetUrl, setResetUrl] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    setResetUrl(null)
    try {
      const response = await authApi.forgotPassword(email) as { message?: string; reset_url?: string; delivered?: boolean }
      setMessage(response?.message ?? "If that email exists, we just sent a reset link.")
      if (response?.reset_url) {
        setResetUrl(response.reset_url)
      }
    } catch {
      setMessage("If that email exists, we just sent a reset link.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
      <h1 className="mb-2 text-2xl font-semibold">Reset your password</h1>
      <p className="mb-6 text-sm text-gray-500">
        Enter your email and we&apos;ll send you a secure reset link.
      </p>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {message ? <p className="text-sm text-gray-600">{message}</p> : null}
        {resetUrl ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">Local reset link</p>
            <a href={resetUrl} className="mt-1 block break-all text-indigo-600 underline hover:text-indigo-700">
              {resetUrl}
            </a>
          </div>
        ) : null}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "Sending..." : "Send reset link"}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-gray-500">
        Back to <Link href="/login" className="text-indigo-600 hover:underline">sign in</Link>
      </p>
    </div>
  )
}
