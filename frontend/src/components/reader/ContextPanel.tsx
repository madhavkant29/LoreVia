"use client"
import { useMemo, useState } from "react"
import { useParams } from "next/navigation"
import type { ChapterCharacter, ContextResult } from "@/types/reader"
import { readerApi } from "@/lib/api/reader"

interface Props {
  result: ContextResult | null
  loading: boolean
  onClose: () => void
  theme: "light" | "dark"
  selectedQuote: string | null
  chapterNumber: number
  chapterTitle: string | null
  characters: ChapterCharacter[]
}

export function ContextPanel({
  result,
  loading,
  onClose,
  theme,
  selectedQuote,
  chapterNumber,
  chapterTitle,
  characters,
}: Props) {
  const { bookId } = useParams<{ bookId: string }>()
  const [savingQuote, setSavingQuote] = useState(false)
  const [quoteCharacter, setQuoteCharacter] = useState("")
  const [quoteNote, setQuoteNote] = useState("")
  const activeCharacter = result?.type === "character" ? result.character : null

  const shell = theme === "dark"
    ? {
        container: "border-white/10 bg-[#101421]/97 text-white",
        sticky: "bg-[#101421]/95 border-white/10",
        tabActive: "bg-indigo-500/18 text-indigo-100",
        tab: "text-stone-400 hover:bg-white/6 hover:text-white",
        card: "border-white/10 bg-white/[0.04]",
        subCard: "border-white/10 bg-black/20",
        muted: "text-stone-400",
        body: "text-stone-300",
        input: "border-white/10 bg-white/5 text-white placeholder:text-stone-500",
        button: "bg-indigo-500 text-white hover:bg-indigo-400",
        line: "bg-white/15",
      }
    : {
        container: "border-stone-200/90 bg-[#fcfaf5]/97 text-stone-950",
        sticky: "bg-[#fcfaf5]/94 border-stone-200/80",
        tabActive: "bg-violet-50 text-violet-700",
        tab: "text-stone-500 hover:bg-stone-100 hover:text-stone-900",
        card: "border-stone-200/80 bg-white/84",
        subCard: "border-violet-100 bg-[linear-gradient(180deg,#f8f5ff,#ffffff)]",
        muted: "text-stone-500",
        body: "text-stone-700",
        input: "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400",
        button: "bg-[linear-gradient(135deg,#4f46e5,#4338ca)] text-white hover:opacity-95",
        line: "bg-stone-200",
      }

  const characterOptions = useMemo(
    () => Array.from(new Set((characters ?? []).map((character) => character.name).filter(Boolean))).sort(),
    [characters]
  )

  const saveSelectedQuote = async () => {
    if (!selectedQuote?.trim()) return
    setSavingQuote(true)
    try {
      await readerApi.saveQuote(bookId, {
        quote_text: selectedQuote,
        chapter_number: chapterNumber,
        character_name: quoteCharacter || null,
        note: quoteNote || null,
      })
      setQuoteCharacter("")
      setQuoteNote("")
    } finally {
      setSavingQuote(false)
    }
  }

  return (
    <aside className={`fixed inset-x-0 bottom-0 top-auto z-30 max-h-[84dvh] overflow-hidden rounded-t-[1.9rem] border shadow-[0_-24px_60px_-30px_rgba(15,23,42,0.28)] md:static md:inset-auto md:max-h-none md:w-[23rem] md:rounded-none md:border-l md:border-t-0 md:shadow-[-24px_0_64px_-48px_rgba(79,70,229,0.3)] xl:w-[25rem] ${shell.container}`}>
      <div className={`sticky top-0 z-10 border-b backdrop-blur ${shell.sticky}`}>
        <div className="flex justify-center pt-3 md:hidden">
          <span className={`h-1.5 w-12 rounded-full ${shell.line}`} />
        </div>
        <div className="px-5 py-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-stone-400">Context Panel</p>
              <h2 className="mt-2 text-3xl text-violet-700" style={{ fontFamily: "var(--reader-display)" }}>
                AI Insights
              </h2>
            </div>
            <button onClick={onClose} aria-label="Close context panel" className={`rounded-full px-3 py-2 text-xs transition ${shell.tab}`}>
              Close
            </button>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-2 text-sm">
            <button className={`rounded-[1rem] px-4 py-3 text-left transition ${shell.tabActive}`}>Character Details</button>
            <button className={`rounded-[1rem] px-4 py-3 text-left transition ${shell.tab}`}>Relationships</button>
            <button className={`rounded-[1rem] px-4 py-3 text-left transition ${shell.tab}`}>Notes</button>
            <button className={`rounded-[1rem] px-4 py-3 text-left transition ${shell.tab}`}>History</button>
          </div>
        </div>
      </div>

      <div className="reader-scrollbar app-scroll flex h-full flex-col overflow-y-auto px-5 pb-[max(env(safe-area-inset-bottom),1rem)] pt-5">
        {selectedQuote?.trim() ? (
          <div className={`mb-5 rounded-[1.5rem] border p-4 ${shell.card}`}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-violet-500">Selected passage</p>
            <p className={`mt-3 whitespace-pre-wrap text-sm leading-7 ${shell.body}`}>{selectedQuote.trim()}</p>
            <div className="mt-4 space-y-3">
              <div className={`rounded-[1rem] border px-3 py-2 text-xs ${shell.card}`}>
                <span className="font-medium">Chapter:</span> {chapterTitle ? `${chapterNumber} - ${chapterTitle}` : `Chapter ${chapterNumber}`}
              </div>
              <select
                value={quoteCharacter}
                onChange={(event) => setQuoteCharacter(event.target.value)}
                className={`w-full rounded-[1rem] border px-3 py-2 text-sm ${shell.input}`}
              >
                <option value="">Who said it? (optional)</option>
                {characterOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <textarea
                value={quoteNote}
                onChange={(event) => setQuoteNote(event.target.value)}
                placeholder="Why does this line matter?"
                rows={3}
                className={`w-full rounded-[1rem] border px-3 py-2 text-sm ${shell.input}`}
              />
              <button onClick={saveSelectedQuote} className={`w-full rounded-[1rem] px-4 py-3 text-sm font-semibold transition ${shell.button}`}>
                {savingQuote ? "Saving..." : "Save line bookmark"}
              </button>
            </div>
          </div>
        ) : null}

        {loading ? <div className={`py-8 text-center text-sm ${shell.muted}`}>Loading...</div> : null}

        {!loading && activeCharacter ? (
          <div className={`rounded-[1.6rem] border p-4 ${shell.card}`}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-violet-500">Character focus</p>

            <div className={`mt-4 rounded-[1.4rem] border p-4 ${shell.subCard}`}>
              <div className="mb-4 flex justify-center md:justify-start">
                <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-[1.35rem] bg-[linear-gradient(135deg,#ece7ff,#ffffff)] text-3xl font-semibold text-violet-700 shadow-inner">
                  {String(activeCharacter.name?.[0] ?? "?").toUpperCase()}
                </div>
              </div>

              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-4xl leading-none text-stone-950" style={{ fontFamily: "var(--reader-display)" }}>
                    {activeCharacter.name}
                  </h3>
                  {activeCharacter.role ? <p className="mt-2 text-sm uppercase tracking-[0.16em] text-violet-600">{activeCharacter.role}</p> : null}
                </div>
                <span className="rounded-full bg-violet-500 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
                  Main Character
                </span>
              </div>

              {activeCharacter.aliases?.length ? (
                <p className={`mt-3 text-sm ${shell.muted}`}>Also known as {activeCharacter.aliases.join(", ")}</p>
              ) : null}

              <div className="mt-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">Biography overview</p>
                <p className={`mt-3 text-base leading-8 ${shell.body}`}>
                  {activeCharacter.description || "LoreVia is still building this character profile from the text around this passage."}
                </p>
              </div>

              {activeCharacter.personality_tags?.length ? (
                <div className="mt-5">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">Traits</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {activeCharacter.personality_tags.slice(0, 5).map((tag: string) => (
                      <span key={tag} className="rounded-full bg-white px-3 py-1 text-xs capitalize text-stone-700 shadow-sm">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            {result?.relationships && result.relationships.length > 0 ? (
              <div className="mt-5">
                <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-400">Relationships</p>
                <div className="space-y-2">
                  {result.relationships.map((relationship, index) => (
                    <div key={index} className={`rounded-[1.1rem] border p-3 ${shell.card}`}>
                      <p className="text-sm font-semibold capitalize text-violet-600">{relationship.type}</p>
                      {relationship.description ? <p className={`mt-1 text-sm leading-7 ${shell.body}`}>{relationship.description}</p> : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <button className={`mt-5 w-full rounded-[1rem] px-4 py-3 text-sm font-semibold transition ${shell.button}`}>
              Open Lore Entry
            </button>
          </div>
        ) : null}

        {!loading && result?.type === "search" ? (
          <div className="flex flex-col gap-3">
            {(result.results ?? []).length === 0 ? <p className={`text-sm ${shell.muted}`}>No relevant passages found.</p> : null}
            {(result.results ?? []).map((searchResult, index) => (
              <div key={index} className={`rounded-[1.35rem] border p-4 ${shell.card}`}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-500">Chapter {searchResult.chapter_num}</p>
                </div>
                <p className={`text-sm leading-7 ${shell.body}`}>{searchResult.text}</p>
              </div>
            ))}
          </div>
        ) : null}

        {!loading && !selectedQuote && !activeCharacter && result?.type !== "search" ? (
          <div className={`rounded-[1.5rem] border p-5 ${shell.card}`}>
            <p className={`text-sm leading-7 ${shell.body}`}>
              Tap a highlighted character name to open a profile here. On mobile, this panel docks as a bottom sheet so context feels attached to the page you are reading.
            </p>
          </div>
        ) : null}
      </div>
    </aside>
  )
}
