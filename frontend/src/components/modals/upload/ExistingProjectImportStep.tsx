"use client"

import type { Dispatch, RefObject, SetStateAction } from "react"

import { Tooltip } from "@/components/ui/Tooltip"
import { ImportStructureEditor } from "@/components/modals/ImportStructureEditor"
import type { BookSelector, ChapterConsistencyReport, ImportPreview } from "@/types/book"

import { buildImportOutcomeCards } from "./uploadUtils"

type ChapterSource = "paste" | "upload"

type Props = {
  isDark: boolean
  isManagingExisting: boolean
  isScreenplayWorkspace: boolean
  selectedExistingBook: BookSelector | null
  chapterSource: ChapterSource
  setChapterSource: Dispatch<SetStateAction<ChapterSource>>
  setError: Dispatch<SetStateAction<string | null>>
  chapterNumber: string
  setChapterNumber: Dispatch<SetStateAction<string>>
  setChapterNumberDirty: Dispatch<SetStateAction<boolean>>
  replaceExisting: boolean
  setReplaceExisting: Dispatch<SetStateAction<boolean>>
  storyUnitLabel: string
  storyUnitLabelTitle: string
  chapterTitle: string
  setChapterTitle: Dispatch<SetStateAction<string>>
  chapterText: string
  setChapterText: Dispatch<SetStateAction<string>>
  inputRef: RefObject<HTMLInputElement | null>
  files: File[]
  onFilesSelected: (files: File[]) => void
  chapterUploadAccept: string
  chapterUploadHelp: string
  splitIntoChapters: boolean
  setSplitIntoChapters: Dispatch<SetStateAction<boolean>>
  chunkLongDocuments: boolean
  setChunkLongDocuments: Dispatch<SetStateAction<boolean>>
  infoButtonClass: string
  chapterReports: ChapterConsistencyReport[]
  importPreview: ImportPreview | null
  setImportPreview: Dispatch<SetStateAction<ImportPreview | null>>
  previewLoading: boolean
  fetchPreview: () => Promise<void>
  showEditor: boolean
  setShowEditor: Dispatch<SetStateAction<boolean>>
}

