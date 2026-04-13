"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { authApi } from "@/lib/api/auth"

export default function ResetPasswordPage() {
  const params = useParams<{ token: string }>()
  const router = useRouter()
  const token = useMemo(() => Array.isArray(params?.token) ? params.token[0] : params?.token ?? "", [params])
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirmPassword) {
      setError("Passwords do not match.")
      return
    }
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      await authApi.resetPassword(token, password)
      setMessage("Password updated. Redirecting you to sign in...")
      window.setTimeout(() => router.push("/login"), 1200)
    } catch {
      setError("This reset link is invalid or expired.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
      <h1 className="mb-2 text-2xl font-semibold">Choose a new password</h1>
      <p className="mb-6 text-sm text-gray-500">
        Pick a strong password you do not reuse anywhere else.
      </p>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <input
          type="password"
          placeholder="New password"
          value={password}
          minLength={8}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <input
          type="password"
          placeholder="Confirm password"
          value={confirmPassword}
          minLength={8}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          className="rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {error ? <p className="text-sm text-red-500">{error}</p> : null}
        {message ? <p className="text-sm text-gray-600">{message}</p> : null}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "Saving..." : "Update password"}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-gray-500">
        Back to <Link href="/login" className="text-indigo-600 hover:underline">sign in</Link>
      </p>
    </div>
  )
}
