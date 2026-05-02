"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { ObsidianVaultPreview } from "@/components/reader/ObsidianVaultPreview"
import { booksApi } from "@/lib/api/books"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, ObsidianPreview } from "@/types/book"

type ExportFormat = "md" | "pdf" | "docx" | "obsidian_folder"
type ManuscriptExportFormat = "pdf" | "docx" | "epub" | "obsidian"

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

function safeFileBase(value: string | undefined, fallback: string) {
  return (value || fallback).replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-") || fallback
}

export default function ExportStudioPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [book, setBook] = useState<Book | null>(null)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<string | null>(null)
  const [bibleFormat, setBibleFormat] = useState<ExportFormat>("obsidian_folder")
  const [manuscriptFormat, setManuscriptFormat] = useState<ManuscriptExportFormat>("docx")
  const [exporting, setExporting] = useState<string | null>(null)
  const [obsidianPreview, setObsidianPreview] = useState<ObsidianPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [manuscriptFiles, setManuscriptFiles] = useState<File[]>([])
  const [notesArchive, setNotesArchive] = useState<File | null>(null)
  const [worldFiles, setWorldFiles] = useState<File[]>([])
  const [importing, setImporting] = useState<string | null>(null)
  const manuscriptInputRef = useRef<HTMLInputElement | null>(null)
  const notesInputRef = useRef<HTMLInputElement | null>(null)
  const worldInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    booksApi.get(bookId)
      .then((value) => {
        if (!active) return
        setBook(value)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [bookId])

  const formatCards = useMemo(
    () => [
      { value: "obsidian_folder" as const, label: "Vault ZIP", meta: "Folder structure for note apps" },
      { value: "docx" as const, label: "DOCX", meta: "Word-ready bible" },
      { value: "pdf" as const, label: "PDF", meta: "Shareable reference" },
      { value: "md" as const, label: "Markdown", meta: "Plain text export" },
    ],
    []
  )

  const exportCharacterBible = async () => {
    if (!book) return
    setExporting("character-bible")
    setStatus(null)
    try {
      const blob = await booksApi.exportCharacterBible(bookId, bibleFormat)
      const extension = bibleFormat === "obsidian_folder" ? "zip" : bibleFormat
      downloadBlob(blob, `${safeFileBase(book.title, "lorevia")}-character-bible.${extension}`)
      setStatus(`Downloaded character bible as ${extension.toUpperCase()}.`)
    } catch {
      setStatus("Could not export the character bible.")
    } finally {
      setExporting(null)
    }
  }

  const exportManuscript = async () => {
    if (!book) return
    setExporting("manuscript")
    setStatus(null)
    try {
      const blob = await booksApi.exportManuscript(bookId, manuscriptFormat)
      const extension = manuscriptFormat === "obsidian" ? "zip" : manuscriptFormat
      downloadBlob(blob, `${safeFileBase(book.title, "lorevia")}-manuscript.${extension}`)
      setStatus(`Downloaded manuscript as ${extension.toUpperCase()}.`)
    } catch {
      setStatus("Could not export the manuscript.")
    } finally {
      setExporting(null)
    }
  }

  const exportNotesZip = async () => {
    if (!book) return
    setExporting("notes")
    setStatus(null)
    try {
      const blob = await booksApi.exportObsidianNotes(bookId)
      downloadBlob(blob, `${safeFileBase(book.title, "lorevia")}-notes.zip`)
      setStatus("Downloaded notes workspace ZIP.")
    } catch {
      setStatus("Could not export the notes workspace.")
    } finally {
      setExporting(null)
    }
  }

  const openPreview = async () => {
    setPreviewLoading(true)
    setStatus(null)
    try {
      const preview = await booksApi.previewCharacterBibleObsidian(bookId)
      setObsidianPreview(preview)
      setStatus("Loaded the character bible file preview.")
    } catch {
      setStatus("Could not load the vault preview.")
    } finally {
      setPreviewLoading(false)
    }
  }

  const importManuscript = async () => {
    if (!manuscriptFiles.length || !book) return
    setImporting("manuscript")
    setStatus(null)
    try {
      const result = await booksApi.importManuscript(bookId, {
        files: manuscriptFiles,
        chunkLongDocuments: true,
        replaceExisting: false,
        workType: book.work_type,
      })
      setStatus(`Imported ${result.imported_chapters.length || result.total_chapters} chapter files into this book.`)
      setManuscriptFiles([])
    } catch {
      setStatus("Could not import manuscript files into this book.")
    } finally {
      setImporting(null)
    }
  }

  const importNotesZip = async () => {
    if (!notesArchive) return
    setImporting("notes")
    setStatus(null)
    try {
      await booksApi.importObsidianNotes(bookId, notesArchive)
      setStatus(`Imported ${notesArchive.name} into the notes workspace.`)
      setNotesArchive(null)
    } catch {
      setStatus("Could not import that notes ZIP.")
    } finally {
      setImporting(null)
    }
  }

  const importWorldDocs = async () => {
    if (!worldFiles.length) return
    setImporting("world")
    setStatus(null)
    try {
      await worldBuildingApi.uploadDocuments(bookId, { files: worldFiles })
      setStatus(`Imported ${worldFiles.length} worldbuilding file${worldFiles.length === 1 ? "" : "s"}.`)
      setWorldFiles([])
    } catch {
      setStatus("Could not import the worldbuilding files.")
    } finally {
      setImporting(null)
    }
  }

  if (loading || !book) {
    return <div className={`flex min-h-screen items-center justify-center ${isDark ? "bg-[#030711] text-slate-400" : "bg-[#f7f5ef] text-stone-500"}`}>Loading export studio...</div>
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#030711_0%,#07111c_52%,#0b1521_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#f8f4eb_0%,#eef5ef_52%,#edf2f8_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-[96rem] px-4 pb-20 pt-8 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="export"
            isDark={isDark}
            title="Author tools"
            description="Import new material, export structured references, and preview the exact vault files before you leave the page."
          />

          <main className="space-y-6">
            <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-[linear-gradient(180deg,rgba(8,12,24,0.96),rgba(12,20,34,0.9))]" : "border-white/70 bg-white/88"}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.32em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>Import & Export</p>
                  <h1 className={`mt-3 font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>{book.title}</h1>
                  <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    Keep imports and exports separate, keep the vault structure visible, and ship the exact files you want instead of bouncing through modal dialogs.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link href={`/${bookId}/notes`} className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}>
                    Open notes workspace
                  </Link>
                  <Link href={`/${bookId}/manuscript`} className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/5 text-slate-200" : "bg-white text-stone-700"}`}>
                    Open manuscript
                  </Link>
                </div>
              </div>
            </section>

            <div className="grid gap-6 2xl:grid-cols-2">
              <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Import</p>
                <h2 className={`mt-3 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Bring material into this book</h2>
                <div className="mt-6 grid gap-4">
                  <ImportCard
                    isDark={isDark}
                    title="Story manuscript"
                    description="Append or sync chapter files into this existing book."
                    files={manuscriptFiles}
                    buttonLabel={importing === "manuscript" ? "Importing..." : "Import manuscript files"}
                    onChoose={() => manuscriptInputRef.current?.click()}
                    onRun={() => void importManuscript()}
                    disabled={!manuscriptFiles.length || importing !== null}
                  />
                  <input
                    ref={manuscriptInputRef}
                    type="file"
                    multiple
                    accept=".docx,.doc,.pdf,.txt,.md,.epub"
                    className="hidden"
                    onChange={(event) => setManuscriptFiles(Array.from(event.target.files ?? []))}
                  />

                  <ImportCard
                    isDark={isDark}
                    title="Vault notes ZIP"
                    description="Import a note vault archive directly into the editable notes workspace."
                    files={notesArchive ? [notesArchive] : []}
                    buttonLabel={importing === "notes" ? "Importing..." : "Import notes ZIP"}
                    onChoose={() => notesInputRef.current?.click()}
                    onRun={() => void importNotesZip()}
                    disabled={!notesArchive || importing !== null}
                  />
                  <input
                    ref={notesInputRef}
                    type="file"
                    accept=".zip,application/zip"
                    className="hidden"
                    onChange={(event) => setNotesArchive(event.target.files?.[0] ?? null)}
                  />

                  <ImportCard
                    isDark={isDark}
                    title="Worldbuilding docs"
                    description="Add lore files that your world gap and wiki tools can analyze separately from the manuscript."
                    files={worldFiles}
                    buttonLabel={importing === "world" ? "Importing..." : "Import worldbuilding"}
                    onChoose={() => worldInputRef.current?.click()}
                    onRun={() => void importWorldDocs()}
                    disabled={!worldFiles.length || importing !== null}
                  />
                  <input
                    ref={worldInputRef}
                    type="file"
                    multiple
                    accept=".docx,.doc,.pdf,.txt,.md"
                    className="hidden"
                    onChange={(event) => setWorldFiles(Array.from(event.target.files ?? []))}
                  />
                </div>
              </section>

              <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>Export</p>
                <h2 className={`mt-3 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Ship clean outputs</h2>

                <div className="mt-6 space-y-5">
                  <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Character bible export</p>
                    <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      {formatCards.map((item) => (
                        <button
                          key={item.value}
                          type="button"
                          onClick={() => setBibleFormat(item.value)}
                          className={`rounded-[1.1rem] border px-4 py-3 text-left transition ${
                            bibleFormat === item.value
                              ? isDark
                                ? "border-violet-400/40 bg-violet-500/10"
                                : "border-violet-200 bg-violet-50"
                              : isDark
                                ? "border-white/10 bg-black/20 hover:bg-white/[0.04]"
                                : "border-stone-200 bg-white hover:bg-stone-50"
                          }`}
                        >
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{item.label}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{item.meta}</p>
                        </button>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => void exportCharacterBible()}
                        disabled={exporting !== null}
                        className="rounded-[1rem] bg-[linear-gradient(135deg,#6d28d9,#4f46e5)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
                      >
                        {exporting === "character-bible" ? "Preparing..." : "Export character bible"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void openPreview()}
                        disabled={previewLoading}
                        className={`rounded-[1rem] border px-5 py-3 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                      >
                        {previewLoading ? "Loading preview..." : "Preview export files"}
                      </button>
                    </div>
                  </div>

                  <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Manuscript export</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(["docx", "pdf", "epub", "obsidian"] as ManuscriptExportFormat[]).map((format) => (
                        <button
                          key={format}
                          type="button"
                          onClick={() => setManuscriptFormat(format)}
                          className={`rounded-full border px-4 py-2 text-sm transition ${
                            manuscriptFormat === format
                              ? isDark
                                ? "border-amber-400/35 bg-amber-500/10 text-amber-100"
                                : "border-amber-200 bg-amber-50 text-amber-800"
                              : isDark
                                ? "border-white/10 bg-black/20 text-slate-200"
                                : "border-stone-200 bg-white text-stone-700"
                          }`}
                        >
                          {format === "obsidian" ? "Vault ZIP" : format.toUpperCase()}
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => void exportManuscript()}
                      disabled={exporting !== null}
                      className="mt-4 rounded-[1rem] bg-[linear-gradient(135deg,#f59e0b,#d97706)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      {exporting === "manuscript" ? "Preparing..." : "Export manuscript"}
                    </button>
                  </div>

                  <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Notes workspace export</p>
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                      Download the editable vault notes separately from the generated character bible files.
                    </p>
                    <button
                      type="button"
                      onClick={() => void exportNotesZip()}
                      disabled={exporting !== null}
                      className="mt-4 rounded-[1rem] bg-[linear-gradient(135deg,#0f766e,#2563eb)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      {exporting === "notes" ? "Preparing..." : "Export notes ZIP"}
                    </button>
                  </div>
                </div>
              </section>
            </div>

            {status ? (
              <div className={`rounded-[1.4rem] border px-4 py-3 text-sm ${isDark ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                {status}
              </div>
            ) : null}

            {obsidianPreview ? (
              <ObsidianVaultPreview bookId={bookId} preview={obsidianPreview} isDark={isDark} />
            ) : null}
          </main>
        </div>
      </div>
    </div>
  )
}

function ImportCard({
  isDark,
  title,
  description,
  files,
  buttonLabel,
  onChoose,
  onRun,
  disabled,
}: {
  isDark: boolean
  title: string
  description: string
  files: File[]
  buttonLabel: string
  onChoose: () => void
  onRun: () => void
  disabled: boolean
}) {
  return (
    <article className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</p>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{description}</p>
      <div className={`mt-3 rounded-[1rem] border border-dashed px-4 py-3 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
        {files.length ? files.map((file) => file.name).join(", ") : "No files selected yet."}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={onChoose} className={`rounded-[1rem] border px-4 py-2.5 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
          Choose files
        </button>
        <button type="button" onClick={onRun} disabled={disabled} className="rounded-[1rem] bg-[linear-gradient(135deg,#059669,#0f766e)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
          {buttonLabel}
        </button>
      </div>
    </article>
  )
}
