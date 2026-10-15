"use client"

import dynamic from "next/dynamic"
import { useEffect, useId, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
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
import type { VaultPreview, VaultNote, WriterWorkspace } from "@/types/book"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { WorkflowBridgePanel } from "@/components/author/WorkflowBridgePanel"
import { ExportStudioSkeleton, ImportCard } from "./exportPage.components"
import { downloadExportBlob, exportErrorMessage, safeFileBase } from "@/lib/utils/exportFiles"
import { importFileError, novelSettingsError, novelSettingsFromWorkspace, type NovelSettings } from "./exportPage.helpers"
import { BIBLE_FORMATS, DEFAULT_EXPORT_OPTIONS, ExportFont, FormatChoices, MANUSCRIPT_FORMATS, ManuscriptOptions, NOVEL_FORMATS, NovelOptions, PublishingDetails, type ExportOptions } from "./exportPage.options"
import { useExportDraftGuard } from "./exportPage.draftGuard"

const VaultPreviewEditor = dynamic(() => import("@/components/reader/VaultPreview").then((module) => module.VaultPreview), { loading: () => <p role="status">Loading vault editor…</p> })
const TASKS = [["manuscript", "Manuscript", "Drafts for editing"], ["novel", "Reader edition", "Publication files"], ["character-bible", "Character bible", "Reference package"], ["notes", "Notes backup", "Editable archive"], ["import", "Import files", "Add source material"]] as const
type FileTask = typeof TASKS[number][0]
type ImportKind = "manuscript" | "notes" | "world"
const muted = "text-[rgb(var(--muted-foreground))]"

export default function ExportStudioPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <ExportStudio bookId={bookId} key={bookId} />
}

