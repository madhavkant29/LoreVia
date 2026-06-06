"use client"

import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { capture } from "@/lib/analytics/posthog"
import type { Character } from "@/types/character"

interface Props {
  bookId: string
  selectedText: string
  isDark: boolean
  firstChapter?: number
  open: boolean
  onClose: () => void
  onCreated?: (character: Character) => void
}

function sanitizeName(raw: string): string {
  return raw.replace(/\s+/g, " ").trim().slice(0, 120)
}

export function AddCharacterFromSelection({
  bookId,
  selectedText,
  isDark,
  firstChapter = 1,
  open,
  onClose,
  onCreated,
}: Props) {
  const [name, setName] = useState(() => sanitizeName(selectedText))
  const [role, setRole] = useState<"mc" | "sc" | "background" | null>(null)
  const [description, setDescription] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const prevOpenRef = useRef(false)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useLayoutEffect(() => {
    if (open && !prevOpenRef.current) {
      setName(sanitizeName(selectedText))
      setRole(null)
      setDescription("")
      setError(null)
    }
    prevOpenRef.current = open
  }, [open, selectedText])

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) {
        setError(null)
        onCloseRef.current()
      }
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [open, busy])

  if (!open) return null

  const handleCreate = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setError("Character name is required.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const created = await booksApi.createCharacter(bookId, {
        name: trimmed,
        firstChapter,
        role: role || undefined,
        description: description.trim() || undefined,
      })
      capture("author_character_created_from_selection", {
        book_id: bookId,
        chapter: firstChapter,
        source: "selection_menu",
      })
      onCreated?.(created)
      setName("")
      setRole(null)
      setDescription("")
      onClose()
    } catch {
      setError("Could not create this character. The name may already exist.")
    } finally {
      setBusy(false)
    }
  }

  const handleCancel = () => {
    if (busy) return
    setError(null)
    onClose()
  }

  const inputClass = `w-full rounded-md border px-3 py-2 text-sm outline-none transition-colors ${
    isDark
      ? "border-white/10 bg-white/[0.04] text-slate-100 focus:border-violet-500/50"
      : "border-stone-200 bg-white text-stone-900 focus:border-violet-400"
  }`

  const selectClass = `w-full rounded-md border px-3 py-2 text-sm outline-none transition-colors ${
    isDark
      ? "border-white/10 bg-white/[0.04] text-slate-100 focus:border-violet-500/50"
      : "border-stone-200 bg-white text-stone-900 focus:border-violet-400"
  }`

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[20vh]" onClick={handleCancel}>
      <div
        className={`mx-4 w-full max-w-md rounded-xl border p-6 shadow-2xl ${
          isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className={`text-base font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>
          Add character from selection
        </h2>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          The selected text will be used as the character name.
        </p>

        <div className="mt-5 space-y-4">
          <div>
            <label className={`mb-1 block text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Name
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputClass}
              disabled={busy}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleCreate()
              }}
            />
          </div>

          <div>
            <label className={`mb-1 block text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Role
            </label>
            <select
              value={role ?? ""}
              onChange={(e) => setRole((e.target.value || null) as "mc" | "sc" | "background" | null)}
              className={selectClass}
              disabled={busy}
            >
              <option value="">Unclassified</option>
              <option value="mc">Primary (MC)</option>
              <option value="sc">Supporting (SC)</option>
              <option value="background">Minor / Background</option>
            </select>
          </div>

          <div>
            <label className={`mb-1 block text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Description <span className="font-normal opacity-60">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={`${inputClass} min-h-[4.5rem] resize-none`}
              disabled={busy}
              maxLength={300}
            />
            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Add a brief character note if the selected text needs context.</p>
          </div>

          {error ? (
            <p className="text-sm text-rose-400">{error}</p>
          ) : null}
        </div>

        <div className="mt-5 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={handleCancel}
            disabled={busy}
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              isDark
                ? "bg-white/8 text-slate-200 hover:bg-white/12"
                : "bg-stone-100 text-stone-700 hover:bg-stone-200"
            } disabled:opacity-40`}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleCreate()}
            disabled={busy || !name.trim()}
            className="rounded-md bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-600 disabled:opacity-40"
          >
            {busy ? "Creating..." : "Create character"}
          </button>
        </div>
      </div>
    </div>
  )
}
