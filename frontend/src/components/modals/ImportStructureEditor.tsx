"use client"
import { memo, useState } from "react"
import type { SectionMeta, SectionType } from "@/types/book"

const SECTION_TYPES: { value: SectionType; label: string; include: boolean }[] = [
  { value: "chapter", label: "Chapter", include: true },
  { value: "prologue", label: "Prologue", include: true },
  { value: "epilogue", label: "Epilogue", include: true },
  { value: "interlude", label: "Interlude", include: true },
  { value: "part", label: "Part", include: true },
  { value: "preface", label: "Preface", include: true },
  { value: "foreword", label: "Foreword", include: true },
  { value: "afterword", label: "Afterword", include: true },
  { value: "appendix", label: "Appendix", include: true },
  { value: "toc", label: "Table of Contents", include: false },
  { value: "dedication", label: "Dedication", include: false },
  { value: "acknowledgements", label: "Acknowledgements", include: false },
  { value: "glossary", label: "Glossary", include: false },
  { value: "notes", label: "Author Notes", include: false },
  { value: "copyright", label: "Copyright", include: false },
  { value: "title_page", label: "Title Page", include: false },
  { value: "unknown", label: "Unknown", include: true },
]

export const ImportStructureEditor = memo(function ImportStructureEditor({
  sections: initialSections,
  isDark = false,
  onSave,
  onCancel,
}: {
  sections: SectionMeta[]
  isDark?: boolean
  onSave: (sections: SectionMeta[]) => void
  onCancel: () => void
}) {
  const [sections, setSections] = useState<SectionMeta[]>(
    initialSections.map((s) => ({ ...s }))
  )
  const [mergeIndex, setMergeIndex] = useState<number | null>(null)

  const updateSection = (index: number, patch: Partial<SectionMeta>) => {
    setSections((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], ...patch }
      return next
    })
  }

  const deleteSection = (index: number) => {
    if (sections.length <= 1) return
    setSections((prev) => prev.filter((_, i) => i !== index))
    setMergeIndex(null)
  }

  const handleMerge = (index: number) => {
    if (mergeIndex === null) {
      setMergeIndex(index)
      return
    }
    if (mergeIndex === index) {
      setMergeIndex(null)
      return
    }
    const from = Math.min(mergeIndex, index)
    const to = Math.max(mergeIndex, index)
    setSections((prev) => {
      const merged: SectionMeta = {
        ...prev[from],
        title: prev[from].title || prev[to].title || `Merged ${from + 1}-${to + 1}`,
        number: Math.min(prev[from].number ?? to, prev[to].number ?? to),
        confidence: (prev[from].confidence + prev[to].confidence) / 2,
      }
      const result = [...prev.slice(0, from), merged, ...prev.slice(to + 1)]
      return result
    })
    setMergeIndex(null)
  }

  const quickMark = (type: SectionType) => {
    setSections((prev) =>
      prev.map((s, i) => ({
        ...s,
        type: i === 0 && type === "preface" && prev.length > 1 ? "preface" : type,
        include_in_analysis: SECTION_TYPES.find((t) => t.value === type)?.include ?? true,
      }))
    )
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
              {sections.length} sections &middot; {analysisCount} marked for analysis
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => quickMark("chapter")}
              className={`rounded px-2 py-1 text-xs font-medium transition ${
                isDark ? "bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30" : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
              }`}
            >
              All chapters
            </button>
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
              mergeIndex === index ? (isDark ? "bg-indigo-500/10" : "bg-indigo-100") : ""
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
                    {SECTION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>

                  <label className={`flex cursor-pointer items-center gap-1.5 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    <input
                      type="checkbox"
                      checked={section.include_in_analysis}
                      onChange={() => toggleInclude(index)}
                      className="h-3.5 w-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    Analyze
                  </label>

                  {index > 0 ? (
                    <button
                      type="button"
                      onClick={() => handleMerge(index)}
                      className={`rounded px-2 py-1 text-xs font-medium transition ${
                        mergeIndex === index
                          ? (isDark ? "bg-indigo-500/30 text-indigo-200" : "bg-indigo-200 text-indigo-800")
                          : mergeIndex !== null
                            ? (isDark ? "bg-amber-500/15 text-amber-300 hover:bg-amber-500/25" : "bg-amber-100 text-amber-700 hover:bg-amber-200")
                            : (isDark ? "text-slate-500 hover:text-slate-300" : "text-slate-400 hover:text-slate-600")
                      }`}
                    >
                      {mergeIndex === index ? "Cancel merge" : mergeIndex !== null ? `Merge with #${mergeIndex + 1}` : "Merge"}
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => deleteSection(index)}
                    disabled={sections.length <= 1}
                    className={`ml-auto rounded px-2 py-1 text-xs font-medium transition disabled:opacity-30 ${
                      isDark ? "text-red-400 hover:text-red-300 hover:bg-red-500/10" : "text-red-500 hover:text-red-700 hover:bg-red-50"
                    }`}
                  >
                    Delete
                  </button>
                </div>
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