export function ExistingProjectImportStep({
  isDark,
  isManagingExisting,
  isScreenplayWorkspace,
  selectedExistingBook,
  chapterSource,
  setChapterSource,
  setError,
  chapterNumber,
  setChapterNumber,
  setChapterNumberDirty,
  replaceExisting,
  setReplaceExisting,
  storyUnitLabel,
  storyUnitLabelTitle,
  chapterTitle,
  setChapterTitle,
  chapterText,
  setChapterText,
  inputRef,
  files,
  onFilesSelected,
  chapterUploadAccept,
  chapterUploadHelp,
  splitIntoChapters,
  setSplitIntoChapters,
  chunkLongDocuments,
  setChunkLongDocuments,
  infoButtonClass,
  chapterReports,
  importPreview,
  setImportPreview,
  previewLoading,
  fetchPreview,
  showEditor,
  setShowEditor,
}: Props) {
  if (!isManagingExisting) return null

  return (
    <div className={`rounded-md border p-5 ${isDark ? "border-indigo-500/20 bg-white/[0.03]" : "border-indigo-200 bg-slate-50"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-indigo-700"}`}>Single-{isScreenplayWorkspace ? "script" : "chapter"} workflow</p>
          <p className={`mt-2 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            LoreVia will attach this {isScreenplayWorkspace ? "scene batch or script segment" : "chapter"} to {selectedExistingBook ? `"${selectedExistingBook.title}"` : "your selected manuscript"}, update character memory and thread data, then surface continuity risks from the fresh ingest.
          </p>
        </div>
        <div className={`rounded-md border px-4 py-3 text-xs ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-white bg-white text-stone-600"}`}>
          <p className="font-semibold">After processing</p>
          <p className="mt-1">You&apos;ll get a fresh summary, new-character changes, thread movement, and continuity review.</p>
        </div>
      </div>

      <div className={`mt-4 inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-white/80"}`}>
        {([
          { value: "paste", label: isScreenplayWorkspace ? "Paste script" : "Paste chapter" },
          { value: "upload", label: "Upload file" },
        ] as const).map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => {
              setChapterSource(option.value)
              setError(null)
            }}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${chapterSource === option.value ? isDark ? "bg-white text-slate-950" : "bg-indigo-600 text-white" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-stone-100"}`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              type="number"
              min={1}
              value={chapterNumber}
              onChange={(event) => {
                setChapterNumber(event.target.value)
                setChapterNumberDirty(true)
              }}
              aria-label={`${storyUnitLabelTitle} number`}
              className={`rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`}
            />
            <label className={`flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-gray-300 bg-white text-slate-700"}`}>
              <input type="checkbox" checked={replaceExisting} onChange={(event) => setReplaceExisting(event.target.checked)} />
              Replace {storyUnitLabel}
            </label>
          </div>

          {chapterSource === "paste" ? (
            <>
              <input type="text" value={chapterTitle} onChange={(event) => setChapterTitle(event.target.value)} aria-label={`${storyUnitLabelTitle} title`} className={`rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`} />
              <textarea value={chapterText} onChange={(event) => setChapterText(event.target.value)} rows={14} aria-label={`${storyUnitLabelTitle} text`} className={`min-h-[280px] rounded-xl border px-3 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-black/20 text-slate-100 focus:border-indigo-400/50" : "border-gray-300 bg-white text-slate-950 focus:border-indigo-400"}`} />
              <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{isScreenplayWorkspace ? "Paste screenplay text here. LoreVia will split scenes, refresh character profiles, and immediately run continuity checks." : "Paste one chapter here. LoreVia will save it into the manuscript, refresh character profiles, and immediately run continuity checks."}</p>
              <div className={`flex items-center justify-between text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                <span>{chapterText.trim() ? `${chapterText.trim().split(/\s+/).length} words ready` : `No ${storyUnitLabel} text pasted yet`}</span>
                <span>{replaceExisting ? `Will replace the selected ${storyUnitLabel} number` : `Will append if the ${storyUnitLabel} number is new`}</span>
              </div>
            </>
          ) : (
            <>
            <div onClick={() => inputRef.current?.click()} className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors ${isDark ? "border-white/15 bg-white/[0.03] hover:border-indigo-400" : "border-gray-300 bg-white hover:border-indigo-400"}`}>
              <input ref={inputRef} type="file" multiple accept={chapterUploadAccept} className="hidden" onChange={(event) => { onFilesSelected(Array.from(event.target.files ?? [])); event.target.value = "" }} />
              <p className={`text-sm ${isDark ? files.length > 0 ? "text-slate-100" : "text-slate-400" : files.length > 0 ? "text-slate-700" : "text-slate-400"}`}>
                {files.length > 0 ? files.length === 1 ? files[0].name : `${files.length} files selected` : chapterUploadHelp}
              </p>
            </div>
            {files.length === 1 && !isScreenplayWorkspace && splitIntoChapters && !replaceExisting ? (
              <div className="space-y-2">
                <button type="button" disabled={previewLoading} onClick={() => void fetchPreview()} className="text-sm font-semibold text-teal-500 underline disabled:opacity-50">
                  {previewLoading ? "Reading structure…" : "Preview and correct outline"}
                </button>
                {importPreview ? (
                  <div className="space-y-2 text-xs">
                    <p className="font-semibold">Full proposed outline ({importPreview.sections.length} sections)</p>
                    <div className="max-h-72 space-y-1 overflow-y-auto">
                      {importPreview.sections.map((section) => <div key={section.id} className={`rounded border p-2 ${isDark ? "border-white/10" : "border-slate-200"}`}>
                        <p>{section.parent_id ? "↳ " : ""}{section.title} · {section.type} · {section.word_count ?? 0} words · {section.source_location ?? "Location unavailable"}</p>
                        {section.opening_excerpt ? <p className="opacity-70">Starts: {section.opening_excerpt}</p> : null}
                        {section.closing_excerpt ? <p className="opacity-70">Ends: {section.closing_excerpt}</p> : null}
                        {section.warnings?.map((warning) => <p key={warning} className="text-amber-500">{warning}</p>)}
                      </div>)}
                    </div>
                    {importPreview.sections.some((section) => section.type === "unknown") ? <p className="text-amber-500">Unclassified sections will be analyzed and use processed-word allowance; check for supplemental text.</p> : null}
                    <button type="button" onClick={() => setShowEditor(true)} className="font-semibold text-teal-500 underline">Correct outline</button>
                    {showEditor ? <ImportStructureEditor sections={importPreview.sections} blockWordCounts={importPreview.block_word_counts} blockOpenings={importPreview.block_openings} blockClosings={importPreview.block_closings} blockLocations={importPreview.block_locations} isDark={isDark} onSave={(sections) => { setImportPreview({ ...importPreview, sections }); setShowEditor(false) }} onCancel={() => setShowEditor(false)} /> : null}
                  </div>
                ) : null}
              </div>
            ) : null}
            </>
          )}
        </div>

        <div className="space-y-3">
          <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-white bg-white"}`}>
            <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Processing options</p>
            <div className="mt-3 flex flex-wrap gap-3">
              <ProcessingOption checked={splitIntoChapters} onChange={setSplitIntoChapters} isDark={isDark} label={isScreenplayWorkspace ? "Split screenplay PDFs into scenes" : "Split PDFs into chapters"} help={isScreenplayWorkspace ? "Keeps detected scene headings together. If screenplay formatting is noisy, LoreVia will still build a stable scene order." : "Keeps detected chapters together. If chapter numbering is inconsistent, LoreVia will use its normal sequential split."} infoButtonClass={infoButtonClass} />
              <ProcessingOption checked={chunkLongDocuments} onChange={setChunkLongDocuments} isDark={isDark} label="Chunk long files" help="Breaks long text into smaller pieces (3,500 words per chapter) for easier processing. This may create more chapters than your original manuscript." infoButtonClass={infoButtonClass} />
              {chunkLongDocuments ? <p className={`ml-5 mt-1 text-xs ${isDark ? "text-amber-300" : "text-amber-700"}`}>Warning: This will split long chapters at 3,500 words. A 35,000-word manuscript may become 10+ chapters.</p> : null}
            </div>
            <div className={`mt-4 rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
              <p className="font-semibold">What LoreVia updates</p>
              <p className="mt-1">Character state, relationship extraction, plot-thread analysis, and {storyUnitLabel}-level continuity flags are all rerun from this {storyUnitLabel} ingest.</p>
              {!replaceExisting && selectedExistingBook ? <p className="mt-2 text-xs opacity-80">Suggested next {storyUnitLabel}: {(selectedExistingBook.total_chapters ?? 0) + 1}</p> : null}
            </div>
          </div>

          <ImportOutcome isDark={isDark} chapterReports={chapterReports} storyUnitLabel={storyUnitLabel} storyUnitLabelTitle={storyUnitLabelTitle} />
        </div>
      </div>
    </div>
  )
}

function ProcessingOption({ checked, onChange, isDark, label, help, infoButtonClass }: { checked: boolean; onChange: Dispatch<SetStateAction<boolean>>; isDark: boolean; label: string; help: string; infoButtonClass: string }) {
  return (
    <label className={`flex items-center gap-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="inline-flex items-center gap-1">
        <span>{label}</span>
        <Tooltip content={help}><button type="button" title={help} aria-label={`What ${label} means`} className={infoButtonClass}>i</button></Tooltip>
      </span>
    </label>
  )
}

function ImportOutcome({ isDark, chapterReports, storyUnitLabel, storyUnitLabelTitle }: { isDark: boolean; chapterReports: ChapterConsistencyReport[]; storyUnitLabel: string; storyUnitLabelTitle: string }) {
  const flags = chapterReports.flatMap((report) => report.continuity_flags.map((flag) => ({ report, flag })))
  return (
    <>
      {chapterReports.length > 0 ? (
        <div className={`rounded-xl border p-4 ${isDark ? "border-teal-500/20 bg-teal-500/10" : "border-teal-200 bg-teal-50"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-teal-200" : "text-teal-800"}`}>Latest chapter outcome</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {buildImportOutcomeCards(chapterReports).map((item) => <div key={item.label} className={`rounded-lg border px-3 py-3 ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-white bg-white text-stone-800"}`}><p className="text-lg font-semibold">{item.value}</p><p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{item.label}</p></div>)}
          </div>
        </div>
      ) : (
        <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}><p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Ready for incremental ingest</p><p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>Choose a {storyUnitLabel} number, paste or upload a single {storyUnitLabel}, and LoreVia will return a focused report instead of making you dig through the whole manuscript again.</p></div>
      )}
      {flags.length > 0 ? (
        <div className={`rounded-xl border p-4 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-amber-200" : "text-amber-800"}`}>Fresh {storyUnitLabel} continuity flags</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>These were surfaced directly from the {storyUnitLabel} you just imported, after LoreVia refreshed stored character and story state.</p>
          <div className="mt-3 space-y-2">{flags.map(({ report, flag }, index) => <div key={`${report.chapter_number}-${index}`} className={`rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-white bg-white text-stone-700"}`}><p className="font-semibold">{storyUnitLabelTitle} {report.chapter_number}{report.chapter_title ? ` - ${report.chapter_title}` : ""}</p><p className="mt-1">{flag}</p></div>)}</div>
        </div>
      ) : null}
    </>
  )
}
