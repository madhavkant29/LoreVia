"use client"

import type { Dispatch, RefObject, SetStateAction } from "react"

import { ImportStructureEditor } from "@/components/modals/ImportStructureEditor"
import { Skeleton } from "@/components/ui/Skeleton"
import type { ImportPreview } from "@/types/book"

type Props = {
  isDark: boolean
  isManagingExisting: boolean
  startEmpty: boolean
  inputRef: RefObject<HTMLInputElement | null>
  newUploadAccept: string
  files: File[]
  onFilesSelected: (files: File[]) => void
  primaryFile: File | null
  isScreenplayWorkspace: boolean
  importPreview: ImportPreview | null
  setImportPreview: Dispatch<SetStateAction<ImportPreview | null>>
  dismissPreview: boolean
  setDismissPreview: Dispatch<SetStateAction<boolean>>
  previewLoading: boolean
  fetchPreview: () => Promise<void>
  setImportAsSingle: Dispatch<SetStateAction<boolean>>
  showEditor: boolean
  setShowEditor: Dispatch<SetStateAction<boolean>>
}

export function UploadSourceStep({
  isDark,
  isManagingExisting,
  startEmpty,
  inputRef,
  newUploadAccept,
  files,
  onFilesSelected,
  primaryFile,
  isScreenplayWorkspace,
  importPreview,
  setImportPreview,
  dismissPreview,
  setDismissPreview,
  previewLoading,
  fetchPreview,
  setImportAsSingle,
  showEditor,
  setShowEditor,
}: Props) {
  if (isManagingExisting || startEmpty) return null

  return (
    <>
      <div className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-slate-50/80"}`}>
        <div className="mb-3">
          <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>File upload</p>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Upload one manuscript file to start your import.</p>
        </div>
        <div
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-6 transition-colors ${
            isDark
              ? files.length > 0 ? "border-indigo-400/50 bg-indigo-500/10" : "border-white/15 bg-black/20 hover:border-indigo-400"
              : files.length > 0 ? "border-indigo-300 bg-indigo-50" : "border-slate-300 bg-white hover:border-indigo-400"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={newUploadAccept}
            className="hidden"
            onChange={(event) => {
              onFilesSelected(Array.from(event.target.files ?? []))
              event.target.value = ""
            }}
          />
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className={`text-base font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                {files.length > 0 ? primaryFile?.name : "Drop a manuscript here or click to browse"}
              </p>
              <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                {files.length > 0
                  ? "Replace the selected file at any time before uploading."
                  : `Supported formats: ${isScreenplayWorkspace ? "PDF, Fountain, TXT, Markdown" : "DOCX, PDF, EPUB, TXT, Markdown, Scrivener"}. Up to 100 MB per file.`}
              </p>
            </div>
            <div className={`inline-flex rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white text-slate-950" : "bg-slate-900 text-white"}`}>
              {files.length > 0 ? "Replace file" : "Choose file"}
            </div>
          </div>
        </div>

        {files.length > 0 && !importPreview && !dismissPreview ? (
          <div className="mt-4 flex items-center gap-3">
            <button type="button" disabled={previewLoading} onClick={() => void fetchPreview()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50">
              {previewLoading ? <span className="flex items-center gap-2"><Skeleton className="h-3.5 w-3.5 rounded-full bg-white/35" />Analyzing structure...</span> : "Preview structure"}
            </button>
            <button type="button" onClick={() => setDismissPreview(true)} className={`text-sm ${isDark ? "text-slate-400 hover:text-slate-300" : "text-slate-500 hover:text-slate-700"}`}>Skip preview</button>
          </div>
        ) : null}
      </div>

      {importPreview && !dismissPreview ? (
        <div className={`rounded-lg border p-5 ${isDark ? "border-indigo-500/30 bg-indigo-500/5" : "border-indigo-200 bg-indigo-50/80"}`}>
          <div className="mb-3 flex items-center justify-between">
            <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-indigo-300" : "text-indigo-600"}`}>Structure preview</p>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${importPreview.sections.some((section) => section.warnings?.length) ? "bg-amber-500/20 text-amber-400" : "bg-emerald-500/15 text-emerald-400"}`}>
              {importPreview.sections.some((section) => section.warnings?.length) ? "Review uncertain boundaries" : "Outline ready for review"}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Language", `${importPreview.detected_language.toUpperCase()}${importPreview.language_confidence > 0 ? ` ${Math.round(importPreview.language_confidence * 100)}%` : ""}`],
              ["Chapters", String(importPreview.chapter_count)],
              ["Front matter", String(importPreview.front_matter_count)],
              ["TOC", importPreview.toc_detected ? "Detected" : "None"],
            ].map(([label, value]) => (
              <div key={label} className={`rounded-lg p-3 ${isDark ? "bg-white/[0.06]" : "bg-white"}`}>
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>{label}</p>
                <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>{value}</p>
              </div>
            ))}
          </div>

          {importPreview.sections.length > 0 ? (
            <div className="mt-3">
              <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Sections ({importPreview.sections.length})</p>
              <div className={`max-h-80 overflow-y-auto rounded-lg border ${isDark ? "border-white/10" : "border-slate-200"}`}>
                {importPreview.sections.map((section) => (
                  <div key={section.id} className={`border-b px-3 py-2 text-xs last:border-b-0 ${isDark ? "border-white/5" : "border-slate-100"}`}>
                    <div className="flex items-center gap-3">
                    <span className={`rounded px-1.5 py-0.5 font-medium ${section.include_in_analysis ? isDark ? "bg-green-500/20 text-green-300" : "bg-green-100 text-green-700" : isDark ? "bg-slate-500/20 text-slate-400" : "bg-slate-100 text-slate-500"}`}>{section.type}</span>
                    <span className={isDark ? "text-slate-300" : "text-slate-700"}>{section.parent_id ? "↳ " : ""}{section.title || `Section ${section.number ?? "?"}`}</span>
                    {!section.include_in_analysis ? <span className={`ml-auto text-[10px] ${isDark ? "text-slate-500" : "text-slate-400"}`}>excluded</span> : null}
                    </div>
                    <p className="mt-1 opacity-70">{section.source_location ?? "Location unavailable"} · {section.word_count ?? 0} words</p>
                    {section.opening_excerpt ? <p className="mt-1 opacity-70">Starts: {section.opening_excerpt}</p> : null}
                    {section.closing_excerpt ? <p className="opacity-70">Ends: {section.closing_excerpt}</p> : null}
                    {section.warnings?.map((warning) => <p key={warning} className="mt-1 text-amber-500">{warning}</p>)}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {importPreview.warnings.length > 0 ? (
            <div className="mt-3 space-y-1">
              {importPreview.warnings.map((warning, index) => (
                <div key={`${warning.message}-${index}`} className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs ${warning.severity === "error" ? isDark ? "bg-red-500/10 text-red-300" : "bg-red-50 text-red-700" : warning.severity === "warning" ? isDark ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-700" : isDark ? "bg-blue-500/10 text-blue-300" : "bg-blue-50 text-blue-700"}`}>
                  <span className="mt-0.5 shrink-0">{warning.severity === "error" ? "⚠" : warning.severity === "warning" ? "▲" : "ℹ"}</span>
                  <span>{warning.message}</span>
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {importPreview.sections.some((section) => section.type === "unknown") ? <p className="w-full text-xs text-amber-500">Unclassified sections will be analyzed and count toward your processed-word allowance. Supplemental material in them may affect analysis.</p> : null}
            <button type="submit" onClick={() => setImportAsSingle(false)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700">Confirm &amp; Import</button>
            <button type="submit" onClick={() => setImportAsSingle(true)} className={`rounded-lg px-4 py-2 text-sm font-medium transition ${isDark ? "border border-white/20 bg-white/5 text-slate-200 hover:bg-white/10" : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"}`}>Import as single file</button>
            <button type="button" onClick={() => setShowEditor(true)} className={`rounded-lg px-4 py-2 text-sm font-medium transition ${isDark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-700"}`}>Edit structure</button>
          </div>
        </div>
      ) : null}

      {importPreview && showEditor ? (
        <ImportStructureEditor
          sections={importPreview.sections}
          blockWordCounts={importPreview.block_word_counts}
          blockOpenings={importPreview.block_openings}
          blockClosings={importPreview.block_closings}
          blockLocations={importPreview.block_locations}
          isDark={isDark}
          onSave={(sections) => {
            setImportPreview({ ...importPreview, sections })
            setShowEditor(false)
          }}
          onCancel={() => setShowEditor(false)}
        />
      ) : null}
    </>
  )
}
