"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
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
  const [search, setSearch] = useState("")
  const [primaryMergeId, setPrimaryMergeId] = useState("")
  const [secondaryMergeId, setSecondaryMergeId] = useState("")
  const [mergeBusy, setMergeBusy] = useState(false)
  const [mergeError, setMergeError] = useState<string | null>(null)
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
        setError("Could not load characters yet.")
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
  const isAuthorMode = book?.mode === "author"
  const normalizedSearch = search.trim().toLowerCase()
  const filteredChars = chars.filter((char) => {
    if (!normalizedSearch) return true
    const haystack = [
      char.name,
      ...(char.aliases ?? []),
      char.description ?? "",
      char.arc_summary ?? "",
    ]
      .join(" ")
      .toLowerCase()
    return haystack.includes(normalizedSearch)
  })

  async function handleMergeCharacters() {
    if (!primaryMergeId || !secondaryMergeId || primaryMergeId === secondaryMergeId) {
      setMergeError("Choose two different characters to merge.")
      return
    }
    setMergeBusy(true)
    setMergeError(null)
    try {
      const response = await booksApi.mergeCharacters(bookId, {
        primaryId: primaryMergeId,
        secondaryId: secondaryMergeId,
      })
      const refreshed = await booksApi.getCharacters(bookId)
      setChars(refreshed)
      setPrimaryMergeId(response.merged)
      setSecondaryMergeId("")
    } catch {
      setMergeError("Could not merge those characters.")
    } finally {
      setMergeBusy(false)
    }
  }

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

        <div className={`mt-6 rounded-[1.5rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex-1">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Find characters</p>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by name, alias, or profile text"
                className={`mt-2 w-full rounded-xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
              />
            </div>
            {isAuthorMode ? (
              <div className="w-full lg:max-w-3xl">
                <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Correction studio</p>
                <div className="mt-2 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                  <select
                    value={primaryMergeId}
                    onChange={(event) => setPrimaryMergeId(event.target.value)}
                    className={`rounded-xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  >
                    <option value="">Choose primary character</option>
                    {chars.map((char) => (
                      <option key={char.id} value={char.id}>{char.name}</option>
                    ))}
                  </select>
                  <select
                    value={secondaryMergeId}
                    onChange={(event) => setSecondaryMergeId(event.target.value)}
                    className={`rounded-xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  >
                    <option value="">Choose duplicate to merge into it</option>
                    {chars.map((char) => (
                      <option key={char.id} value={char.id}>{char.name}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => void handleMergeCharacters()}
                    disabled={mergeBusy}
                    className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-60"
                  >
                    {mergeBusy ? "Merging..." : "Merge"}
                  </button>
                </div>
                <p className={`mt-2 text-xs leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  Use the card editor to rename characters or fix aliases. Use merge when two extracted profiles are really the same person. Use delete on the card for false positives.
                </p>
                {mergeError ? <p className="mt-2 text-sm text-red-500">{mergeError}</p> : null}
              </div>
            ) : null}
          </div>
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
          {filteredChars.map((char) => (
            <CharacterCard
              key={char.id}
              character={char}
              bookId={bookId}
              editable={book?.mode === "author"}
              theme={theme}
              onUpdated={(updated) => {
                setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
              }}
              onDeleted={(characterId) => {
                setChars((current) => current.filter((item) => item.id !== characterId))
                if (primaryMergeId === characterId) setPrimaryMergeId("")
                if (secondaryMergeId === characterId) setSecondaryMergeId("")
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
