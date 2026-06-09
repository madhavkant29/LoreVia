"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { AuthLink } from "@/components/auth/AuthLink"
import { GoogleOAuthButton } from "@/components/auth/GoogleOAuthButton"
import { authApi } from "@/lib/api/auth"
import { validateRegisterPassword, validateRegisterUsername } from "@/lib/auth/registerValidation"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { getOrCreateDeviceId } from "@/lib/utils/device"

function generateStrongPassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*()-_=+?"
  const buffer = new Uint32Array(20)
  crypto.getRandomValues(buffer)
  return Array.from(buffer, (value) => alphabet[value % alphabet.length]).join("")
}

export default function RegisterPage() {
  const [email, setEmail] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [validatingSession, setValidatingSession] = useState(false)
  const router = useRouter()
  const user = useAuthStore(s => s.user)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    // Verify session is actually valid before redirecting to prevent
    // issues with stale cached user data causing unwanted redirects
    if (user) {
      setValidatingSession(true)
      authApi.me()
        .then((validUser) => {
          if (validUser) {
            router.replace("/library")
          } else {
            // Session expired, clear stale user and set marker for middleware
            document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
            useAuthStore.getState().logout()
            setValidatingSession(false)
          }
        })
        .catch(() => {
          // Session invalid, clear stale user and set marker for middleware
          document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
          useAuthStore.getState().logout()
          setValidatingSession(false)
        })
    }
  }, [user, router])

  // Show loading state while validating existing session
  if (validatingSession) {
    return (
      <div className={`rounded-lg border p-8 ${
        isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"
      }`}>
        <div className="flex items-center justify-center py-12">
          <div className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Checking session...
          </div>
        </div>
      </div>
    )
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()

    const trimmedEmail = email.trim()
    const trimmedUsername = username.trim()
    const usernameError = validateRegisterUsername(trimmedUsername)
    if (usernameError) {
      setError(usernameError)
      return
    }

    const passwordValidation = validateRegisterPassword(password, trimmedEmail)
    if (!passwordValidation.isValid) {
      setError(passwordValidation.message)
      return
    }

    if (!acceptedTerms) {
      setError("Please accept the Terms, Compliance notice, and EULA before creating your account.")
      return
    }

    setLoading(true)
    setError(null)
    try {
      const result = await authApi.register(trimmedEmail, trimmedUsername, password, acceptedTerms, getOrCreateDeviceId())
      if (!result?.email) {
        setError("Could not create your account. Please try again.")
        return
      }
      router.push(`/verify-email?email=${encodeURIComponent(result.email)}`)
    } catch (error: unknown) {
      if (typeof error === "object" && error && "response" in error) {
        const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
        if (typeof detail === "string" && detail.trim()) {
          setError(detail)
          return
        }
      }
      setError("Registration failed. Email may already be taken.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`rounded-lg border p-8 ${
      isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"
    }`}>
      <div className="mb-8 text-center">
        <h1 className={`text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Create account</h1>
        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          Set up your LoreVia for authors account, then verify your email before opening your manuscript workspace.
        </p>
      </div>

      <GoogleOAuthButton
        acceptedTerms={acceptedTerms}
        className="mb-6"
        requireAcceptedTerms
        onError={setError}
      />

      <div className="relative mb-6 flex items-center">
        <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
        <span className={`px-3 text-3xs font-medium uppercase tracking-[0.18em] ${isDark ? "text-slate-600" : "text-stone-400"}`}>
          or
        </span>
        <div className={`h-px flex-1 ${isDark ? "bg-white/[0.07]" : "bg-stone-200"}`} />
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Email</span>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className={`rounded-md border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-700/30 ${
              isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-300 bg-white text-stone-900"
            }`}
            required
            autoComplete="email"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Username</span>
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            className={`rounded-md border px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-700/30 ${
              isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-300 bg-white text-stone-900"
            }`}
            required
            minLength={3}
            maxLength={32}
            autoComplete="username"
          />
        </label>
        <div className="space-y-3">
          <label className="flex flex-col gap-1.5">
            <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Password</span>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className={`w-full rounded-md border px-3 py-3 pr-20 text-sm focus:outline-none focus:ring-2 focus:ring-teal-700/30 ${
                  isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-300 bg-white text-stone-900"
                }`}
                required
                minLength={12}
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                className={`absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium transition ${
                  isDark ? "text-slate-300 hover:text-white" : "text-stone-500 hover:text-stone-900"
                }`}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setPassword(generateStrongPassword())}
              className={`rounded-md border px-3 py-1.5 text-xs font-medium transition ${
                isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-300 bg-white text-stone-700 hover:bg-stone-50"
              }`}
            >
              Generate strong password
            </button>
          </div>
        </div>
        {error && (
          <p className={`rounded-md border px-4 py-3 text-sm ${
            isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"
          }`}>
            {error}
          </p>
        )}
        <label className={`flex items-start gap-3 rounded-md border px-4 py-3 text-sm ${
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
            <span className={`mt-2 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              LoreVia uses a device identifier to help prevent fake or abusive repeat signups and may limit account creation to two accounts per device.
            </span>
          </span>
        </label>
        <button
          type="submit"
          disabled={loading}
          className={`rounded-md py-3 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
            isDark ? "bg-[#1f615d] hover:bg-[#174c49]" : "bg-stone-950 hover:bg-stone-800"
          }`}
        >
          {loading ? "Creating..." : "Create account"}
        </button>
      </form>

      <p className={`mt-5 text-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
        Have an account?{" "}
        <AuthLink href="/login" className={`font-medium hover:underline ${isDark ? "text-white" : "text-stone-900"}`}>
          Sign in
        </AuthLink>
      </p>
    </div>
  )
}
