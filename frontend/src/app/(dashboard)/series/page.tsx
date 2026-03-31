"use client"
import { useEffect, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"

export default function SeriesPage() {
  const user = useAuthStore((state) => state.user)
  const { theme } = usePreferencesStore()
  const [books, setBooks] = useState<Book[]>([])
  const isDark = theme === "dark"

  useEffect(() => {
    if (user?.tier === "pro" || user?.tier === "power" || user?.tier === "admin") {
      booksApi.list().then(setBooks).catch(() => {})
    }
  }, [user?.tier])

  if (!user || user.tier === "free") {
    return (
      <div className={`rounded-[2rem] border p-8 ${isDark ? "border-white/10 bg-white/5" : "border-amber-300 bg-amber-50"}`}>
        <h1 className={`text-3xl font-serif ${isDark ? "text-white" : "text-stone-900"}`}>Series Workspace</h1>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-700"}`}>
          Series mode is reserved for paid plans. It is designed for readers moving through multiple books who want earlier volumes to inform the next one without losing continuity.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/85"}`}>
        <h1 className={`text-3xl font-serif ${isDark ? "text-white" : "text-stone-900"}`}>Series Workspace</h1>
        <p className={`mt-3 max-w-2xl text-sm leading-6 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Build a premium multi-book lane for sagas, trilogies, and long-form universes. This area is where cross-book continuity can grow into a real guided reading journey.
        </p>
      </section>
      <div className="grid gap-4 md:grid-cols-2">
        {books.map((book) => (
          <div key={book.id} className={`rounded-[1.75rem] border p-5 shadow-[0_20px_70px_-52px_rgba(15,23,42,0.35)] ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
            <p className={`text-lg font-medium ${isDark ? "text-white" : "text-gray-900"}`}>{book.title}</p>
            {book.author ? <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>{book.author}</p> : null}
            <p className={`mt-3 text-sm ${isDark ? "text-gray-300" : "text-gray-600"}`}>
              Use this title as part of a broader series reading lane when moving from one volume into the next.
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
