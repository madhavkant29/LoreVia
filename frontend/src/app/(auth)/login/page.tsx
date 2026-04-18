"use client"
import { Suspense, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useSearchParams } from "next/navigation"
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

function LoginInner() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const searchParams = useSearchParams()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const setUser = useAuthStore(s => s.setUser)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    if (user) router.replace("/library")
  }, [user, router])

  useEffect(() => {
    const oauthError = searchParams.get("error")
    if (oauthError) {
      setError(oauthError)
    }
  }, [searchParams])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true); setError(null)
    try {
      const res = await authApi.login(email, password)
      setAuth(res.access_token, res.refresh_token)
      const me = await authApi.me()
      setUser(me)
      router.push("/library")
    } catch { setError("Invalid email or password") }
    finally { setLoading(false) }
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
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })
  }

  return (
    <div className={`rounded-[2rem] border p-8 shadow-[0_28px_90px_-55px_rgba(15,23,42,0.28)] backdrop-blur ${
      isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/90"
    }`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.26em] ${isDark ? "text-indigo-300" : "text-sky-800"}`}>Welcome back</p>
      <h1 className={`mt-3 font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>Sign in</h1>
      <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
        Return to your library, pick up the thread, and keep reading with your notes, summaries, and character context intact.
      </p>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)}
          className={`rounded-xl border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
            isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500" : "border-stone-300 bg-white text-stone-900 placeholder:text-stone-400"
          }`} required />
        <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
          className={`rounded-xl border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
            isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500" : "border-stone-300 bg-white text-stone-900 placeholder:text-stone-400"
          }`} required />
        <div className="flex justify-end">
          <Link href="/forgot-password" className={`text-xs font-medium hover:underline ${
            isDark ? "text-slate-300 hover:text-white" : "text-stone-700 hover:text-stone-950"
          }`}>
            Forgot password?
          </Link>
        </div>
        {error && (
          <p className={`rounded-xl border px-4 py-3 text-sm ${
            isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"
          }`}>
            {error}
          </p>
        )}
        <button type="submit" disabled={loading}
          className={`rounded-xl py-3 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
            isDark ? "bg-[linear-gradient(135deg,#4f46e5,#4338ca)] hover:opacity-95" : "bg-stone-950 hover:bg-stone-800"
          }`}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className={`w-full border-t ${isDark ? "border-white/10" : "border-stone-200"}`} />
        </div>
        <div className={`relative flex justify-center text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
          <span className={`px-3 uppercase tracking-[0.18em] ${isDark ? "bg-[#081427]" : "bg-white"}`}>or continue with</span>
        </div>
      </div>
      <button
        type="button"
        onClick={signInWithGoogle}
        className={`group flex w-full items-center justify-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium shadow-[0_10px_30px_-22px_rgba(15,23,42,0.35)] transition-all hover:-translate-y-0.5 hover:shadow-[0_18px_34px_-24px_rgba(15,23,42,0.35)] ${
          isDark
            ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
            : "border-stone-200 bg-white text-stone-800 hover:border-stone-300 hover:bg-stone-50"
        }`}
      >
        <span className={`flex h-9 w-9 items-center justify-center rounded-full border shadow-sm transition-colors ${
          isDark ? "border-white/10 bg-white/5 group-hover:bg-white/10" : "border-stone-200 bg-white group-hover:border-stone-300"
        }`}>
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/>
          <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
          <path fill="#FBBC05" d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z"/>
          <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z"/>
          </svg>
        </span>
        <span className="flex flex-col items-start text-left">
          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Google</span>
          <span>Continue with Google</span>
        </span>
      </button>
      <p className={`mt-5 text-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
        No account?{" "}
        <Link href="/register" className={`font-medium hover:underline ${isDark ? "text-white" : "text-stone-900"}`}>Create one</Link>
      </p>
    </div>
  )
}
