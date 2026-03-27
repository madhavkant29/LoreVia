"use client"
import Link from "next/link"
import { useAuthStore } from "@/lib/stores/authStore"

export function Navbar() {
  const { user, logout } = useAuthStore()
  return (
    <nav className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
      <Link href="/library" className="font-semibold text-gray-900">LoreVia</Link>
      <div className="flex items-center gap-4">
        <Link href="/library" className="text-sm text-gray-600 hover:text-gray-900">Library</Link>
        <Link href="/settings" className="text-sm text-gray-600 hover:text-gray-900">Settings</Link>
        {user && <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>}
      </div>
    </nav>
  )
}
