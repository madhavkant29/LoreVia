"use client"

import axios from "axios"
import dynamic from "next/dynamic"
import { useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { strToU8, zipSync } from "fflate"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { READER_FONT_OPTIONS } from "@/lib/utils/readerTypography"
import type { ReaderFontFamily } from "@/lib/utils/readerTypography"
import type { Book, VaultPreview, VaultNote } from "@/types/book"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { CardSkeleton, RowSkeleton, SidebarSkeleton, Skeleton } from "@/components/ui/Skeleton"

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <SidebarSkeleton />,
  }
)

const VaultPreview = dynamic(
  () => import("@/components/reader/VaultPreview").then((module) => module.VaultPreview),
  {
    loading: () => null,
  }
)

type ExportFormat = "md" | "pdf" | "docx" | "vault_folder"
type ManuscriptExportFormat = "pdf" | "docx" | "epub" | "vault"

const MANUSCRIPT_EXPORT_FORMATS: ManuscriptExportFormat[] = ["docx", "pdf", "epub", "vault"]

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

async function blobToBytes(blob: Blob) {
  return new Uint8Array(await blob.arrayBuffer())
}

function getApiErrorDetail(error: unknown) {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : null
}

export default function ExportStudioPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: book = null, isLoading: loading } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const [status, setStatus] = useState<string | null>(null)
  const [bibleFormat, setBibleFormat] = useState<ExportFormat>("vault_folder")
  const [manuscriptFormat, setManuscriptFormat] = useState<ManuscriptExportFormat>("docx")
  const [exportFontFamily, setExportFontFamily] = useState<ReaderFontFamily>("serif")
  const [includeSceneMetadata, setIncludeSceneMetadata] = useState(true)
  const [includeTableOfContents, setIncludeTableOfContents] = useState(false)
  const [exporting, setExporting] = useState<string | null>(null)
  const [vaultPreview, setVaultPreview] = useState<VaultPreview | null>(null)
  const [bibleNotes, setBibleNotes] = useState<VaultNote[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [manuscriptFiles, setManuscriptFiles] = useState<File[]>([])
  const [notesArchive, setNotesArchive] = useState<File | null>(null)
  const [worldFiles, setWorldFiles] = useState<File[]>([])
  const [importing, setImporting] = useState<string | null>(null)
  const manuscriptInputRef = useRef<HTMLInputElement | null>(null)
  const notesInputRef = useRef<HTMLInputElement | null>(null)
  const worldInputRef = useRef<HTMLInputElement | null>(null)

  const formatCards = useMemo(
    () => [
      { value: "vault_folder" as const, label: "Vault ZIP", meta: "Folder structure for note apps" },
      { value: "docx" as const, label: "DOCX", meta: "Word-ready bible" },
      { value: "pdf" as const, label: "PDF", meta: "Shareable reference" },
      { value: "md" as const, label: "Markdown", meta: "Plain text export" },
    ],
    []
  )

  const selectedExportFontLabel = useMemo(
    () => READER_FONT_OPTIONS.find((option) => option.value === exportFontFamily)?.label ?? "Serif",
    [exportFontFamily]
  )

  const exportBundleFontNotice = useMemo(
    () => [
      "LoreVia Font Notice",
      "",
      `Selected export font: ${selectedExportFontLabel}`,
      "",
      "DOCX and EPUB exports declare the selected font family. PDF exports use safe built-in PDF mappings unless an open font file is explicitly bundled.",
      "Old Style Serif is a fallback stack and LoreVia does not redistribute proprietary Apple, Microsoft, Monotype, or other system font files.",
      "EB Garamond is licensed under the SIL Open Font License, Version 1.1. Copyright 2017 The EB Garamond Project Authors. License: https://openfontlicense.org.",
    ].join("\n"),
    [selectedExportFontLabel]
  )

  const exportCharacterBible = async () => {
    if (!book) return
    setExporting("character-bible")
    setStatus(null)
    try {
      const blob = await booksApi.exportCharacterBible(bookId, bibleFormat, exportFontFamily)
      const extension = bibleFormat === "vault_folder" ? "zip" : bibleFormat
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
      const blob = await booksApi.exportManuscript(bookId, manuscriptFormat, "standard_manuscript", includeSceneMetadata, exportFontFamily, includeTableOfContents)
      const extension = manuscriptFormat === "vault" ? "zip" : manuscriptFormat
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
      const blob = await booksApi.exportVaultNotes(bookId)
      downloadBlob(blob, `${safeFileBase(book.title, "lorevia")}-notes.zip`)
      setStatus("Downloaded notes workspace ZIP.")
    } catch {
      setStatus("Could not export the notes workspace.")
    } finally {
      setExporting(null)
    }
  }

  const exportAllDocuments = async () => {
    if (!book) return
    setExporting("all")
    setStatus(null)
    try {
      const base = safeFileBase(book.title, "lorevia")
      const files: Record<string, Uint8Array> = {
        "FONT-NOTICE.txt": strToU8(exportBundleFontNotice),
      }
      for (const format of formatCards.map((item) => item.value)) {
        const blob = await booksApi.exportCharacterBible(bookId, format, exportFontFamily)
        const extension = format === "vault_folder" ? "zip" : format
        files[`character-bible/${base}-character-bible.${extension}`] = await blobToBytes(blob)
      }
      for (const format of MANUSCRIPT_EXPORT_FORMATS) {
        const blob = await booksApi.exportManuscript(bookId, format, "standard_manuscript", includeSceneMetadata, exportFontFamily, includeTableOfContents)
        const extension = format === "vault" ? "zip" : format
        files[`manuscript/${base}-manuscript.${extension}`] = await blobToBytes(blob)
      }
      const notesBlob = await booksApi.exportVaultNotes(bookId)
      files[`notes/${base}-notes.zip`] = await blobToBytes(notesBlob)
      const archive = zipSync(files)
      downloadBlob(new Blob([archive as unknown as BlobPart], { type: "application/zip" }), `${base}-all-exports.zip`)
      setStatus("Downloaded one ZIP with all manuscript, character bible, and notes export files.")
    } catch {
      setStatus("Could not export every document. Try the single export buttons for any failed format.")
    } finally {
      setExporting(null)
    }
  }

  const openPreview = async () => {
    setPreviewLoading(true)
    setStatus(null)
    try {
      const [preview, savedNotes] = await Promise.all([
        booksApi.previewCharacterBibleVault(bookId),
        booksApi.listCharacterBibleVaultNotes(bookId).catch(() => []),
      ])
      setVaultPreview(preview)
      setBibleNotes(savedNotes)
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
      await booksApi.importVaultNotes(bookId, notesArchive)
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
    } catch (error) {
      setStatus(getApiErrorDetail(error) ?? "Could not import the worldbuilding files.")
    } finally {
      setImporting(null)
    }
  }

  if (loading || !book) {
    return <ExportStudioSkeleton isDark={isDark} />
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#11191a] text-slate-100" : "bg-[#f4f5f3] text-stone-950"}`}>
      <div className="mx-auto max-w-[96rem] px-4 pb-20 pt-8 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="export"
            isDark={isDark}
            bookData={book}
            title="Author tools"
            description="Import new material, export structured references, and preview the exact vault files before you leave the page."
            variant="rail"
            railSize="compact"
          />

          <main className="space-y-6">
            <WorkspaceFamilyHeader
              active="export"
              bookId={bookId}
              family="publish-export"
              title={book.title}
              description="Keep imports and exports separate, keep the vault structure visible, and ship the exact files you intend to use."
              actions={(
                <>
                  <Link href={`/${bookId}/notes`} className={`rounded-md px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}>
                    Open notes workspace
                  </Link>
                  <Link href={`/${bookId}/manuscript`} className={`rounded-md px-4 py-2 text-sm font-medium ${isDark ? "bg-white/5 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>
                    Open manuscript
                  </Link>
                </>
              )}
            />

            <div className="grid gap-6 2xl:grid-cols-2">
              <section className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Import</p>
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

              <section className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>Export</p>
                <h2 className={`mt-3 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Ship clean outputs</h2>

                <div className="mt-6 space-y-5">
                  <div className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                      <label className="block">
                        <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Export font</span>
                        <select
                          value={exportFontFamily}
                          onChange={(event) => setExportFontFamily(event.target.value as ReaderFontFamily)}
                          className={`mt-2 min-h-11 w-full rounded-md border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
                            isDark ? "border-white/10 bg-black/30 text-slate-100" : "border-stone-200 bg-white text-stone-800"
                          }`}
                        >
                          {READER_FONT_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        onClick={() => void exportAllDocuments()}
                        disabled={exporting !== null}
                        className="inline-flex min-h-11 items-center justify-center rounded-md bg-stone-900 px-5 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:opacity-60 dark:bg-white dark:text-stone-950 dark:hover:bg-slate-200"
                      >
                        {exporting === "all" ? "Preparing all..." : "Export everything"}
                      </button>
                    </div>
                    <p className={`mt-3 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      DOCX and EPUB declare this font family. PDF exports use safe built-in PDF mappings, and ZIP exports include a font notice. Proprietary system font files are not redistributed.
                    </p>
                  </div>

                  <div className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Character bible export</p>
                    <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      {formatCards.map((item) => (
                        <button
                          key={item.value}
                          type="button"
                          onClick={() => setBibleFormat(item.value)}
                          className={`rounded-md border px-4 py-3 text-left transition ${
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
                        className="rounded-md bg-violet-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-600 disabled:opacity-60"
                      >
                        {exporting === "character-bible" ? "Preparing..." : "Export character bible"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void openPreview()}
                        disabled={previewLoading}
                        className={`rounded-md border px-5 py-3 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                      >
                        {previewLoading ? "Loading preview..." : "Preview export files"}
                      </button>
                    </div>
                    {bibleNotes.length > 0 ? (
                      <div className={`mt-4 rounded-md border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Saved bible note overrides</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {bibleNotes.slice(0, 8).map((note) => (
                            <span key={note.id} className={`rounded-md px-2.5 py-1 text-xs ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                              {note.path}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>

                  <div className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Manuscript export</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {MANUSCRIPT_EXPORT_FORMATS.map((format) => (
                        <button
                          key={format}
                          type="button"
                          onClick={() => setManuscriptFormat(format)}
                          className={`rounded-md border px-4 py-2 text-sm transition ${
                            manuscriptFormat === format
                              ? isDark
                                ? "border-amber-400/35 bg-amber-500/10 text-amber-100"
                                : "border-amber-200 bg-amber-50 text-amber-800"
                              : isDark
                                ? "border-white/10 bg-black/20 text-slate-200"
                                : "border-stone-200 bg-white text-stone-700"
                          }`}
                        >
                          {format === "vault" ? "Vault ZIP" : format.toUpperCase()}
                        </button>
                      ))}
                    </div>
                    <label className={`mt-4 flex items-start gap-3 rounded-md border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                      <input
                        type="checkbox"
                        checked={includeSceneMetadata}
                        onChange={(event) => setIncludeSceneMetadata(event.target.checked)}
                        className="mt-1 h-4 w-4 rounded border-stone-300"
                      />
                      <span>
                        <span className="block font-semibold">Include scene metadata</span>
                        <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                          Disable for clean prose with scene breaks rendered as ***.
                        </span>
                      </span>
                    </label>
                    <label className={`mt-3 flex items-start gap-3 rounded-md border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                      <input
                        type="checkbox"
                        checked={includeTableOfContents}
                        onChange={(event) => setIncludeTableOfContents(event.target.checked)}
                        className="mt-1 h-4 w-4 rounded border-stone-300"
                      />
                      <span>
                        <span className="block font-semibold">Add table of contents</span>
                        <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                          Inserts a TOC after the cover page. PDF exports include generated page numbers; Word updates page numbers when the field refreshes.
                        </span>
                      </span>
                    </label>
                    <button
                      type="button"
                      onClick={() => void exportManuscript()}
                      disabled={exporting !== null}
                      className="mt-4 rounded-md bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60"
                    >
                      {exporting === "manuscript" ? "Preparing..." : "Export manuscript"}
                    </button>
                  </div>

                  <div className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Notes workspace export</p>
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                      Download the editable vault notes separately from the generated character bible files.
                    </p>
                    <button
                      type="button"
                      onClick={() => void exportNotesZip()}
                      disabled={exporting !== null}
                      className="mt-4 rounded-md bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60"
                    >
                      {exporting === "notes" ? "Preparing..." : "Export notes ZIP"}
                    </button>
                  </div>
                </div>
              </section>
            </div>

            {status ? (
              <div className={`rounded-lg border px-4 py-3 text-sm ${isDark ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                {status}
              </div>
            ) : null}

            {vaultPreview ? (
              <VaultPreview bookId={bookId} preview={vaultPreview} isDark={isDark} />
            ) : null}
          </main>
        </div>
      </div>
    </div>
  )
}

function ExportStudioSkeleton({ isDark }: { isDark: boolean }) {
  return (
    <div className={`min-h-screen ${isDark ? "bg-[#11191a] text-slate-100" : "bg-[#f4f5f3] text-stone-950"}`}>
      <div className="mx-auto max-w-[96rem] px-4 pb-20 pt-8 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <SidebarSkeleton />
          <main className="space-y-6" role="status" aria-label="Loading export studio" aria-busy="true">
            <span className="sr-only">Loading export studio</span>
            <section className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
              <Skeleton className="h-4 w-28" />
              <Skeleton className="mt-4 h-8 w-64 max-w-full" />
              <Skeleton className="mt-3 h-4 w-full max-w-2xl" />
              <div className="mt-5 flex flex-wrap gap-3">
                <Skeleton className="h-10 w-36 rounded-md" />
                <Skeleton className="h-10 w-32 rounded-md" />
              </div>
            </section>
            <div className="grid gap-6 2xl:grid-cols-2">
              <CardSkeleton className="min-h-[28rem]" />
              <div className="space-y-5">
                <CardSkeleton />
                <RowSkeleton />
                <RowSkeleton />
              </div>
            </div>
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
    <article className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</p>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{description}</p>
      <div className={`mt-3 rounded-md border border-dashed px-4 py-3 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
        {files.length ? files.map((file) => file.name).join(", ") : "No files selected yet."}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={onChoose} className={`rounded-md border px-4 py-2.5 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
          Choose files
        </button>
        <button type="button" onClick={onRun} disabled={disabled} className="rounded-md bg-[#1f615d] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60">
          {buttonLabel}
        </button>
      </div>
    </article>
  )
}