function ExportStudio({ bookId }: { bookId: string }) {
  const id = useId()
  const client = useQueryClient()
  const isDark = usePreferencesStore((state) => state.theme) === "dark"
  const paid = canUseAuthorFeatures(useAuthStore((state) => state.user?.tier))
  const [task, setTask] = useState<FileTask>("manuscript")
  const [options, setOptions] = useState<ExportOptions>(DEFAULT_EXPORT_OPTIONS)
  const [busy, setBusy] = useState<string | null>(null)
  const busyRef = useRef(false)
  const [bridgeBusy, setBridgeBusy] = useState(false)
  const [vaultState, setVaultState] = useState({ dirty: false, busy: false })
  const blocked = !!busy || bridgeBusy || vaultState.busy
  const [status, setStatus] = useState<{ error: boolean; message: string } | null>(null)
  const [saved, setSaved] = useState<NovelSettings | null>(null)
  const [draft, setDraft] = useState<NovelSettings>(novelSettingsFromWorkspace())
  const [vaultPreview, setVaultPreview] = useState<VaultPreview | null>(null)
  const [bibleNotes, setBibleNotes] = useState<VaultNote[]>([])
  const [overrideError, setOverrideError] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<Record<ImportKind, File[]>>({ manuscript: [], notes: [], world: [] })
  const [notesConfirmed, setNotesConfirmed] = useState(false)
  const manuscriptInput = useRef<HTMLInputElement>(null)
  const notesInput = useRef<HTMLInputElement>(null)
  const worldInput = useRef<HTMLInputElement>(null)
  const bookQuery = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "detail")), queryFn: () => booksApi.get(bookId) })
  const book = bookQuery.data
  const owner = book?.access_class === "owner"
  const authorTools = owner && paid
  const canExport = owner || !!book?.collaboration_permissions?.can_export
  const canBible = authorTools || (canExport && !!book?.collaboration_permissions?.can_view_story_bible)
  const canEditSettings = authorTools || !!book?.collaboration_permissions?.can_edit_manuscript
  const workspace = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "writer-workspace")), queryFn: () => booksApi.getWriterWorkspace(bookId), enabled: !!book && canEditSettings && task === "novel" })
  const dirty = saved !== null && JSON.stringify(saved) !== JSON.stringify(draft)
  const settingsError = novelSettingsError(draft)
  useExportDraftGuard(dirty || vaultState.dirty || Object.values(selectedFiles).some((files) => files.length > 0), blocked)

  useEffect(() => {
    if (saved !== null || !workspace.data) return
    const initial = novelSettingsFromWorkspace(workspace.data)
    setSaved(initial)
    setDraft(initial)
  }, [saved, workspace.data])

  const updateOptions = (patch: Partial<ExportOptions>) => setOptions((current) => ({ ...current, ...patch }))
  const run = async (label: string, failure: string, action: () => Promise<string>) => {
    if (busyRef.current || bridgeBusy || vaultState.busy) return
    busyRef.current = true
    setBusy(label)
    setStatus(null)
    try { setStatus({ error: false, message: await action() }) }
    catch (error) { setStatus({ error: true, message: await exportErrorMessage(error, failure) }) }
    finally { busyRef.current = false; setBusy(null) }
  }
  const download = (blob: Blob, name: string, kind: string, format: string) => {
    downloadExportBlob(blob, `${safeFileBase(book?.title, "lorevia")}-${name}.${format}`)
    capture("first_export_completed", { book_id: bookId, export_kind: kind, format })
  }
  const novelBlob = (format: ExportOptions["novel"]) => booksApi.exportNovel(bookId, format, options.preset, options.images, options.font, { imagePlacement: options.imagePlacement, includeImageCaptions: options.captions, previewChapters: options.sample ? 2 : null })

  const exportCurrent = () => {
    if (!book || !canExport || (task === "novel" && dirty) || vaultState.dirty) return
    void run(`Preparing ${TASKS.find(([value]) => value === task)?.[1].toLowerCase()}…`, "The export could not be completed. Your options are preserved; try again.", async () => {
      if (task === "manuscript") {
        const format = options.manuscript === "vault" ? "zip" : options.manuscript
        download(await booksApi.exportManuscript(bookId, options.manuscript, "standard_manuscript", options.scenes, options.font, options.toc), "manuscript", "manuscript", format)
        return `Downloaded manuscript as ${format.toUpperCase()}.`
      }
      if (task === "novel") {
        download(await novelBlob(options.novel), options.sample ? "novel-preview" : "novel", options.sample ? "novel_preview" : "novel", options.novel)
        return options.sample ? `Downloaded first 2-chapter sample as ${options.novel.toUpperCase()}.` : `Downloaded novel export as ${options.novel.toUpperCase()}.`
      }
      if (task === "character-bible") {
        const format = options.bible === "vault_folder" ? "zip" : options.bible
        download(await booksApi.exportCharacterBible(bookId, options.bible, options.font), "character-bible", "character_bible", format)
        return `Downloaded character bible as ${format.toUpperCase()}.`
      }
      download(await booksApi.exportVaultNotes(bookId), "notes", "notes", "zip")
      return "Downloaded notes workspace ZIP."
    })
  }

  const saveSettings = () => {
    if (!saved || !dirty || settingsError) return
    void run("Saving publishing details…", "Could not save the novel export settings. Your edits are preserved.", async () => {
      const result = await booksApi.saveNovelSettings(bookId, draft)
      setSaved(result); setDraft(result)
      client.setQueryData<WriterWorkspace>(asQueryKey(bookCacheKey(bookId, "writer-workspace")), (current) => current ? { ...current, novel_preface: result.preface, novel_front_matter: result.front_matter, novel_epub_metadata: result.epub_metadata } : current)
      return "Saved novel export settings."
    })
  }

  const previewBible = () => void run("Loading character bible preview…", "Could not load the vault preview. Try again.", async () => {
    const [preview, notes] = await Promise.allSettled([booksApi.previewCharacterBibleVault(bookId), booksApi.listCharacterBibleVaultNotes(bookId)])
    if (preview.status === "rejected") throw preview.reason
    setVaultPreview(preview.value)
    setOverrideError(notes.status === "rejected")
    if (notes.status === "fulfilled") setBibleNotes(notes.value)
    return notes.status === "rejected" ? "Loaded the preview, but saved override paths could not be listed. Use Retry override list below." : "Loaded the character bible file preview."
  })

  const importFiles = (kind: ImportKind) => {
    const files = selectedFiles[kind]
    const validation = importFileError(files, kind)
    if (!book || !authorTools || validation || (kind === "notes" && !notesConfirmed)) return
    void run(`Importing ${kind} files…`, "The import could not be confirmed. Check the destination before retrying to avoid duplicate imports.", async () => {
      let message: string
      if (kind === "manuscript") {
        const result = await booksApi.importManuscript(bookId, { files, chunkLongDocuments: true, replaceExisting: false, workType: book.work_type })
        message = `Imported ${result.imported_chapters.length} chapter files into this book.`
      } else if (kind === "notes") {
        await booksApi.importVaultNotes(bookId, files[0])
        message = `Imported ${files[0].name} into the notes workspace.`
        setNotesConfirmed(false)
      } else {
        await worldBuildingApi.uploadDocuments(bookId, { files })
        message = `Imported ${files.length} worldbuilding file${files.length === 1 ? "" : "s"}.`
      }
      setSelectedFiles((current) => ({ ...current, [kind]: [] }))
      const input = kind === "manuscript" ? manuscriptInput : kind === "notes" ? notesInput : worldInput
      if (input.current) input.current.value = ""
      return message
    })
  }

  const exportAll = () => {
    if (dirty || vaultState.dirty || !authorTools) return
    void run("Preparing all files…", "Could not export every document. No partial ZIP was downloaded. Try the individual formats.", async () => {
      const base = safeFileBase(book?.title, "lorevia")
      const font = READER_FONT_OPTIONS.find((item) => item.value === options.font)?.label ?? options.font
      const files: Record<string, Uint8Array> = { "FONT-NOTICE.txt": strToU8(`LoreVia Font Notice\n\nSelected export font: ${font}\nDOCX and EPUB declare the font family; PDF uses built-in alternatives. Proprietary system fonts are not redistributed. EB Garamond: SIL Open Font License 1.1, Copyright 2017 The EB Garamond Project Authors. https://openfontlicense.org.\n`) }
      let completed = 0
      const add = async (path: string, blob: Promise<Blob>) => { files[path] = new Uint8Array(await (await blob).arrayBuffer()); setBusy(`Preparing all files… ${++completed}/12 formats ready`) }
      for (const format of BIBLE_FORMATS) await add(`character-bible/${base}-character-bible.${format === "vault_folder" ? "zip" : format}`, booksApi.exportCharacterBible(bookId, format, options.font))
      for (const format of MANUSCRIPT_FORMATS) await add(`manuscript/${base}-manuscript.${format === "vault" ? "zip" : format}`, booksApi.exportManuscript(bookId, format, "standard_manuscript", options.scenes, options.font, options.toc))
      for (const format of NOVEL_FORMATS) await add(`novel/${base}-${options.sample ? "novel-preview" : "novel"}.${format}`, novelBlob(format))
      await add(`notes/${base}-notes.zip`, booksApi.exportVaultNotes(bookId))
      const archive = zipSync(files)
      downloadExportBlob(new Blob([archive as unknown as BlobPart], { type: "application/zip" }), `${base}-all-exports.zip`)
      return "Downloaded one ZIP with all manuscript, novel, character bible, and notes export files."
    })
  }

  if (bookQuery.isLoading) return <ExportStudioSkeleton isDark={isDark} />
  if (!book) return <WorkspacePage><main className="mx-auto max-w-4xl py-8"><h1 className="text-3xl font-semibold">Files & Export</h1><p role="alert" className="mt-4">This project could not be loaded. Check your access or try again.</p><button className="app-button-secondary mt-4" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry project</button><Link href="/library" className="ml-4 underline">Back to library</Link></main></WorkspacePage>
  const permitted = task === "manuscript" || task === "novel" ? canExport : task === "character-bible" ? canBible : authorTools
  const editingReady = !canEditSettings || (saved !== null && !workspace.isError)
  return <WorkspacePage><main data-export-workspace className="mx-auto min-w-0 max-w-6xl space-y-6 pb-20 pt-6 [overflow-wrap:anywhere]">
    <WorkspaceFamilyHeader active="export" bookId={bookId} family="publish-export" title="Files & Export" description={`Prepare ${book.title} for editing, reading, or backup.`} actions={<><Link href={`/${bookId}/manuscript`} className="app-button-secondary">Open manuscript</Link><button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></>} />
    {bookQuery.isError ? <p role="alert" className="text-sm">Project details could not be refreshed. <button className="underline" onClick={() => void bookQuery.refetch()}>Retry project</button></p> : null}
    {!paid && owner ? <p className={`text-sm leading-6 ${muted}`}>Owned manuscript and reader-edition exports remain available. Notes, import, and character-bible tools require an active trial, Author, or Architect plan.</p> : null}
    <nav aria-label="File tasks" className="border-y border-[rgb(var(--border))]">
      <div role="tablist" aria-label="File task" className="hidden md:grid md:grid-cols-5">{TASKS.map(([value, label, description], index) => <button type="button" role="tab" id={`${id}-${value}`} key={value} aria-selected={task === value} aria-controls={`${id}-task`} disabled={blocked} tabIndex={task === value ? 0 : -1} onClick={() => setTask(value)} onKeyDown={(event) => {
        const next = event.key === "ArrowRight" ? (index + 1) % TASKS.length : event.key === "ArrowLeft" ? (index + TASKS.length - 1) % TASKS.length : event.key === "Home" ? 0 : event.key === "End" ? TASKS.length - 1 : null
        if (next === null) return
        event.preventDefault(); setTask(TASKS[next][0]); document.getElementById(`${id}-${TASKS[next][0]}`)?.focus()
      }} className={`min-w-0 border-b-2 px-3 py-4 text-left text-sm ${task === value ? "border-[rgb(var(--accent))]" : "border-transparent"}`}><span className="block font-semibold">{label}</span><span className={`mt-1 block ${muted}`}>{description}</span></button>)}</div>
      <label className="block py-3 text-sm md:hidden">Choose a file task<select value={task} disabled={blocked} onChange={(event) => setTask(event.target.value as FileTask)} className="export-field mt-2 min-h-11 w-full border border-[rgb(var(--border))] px-3">{TASKS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    </nav>
    {busy ? <p role="status" className="border-l-2 border-[rgb(var(--accent))] pl-4 text-sm">{busy} Keep this page open until it finishes.</p> : null}
    {status ? <p role={status.error ? "alert" : "status"} className={`border-l-2 pl-4 text-sm leading-6 ${status.error ? "border-rose-600" : "border-[rgb(var(--accent))]"}`}>{status.message}</p> : null}
    {vaultState.dirty ? <p className="text-sm">Save the remaining vault edits before exporting. <button type="button" className="underline" onClick={() => setTask("character-bible")}>Return to vault editor</button></p> : null}
    {dirty && task !== "novel" ? <p className="text-sm">Publishing details have unsaved changes. <button className="underline underline-offset-4" onClick={() => setTask("novel")}>Return to reader edition</button></p> : null}
    <section id={`${id}-task`} aria-label={TASKS.find(([value]) => value === task)?.[1]}>
      {!permitted ? <div className="border-b border-[rgb(var(--border))] py-6"><h2 className="text-xl font-semibold">This file task is unavailable</h2><p className={`mt-2 text-sm ${muted}`}>{owner ? "This task requires author tools on your plan." : "This task is not included in your project access. Ask the owner for the appropriate access."}</p>{owner ? <Link href="/pricing" className="app-button-secondary mt-4">View plans</Link> : null}</div> : task === "import" ? <fieldset disabled={blocked} className="min-w-0">
        <h2 className="text-xl font-semibold">Import files</h2><p className={`mt-2 text-sm leading-6 ${muted}`}>Manuscript files append chapters. Notes ZIPs replace notes with matching paths. Worldbuilding files are added separately.</p>
        {([['manuscript', 'Story manuscript', 'Append chapter files without replacing existing chapters.', '.docx,.doc,.pdf,.txt,.md,.epub', manuscriptInput, 'Import manuscript files'], ['notes', 'Vault notes ZIP', 'Import UTF-8 Markdown notes. Matching note paths will be overwritten; export a notes backup first.', '.zip', notesInput, 'Import notes ZIP'], ['world', 'Worldbuilding docs', 'Add lore documents for the worldbuilding tools.', '.docx,.doc,.pdf,.txt,.md', worldInput, 'Import worldbuilding']] as const).map(([kind, title, description, accept, input, label]) => {
          const files = selectedFiles[kind]; const error = files.length ? importFileError(files, kind) : null
          return <div key={kind} className="mt-5 border-t border-[rgb(var(--border))] pt-5"><ImportCard isDark={isDark} title={title} description={description} files={files} buttonLabel={label} onChoose={() => input.current?.click()} onRun={() => importFiles(kind)} disabled={!files.length || !!error || blocked || (kind === "notes" && !notesConfirmed)} onClear={() => { setSelectedFiles((current) => ({ ...current, [kind]: [] })); if (input.current) input.current.value = ""; if (kind === "notes") setNotesConfirmed(false) }} />
            <input ref={input} aria-label={`Choose ${title} files`} type="file" multiple={kind !== "notes"} accept={accept} className="hidden" onChange={(event) => { setSelectedFiles((current) => ({ ...current, [kind]: Array.from(event.target.files ?? []) })); if (kind === "notes") setNotesConfirmed(false) }} />
            {error ? <p role="alert" className="mt-3 text-sm text-rose-700 dark:text-rose-300">{error}</p> : null}
            {kind === "notes" ? <label className="mt-3 flex items-start gap-3 text-sm"><input type="checkbox" checked={notesConfirmed} onChange={(event) => setNotesConfirmed(event.target.checked)} className="mt-1" /><span>I understand that matching note paths will be replaced.</span></label> : null}
          </div>
        })}
      </fieldset> : <>
        <h2 className="text-xl font-semibold">{task === "manuscript" ? "Export a manuscript" : task === "novel" ? "Export a reader edition" : task === "character-bible" ? "Export a character bible" : "Back up notes"}</h2>
        <fieldset disabled={blocked || bookQuery.isError || vaultState.dirty} className="mt-5 min-w-0 space-y-5">
          {task !== "notes" ? <ExportFont value={options.font} onChange={(font) => updateOptions({ font })} /> : null}
          {task === "manuscript" ? <ManuscriptOptions options={options} update={updateOptions} /> : null}
          {task === "novel" ? <div data-testid="novel-export-card">
            <div className="mb-4 flex items-start gap-4">{book.cover_url ? <img src={book.cover_url} alt={`${book.title} cover`} className="w-16 shrink-0 border border-[rgb(var(--border))] object-cover" /> : null}<p className={`text-sm leading-6 ${muted}`}>{book.cover_url ? "Uses the current book cover." : "A blank cover is generated for this edition."}</p></div><NovelOptions options={options} update={updateOptions} />
            {canEditSettings && !saved && !workspace.isError ? <p role="status" className="mt-4 text-sm">Loading saved publishing details…</p> : null}
            {canEditSettings && workspace.isError ? <p role="alert" className="mt-4 text-sm">Publishing details could not be loaded. Your edits are preserved. <button type="button" className="underline" disabled={workspace.isFetching} onClick={() => void workspace.refetch()}>Retry publishing details</button></p> : null}
            {canEditSettings && saved ? <PublishingDetails draft={draft} onChange={setDraft} dirty={dirty} busy={blocked || workspace.isError} error={settingsError} onSave={saveSettings} onDiscard={() => { if (window.confirm("Discard unsaved publishing details?")) setDraft(saved) }} /> : null}
            {dirty ? <p className="mt-3 text-sm">Save or discard publishing changes before exporting.</p> : null}
            <button type="button" className="app-button-primary mt-5" disabled={dirty || !editingReady} onClick={exportCurrent}>Export novel</button>
          </div> : null}
          {task === "character-bible" ? <><FormatChoices values={BIBLE_FORMATS} value={options.bible} onChange={(bible) => updateOptions({ bible })} /><p className={`text-sm leading-6 ${muted}`}>Vault ZIP includes folders for note apps. DOCX, PDF, and Markdown provide a generated reference.</p>{authorTools ? <button type="button" className="app-button-secondary mr-3" onClick={() => { if (!vaultPreview) previewBible(); else { const editor = document.getElementById(`${id}-vault`); editor?.scrollIntoView({ behavior: "smooth", block: "start" }); editor?.focus({ preventScroll: true }) } }}>{vaultPreview ? "View vault editor" : "Preview export files"}</button> : null}{overrideError ? <p role="alert" className="text-sm">Saved override paths could not be listed. <button type="button" className="underline" onClick={() => void run("Loading saved override paths…", "Could not load saved override paths.", async () => { setBibleNotes(await booksApi.listCharacterBibleVaultNotes(bookId)); setOverrideError(false); return "Loaded saved override paths." })}>Retry override list</button></p> : null}{bibleNotes.length ? <details><summary className="cursor-pointer text-sm">Saved bible note overrides ({bibleNotes.length})</summary><ul className="mt-2 space-y-1 text-sm">{bibleNotes.map((note) => <li key={note.id}>{note.path}</li>)}</ul></details> : null}</> : null}
          {task === "notes" ? <p className={`text-sm leading-6 ${muted}`}>Download editable notes separately from generated character bible files. Keep this backup before importing notes with matching paths.</p> : null}
          {task !== "novel" ? <button type="button" className="app-button-primary" onClick={exportCurrent}>{task === "manuscript" ? "Export manuscript" : task === "character-bible" ? "Export character bible" : "Export notes ZIP"}</button> : null}
          {task === "notes" ? <details className="border-t border-[rgb(var(--border))] pt-4"><summary className="cursor-pointer text-sm font-semibold">Download every available format</summary><p className={`mt-3 text-sm leading-6 ${muted}`}>Includes 12 files plus a font notice. Uses your current manuscript and reader-edition options: {options.sample ? "first 2 novel chapters only" : "complete reader edition"}, {options.images ? "with available images" : "without images"}, {options.preset.replaceAll("_", " ")}. This can take longer than a single export.</p><button type="button" disabled={dirty} onClick={exportAll} className="app-button-secondary mt-4">Export everything</button></details> : null}
        </fieldset>
      </>}
    </section>
    {vaultPreview ? <div id={`${id}-vault`} tabIndex={-1} hidden={task !== "character-bible"}><VaultPreviewEditor bookId={bookId} preview={vaultPreview} isDark={isDark} disabled={!!busy || bridgeBusy} onStateChange={setVaultState} /></div> : null}
    {authorTools ? <details className="border-t border-[rgb(var(--border))] pt-5"><summary className="cursor-pointer text-sm font-semibold">Word and Scrivener round trip</summary><fieldset disabled={!!busy || vaultState.busy} className="mt-4 min-w-0"><WorkflowBridgePanel bookId={bookId} bookTitle={book.title} isDark={isDark} disabled={!!busy || vaultState.busy} onBusyChange={setBridgeBusy} /></fieldset></details> : null}
  </main></WorkspacePage>
}
