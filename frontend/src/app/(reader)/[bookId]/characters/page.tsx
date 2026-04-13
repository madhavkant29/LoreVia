"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import axios from "axios"
import { booksApi } from "@/lib/api/books"
import type { Character } from "@/types/character"
import { CharacterCard } from "@/components/characters/CharacterCard"

export default function CharactersPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [chars, setChars] = useState<Character[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const router = useRouter()

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    booksApi.getCharacters(bookId)
      .then((data) => {
        if (!active) return
        setChars(data)
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

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-white text-black"}`}>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white" : "text-sm text-gray-400 hover:text-gray-600"}>{"<- Back"}</button>
          <h1 className="text-2xl font-semibold">Characters ({chars.length})</h1>
        </div>
        {error ? (
          <div className={theme === "dark" ? "rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200" : "rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"}>
            {error}
          </div>
        ) : loading ? (
          <div className={theme === "dark" ? "rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-gray-300" : "rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600"}>
            Loading characters...
          </div>
        ) : chars.length === 0 ? (
          <div className={theme === "dark" ? "rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-gray-300" : "rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600"}>
            No character profiles are ready yet. Processing continues in the background after upload.
          </div>
        ) : null}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {chars.map(char => (
            <CharacterCard key={char.id} character={char} theme={theme} />
          ))}
        </div>
      </div>
    </div>
  )
}
