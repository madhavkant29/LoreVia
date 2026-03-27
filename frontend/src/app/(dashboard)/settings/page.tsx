"use client"
import { useAuthStore } from "@/lib/stores/authStore"
import { authApi } from "@/lib/api/auth"

const MODES = [
  { value: "casual", label: "Casual", desc: "Quick summaries, essential context" },
  { value: "analyst", label: "Analyst", desc: "Deep breakdowns, full analysis" },
  { value: "speed", label: "Speed", desc: "Key points only, minimal detail" },
]

export default function SettingsPage() {
  const { user, setUser, logout } = useAuthStore()

  const changeMode = async (mode: string) => {
    await authApi.setReadingMode(mode)
    if (user) setUser({ ...user, reading_mode: mode as any })
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-semibold mb-8">Settings</h1>
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <h2 className="font-medium mb-1">Account</h2>
        <p className="text-sm text-gray-600 mb-1">Email: <span className="font-medium">{user?.email}</span></p>
        <p className="text-sm text-gray-600">Plan: <span className="font-medium capitalize">{user?.tier ?? "free"}</span></p>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <h2 className="font-medium mb-3">Reading Mode</h2>
        <div className="flex flex-col gap-2">
          {MODES.map(m => (
            <button key={m.value} onClick={() => changeMode(m.value)}
              className={`text-left px-4 py-3 rounded-lg border transition-colors ${
                user?.reading_mode === m.value
                  ? "border-indigo-500 bg-indigo-50"
                  : "border-gray-200 hover:border-gray-300"
              }`}>
              <p className="font-medium text-sm">{m.label}</p>
              <p className="text-xs text-gray-500">{m.desc}</p>
            </button>
          ))}
        </div>
      </div>
      <button onClick={logout} className="text-sm text-red-500 hover:text-red-700 transition-colors">
        Sign out
      </button>
    </div>
  )
}
