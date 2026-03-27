"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const setAuth = useAuthStore(s => s.setAuth)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true); setError(null)
    try {
      const res = await authApi.login(email, password)
      setAuth(res.access_token, res.refresh_token)
      router.push("/library")
    } catch { setError("Invalid email or password") }
    finally { setLoading(false) }
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
      <h1 className="text-2xl font-semibold mb-6">Sign in</h1>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
        <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button type="submit" disabled={loading}
          className="bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
      <p className="text-sm text-gray-500 mt-4 text-center">
        No account? <Link href="/register" className="text-indigo-600 hover:underline">Register</Link>
      </p>
    </div>
  )
}
