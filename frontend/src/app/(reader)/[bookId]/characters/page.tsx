"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import axios from "axios"
import { booksApi } from "@/lib/api/books"
import { CharacterCard } from "@/components/characters/CharacterCard"
import type { Book } from "@/types/book"
import type { Character } from "@/types/character"

export default function CharactersPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [book, setBook] = useState<Book | null>(null)
  const [chars, setChars] = useState<Character[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const router = useRouter()

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    Promise.all([booksApi.get(bookId), booksApi.getCharacters(bookId)])
      .then(([bookData, characterData]) => {
        if (!active) return
        setBook(bookData)
        setChars(characterData)
      })
      .catch((err) => {
        if (!active) return
        const message = axios.isAxiosError(err) && typeof err.response?.data?.detail === "string"
          ? err.response.data.detail
          : "Could not load characters yet."
        setError(message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [bookId])

  useEffect(() => {
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
  }, [])

  const isDark = theme === "dark"

  return (
    <div className={`min-h-screen transition-colors ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-7xl px-4 pb-24 pt-6 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => router.back()}
            className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}
          >
            {"<- Back"}
          </button>
          <div className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/80 text-stone-600"}`}>
            {chars.length} characters
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-2">
          <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Character index</p>
          <h1 className={`font-serif text-5xl leading-[0.95] tracking-tight sm:text-6xl ${isDark ? "text-white" : "text-stone-950"}`}>People, gathered.</h1>
          <p className={`mt-2 max-w-3xl text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Profiles stay concise and grounded, and in author mode you can correct them before sharing or exporting.
          </p>
        </div>

        {error ? (
          <div className={isDark ? "mt-6 rounded-[1.5rem] border border-red-500/30 bg-red-500/10 p-5 text-sm text-red-200" : "mt-6 rounded-[1.5rem] border border-red-200 bg-red-50 p-5 text-sm text-red-700"}>
            {error}
          </div>
        ) : loading ? (
          <div className={isDark ? "mt-6 rounded-[1.5rem] border border-white/10 bg-white/5 p-5 text-sm text-slate-300" : "mt-6 rounded-[1.5rem] border border-stone-200 bg-white/70 p-5 text-sm text-stone-600"}>
            Loading characters...
          </div>
        ) : chars.length === 0 ? (
          <div className={isDark ? "mt-6 rounded-[1.5rem] border border-white/10 bg-white/5 p-5 text-sm text-slate-300" : "mt-6 rounded-[1.5rem] border border-stone-200 bg-white/70 p-5 text-sm text-stone-600"}>
            No character profiles are ready yet. Processing continues in the background after upload.
          </div>
        ) : null}

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {chars.map((char) => (
            <CharacterCard
              key={char.id}
              character={char}
              bookId={bookId}
              editable={book?.mode === "author"}
              theme={theme}
              onUpdated={(updated) => {
                setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
