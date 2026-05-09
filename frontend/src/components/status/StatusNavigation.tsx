"use client"

import Link from "next/link"
import { useAuthStore } from "@/lib/stores/authStore"

export function StatusNavigation() {
  const { user, hydrated } = useAuthStore()
  const showLibraryLink = hydrated && Boolean(user)

  const linkClass =
    "rounded-full border border-white/10 bg-white/[0.04] px-5 py-2.5 text-sm font-semibold text-white transition hover:border-white/25 hover:bg-white/[0.08] hover:text-white"

  return (
    <div className="mt-8 flex flex-wrap gap-3">
      <Link href="/" className={linkClass}>
        Back to home
      </Link>
      {showLibraryLink ? (
        <Link href="/library" className={linkClass}>
          Go to library
        </Link>
      ) : (
        <Link href="/register" className={linkClass}>
          Sign in or create account
        </Link>
      )}
    </div>
  )
}
