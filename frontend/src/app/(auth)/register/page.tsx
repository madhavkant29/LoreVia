"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"

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
    setLoading(true); setError(null)
    try {
      const res = await authApi.register(email, password)
      setAuth(res.access_token, res.refresh_token)
      const me = await authApi.me()
      setUser(me)
      router.push("/library")
    } catch { setError("Registration failed. Email may already be taken.") }
    finally { setLoading(false) }
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
      <h1 className="text-2xl font-semibold mb-6">Create account</h1>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
        <div className="space-y-3">
          <input type="password" placeholder="Password (12+ chars recommended)" value={password} onChange={e => setPassword(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full" required minLength={8} />
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-gray-900">Password strength</p>
                <p className="text-xs text-gray-500">Use a long, unique password you do not reuse anywhere else.</p>
              </div>
              <button
                type="button"
                onClick={() => setPassword(generateStrongPassword())}
                className="rounded-full border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-white"
              >
                Generate strong password
              </button>
            </div>
            <div className="mt-4">
              <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                <div
                  className={`${passwordState.color} h-full transition-all`}
                  style={{ width: `${Math.max((passwordState.score / 7) * 100, password ? 12 : 0)}%` }}
                />
              </div>
              <p className="mt-2 text-xs font-medium text-gray-700">{password ? passwordState.label : "Add a password to see a recommendation"}</p>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {passwordState.checks.map((check) => (
                <div key={check.label} className={`rounded-lg px-3 py-2 text-xs ${check.passed ? "bg-emerald-50 text-emerald-700" : "bg-white text-gray-500 border border-gray-200"}`}>
                  {check.label}
                </div>
              ))}
            </div>
          </div>
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button type="submit" disabled={loading}
          className="bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          {loading ? "Creating..." : "Create account"}
        </button>
      </form>
      <p className="text-sm text-gray-500 mt-4 text-center">
        Have an account? <Link href="/login" className="text-indigo-600 hover:underline">Sign in</Link>
      </p>
    </div>
  )
}
