"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { zipSync, strToU8 } from "fflate"
import { booksApi } from "@/lib/api/books"
import type { ObsidianPreview, ObsidianPreviewFile } from "@/types/book"

function cleanSegment(value: string) {
  return value.replace(/\.[^.]+$/, "").replace(/^\d+\s*-\s*/, "").trim()
}

function noteTitle(file: ObsidianPreviewFile) {
  return cleanSegment(file.path.split("/").pop() ?? file.path)
}

function folderLabel(file: ObsidianPreviewFile, rootFolder: string) {
  const relative = file.path.replace(`${rootFolder}/`, "")
  const folder = relative.includes("/") ? relative.split("/").slice(0, -1).join("/") : "Root"
  return folder || "Root"
}

function searchBlob(value: string) {
  return value.toLowerCase()
}

function safeSlug(value: string) {
  return value
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .toLowerCase() || "obsidian-vault"
}

export function ObsidianVaultPreview({
  bookId,
  preview,
  isDark,
}: {
  bookId: string
  preview: ObsidianPreview
  isDark: boolean
}) {
  const [query, setQuery] = useState("")
  const [selectedPath, setSelectedPath] = useState<string>("")
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<string | null>(null)
  const saveTimersRef = useRef<Record<string, number>>({})
  const latestDraftRef = useRef<Record<string, string>>({})

  const files = useMemo(
    () => [...preview.files].sort((a, b) => a.path.localeCompare(b.path)),
    [preview.files]
  )

  const filteredFiles = useMemo(() => {
    const trimmed = query.trim()
    if (!trimmed) return files
    const term = searchBlob(trimmed)
    return files.filter((file) => {
      const relPath = file.path.replace(`${preview.root_folder}/`, "")
      const content = drafts[file.path] ?? file.content
      return (
        searchBlob(file.path).includes(term) ||
        searchBlob(relPath).includes(term) ||
        searchBlob(content).includes(term)
      )
    })
  }, [drafts, files, preview.root_folder, query])

  const selectedFile = useMemo(
    () => files.find((file) => file.path === selectedPath) ?? files[0] ?? null,
    [files, selectedPath]
  )

  useEffect(() => {
    if (!selectedFile) return
    if (!selectedPath) {
      setSelectedPath(selectedFile.path)
    }
  }, [selectedFile, selectedPath])

  useEffect(() => {
    if (!selectedFile) return
    setDrafts((current) => {
      if (current[selectedFile.path] !== undefined) return current
      return { ...current, [selectedFile.path]: selectedFile.content }
    })
  }, [selectedFile])

  useEffect(() => {
    if (!selectedFile) return
    if (filteredFiles.length > 0 && !filteredFiles.some((file) => file.path === selectedPath)) {
      setSelectedPath(filteredFiles[0].path)
    }
  }, [filteredFiles, selectedFile, selectedPath])

  const selectedContent = selectedFile ? drafts[selectedFile.path] ?? selectedFile.content : ""
  const selectedHasChanges = selectedFile ? selectedContent !== selectedFile.content : false
  const editedCount = files.filter((file) => (drafts[file.path] ?? file.content) !== file.content).length
  const noteCount = files.length

  useEffect(() => {
    return () => {
      for (const timer of Object.values(saveTimersRef.current)) {
        window.clearTimeout(timer)
      }
      saveTimersRef.current = {}
    }
  }, [])

  useEffect(() => {
    if (!selectedFile) return
    const path = selectedFile.path
    const timer = saveTimersRef.current[path]
    if (!selectedHasChanges) {
      if (timer) {
        window.clearTimeout(timer)
        delete saveTimersRef.current[path]
      }
      return
    }
    if (timer) {
      window.clearTimeout(timer)
    }
    saveTimersRef.current[path] = window.setTimeout(() => {
      delete saveTimersRef.current[path]
      void saveDraft(path, selectedContent)
    }, 700)
  }, [selectedContent, selectedFile, selectedHasChanges])

  const saveDraft = async (path: string, content: string) => {
    latestDraftRef.current[path] = content
    const pending = saveTimersRef.current[path]
    if (pending) {
      window.clearTimeout(pending)
      delete saveTimersRef.current[path]
    }
    const relative = path.replace(`${preview.root_folder}/`, "")
    setStatus(`Saving ${relative}...`)
    try {
      const result = await booksApi.saveCharacterBibleObsidianNote(bookId, { path, content })
      if (latestDraftRef.current[path] !== result.content) {
        return
      }
      setDrafts((current) => ({ ...current, [path]: result.content }))
      setStatus(result.persisted ? `Saved ${relative}` : `Reset ${relative} to the generated version`)
    } catch {
      setStatus(`Could not save ${relative}`)
    }
  }

  const handleSelect = (path: string) => {
    setSelectedPath(path)
    setStatus(null)
  }

  const handleResetCurrent = () => {
    if (!selectedFile) return
    const path = selectedFile.path
    latestDraftRef.current[path] = selectedFile.content
    setDrafts((current) => ({
      ...current,
      [path]: selectedFile.content,
    }))
    setStatus(`Reset ${selectedFile.path.replace(`${preview.root_folder}/`, "")}`)
    void saveDraft(path, selectedFile.content)
  }

  const handleResetAll = () => {
    const next: Record<string, string> = {}
    for (const file of files) {
      latestDraftRef.current[file.path] = file.content
      next[file.path] = file.content
    }
    setDrafts(next)
    setStatus("Reset all notes")
    void Promise.all(files.map((file) => saveDraft(file.path, file.content)))
  }

  const handleSaveCurrent = () => {
    if (!selectedFile) return
    void saveDraft(selectedFile.path, selectedContent)
  }

  const handleDownloadEditedVault = () => {
    const archive = zipSync(
      Object.fromEntries(
        files.map((file) => [file.path, strToU8(drafts[file.path] ?? file.content)])
      ),
      { level: 6 }
    )
    const blob = new Blob([archive as unknown as BlobPart], { type: "application/zip" })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `${safeSlug(preview.root_folder)}-edited.zip`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    setStatus("Downloaded edited vault")
  }

  return (
    <div className={`rounded-[2rem] border p-4 shadow-[0_30px_80px_-44px_rgba(15,23,42,0.75)] ${isDark ? "border-white/10 bg-[linear-gradient(180deg,rgba(10,10,12,0.95),rgba(17,24,39,0.9))]" : "border-stone-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(248,250,252,0.9))]"}`}>
      <div className="flex flex-col gap-4 border-b border-white/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
            <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-sky-300" : "text-sky-600"}`}>Vault export</p>
            <h3 className={`mt-2 font-serif text-3xl tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Vault preview and editor</h3>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
              Browse every exported note, edit the markdown in-app, and export a fresh vault ZIP when you're done.
            </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatPill label="Files" value={String(noteCount)} isDark={isDark} />
          <StatPill label="Edited" value={String(editedCount)} isDark={isDark} />
          <StatPill label="Root" value={preview.root_folder} isDark={isDark} wide />
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className={`rounded-[1.5rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/80"}`}>
          <div className="flex items-center justify-between gap-3 px-1 py-1.5">
            <div>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Vault Map</p>
              <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{filteredFiles.length} notes visible</p>
            </div>
            <button
              type="button"
              onClick={handleResetAll}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
            >
              Reset all
            </button>
          </div>

          <label className={`mt-3 flex items-center gap-2 rounded-[1rem] border px-3 py-2 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
            <svg className={`h-4 w-4 ${isDark ? "text-slate-500" : "text-stone-400"}`} viewBox="0 0 20 20" fill="none">
              <path d="M8.5 15a6.5 6.5 0 1 1 4.56-11.1A6.5 6.5 0 0 1 8.5 15Z" stroke="currentColor" strokeWidth="1.6" />
              <path d="m13.5 13.5 3 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search notes or content"
              className={`w-full bg-transparent text-sm outline-none placeholder:text-slate-400 ${isDark ? "text-slate-100" : "text-stone-900"}`}
            />
          </label>

          <div className="mt-3 max-h-[34rem] space-y-2 overflow-auto pr-1">
            {filteredFiles.length === 0 ? (
              <div className={`rounded-[1rem] border border-dashed px-4 py-8 text-center text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
                No notes match that search.
              </div>
            ) : filteredFiles.map((file) => {
              const active = file.path === selectedFile?.path
              const draft = drafts[file.path] ?? file.content
              const changed = draft !== file.content
              return (
                <button
                  key={file.path}
                  type="button"
                  onClick={() => handleSelect(file.path)}
                  className={`group w-full rounded-[1.15rem] border px-4 py-3 text-left transition ${
                    active
                      ? isDark
                        ? "border-sky-400/35 bg-sky-500/10 shadow-[0_10px_30px_-18px_rgba(56,189,248,0.8)]"
                        : "border-sky-300 bg-sky-50 shadow-sm"
                      : isDark
                        ? "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]"
                        : "border-stone-200 bg-white hover:border-stone-300 hover:bg-stone-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{noteTitle(file)}</p>
                      <p className={`mt-1 truncate text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{file.path.replace(`${preview.root_folder}/`, "")}</p>
                    </div>
                    {changed ? (
                      <span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-[0.16em] ${isDark ? "bg-amber-500/15 text-amber-300" : "bg-amber-100 text-amber-700"}`}>Edited</span>
                    ) : null}
                  </div>
                  <p className={`mt-2 text-[11px] ${isDark ? "text-slate-600" : "text-stone-400"}`}>{folderLabel(file, preview.root_folder)}</p>
                </button>
              )
            })}
          </div>
        </aside>

        <section className={`rounded-[1.5rem] border p-4 ${isDark ? "border-white/10 bg-black/25" : "border-stone-200 bg-white"}`}>
          {selectedFile ? (
            <div className="flex h-full min-h-[42rem] flex-col">
              <div className="flex flex-col gap-4 border-b border-white/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
                <div className="min-w-0">
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Editing</p>
                  <h4 className={`mt-2 truncate font-serif text-2xl ${isDark ? "text-white" : "text-stone-950"}`}>{noteTitle(selectedFile)}</h4>
                  <p className={`mt-1 truncate text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{selectedFile.path.replace(`${preview.root_folder}/`, "")}</p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <StatPill label="Words" value={String(selectedContent.trim() ? selectedContent.trim().split(/\s+/).length : 0)} isDark={isDark} compact />
                  <StatPill label="Chars" value={String(selectedContent.length)} isDark={isDark} compact />
                </div>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_15rem]">
                <div className="space-y-3">
                  <div className={`rounded-[1.25rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                        {selectedHasChanges ? "You have unsaved edits for this note." : "This note matches the exported file."}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                        onClick={() => {
                          const writeText = navigator.clipboard?.writeText
                          if (!writeText) return
                          writeText.call(navigator.clipboard, selectedContent).catch(() => {})
                        }}
                          className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                        >
                          Copy text
                        </button>
                        <button
                          type="button"
                          onClick={handleSaveCurrent}
                          className="rounded-full bg-[linear-gradient(135deg,#334155,#0f766e)] px-3 py-1.5 text-xs font-semibold text-white shadow-[0_12px_30px_-16px_rgba(15,118,110,0.8)] transition hover:translate-y-[-1px]"
                        >
                          Save note
                        </button>
                        <button
                          type="button"
                          onClick={handleResetCurrent}
                          className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                        >
                          Reset file
                        </button>
                        <button
                          type="button"
                          onClick={handleDownloadEditedVault}
                          className="rounded-full bg-[linear-gradient(135deg,#0f766e,#2563eb)] px-3 py-1.5 text-xs font-semibold text-white shadow-[0_12px_30px_-16px_rgba(37,99,235,0.8)] transition hover:translate-y-[-1px]"
                        >
                          Download edited Vault ZIP
                        </button>
                      </div>
                    </div>
                  </div>

                  <textarea
                    value={selectedContent}
                    onChange={(event) => {
                      const value = event.target.value
                      latestDraftRef.current[selectedFile.path] = value
                      setDrafts((current) => ({ ...current, [selectedFile.path]: value }))
                      setStatus(null)
                    }}
                    spellCheck={false}
                    className={`min-h-[30rem] w-full resize-y rounded-[1.2rem] border px-4 py-4 font-mono text-sm leading-7 outline-none transition ${isDark ? "border-white/10 bg-[#050816] text-slate-100 placeholder:text-slate-600 focus:border-sky-400/40" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400 focus:border-sky-300"}`}
                  />
                </div>

                <div className="space-y-3">
                  <div className={`rounded-[1.25rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Note Info</p>
                    <div className="mt-3 space-y-3 text-sm">
                      <InfoRow label="Folder" value={folderLabel(selectedFile, preview.root_folder)} isDark={isDark} />
                      <InfoRow label="Path" value={selectedFile.path.replace(`${preview.root_folder}/`, "")} isDark={isDark} />
                      <InfoRow label="Changes" value={selectedHasChanges ? "Edited" : "Synced"} isDark={isDark} />
                    </div>
                  </div>

                  <div className={`rounded-[1.25rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Notes</p>
                      <ul className={`mt-3 space-y-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                        <li>Use the search box to jump between any exported note.</li>
                        <li>Edit notes directly here, then export the updated vault ZIP.</li>
                        <li>Obsidian will open the edited archive the same way as the original export.</li>
                      </ul>
                  </div>

                  {status ? (
                    <div className={`rounded-[1.25rem] border px-4 py-3 text-sm ${isDark ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                      {status}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <div className={`flex min-h-[42rem] items-center justify-center rounded-[1.5rem] border border-dashed ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
              <p>Select a note to start editing.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function InfoRow({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</span>
      <span className={`max-w-[60%] text-right text-xs leading-5 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{value}</span>
    </div>
  )
}

function StatPill({
  label,
  value,
  isDark,
  compact = false,
  wide = false,
}: {
  label: string
  value: string
  isDark: boolean
  compact?: boolean
  wide?: boolean
}) {
  return (
    <div className={`rounded-[1rem] border px-3 py-2 ${wide ? "min-w-[12rem]" : ""} ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
      <p className={`text-[10px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`${compact ? "mt-1 text-xs" : "mt-1.5 text-sm"} truncate font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
    </div>
  )
}
