"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { supabase } from "@/lib/supabase"

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  )
}

// ─── Google Icon ──────────────────────────────────────────────────────────────

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true" className="shrink-0">
      <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" />
      <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z" />
    </svg>
  )
}

// ─── Inner login form ─────────────────────────────────────────────────────────

function LoginInner() {
  const [email, setEmail]       = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  const router       = useRouter()
  const searchParams = useSearchParams()
  const user         = useAuthStore((s) => s.user)
  const setAuth      = useAuthStore((s) => s.setAuth)
  const setUser      = useAuthStore((s) => s.setUser)
  const { theme }    = usePreferencesStore()
  const isDark       = theme === "dark"

  useEffect(() => {
    if (user) router.replace("/library")
  }, [user, router])

  useEffect(() => {
    const oauthError = searchParams.get("error")
    if (oauthError) setError(oauthError)
  }, [searchParams])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await authApi.login(email, password)
      setAuth(res.access_token, res.refresh_token)
      const me = await authApi.me()
      setUser(me)
      router.push("/library")
    } catch {
      setError("Invalid email or password.")
    } finally {
      setLoading(false)
    }
  }

  const signInWithGoogle = async () => {
    if (!supabase) {
      setError("Google sign-in is not configured right now.")
      return
    }
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem("lorevia-oauth-accepted-terms", "false")
    }
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
  }

  // ── Shared input class ──────────────────────────────────────────────────────
  const inputCls = [
    "w-full rounded-xl border px-4 py-3 text-sm transition-colors",
    "focus:outline-none focus:ring-2 focus:ring-offset-0",
    isDark
      ? "border-white/[0.08] bg-white/[0.04] text-slate-100 placeholder:text-slate-600 focus:border-white/20 focus:ring-white/10"
      : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400 focus:border-stone-300 focus:ring-stone-100",
  ].join(" ")

  return (
    /*
     * Full-viewport centered shell — same structure as the landing page main.
     * Uses the same background gradient so the page feels native to the brand.
     */
    <main
      className={`relative flex min-h-screen items-center justify-center px-4 py-16 ${
        isDark
          ? "bg-[linear-gradient(180deg,#000000_0%,#050505_60%,#0b0b0b_100%)] text-slate-100"
          : "bg-[linear-gradient(180deg,#fbf7ef_0%,#f7f2eb_60%,#f3efe9_100%)] text-stone-950"
      }`}
    >
      {/* Noise grain — matches landing page */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[9999] opacity-[0.032]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          backgroundRepeat: "repeat",
          backgroundSize: "200px 200px",
        }}
      />

      {/* Ambient glow behind the card */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className={`absolute top-0 left-1/2 -translate-x-1/2 h-[500px] w-[700px] rounded-full blur-[120px] ${
            isDark ? "opacity-[0.12] bg-violet-600" : "opacity-[0.16] bg-violet-300"
          }`}
        />
      </div>

      {/* Card */}
      <div className="relative z-10 w-full max-w-[400px]">

        {/* Logo */}
        <div className="mb-10 flex justify-center">
          <Link href="/">
            <img src="/logoandtext.png" alt="LoreVia" className="h-9 w-auto opacity-90 hover:opacity-100 transition-opacity" />
          </Link>
        </div>

        {/* Heading */}
        <div className="mb-8 text-center">
          <h1 className={`font-serif text-[2.4rem] leading-tight tracking-[-0.02em] ${isDark ? "text-white" : "text-stone-950"}`}>
            Welcome back
          </h1>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Sign in to continue to your library
          </p>
        </div>

        {/* Google button — primary option, shown first */}
        <button
          type="button"
          onClick={signInWithGoogle}
          className={`flex w-full items-center justify-center gap-2.5 rounded-xl border px-4 py-3 text-sm font-medium transition hover:-translate-y-[1px] active:translate-y-0 ${
            isDark
              ? "border-white/10 bg-white/[0.05] text-slate-200 hover:bg-white/[0.09]"
              : "border-stone-200 bg-white text-stone-800 shadow-sm hover:border-stone-300 hover:bg-stone-50"
          }`}
        >
          <GoogleIcon />
          Continue with Google
        </button>

        {/* Divider */}
        <div className="relative my-6 flex items-center">
          <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
          <span className={`px-3 text-[11px] font-medium uppercase tracking-[0.18em] ${isDark ? "text-slate-600" : "text-stone-400"}`}>
            or
          </span>
          <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
        </div>

        {/* Email / password form */}
        <form onSubmit={submit} className="flex flex-col gap-3">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls}
            required
            autoComplete="email"
          />

          <div className="flex flex-col gap-1.5">
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputCls}
              required
              autoComplete="current-password"
            />
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

          {/* Error */}
          {error && (
            <p className={`rounded-xl border px-4 py-3 text-sm ${
              isDark
                ? "border-rose-500/25 bg-rose-500/[0.08] text-rose-300"
                : "border-rose-200 bg-rose-50 text-rose-600"
            }`}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className={`mt-1 rounded-xl py-3 text-sm font-semibold transition hover:-translate-y-[1px] active:translate-y-0 disabled:pointer-events-none disabled:opacity-40 ${
              isDark
                ? "bg-white text-black hover:bg-stone-100"
                : "bg-stone-950 text-white hover:bg-stone-800"
            }`}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {/* Footer */}
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