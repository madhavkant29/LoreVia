"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { booksApi } from "@/lib/api/books"
import type { Character } from "@/types/character"
import { CharacterCard } from "@/components/characters/CharacterCard"

export default function CharactersPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [chars, setChars] = useState<Character[]>([])
  const router = useRouter()

  useEffect(() => { booksApi.getCharacters(bookId).then(setChars) }, [bookId])

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">← Back</button>
        <h1 className="text-2xl font-semibold">Characters ({chars.length})</h1>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        {chars.map(char => (
          <CharacterCard key={char.id} character={char} />
        ))}
      </div>
    </div>
  )
}
