import Link from "next/link"
import { useEffect, useRef } from "react"
import type { Route } from "next"

import { LabeledField, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import {
  badgeClass,
  inputClass,
  mutedTextClass,
  primaryButtonClass,
  secondaryButtonClass,
  softPanelClass,
} from "./WorldbuildingWorkspace.helpers"

export function WorldCorpusUploadCard({
  bookId,
  focus,
  isDark,
  uploadLimitNote,
  uploadTitle,
  uploadFiles,
  replaceCorpusOnUpload,
  uploadingFiles,
  onUploadTitleChange,
  onUploadFilesChange,
  onReplaceCorpusOnUploadChange,
  onUploadDocumentFiles,
}: {
  bookId: string
  focus: "editor" | "gap"
  isDark: boolean
  uploadLimitNote: string | null
  uploadTitle: string
  uploadFiles: File[]
  replaceCorpusOnUpload: boolean
  uploadingFiles: boolean
  onUploadTitleChange: (value: string) => void
  onUploadFilesChange: (files: File[]) => void
  onReplaceCorpusOnUploadChange: (value: boolean) => void
  onUploadDocumentFiles: () => void
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  useEffect(() => { if (!uploadFiles.length && fileInput.current) fileInput.current.value = "" }, [uploadFiles.length])
  return (
    <WorkspaceCard
      number="1"
      sectionLabel="World Corpus"
      title="Add or replace reference docs"
      description="Upload your worldbuilding reference materials. Use them as the canon source of truth for comparison."
      isDark={isDark}
      action={focus === "editor" ? (
        <Link href={`/${bookId}/world-gap` as Route} className={secondaryButtonClass(isDark)}>
          Open World Gap Detection
        </Link>
      ) : null}
    >
      <div className="space-y-4">
        {uploadLimitNote ? (
          <div className={`rounded-md border px-4 py-3 text-xs leading-5 ${softPanelClass(isDark)}`}>
            {uploadLimitNote}
          </div>
        ) : null}

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
          <div className="space-y-3">
            <LabeledField label="Upload title" isDark={isDark}>
              <input
                value={uploadTitle}
                onChange={(event) => onUploadTitleChange(event.target.value)}
                className={inputClass(isDark)}
              />
            </LabeledField>

            <div className={`rounded-lg border border-dashed p-4 ${isDark ? "border-white/[0.12] bg-[#07111f]" : "border-stone-300 bg-stone-50"}`}>
              <label className="block cursor-pointer">
                <span className="sr-only">Upload world corpus files</span>
                <input
                  type="file"
                  aria-label="Upload world corpus files"
                  ref={fileInput}
                  multiple
                  onChange={(event) => onUploadFilesChange(Array.from(event.target.files ?? []))}
                  className="block w-full text-sm file:mr-3 file:min-h-11 file:rounded-sm file:border file:border-[rgb(var(--border))] file:bg-[rgb(var(--background))] file:px-3 file:text-[rgb(var(--foreground))]"
                />
                <div className="space-y-2">
                  <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-stone-900"}`}>
                    Choose reference files to import
                  </p>
                  <p className={`text-xs ${mutedTextClass(isDark)}`}>
                    {uploadFiles.length > 0
                      ? `${uploadFiles.length} file${uploadFiles.length === 1 ? "" : "s"} selected`
                      : "Upload reference docs to extend or replace the current world corpus."}
                  </p>
                  {uploadFiles.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {uploadFiles.slice(0, 4).map((file) => (
                        <span key={`${file.name}-${file.size}`} className={badgeClass(isDark)}>
                          {file.name}
                        </span>
                      ))}
                      {uploadFiles.length > 4 ? <span className={badgeClass(isDark)}>+{uploadFiles.length - 4} more</span> : null}
                    </div>
                  ) : null}
                </div>
              </label>
            </div>
          </div>

          <div className="flex flex-col gap-3 lg:min-w-[12rem]">
            <label className={`flex items-start gap-3 rounded-md border px-4 py-3 text-sm ${softPanelClass(isDark)}`}>
              <input
                type="checkbox"
                checked={replaceCorpusOnUpload}
                onChange={(event) => onReplaceCorpusOnUploadChange(event.target.checked)}
                className="mt-0.5"
              />
              <span>
                <span className={`block font-medium ${isDark ? "text-slate-100" : "text-stone-900"}`}>Replace active world corpus</span>
                <span className={`mt-1 block text-xs ${mutedTextClass(isDark)}`}>Use the uploaded files instead of appending to the current corpus.</span>
              </span>
            </label>

            <button
              type="button"
              onClick={onUploadDocumentFiles}
              disabled={uploadingFiles || uploadFiles.length === 0}
              className={primaryButtonClass("teal")}
            >
              {uploadingFiles ? "Uploading..." : replaceCorpusOnUpload ? "Replace corpus" : "Add to corpus"}
            </button>
          </div>
        </div>
      </div>
    </WorkspaceCard>
  )
}
