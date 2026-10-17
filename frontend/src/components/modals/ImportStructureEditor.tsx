"use client"
import { memo, useState } from "react"
import type { SectionMeta, SectionType } from "@/types/book"

const SECTION_TYPES: { value: SectionType; label: string; include: boolean }[] = [
  { value: "chapter", label: "Chapter", include: true },
  { value: "prologue", label: "Prologue", include: true },
  { value: "epilogue", label: "Epilogue", include: true },
  { value: "interlude", label: "Interlude", include: true },
  { value: "part_opening", label: "Part opening", include: true },
  { value: "preface", label: "Preface", include: true },
  { value: "foreword", label: "Foreword", include: true },
  { value: "afterword", label: "Afterword", include: true },
  { value: "appendix", label: "Appendix", include: true },
  { value: "dedication", label: "Dedication", include: false },
  { value: "acknowledgements", label: "Acknowledgements", include: false },
  { value: "glossary", label: "Glossary", include: false },
  { value: "notes", label: "Author Notes", include: false },
  { value: "chronology", label: "Chronology", include: false },
  { value: "copyright", label: "Copyright", include: false },
  { value: "title_page", label: "Title Page", include: false },
  { value: "unknown", label: "Unknown", include: true },
]

export const ImportStructureEditor = memo(function ImportStructureEditor({
  sections: initialSections,
  blockWordCounts = [],
  blockOpenings = [],
  blockClosings = [],
  blockLocations = [],
  isDark = false,
  onSave,
  onCancel,
}: {
  sections: SectionMeta[]
  blockWordCounts?: number[]
  blockOpenings?: string[]
  blockClosings?: string[]
  blockLocations?: Array<string | null>
  isDark?: boolean
  onSave: (sections: SectionMeta[]) => void
  onCancel: () => void
}) {
  const [sections, setSections] = useState<SectionMeta[]>(
    initialSections.map((s) => ({ ...s }))
  )

  const updateSection = (index: number, patch: Partial<SectionMeta>) => {
    setSections((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], ...patch }
      return next
    })
  }

  const shiftBoundary = (index: number, delta: number) => {
    setSections((prev) => {
      const next = prev.map((section) => ({ ...section }))
      const left = next[index]
      const right = next[index + 1]
      if (!left || !right || left.end_block == null || right.end_block == null || left.start_block == null) return prev
      if (["part", "toc"].includes(left.type) || ["part", "toc"].includes(right.type)) return prev
      const boundary = left.end_block + delta
      if (boundary <= left.start_block || boundary >= right.end_block) return prev
      left.end_block = boundary
      right.start_block = boundary
      for (const item of [left, right]) {
        const start = item.start_block ?? 0
        const end = item.end_block ?? start
        if (blockWordCounts.length) item.word_count = blockWordCounts.slice(start, end).reduce((sum, count) => sum + count, 0)
        if (blockOpenings[start]) item.opening_excerpt = blockOpenings[start]
        if (blockClosings[end - 1]) item.closing_excerpt = blockClosings[end - 1]
        const first = blockLocations[start]
        const last = blockLocations[end - 1]
        if (first) item.source_location = last && last !== first ? `${first} – ${last}` : first
      }
      return next
    })
  }

  const makePart = (index: number) => {
    setSections((prev) => {
      const target = prev[index]
      if (!target || target.start_block == null || target.type === "toc" || target.type === "part") return prev
      const partId = `part-${crypto.randomUUID()}`
      const group: SectionMeta = {
        ...target, id: partId, type: "part", title: target.title,
        parent_id: null, end_block: target.start_block,
        include_in_analysis: false, word_count: 0,
        opening_excerpt: "", closing_excerpt: "", warnings: [],
      }
      const opening = { ...target, type: "part_opening" as const, parent_id: partId, include_in_analysis: true }
      return [...prev.slice(0, index), group, opening, ...prev.slice(index + 1)]
    })
  }

  const removePart = (index: number) => {
    setSections((prev) => {
      const group = prev[index]
      if (!group || group.type !== "part") return prev
      const earlierPart = [...prev.slice(0, index)].reverse().find((item) => item.type === "part")
      return prev.filter((_, position) => position !== index).map((item) => {
        if (item.parent_id !== group.id) return item
        return {
          ...item,
          type: item.type === "part_opening" ? "chapter" as const : item.type,
          title: item.type === "part_opening" ? group.title : item.title,
          parent_id: earlierPart?.id ?? null,
        }
      })
    })
  }

  const toggleInclude = (index: number) => {
    setSections((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], include_in_analysis: !next[index].include_in_analysis }
      return next
    })
  }

  const analysisCount = sections.filter((s) => s.include_in_analysis).length

  return (
    <div className={`rounded-lg border ${isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
      <div className={`border-b px-4 py-3 ${isDark ? "border-white/10" : "border-slate-200"}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
              Edit section structure
            </p>
            <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {sections.length} sections &middot; {analysisCount} marked for analysis. Boundary moves retain every source block.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onCancel}
              className={`text-xs ${isDark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-700"}`}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>

      <div className={`max-h-96 overflow-y-auto ${isDark ? "divide-white/5" : "divide-slate-100"} divide-y`}>
        {sections.map((section, index) => (
          <div
            key={section.id}
            className={`px-4 py-3 transition ${
              section.warnings?.length ? (isDark ? "bg-amber-500/10" : "bg-amber-50") : ""
            }`}
          >
            <div className="flex items-start gap-3">
              <span className={`mt-2 shrink-0 text-xs font-mono ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                {index + 1}
              </span>

              <div className="flex-1 space-y-2">
                <input
                  type="text"
                  value={section.title}
                  onChange={(e) => updateSection(index, { title: e.target.value })}
                  className={`w-full rounded border px-2 py-1 text-sm font-medium transition focus:outline-none focus:ring-1 ${
                    isDark
                      ? "border-white/10 bg-white/5 text-slate-100 focus:ring-indigo-500"
                      : "border-slate-200 bg-white text-slate-900 focus:ring-indigo-500"
                  }`}
                  aria-label={`Section ${index + 1} title`}
                />

                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={section.type}
                    onChange={(e) => {
                      const newType = e.target.value as SectionType
                      const typeInfo = SECTION_TYPES.find((t) => t.value === newType)
                      updateSection(index, {
                        type: newType,
                        include_in_analysis: typeInfo?.include ?? true,
                      })
                    }}
                    className={`rounded border px-2 py-1 text-xs transition focus:outline-none focus:ring-1 ${
                      isDark
                        ? "border-white/10 bg-white/5 text-slate-200 focus:ring-indigo-500"
                        : "border-slate-200 bg-white text-slate-700 focus:ring-indigo-500"
                    }`}
                  >
                    {(section.type === "part" ? [{ value: "part" as SectionType, label: "Part heading", include: false }] : section.type === "toc" ? [{ value: "toc" as SectionType, label: "Table of Contents", include: false }, ...SECTION_TYPES] : SECTION_TYPES).map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>

                  <label className={`flex cursor-pointer items-center gap-1.5 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    <input
                      type="checkbox"
                      checked={section.include_in_analysis}
                      disabled={section.type === "part" || section.type === "toc"}
                      onChange={() => toggleInclude(index)}
                      className="h-3.5 w-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    Analyze
                  </label>

                  {section.type !== "part" && section.type !== "toc" ? (
                    <label className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                      Part <select aria-label={`Section ${index + 1} Part`} value={section.parent_id ?? ""} onChange={(e) => updateSection(index, { parent_id: e.target.value || null })} className={`ml-1 rounded border px-1 py-0.5 ${isDark ? "border-white/10 bg-slate-900" : "border-slate-200 bg-white"}`}>
                        <option value="">None</option>
                        {sections.slice(0, index).filter((item) => item.type === "part").map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                      </select>
                    </label>
                  ) : null}
                  {section.type === "part" ? (
                    <button type="button" onClick={() => removePart(index)} className="text-xs font-semibold text-amber-500 underline">Remove Part grouping</button>
                  ) : section.type !== "toc" ? (
                    <button type="button" onClick={() => makePart(index)} className="text-xs font-semibold text-teal-500 underline">Make this a Part opening</button>
                  ) : null}
                </div>
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>{section.source_location ?? "Source location unavailable"} · {section.word_count ?? 0} words · blocks {section.start_block ?? 0}–{section.end_block ?? 0}</p>
                {section.opening_excerpt ? <p className="text-xs opacity-70">Starts: {section.opening_excerpt}</p> : null}
                {section.closing_excerpt ? <p className="text-xs opacity-70">Ends: {section.closing_excerpt}</p> : null}
                {section.warnings?.map((warning) => <p key={warning} className="text-xs text-amber-500">{warning}</p>)}
                {index < sections.length - 1 && section.type !== "part" && section.type !== "toc" && sections[index + 1].type !== "part" && sections[index + 1].type !== "toc" ? (
                  <div className="flex gap-2 text-xs">
                    <button type="button" onClick={() => shiftBoundary(index, -1)} className="underline">Move next block into next section</button>
                    <button type="button" onClick={() => shiftBoundary(index, 1)} className="underline">Move next block into this section</button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className={`border-t px-4 py-3 flex items-center justify-between ${isDark ? "border-white/10" : "border-slate-200"}`}>
        <div className="flex items-center gap-2">
          <span className={`inline-flex h-2 w-2 rounded-full ${analysisCount > 0 ? "bg-green-500" : "bg-amber-500"}`} />
          <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
            {analysisCount} section{analysisCount !== 1 ? "s" : ""} will be analyzed
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCancel}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              isDark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Discard
          </button>
          <button
            type="button"
            onClick={() => onSave(sections)}
            className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
              isDark
                ? "bg-indigo-600 text-white hover:bg-indigo-700"
                : "bg-indigo-600 text-white hover:bg-indigo-700"
            }`}
          >
            Save changes
          </button>
        </div>
      </div>
    </div>
  )
})
