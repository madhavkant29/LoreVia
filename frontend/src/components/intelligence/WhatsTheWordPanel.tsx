"use client"

import { useMemo, useState } from "react"

import { intelligenceApi } from "@/lib/api/intelligence"
import {
  WHATS_THE_WORD_MIN_DESCRIPTION_WORDS,
  canSubmitWhatsTheWordDescription,
  countWhatsTheWordDescriptionWords,
} from "@/lib/utils/whatsTheWord"
import type { WhatsTheWordResponse } from "@/types/intelligence"

export function WhatsTheWordPanel({
  bookId,
  isDark,
  className,
}: {
  bookId: string
  isDark: boolean
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const [description, setDescription] = useState("")
  const [result, setResult] = useState<WhatsTheWordResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const descriptionWordCount = useMemo(
    () => countWhatsTheWordDescriptionWords(description),
    [description]
  )
  const canSubmit = canSubmitWhatsTheWordDescription(description)

  const requestWord = async (retry = false) => {
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    try {
      const nextResult = await intelligenceApi.whatsTheWord(
        bookId,
        description.trim(),
        retry ? result?.word ?? null : null
      )
      setResult(nextResult)
    } catch {
      setError("Couldn't find the word right now. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={`inline-flex items-center rounded-full px-4 py-2 text-sm font-medium ${
          isDark ? "bg-white/10 text-slate-100" : "bg-stone-100 text-stone-800"
        }`}
      >
        {open ? "Hide what's the word" : "What's the word"}
      </button>

      {open ? (
        <div
          className={`mt-3 rounded-[1.1rem] border p-4 ${
            isDark ? "border-white/10 bg-black/25" : "border-stone-200 bg-white/92"
          }`}
        >
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 flex-1">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>
                Word finder
              </p>
              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                Describe the missing word in plain language, and LoreVia will suggest one precise fit.
              </p>
              <textarea
                value={description}
                onChange={(event) => {
                  setDescription(event.target.value)
                  setError(null)
                  setResult(null)
                }}
                rows={4}
                placeholder="For example: a smile that hides contempt behind politeness"
                className={`mt-3 w-full rounded-[1rem] border px-4 py-3 text-sm leading-6 ${
                  isDark
                    ? "border-white/10 bg-[#020617] text-slate-100 placeholder:text-slate-500"
                    : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"
                }`}
              />
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <p className={`text-xs ${descriptionWordCount >= WHATS_THE_WORD_MIN_DESCRIPTION_WORDS ? isDark ? "text-emerald-300" : "text-emerald-700" : isDark ? "text-slate-400" : "text-stone-500"}`}>
                  Use at least {WHATS_THE_WORD_MIN_DESCRIPTION_WORDS} words for a more accurate result.
                </p>
                <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                  {descriptionWordCount} / {WHATS_THE_WORD_MIN_DESCRIPTION_WORDS}+ words
                </span>
              </div>
            </div>

            <div className="w-full lg:max-w-[18rem]">
              <div
                className={`rounded-[1rem] border px-4 py-4 ${
                  isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"
                }`}
              >
                <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                  Suggestion
                </p>
                {result ? (
                  <>
                    <p className={`mt-3 text-3xl font-semibold lowercase ${isDark ? "text-white" : "text-stone-950"}`}>
                      {result.word}
                    </p>
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                      {result.gloss}
                    </p>
                  </>
                ) : (
                  <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Your one-word suggestion will appear here.
                  </p>
                )}
              </div>

              {error ? <p className="mt-3 text-sm text-rose-500">{error}</p> : null}

              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void requestWord(false)}
                  disabled={!canSubmit || loading}
                  className="rounded-full bg-[linear-gradient(135deg,#2563eb,#1d4ed8)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {loading ? "Finding..." : "Find word"}
                </button>
                <button
                  type="button"
                  onClick={() => void requestWord(true)}
                  disabled={!canSubmit || !result || loading}
                  className={`rounded-full px-4 py-2 text-sm font-medium ${
                    isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"
                  }`}
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
