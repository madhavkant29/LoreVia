"use client"
import { useState, useRef, useEffect } from "react"
import { intelligenceApi } from "@/lib/api/intelligence"
import type { Character } from "@/types/character"
import type { ChatMessage } from "@/types/intelligence"

interface Props {
  character: Character
  bookId: string
  currentChapter: number
}

export function CharacterChat({ character, bookId, currentChapter }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg: ChatMessage = { role: "user", content: input }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setLoading(true)
    setError(null)

    try {
      const res = await intelligenceApi.chat(
        bookId, character.id,
        [...messages, userMsg],
        currentChapter,
      )
      setMessages(prev => [...prev, { role: "assistant", content: res.reply }])
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Chat failed")
      setMessages(prev => prev.slice(0, -1))
      setInput(userMsg.content)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 shrink-0">
        <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 text-xs font-bold">
          {character.name[0]}
        </div>
        <p className="text-sm font-medium">Chat with {character.name}</p>
        <p className="text-xs text-gray-400 ml-auto">Ch. {currentChapter} context</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {messages.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6 italic">
            Ask {character.name} anything about the story so far...
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-xs rounded-2xl px-3 py-2 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-indigo-600 text-white"
                : "bg-gray-100 text-gray-800"
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-3 py-2">
              <div className="flex gap-1">
                {[0,1,2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="text-xs text-red-500 px-4 pb-1">{error}</p>}

      <div className="flex gap-2 p-3 border-t border-gray-100 shrink-0">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
          placeholder={`Ask ${character.name}...`}
          className="flex-1 border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button onClick={send} disabled={loading || !input.trim()}
          className="px-3 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          →
        </button>
      </div>
    </div>
  )
}
