"use client"

import Link from "next/link"
import { Suspense, useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailInner />
    </Suspense>
  )
}

function VerifyEmailInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((state) => state.setUser)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const email = useMemo(() => searchParams.get("email") ?? "", [searchParams])
  const token = useMemo(() => searchParams.get("token") ?? "", [searchParams])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [resending, setResending] = useState(false)

  useEffect(() => {
    if (!token) return

    let active = true
    const runVerification = async () => {
      setVerifying(true)
      setError(null)
      try {
        const user = await authApi.verifyEmail(token)
        if (!active) return
        setUser(user)
        router.replace(user.username ? "/library" : "/complete-username")
      } catch (err: unknown) {
        if (!active) return
        if (typeof err === "object" && err && "response" in err) {
          const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          if (typeof detail === "string" && detail.trim()) {
            setError(detail)
          } else {
            setError("Could not verify your email.")
          }
        } else {
          setError("Could not verify your email.")
        }
      } finally {
        if (active) {
          setVerifying(false)
        }
      }
    }

    runVerification()
    return () => {
      active = false
    }
  }, [router, setUser, token])

  const resend = async () => {
    if (!email) {
      setError("Add your email to resend the verification link.")
      return
    }
    setResending(true)
    setError(null)
    setMessage(null)
    try {
      await authApi.resendVerification(email)
      setMessage("If that account exists and still needs verification, we sent a fresh email.")
    } catch {
      setError("Could not resend the verification email right now.")
    } finally {
      setResending(false)
    }
  }

  return (
    <main>
      <div className={`border-y py-8 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div className="mb-6">
          <h1 className={`text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Verify your email</h1>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            {token
              ? "We're confirming your email now."
              : email
                ? `We sent a verification link to ${email}.`
                : "Check your inbox for the verification link we sent after signup."}
          </p>
        </div>

        {verifying ? (
          <p className={`rounded-md border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
            Verifying your email...
          </p>
        ) : null}

        {message ? (
          <p className={`rounded-md border px-4 py-3 text-sm ${isDark ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
            {message}
          </p>
        ) : null}

        {error ? (
          <p className={`rounded-md border px-4 py-3 text-sm ${isDark ? "border-rose-500/25 bg-rose-500/[0.08] text-rose-300" : "border-rose-200 bg-rose-50 text-rose-600"}`}>
            {error}
          </p>
        ) : null}

        <div className="mt-6 flex flex-col gap-3">
          <button
            type="button"
            onClick={resend}
            disabled={resending || verifying}
            className={`rounded-md py-3 text-sm font-semibold transition disabled:pointer-events-none disabled:opacity-40 ${
              isDark ? "bg-white text-black hover:bg-stone-100" : "bg-stone-950 text-white hover:bg-stone-800"
            }`}
          >
            {resending ? "Sending..." : "Resend verification email"}
          </button>

          <Link
            href="/login"
            className={`text-center text-sm font-medium transition hover:underline ${
              isDark ? "text-slate-300" : "text-stone-700"
            }`}
          >
            Back to sign in
          </Link>
        </div>
      </div>
    </main>
  )
}
