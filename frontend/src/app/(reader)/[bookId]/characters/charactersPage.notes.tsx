import Link from "next/link"

import type { Character } from "@/types/character"
import { SurfaceCard } from "./charactersPage.components"

type CharacterNotesTabProps = {
  bookId: string
  character: Character
  isDark: boolean
  noteToast: string | null
  onSaveCharacterNote: () => void
}

export function CharacterNotesTab({
  bookId,
  character,
  isDark,
  noteToast,
  onSaveCharacterNote,
}: CharacterNotesTabProps) {
  return (
    <div className="mt-5 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onSaveCharacterNote}
          className={`rounded-sm px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white"}`}
        >
          Save character note
        </button>
        <Link
          href={`/${bookId}/notes`}
          className={`rounded-sm px-4 py-2 text-sm font-medium ${isDark ? "bg-white/[0.08] text-slate-200" : "bg-stone-100 text-stone-700"}`}
        >
          Open notes workspace
        </Link>
        {noteToast ? <span className={`text-sm ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>{noteToast}</span> : null}
      </div>

      <SurfaceCard title="Related notes" isDark={isDark}>
        {(character.relationship_summaries?.length ?? 0) > 0 ? (
          <div className="space-y-3">
            {character.relationship_summaries?.map((summary, index) => (
              <div key={`${character.id}-note-${index}`} className={`rounded-sm border px-4 py-3 text-sm leading-6 ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                {summary}
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No linked notes yet. Use the Notes workspace to connect scene or research notes to this character.</p>
        )}
      </SurfaceCard>
    </div>
  )
}
