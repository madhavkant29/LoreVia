"use client"

import axios from "axios"
import dynamic from "next/dynamic"
import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { strToU8, zipSync } from "fflate"

import { booksApi } from "@/lib/api/books"
import { capture } from "@/lib/analytics/posthog"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { READER_FONT_OPTIONS } from "@/lib/utils/readerTypography"
import type { ReaderFontFamily } from "@/lib/utils/readerTypography"
import type { Book, NovelEpubMetadata, NovelExportPreset, NovelFrontMatter, NovelImagePlacement, VaultPreview, VaultNote, WriterWorkspace } from "@/types/book"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { CardSkeleton, RowSkeleton, SidebarSkeleton, Skeleton } from "@/components/ui/Skeleton"
import { Tooltip } from "@/components/ui/Tooltip"
import { WorkflowBridgePanel } from "@/components/author/WorkflowBridgePanel"

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
type NovelExportFormat = "pdf" | "docx" | "epub"

const MANUSCRIPT_EXPORT_FORMATS: ManuscriptExportFormat[] = ["docx", "pdf", "epub", "vault"]
const NOVEL_EXPORT_FORMATS: NovelExportFormat[] = ["pdf", "docx", "epub"]
const NOVEL_EXPORT_PRESETS: Array<{ value: NovelExportPreset; label: string; meta: string }> = [
 { value: "standard_novel", label: "Standard novel", meta: "A5 pages, Garamond, compact margins" },
 { value: "trade_novel", label: "Trade paperback", meta: "6x9 print-ready trim and balanced margins" },
 { value: "large_print", label: "Large print", meta: "Letter pages, Georgia, larger text" },
 { value: "ebook_optimized", label: "eBook optimized", meta: "Tighter digital reading layout" },
]
const NOVEL_IMAGE_PLACEMENTS: Array<{ value: NovelImagePlacement; label: string; meta: string }> = [
 { value: "inline", label: "Inline markers", meta: "Place images at stored image markers" },
 { value: "end", label: "Chapter end", meta: "Place images after chapter text" },
 { value: "plates", label: "Image plates", meta: "Start each image on its own page/plate" },
]
const EMPTY_NOVEL_FRONT_MATTER: NovelFrontMatter = {
 dedication: "",
 acknowledgements: "",
 copyright_page: "",
 about_author: "",
 series_book_list: "",
}
const EMPTY_NOVEL_EPUB_METADATA: NovelEpubMetadata = {
 publisher: "",
 language: "en",
 isbn: "",
 description: "",
 series_name: "",
 series_number: "",
}

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
 const userTier = useAuthStore((state) => state.user?.tier)
 const canUseAuthorTools = canUseAuthorFeatures(userTier)
 const isDark = theme === "dark"
 const { data: book = null, isLoading: loading } = useQuery<Book | null>({
 queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
 queryFn: () => booksApi.get(bookId),
 })
 const { data: writerWorkspace = null } = useQuery<WriterWorkspace | null>({
 queryKey: asQueryKey(bookCacheKey(bookId, "writer-workspace")),
 queryFn: () => booksApi.getWriterWorkspace(bookId),
 enabled: Boolean(bookId),
 })
 const [status, setStatus] = useState<string | null>(null)
 const [bibleFormat, setBibleFormat] = useState<ExportFormat>("vault_folder")
 const [manuscriptFormat, setManuscriptFormat] = useState<ManuscriptExportFormat>("docx")
 const [novelFormat, setNovelFormat] = useState<NovelExportFormat>("pdf")
 const [novelPreset, setNovelPreset] = useState<NovelExportPreset>("standard_novel")
 const [novelPreface, setNovelPreface] = useState("")
 const [novelFrontMatter, setNovelFrontMatter] = useState<NovelFrontMatter>(EMPTY_NOVEL_FRONT_MATTER)
 const [novelEpubMetadata, setNovelEpubMetadata] = useState<NovelEpubMetadata>(EMPTY_NOVEL_EPUB_METADATA)
 const [includeNovelImages, setIncludeNovelImages] = useState(false)
 const [novelImagePlacement, setNovelImagePlacement] = useState<NovelImagePlacement>("inline")
  const [includeNovelImageCaptions, setIncludeNovelImageCaptions] = useState(false)
 const [previewNovelExport, setPreviewNovelExport] = useState(false)
 const [savingNovelPreface, setSavingNovelPreface] = useState(false)
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

 useEffect(() => {
 setNovelPreface(writerWorkspace?.novel_preface ?? "")
 setNovelFrontMatter({ ...EMPTY_NOVEL_FRONT_MATTER, ...(writerWorkspace?.novel_front_matter ?? {}) })
 setNovelEpubMetadata({ ...EMPTY_NOVEL_EPUB_METADATA, ...(writerWorkspace?.novel_epub_metadata ?? {}) })
 }, [writerWorkspace?.novel_epub_metadata, writerWorkspace?.novel_front_matter, writerWorkspace?.novel_preface])

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
 capture("first_export_completed", { book_id: bookId, export_kind: "character_bible", format: extension })
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
 capture("first_export_completed", { book_id: bookId, export_kind: "manuscript", format: extension })
 setStatus(`Downloaded manuscript as ${extension.toUpperCase()}.`)
 } catch {
 setStatus("Could not export the manuscript.")
 } finally {
 setExporting(null)
 }
 }

 const saveNovelSettings = async (
 nextPreface = novelPreface,
 nextFrontMatter = novelFrontMatter,
 nextEpubMetadata = novelEpubMetadata
 ) => {
 if (!book) return
 setSavingNovelPreface(true)
 setStatus(null)
 try {
 const result = await booksApi.saveNovelSettings(bookId, {
 preface: nextPreface,
 front_matter: nextFrontMatter,
 epub_metadata: nextEpubMetadata,
 })
 setNovelPreface(result.preface)
 setNovelFrontMatter(result.front_matter)
 setNovelEpubMetadata(result.epub_metadata)
 setStatus("Saved novel export settings.")
 } catch {
 setStatus("Could not save the novel export settings.")
 } finally {
 setSavingNovelPreface(false)
 }
 }

 const exportNovel = async () => {
 if (!book) return
 setExporting("novel")
 setStatus(null)
 try {
 const blob = await booksApi.exportNovel(bookId, novelFormat, novelPreset, includeNovelImages, exportFontFamily, {
 imagePlacement: novelImagePlacement,
 includeImageCaptions: includeNovelImageCaptions,
 previewChapters: previewNovelExport ? 2 : null,
 })
 downloadBlob(blob, `${safeFileBase(book.title, "lorevia")}-${previewNovelExport ? "novel-preview" : "novel"}.${novelFormat}`)
 capture("first_export_completed", { book_id: bookId, export_kind: previewNovelExport ? "novel_preview" : "novel", format: novelFormat })
 setStatus(previewNovelExport ? `Downloaded first 2-chapter sample as ${novelFormat.toUpperCase()}.` : `Downloaded novel export as ${novelFormat.toUpperCase()}.`)
 } catch {
 setStatus("Could not export the reader-ready novel.")
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
 capture("first_export_completed", { book_id: bookId, export_kind: "notes", format: "zip" })
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
 for (const format of NOVEL_EXPORT_FORMATS) {
 const blob = await booksApi.exportNovel(bookId, format, novelPreset, includeNovelImages, exportFontFamily, {
 imagePlacement: novelImagePlacement,
 includeImageCaptions: includeNovelImageCaptions,
 previewChapters: previewNovelExport ? 2 : null,
 })
 files[`novel/${base}-${previewNovelExport ? "novel-preview" : "novel"}.${format}`] = await blobToBytes(blob)
 }
 const notesBlob = await booksApi.exportVaultNotes(bookId)
 files[`notes/${base}-notes.zip`] = await blobToBytes(notesBlob)
 const archive = zipSync(files)
 downloadBlob(new Blob([archive as unknown as BlobPart], { type: "application/zip" }), `${base}-all-exports.zip`)
 setStatus("Downloaded one ZIP with all manuscript, novel, character bible, and notes export files.")
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
 {canUseAuthorTools ? (
 <>
 <Link href={`/${bookId}/notes`} className={` px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}>
 Open notes workspace
 </Link>
 <Link href={`/${bookId}/manuscript`} className={` px-4 py-2 text-sm font-medium ${isDark ? "bg-white/5 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>
 Open manuscript
 </Link>
 </>
 ) : null}
 </>
 )}
 />
 {!canUseAuthorTools ? (
 <div className={` border px-5 py-4 text-sm leading-6 ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`} role="status">
 Free accounts can export the manuscript files for owned projects. Import, notes, character bible, and bulk author exports require an active trial, Author, or Architect plan.
 </div>
 ) : null}

 <div className="grid gap-6 2xl:grid-cols-2">
 {canUseAuthorTools ? (
 <section className={` border p-6 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
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
 ) : null}

 <section className={` border p-6 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
 <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>Export</p>
 <h2 className={`mt-3 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Ship clean outputs</h2>

 <div className="mt-6 space-y-5">
 {canUseAuthorTools ? (
 <div className={` border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
 <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
 <label className="block">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Export font</span>
 <select
 value={exportFontFamily}
 onChange={(event) => setExportFontFamily(event.target.value as ReaderFontFamily)}
 className={`mt-2 min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 [&>option]:bg-black [&>option]:text-slate-100" : "border-stone-200 bg-white text-stone-800"
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
 className="inline-flex min-h-11 items-center justify-center bg-stone-900 px-5 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:opacity-60 dark:bg-white dark:text-stone-950 dark:hover:bg-slate-200"
 >
 {exporting === "all" ? "Preparing all..." : "Export everything"}
 </button>
 </div>
 <p className={`mt-3 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
 DOCX and EPUB declare this font family. PDF exports use safe built-in PDF mappings, and ZIP exports include a font notice. Proprietary system font files are not redistributed.
 </p>
 </div>
 ) : null}

 {canUseAuthorTools ? (
 <div className={` border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
 <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Character bible export</p>
 <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
 {formatCards.map((item) => (
 <button
 key={item.value}
 type="button"
 onClick={() => setBibleFormat(item.value)}
 className={` border px-4 py-3 text-left transition ${
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
 className=" bg-violet-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-600 disabled:opacity-60"
 >
 {exporting === "character-bible" ? "Preparing..." : "Export character bible"}
 </button>
 <button
 type="button"
 onClick={() => void openPreview()}
 disabled={previewLoading}
 className={` border px-5 py-3 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
 >
 {previewLoading ? "Loading preview..." : "Preview export files"}
 </button>
 </div>
 {bibleNotes.length > 0 ? (
 <div className={`mt-4 border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
 <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Saved bible note overrides</p>
 <div className="mt-2 flex flex-wrap gap-2">
 {bibleNotes.slice(0, 8).map((note) => (
 <span key={note.id} className={` px-2.5 py-1 text-xs ${isDark ? "bg-white/[0.08] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
 {note.path}
 </span>
 ))}
 </div>
 </div>
 ) : null}
 </div>
 ) : null}

 <div className={` border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
 <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Manuscript export</p>
 <div className="mt-3 flex flex-wrap gap-2">
 {MANUSCRIPT_EXPORT_FORMATS.map((format) => (
 <button
 key={format}
 type="button"
 onClick={() => setManuscriptFormat(format)}
 className={` border px-4 py-2 text-sm transition ${
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
 <label className={`mt-4 flex items-start gap-3 border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
 <input
 type="checkbox"
 checked={includeSceneMetadata}
 onChange={(event) => setIncludeSceneMetadata(event.target.checked)}
 className="mt-1 h-4 w-4 border-stone-300"
 />
 <span>
 <span className="block font-semibold">Include scene metadata</span>
 <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
 Disable for clean prose with scene breaks rendered as ***.
 </span>
 </span>
 </label>
 <label className={`mt-3 flex items-start gap-3 border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
 <input
 type="checkbox"
 checked={includeTableOfContents}
 onChange={(event) => setIncludeTableOfContents(event.target.checked)}
 className="mt-1 h-4 w-4 border-stone-300"
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
 className="mt-4 bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60"
 >
 {exporting === "manuscript" ? "Preparing..." : "Export manuscript"}
 </button>
 </div>

 <div data-testid="novel-export-card" className={` border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
 <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_8rem]">
 <div>
 <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Novel export</p>
 <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
 Reader-ready book files with cover page, table of contents, optional preface, chapters, and end marker.
 </p>
 </div>
 <div className={`overflow-hidden border ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
 {book.cover_url ? (
 <img src={book.cover_url} alt={`${book.title} cover`} className="aspect-[2/3] h-full w-full object-cover" />
 ) : (
 <div className={`flex aspect-[2/3] items-center justify-center px-3 text-center text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
 Blank cover generated on export
 </div>
 )}
 </div>
 </div>
 <div className="mt-4 flex flex-wrap gap-2">
 {NOVEL_EXPORT_FORMATS.map((format) => (
 <button
 key={format}
 type="button"
 onClick={() => setNovelFormat(format)}
 className={` border px-4 py-2 text-sm transition ${
 novelFormat === format
 ? isDark
 ? "border-teal-400/35 bg-teal-500/10 text-teal-100"
 : "border-teal-200 bg-teal-50 text-teal-800"
 : isDark
 ? "border-white/10 bg-black/20 text-slate-200"
 : "border-stone-200 bg-white text-stone-700"
 }`}
 >
 {format.toUpperCase()}
 </button>
 ))}
 </div>
 <label className="mt-4 block">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Page template</span>
 <select
 value={novelPreset}
 onChange={(event) => setNovelPreset(event.target.value as NovelExportPreset)}
 className={`mt-2 min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 [&>option]:bg-black [&>option]:text-slate-100" : "border-stone-200 bg-white text-stone-800"
 }`}
 >
 {NOVEL_EXPORT_PRESETS.map((presetOption) => (
 <option key={presetOption.value} value={presetOption.value}>
 {presetOption.label} - {presetOption.meta}
 </option>
 ))}
 </select>
 </label>
 {novelFormat === "docx" ? (
 <p className={`mt-3 border px-3 py-2 text-xs leading-5 ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
 DOCX table-of-contents page numbers update after opening in Word: right-click the table and choose Update Field.
 </p>
 ) : null}
 <label className={`mt-4 flex items-start gap-3 border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
 <input
 type="checkbox"
 checked={previewNovelExport}
 onChange={(event) => setPreviewNovelExport(event.target.checked)}
 className="mt-1 h-4 w-4 border-stone-300"
 />
 <span>
 <span className="block font-semibold">Export first 2 chapters only</span>
 <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
 Creates a quick sample file for checking templates, TOC links, and image placement.
 </span>
 </span>
 </label>
 <label className={`mt-4 flex items-start gap-3 border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
 <input
 type="checkbox"
 checked={includeNovelImages}
 onChange={(event) => setIncludeNovelImages(event.target.checked)}
 className="mt-1 h-4 w-4 border-stone-300"
 />
 <span>
 <span className="block font-semibold">Include chapter images</span>
 <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
 Embeds stored chapter images where available; missing or unreadable images are skipped.
 </span>
 </span>
 </label>
 {includeNovelImages ? (
 <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(12rem,0.55fr)]">
 <label className="block">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Image placement</span>
 <select
 value={novelImagePlacement}
 onChange={(event) => setNovelImagePlacement(event.target.value as NovelImagePlacement)}
 className={`mt-2 min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 [&>option]:bg-black [&>option]:text-slate-100" : "border-stone-200 bg-white text-stone-800"
 }`}
 >
 {NOVEL_IMAGE_PLACEMENTS.map((placement) => (
 <option key={placement.value} value={placement.value}>
 {placement.label} - {placement.meta}
 </option>
 ))}
 </select>
 </label>
 <label className={`flex items-start gap-3 border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
 <input
 type="checkbox"
 checked={includeNovelImageCaptions}
 onChange={(event) => setIncludeNovelImageCaptions(event.target.checked)}
 className="mt-1 h-4 w-4 border-stone-300"
 />
 <Tooltip content="Displays caption text below each embedded image when available" side="top" align="start">
                          <span className="font-semibold">Include stored captions</span>
 </Tooltip>
 </label>
 </div>
 ) : null}
 {canUseAuthorTools ? (
 <div className="mt-4">
 <label className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`} htmlFor="novel-preface">
 Preface
 </label>
 <textarea
 id="novel-preface"
 value={novelPreface}
 onChange={(event) => setNovelPreface(event.target.value)}
 rows={6}
 className={`mt-2 w-full border px-3 py-3 text-sm leading-6 outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 placeholder="Optional preface text for the reader-ready novel export."
 />

 <div className="mt-5 grid gap-4 md:grid-cols-2">
 {[
 ["dedication", "Dedication"] as const,
 ["copyright_page", "Copyright page"] as const,
 ["acknowledgements", "Acknowledgements"] as const,
 ["about_author", "About the author"] as const,
 ["series_book_list", "Series / book list"] as const,
 ].map(([key, label]) => (
 <label key={key} className={key === "series_book_list" ? "block md:col-span-2" : "block"}>
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{label}</span>
 <textarea
 value={novelFrontMatter[key]}
 onChange={(event) => setNovelFrontMatter((current) => ({ ...current, [key]: event.target.value }))}
 rows={key === "series_book_list" ? 4 : 3}
 className={`mt-2 w-full border px-3 py-3 text-sm leading-6 outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 />
 </label>
 ))}
 </div>
 <div className="mt-5 grid gap-4 md:grid-cols-2">
 <label className="block">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Publisher</span>
 <input
 value={novelEpubMetadata.publisher}
 onChange={(event) => setNovelEpubMetadata((current) => ({ ...current, publisher: event.target.value }))}
 className={`mt-2 min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 />
 </label>
 <label className="block">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Language</span>
 <input
 value={novelEpubMetadata.language}
 onChange={(event) => setNovelEpubMetadata((current) => ({ ...current, language: event.target.value }))}
 className={`mt-2 min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 placeholder="en"
 />
 </label>
 <label className="block">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>ISBN</span>
 <input
 value={novelEpubMetadata.isbn}
 onChange={(event) => setNovelEpubMetadata((current) => ({ ...current, isbn: event.target.value }))}
 className={`mt-2 min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 />
 </label>
 <label className="block">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Series</span>
 <div className="mt-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_7rem]">
 <input
 value={novelEpubMetadata.series_name}
 onChange={(event) => setNovelEpubMetadata((current) => ({ ...current, series_name: event.target.value }))}
 className={`min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 />
 <input aria-label="Series number"
 value={novelEpubMetadata.series_number}
 onChange={(event) => setNovelEpubMetadata((current) => ({ ...current, series_number: event.target.value }))}
 className={`min-h-11 w-full border px-3 text-sm outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 placeholder="#"
 />
 </div>
 </label>
 <label className="block md:col-span-2">
 <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Description / blurb</span>
 <textarea
 value={novelEpubMetadata.description}
 onChange={(event) => setNovelEpubMetadata((current) => ({ ...current, description: event.target.value }))}
 rows={4}
 className={`mt-2 w-full border px-3 py-3 text-sm leading-6 outline-none transition focus:ring-2 focus:ring-teal-500/30 ${
 isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-800 placeholder:text-stone-400"
 }`}
 />
 </label>
 </div>
 </div>
 ) : null}
 <div className="mt-4 flex flex-wrap gap-3">
 <button
 type="button"
 onClick={() => void exportNovel()}
 disabled={exporting !== null}
 className=" bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60"
 >
 {exporting === "novel" ? "Preparing..." : "Export novel"}
 </button>
 {canUseAuthorTools ? (
 <button
 type="button"
 onClick={() => void saveNovelSettings()}
 disabled={savingNovelPreface}
 className=" bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60"
 >
 {savingNovelPreface ? "Saving..." : "Save novel settings"}
 </button>
 ) : null}
 </div>
 </div>

 {canUseAuthorTools ? (
 <div className={` border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
 <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Notes workspace export</p>
 <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
 Download the editable vault notes separately from the generated character bible files.
 </p>
 <button
 type="button"
 onClick={() => void exportNotesZip()}
 disabled={exporting !== null}
 className="mt-4 bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60"
 >
 {exporting === "notes" ? "Preparing..." : "Export notes ZIP"}
 </button>
 </div>
 ) : null}
 </div>
 </section>
 </div>

 {status ? (
 <div className={` border px-4 py-3 text-sm ${isDark ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
 {status}
 </div>
 ) : null}

 <WorkflowBridgePanel bookId={bookId} bookTitle={book?.title ?? "LoreVia Project"} isDark={isDark} />

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
 <section className={` border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
 <Skeleton className="h-4 w-28" />
 <Skeleton className="mt-4 h-8 w-64 max-w-full" />
 <Skeleton className="mt-3 h-4 w-full max-w-2xl" />
 <div className="mt-5 flex flex-wrap gap-3">
 <Skeleton className="h-10 w-36 " />
 <Skeleton className="h-10 w-32 " />
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
 <article className={` border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
 <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</p>
 <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{description}</p>
 <div className={`mt-3 border border-dashed px-4 py-3 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
 {files.length ? files.map((file) => file.name).join(", ") : "No files selected yet."}
 </div>
 <div className="mt-4 flex flex-wrap gap-3">
 <button type="button" onClick={onChoose} className={` border px-4 py-2.5 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
 Choose files
 </button>
 <button type="button" onClick={onRun} disabled={disabled} className=" bg-[#1f615d] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#25756f] disabled:opacity-60">
 {buttonLabel}
 </button>
 </div>
 </article>
 )
}
