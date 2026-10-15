"use client"

import type { Dispatch, RefObject, SetStateAction } from "react"

type Props = {
  isDark: boolean
  isManagingExisting: boolean
  isScreenplayWorkspace: boolean
  advancedSettingsOpen: boolean
  setAdvancedSettingsOpen: Dispatch<SetStateAction<boolean>>
  preserveChapterNumbers: boolean
  setPreserveChapterNumbers: Dispatch<SetStateAction<boolean>>
  preserveSourceChapters: boolean
  setPreserveSourceChapters: Dispatch<SetStateAction<boolean>>
  coverInputRef: RefObject<HTMLInputElement | null>
  coverFile: File | null
  onCoverSelected: (file: File | null) => void
  autoExtractCover: boolean
  setAutoExtractCover: Dispatch<SetStateAction<boolean>>
}

export function AdvancedImportSettings({
  isDark,
  isManagingExisting,
  isScreenplayWorkspace,
  advancedSettingsOpen,
  setAdvancedSettingsOpen,
  preserveChapterNumbers,
  setPreserveChapterNumbers,
  preserveSourceChapters,
  setPreserveSourceChapters,
  coverInputRef,
  coverFile,
  onCoverSelected,
  autoExtractCover,
  setAutoExtractCover,
}: Props) {
  if (isManagingExisting) return null

  return (
    <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
      <button type="button" onClick={() => setAdvancedSettingsOpen((current) => !current)} className="flex w-full items-center justify-between text-left">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Advanced import settings</p>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Optional controls for structure, chapter preservation, and cover handling.</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-slate-700"}`}>{advancedSettingsOpen ? "Hide" : "Show"}</span>
      </button>

      {advancedSettingsOpen ? (
        <div className="mt-4">
          <label className="mb-4 flex items-start gap-3">
            <input type="checkbox" checked={preserveChapterNumbers || preserveSourceChapters} onChange={(event) => setPreserveChapterNumbers(event.target.checked)} disabled={preserveSourceChapters} className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed" />
            <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>{isScreenplayWorkspace ? "Preserve detected scene order from the source file" : "Preserve chapter numbers from the source file"}</p>
          </label>

          <label className="mb-4 flex items-start gap-3">
            <input
              type="checkbox"
              checked={preserveSourceChapters}
              onChange={(event) => {
                setPreserveSourceChapters(event.target.checked)
                if (event.target.checked) setPreserveChapterNumbers(true)
              }}
              className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>{isScreenplayWorkspace ? "Keep each detected scene exactly as uploaded" : "Keep each detected chapter exactly as uploaded"}</p>
          </label>

          <div className="mb-4">
            <input
              ref={coverInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null
                onCoverSelected(file)
                if (file) setAutoExtractCover(false)
                event.target.value = ""
              }}
            />
            <button type="button" onClick={() => coverInputRef.current?.click()} className={`w-full rounded-lg border px-3 py-2.5 text-sm transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-gray-300 bg-white text-slate-700 hover:bg-gray-50"}`}>{coverFile ? `Cover selected: ${coverFile.name}` : "Upload separate cover image"}</button>
            <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>Select a separate cover image file (PNG, JPEG, WebP)</p>
          </div>

          <label className={`flex items-start gap-3 ${coverFile ? "opacity-50" : ""}`}>
            <input
              type="checkbox"
              checked={autoExtractCover}
              onChange={(event) => {
                setAutoExtractCover(event.target.checked)
                if (event.target.checked) onCoverSelected(null)
              }}
              disabled={Boolean(coverFile)}
              className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed"
            />
            <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>Use the first PDF page as the book cover</p>
          </label>
        </div>
      ) : null}
    </div>
  )
}
