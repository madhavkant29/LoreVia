"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { supabase } from "@/lib/supabase"

function evaluatePassword(password: string, email: string) {
  const lengthScore = password.length >= 16 ? 3 : password.length >= 12 ? 2 : password.length >= 8 ? 1 : 0
  const hasLower = /[a-z]/.test(password)
  const hasUpper = /[A-Z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasSymbol = /[^A-Za-z0-9]/.test(password)
  const varietyScore = [hasLower, hasUpper, hasDigit, hasSymbol].filter(Boolean).length
  const emailLocal = email.split("@")[0]?.toLowerCase()
  const usesEmail = !!emailLocal && emailLocal.length >= 3 && password.toLowerCase().includes(emailLocal)
  const repeatedPattern = /(.)\1{2,}/.test(password)

  let score = lengthScore + varietyScore
  if (usesEmail) score -= 2
  if (repeatedPattern) score -= 1
  score = Math.max(0, Math.min(score, 7))

  const label = score >= 6 ? "Strong" : score >= 4 ? "Good" : score >= 2 ? "Weak" : "Very weak"
  const color = score >= 6 ? "bg-emerald-500" : score >= 4 ? "bg-amber-500" : "bg-rose-500"

  return {
    score,
    label,
    color,
    checks: [
      { label: "12+ characters", passed: password.length >= 12 },
      { label: "Upper + lower case", passed: hasLower && hasUpper },
      { label: "Number included", passed: hasDigit },
      { label: "Symbol included", passed: hasSymbol },
      { label: "Does not use your email", passed: !usesEmail },
    ],
  }
}

function generateStrongPassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*()-_=+?"
  const buffer = new Uint32Array(20)
  crypto.getRandomValues(buffer)
  return Array.from(buffer, (value) => alphabet[value % alphabet.length]).join("")
}

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

export default function RegisterPage() {
  const [email, setEmail] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const user = useAuthStore(s => s.user)
  const setUser = useAuthStore(s => s.setUser)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const passwordState = evaluatePassword(password, email)

  useEffect(() => {
    if (user) router.replace("/library")
  }, [user, router])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!acceptedTerms) {
      setError("Please accept the Terms, Compliance notice, and EULA before creating your account.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await authApi.register(email, username, password, acceptedTerms)
      const me = res.user ?? await authApi.me()
      if (!me) {
        throw new Error("Could not load your profile after creating the account.")
      }
      setUser(me)
      router.push("/library")
    } catch {
      setError("Registration failed. Email may already be taken.")
    } finally {
      setLoading(false)
    }
  }

  const signInWithGoogle = async () => {
    if (!supabase) {
      setError("Google sign-in is not configured right now.")
      return
    }
    if (!acceptedTerms) {
      setError("Please accept the Terms, Compliance notice, and EULA before continuing with Google.")
      return
    }
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem("lorevia-oauth-accepted-terms", "true")
    }
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })
  }

  return (
    <div className={`rounded-[2rem] border p-8 shadow-[0_28px_90px_-55px_rgba(15,23,42,0.28)] backdrop-blur ${
      isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"
    }`}>
      <div className="mb-8 text-center">
        <h1 className={`text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Create account</h1>
        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          Set up your account to start using LoreVia.
        </p>
      </div>

      <button
        type="button"
        onClick={signInWithGoogle}
        className={`mb-6 flex w-full items-center justify-center gap-2.5 rounded-xl border px-4 py-3 text-sm font-medium transition hover:-translate-y-[1px] active:translate-y-0 ${
          isDark
            ? "border-white/10 bg-white/[0.05] text-slate-200 hover:bg-white/[0.09]"
            : "border-stone-200 bg-white text-stone-800 shadow-sm hover:border-stone-300 hover:bg-stone-50"
        }`}
      >
        <GoogleIcon />
        Continue with Google
      </button>

      <div className="relative mb-6 flex items-center">
        <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
        <span className={`px-3 text-[11px] font-medium uppercase tracking-[0.18em] ${isDark ? "text-slate-600" : "text-stone-400"}`}>
          or
        </span>
        <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className={`rounded-xl border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
            isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500" : "border-stone-300 bg-white text-stone-900 placeholder:text-stone-400"
          }`}
          required
        />
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
          className={`rounded-xl border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
            isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500" : "border-stone-300 bg-white text-stone-900 placeholder:text-stone-400"
          }`}
          required
          minLength={3}
          maxLength={32}
        />
        <div className="space-y-3">
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className={`w-full rounded-xl border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
              isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500" : "border-stone-300 bg-white text-stone-900 placeholder:text-stone-400"
            }`}
            required
            minLength={12}
          />
          <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>Password quality</p>
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Use a long, unique password you do not reuse anywhere else.</p>
              </div>
              <button
                type="button"
                onClick={() => setPassword(generateStrongPassword())}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-300 text-stone-700 hover:bg-white"
                }`}
              >
                Generate strong password
              </button>
            </div>
            <div className="mt-4">
              <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
                <div
                  className={`${passwordState.color} h-full transition-all`}
                  style={{ width: `${Math.max((passwordState.score / 7) * 100, password ? 12 : 0)}%` }}
                />
              </div>
              <p className={`mt-2 text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>{password ? passwordState.label : "Add a password to see a recommendation"}</p>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {passwordState.checks.map((check) => (
                <div
                  key={check.label}
                  className={`rounded-lg px-3 py-2 text-xs ${
                    check.passed
                      ? isDark ? "bg-emerald-500/15 text-emerald-200 border border-emerald-500/20" : "bg-emerald-50 text-emerald-700"
                      : isDark ? "border border-white/10 bg-white/5 text-slate-400" : "border border-stone-200 bg-white text-stone-500"
                  }`}
                >
                  {check.label}
                </div>
              ))}
            </div>
          </div>
        </div>
        {error && (
          <p className={`rounded-xl border px-4 py-3 text-sm ${
            isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"
          }`}>
            {error}
          </p>
        )}
        <label className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${
          isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"
        }`}>
          <input
            type="checkbox"
            checked={acceptedTerms}
            onChange={(e) => setAcceptedTerms(e.target.checked)}
            className={`mt-0.5 h-4 w-4 rounded focus:ring-indigo-500 ${
              isDark ? "border-white/20 bg-white/5 text-indigo-400" : "border-stone-300 text-stone-900 focus:ring-stone-900/20"
            }`}
            required
          />
          <span className="leading-6">
            I agree to the{" "}
            <Link href="/terms" target="_blank" rel="noreferrer" className={`font-medium hover:underline ${isDark ? "text-white" : "text-stone-900"}`}>
              Terms of Service
            </Link>
            {", "}
            <Link href="/compliance" target="_blank" rel="noreferrer" className={`font-medium hover:underline ${isDark ? "text-white" : "text-stone-900"}`}>
              Compliance notice
            </Link>
            {" and "}
            <Link href="/eula" target="_blank" rel="noreferrer" className={`font-medium hover:underline ${isDark ? "text-white" : "text-stone-900"}`}>
              EULA
            </Link>
            .
          </span>
        </label>
        <button
          type="submit"
          disabled={loading}
          className={`rounded-xl py-3 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
            isDark ? "bg-[linear-gradient(135deg,#4f46e5,#4338ca)] hover:opacity-95" : "bg-stone-950 hover:bg-stone-800"
          }`}
        >
          {loading ? "Creating..." : "Create account"}
        </button>
      </form>

      <p className={`mt-5 text-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
        Have an account?{" "}
        <Link href="/login" className={`font-medium hover:underline ${isDark ? "text-white" : "text-stone-900"}`}>Sign in</Link>
      </p>
    </div>
  )
}
