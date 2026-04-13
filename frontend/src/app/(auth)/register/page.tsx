"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"
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

export default function RegisterPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const setUser = useAuthStore(s => s.setUser)
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
    setLoading(true); setError(null)
    try {
      const res = await authApi.register(email, password, acceptedTerms)
      setAuth(res.access_token, res.refresh_token)
      const me = await authApi.me()
      setUser(me)
      router.push("/library")
    } catch { setError("Registration failed. Email may already be taken.") }
    finally { setLoading(false) }
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
    <div className="rounded-[2rem] border border-white/80 bg-white/92 p-8 shadow-[0_28px_90px_-55px_rgba(15,23,42,0.28)] backdrop-blur">
      <p className="text-xs font-semibold uppercase tracking-[0.26em] text-amber-700">Create your workspace</p>
      <h1 className="mt-3 font-serif text-4xl text-stone-950">Register</h1>
      <p className="mt-3 text-sm leading-7 text-stone-600">
        Start with the free plan, upload a book, and build a cleaner reading workspace around continuity instead of clutter.
      </p>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)}
          className="rounded-xl border border-stone-300 bg-white px-3 py-3 text-sm text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-900/20" required />
        <div className="space-y-3">
          <input type="password" placeholder="Password (12+ chars recommended)" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full rounded-xl border border-stone-300 bg-white px-3 py-3 text-sm text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-900/20" required minLength={12} />
          <div className="rounded-xl border border-stone-200 bg-stone-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-stone-900">Password quality</p>
                <p className="text-xs text-stone-500">Use a long, unique password you do not reuse anywhere else.</p>
              </div>
              <button
                type="button"
                onClick={() => setPassword(generateStrongPassword())}
                className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:bg-white"
              >
                Generate strong password
              </button>
            </div>
            <div className="mt-4">
              <div className="h-2 overflow-hidden rounded-full bg-stone-200">
                <div
                  className={`${passwordState.color} h-full transition-all`}
                  style={{ width: `${Math.max((passwordState.score / 7) * 100, password ? 12 : 0)}%` }}
                />
              </div>
              <p className="mt-2 text-xs font-medium text-stone-700">{password ? passwordState.label : "Add a password to see a recommendation"}</p>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {passwordState.checks.map((check) => (
                <div key={check.label} className={`rounded-lg px-3 py-2 text-xs ${check.passed ? "bg-emerald-50 text-emerald-700" : "border border-stone-200 bg-white text-stone-500"}`}>
                  {check.label}
                </div>
              ))}
            </div>
          </div>
        </div>
        {error && <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        <label className="flex items-start gap-3 rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-700">
          <input
            type="checkbox"
            checked={acceptedTerms}
            onChange={(e) => setAcceptedTerms(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-stone-300 text-stone-900 focus:ring-stone-900/20"
            required
          />
          <span className="leading-6">
            I agree to the{" "}
            <Link href="/terms" target="_blank" rel="noreferrer" className="font-medium text-stone-900 hover:underline">
              Terms of Service
            </Link>
            {", "}
            <Link href="/compliance" target="_blank" rel="noreferrer" className="font-medium text-stone-900 hover:underline">
              Compliance notice
            </Link>
            {" and "}
            <Link href="/eula" target="_blank" rel="noreferrer" className="font-medium text-stone-900 hover:underline">
              EULA
            </Link>
            .
          </span>
        </label>
        <button type="submit" disabled={loading}
          className="rounded-xl bg-stone-950 py-3 text-sm font-semibold text-white transition-colors hover:bg-stone-800 disabled:opacity-50">
          {loading ? "Creating..." : "Create account"}
        </button>
      </form>
      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-stone-200" />
        </div>
        <div className="relative flex justify-center text-xs text-stone-400">
          <span className="bg-white px-3 uppercase tracking-[0.18em]">or continue with</span>
        </div>
      </div>
      <button
        type="button"
        onClick={signInWithGoogle}
        className="group flex w-full items-center justify-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm font-medium text-stone-800 shadow-[0_10px_30px_-22px_rgba(15,23,42,0.35)] transition-all hover:-translate-y-0.5 hover:border-stone-300 hover:bg-stone-50 hover:shadow-[0_18px_34px_-24px_rgba(15,23,42,0.35)]"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full border border-stone-200 bg-white shadow-sm transition-colors group-hover:border-stone-300">
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/>
          <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
          <path fill="#FBBC05" d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z"/>
          <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z"/>
          </svg>
        </span>
        <span className="flex flex-col items-start text-left">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">Google</span>
          <span>Continue with Google</span>
        </span>
      </button>
      <p className="mt-5 text-center text-sm text-stone-500">
        Have an account? <Link href="/login" className="font-medium text-stone-900 hover:underline">Sign in</Link>
      </p>
    </div>
  )
}
