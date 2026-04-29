"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import type { Route } from "next"

import { worldBuildingApi } from "@/lib/api/worldBuilding"
import type {
  WorldBuildingDocument,
  WorldGapItem,
  WorldGapResult,
  WorldNote,
} from "@/types/world-building"

type WorkspaceFocus = "editor" | "gap"

export function WorldbuildingWorkspace({
  bookId,
  isDark,
  focus = "editor",
}: {
  bookId: string
  isDark: boolean
  focus?: WorkspaceFocus
}) {
  const [documents, setDocuments] = useState<WorldBuildingDocument[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState("")
  const [draftText, setDraftText] = useState("")
  const [loadingDocuments, setLoadingDocuments] = useState(true)
  const [loadingDocumentBody, setLoadingDocumentBody] = useState(false)
  const [savingDocument, setSavingDocument] = useState(false)
  const [deletingDocument, setDeletingDocument] = useState(false)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [uploadTitle, setUploadTitle] = useState("")
  const [replaceCorpusOnUpload, setReplaceCorpusOnUpload] = useState(false)
  const [uploadingFiles, setUploadingFiles] = useState(false)
  const [analysis, setAnalysis] = useState<WorldGapResult | null>(null)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [notes, setNotes] = useState<WorldNote[]>([])
  const [loadingNotes, setLoadingNotes] = useState(true)
  const [noteSavingId, setNoteSavingId] = useState<string | null>(null)
  const [noteStatusId, setNoteStatusId] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId]
  )
  const openGapIds = useMemo(
    () => new Set(notes.filter((note) => note.status !== "addressed" && note.linked_gap_id).map((note) => note.linked_gap_id as string)),
    [notes]
  )
  const totalWorldWords = useMemo(
    () => documents.reduce((sum, document) => sum + (document.word_count ?? 0), 0),
    [documents]
  )
  const groupedNotes = useMemo(() => {
    const open = notes.filter((note) => note.status !== "addressed")
    const addressed = notes.filter((note) => note.status === "addressed")
    return { open, addressed }
  }, [notes])

  const loadNotes = async () => {
    setLoadingNotes(true)
    try {
      const payload = await worldBuildingApi.listNotes(bookId)
      setNotes(payload)
    } finally {
      setLoadingNotes(false)
    }
  }

  const loadDocumentBody = async (documentId: string) => {
    setLoadingDocumentBody(true)
    try {
      const payload = await worldBuildingApi.getDocument(bookId, documentId)
      setSelectedDocumentId(payload.id)
      setDraftTitle(payload.title)
      setDraftText(payload.text)
    } finally {
      setLoadingDocumentBody(false)
    }
  }

  const loadDocuments = async (preferredDocumentId?: string | null) => {
    setLoadingDocuments(true)
    try {
      const payload = await worldBuildingApi.listDocuments(bookId)
      setDocuments(payload)
      const nextSelectedId = preferredDocumentId && payload.some((item) => item.id === preferredDocumentId)
        ? preferredDocumentId
        : payload[0]?.id ?? null
      if (nextSelectedId) {
        await loadDocumentBody(nextSelectedId)
      } else {
        setSelectedDocumentId(null)
        setDraftTitle("")
        setDraftText("")
      }
    } finally {
      setLoadingDocuments(false)
    }
  }

  const runAnalysis = async () => {
    setLoadingAnalysis(true)
    try {
      const payload = await worldBuildingApi.getGaps(bookId)
      setAnalysis(payload)
    } finally {
      setLoadingAnalysis(false)
    }
  }

  useEffect(() => {
    loadDocuments().catch(() => {
      setDocuments([])
      setSelectedDocumentId(null)
      setDraftTitle("")
      setDraftText("")
      setLoadingDocuments(false)
    })
    loadNotes().catch(() => {
      setNotes([])
      setLoadingNotes(false)
    })
  }, [bookId])

  useEffect(() => {
    if (focus !== "gap") return
    if (!documents.length) {
      setAnalysis(null)
      return
    }
    runAnalysis().catch(() => setAnalysis(null))
  }, [documents.length, focus])

  const saveDocument = async () => {
    if (!draftText.trim()) return
    setSavingDocument(true)
    try {
      if (selectedDocumentId) {
        const updated = await worldBuildingApi.updateDocument(bookId, selectedDocumentId, {
          title: draftTitle.trim() || selectedDocument?.title || "Worldbuilding Manuscript",
          text: draftText,
        })
        setDraftTitle(updated.title)
        setDraftText(updated.text)
        await loadDocuments(updated.id)
        setStatusMessage(`Saved ${updated.title}.`)
      } else {
        const created = await worldBuildingApi.uploadDocuments(bookId, {
          title: draftTitle.trim() || "Worldbuilding Manuscript",
          text: draftText,
        })
        const nextSelected = created[0]?.id ?? null
        await loadDocuments(nextSelected)
        setStatusMessage(created.length ? `Created ${created[0].title}.` : "Created worldbuilding document.")
      }
      if (focus === "gap") {
        await runAnalysis()
      }
    } finally {
      setSavingDocument(false)
    }
  }

  const uploadDocumentFiles = async () => {
    if (!uploadFiles.length) return
    setUploadingFiles(true)
    try {
      const created = await worldBuildingApi.uploadDocuments(bookId, {
        title: uploadTitle.trim() || undefined,
        files: uploadFiles,
        replaceExisting: replaceCorpusOnUpload,
      })
      setUploadFiles([])
      setUploadTitle("")
      setReplaceCorpusOnUpload(false)
      await loadDocuments(created[0]?.id ?? null)
      if (focus === "gap") {
        await runAnalysis()
      }
      setStatusMessage(
        replaceCorpusOnUpload
          ? "Replaced the active world corpus and loaded the new documents."
          : `Added ${created.length} worldbuilding document${created.length === 1 ? "" : "s"} to the corpus.`
      )
    } finally {
      setUploadingFiles(false)
    }
  }

  const deleteDocument = async () => {
    if (!selectedDocumentId) return
    setDeletingDocument(true)
    try {
      await worldBuildingApi.deleteDocument(bookId, selectedDocumentId)
      await loadDocuments()
      if (focus === "gap") {
        await runAnalysis()
      }
      setStatusMessage("Removed that worldbuilding document from the active corpus.")
    } finally {
      setDeletingDocument(false)
    }
  }

  const saveGapAsNote = async (item: WorldGapItem) => {
    setNoteSavingId(item.id)
    try {
      const created = await worldBuildingApi.createNote(bookId, {
        world_document_id: item.world_document_id,
        note_type: "world_gap",
        chapter_number: item.story_chapter_number ?? null,
        title: item.title,
        body: item.description,
        priority: item.priority >= 8 ? "critical" : item.priority >= 6 ? "high" : "medium",
        status: "open",
        linked_gap_id: item.id,
        context_label: item.world_document_title ?? item.character_name ?? null,
        suggested_fix: item.suggested_fix,
      })
      setNotes((current) => [created, ...current])
    } finally {
      setNoteSavingId(null)
    }
  }

  const setNoteStatus = async (noteId: string, status: string) => {
    setNoteStatusId(noteId)
    try {
      const updated = await worldBuildingApi.updateNoteStatus(bookId, noteId, status)
      setNotes((current) => current.map((note) => (note.id === updated.id ? updated : note)))
    } finally {
      setNoteStatusId(null)
    }
  }

  const uploadPanel = (
    <section className={`rounded-[1.5rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/82"}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>World corpus</p>
          <h3 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Add or replace reference docs</h3>
        </div>
        {focus === "editor" ? (
          <Link href={`/${bookId}/world-gap` as Route} className={`rounded-full border px-3 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
            Open World Gap Detection
          </Link>
        ) : null}
      </div>
      <div className="mt-4 grid gap-3">
        <input
          value={uploadTitle}
          onChange={(event) => setUploadTitle(event.target.value)}
          placeholder="Optional shared title for this upload batch"
          className={`rounded-[1rem] border px-4 py-3 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
        <input
          type="file"
          multiple
          onChange={(event) => setUploadFiles(Array.from(event.target.files ?? []))}
          className={`rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-200 file:text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
        />
        <label className={`flex items-center gap-3 text-sm ${isDark ? "text-slate-300" : "text-stone-700"}`}>
          <input
            type="checkbox"
            checked={replaceCorpusOnUpload}
            onChange={(event) => setReplaceCorpusOnUpload(event.target.checked)}
          />
          Replace the active world corpus instead of appending to it
        </label>
        <button
          type="button"
          onClick={uploadDocumentFiles}
          disabled={uploadingFiles || uploadFiles.length === 0}
          className="rounded-[1rem] bg-[linear-gradient(135deg,#f59e0b,#d97706)] px-4 py-3 text-sm font-semibold text-white transition disabled:opacity-50"
        >
          {uploadingFiles ? "Uploading..." : replaceCorpusOnUpload ? "Replace corpus" : "Add documents"}
        </button>
      </div>
    </section>
  )

  const editorPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Worldbuilding manuscript</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>
            {selectedDocument ? selectedDocument.title : "Start a new world document"}
          </h2>
        </div>
        <div className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          {selectedDocument ? `Last updated ${new Date(selectedDocument.updated_at).toLocaleString()}` : "Type directly or upload files to build the corpus."}
        </div>
      </div>
      <div className="mt-5 grid gap-3">
        <input
          value={draftTitle}
          onChange={(event) => setDraftTitle(event.target.value)}
          placeholder="Document title"
          className={`rounded-[1rem] border px-4 py-3 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
        <textarea
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
          placeholder="Worldbuilding notes, lore rules, places, factions, timeline details, and reference canon live here."
          rows={18}
          className={`min-h-[28rem] rounded-[1.3rem] border px-4 py-4 text-sm leading-7 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={saveDocument}
            disabled={savingDocument || !draftText.trim()}
            className="rounded-[1rem] bg-[linear-gradient(135deg,#059669,#047857)] px-4 py-3 text-sm font-semibold text-white transition disabled:opacity-50"
          >
            {savingDocument ? "Saving..." : selectedDocument ? "Save document" : "Create document"}
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedDocumentId(null)
              setDraftTitle("")
              setDraftText("")
            }}
            className={`rounded-[1rem] border px-4 py-3 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
          >
            New blank document
          </button>
          {selectedDocument ? (
            <button
              type="button"
              onClick={deleteDocument}
              disabled={deletingDocument}
              className={`rounded-[1rem] border px-4 py-3 text-sm font-semibold ${isDark ? "border-rose-400/20 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}
            >
              {deletingDocument ? "Removing..." : "Delete document"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => void runAnalysis()}
            disabled={loadingAnalysis || documents.length === 0}
            className={`rounded-[1rem] border px-4 py-3 text-sm font-semibold ${isDark ? "border-amber-300/20 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}
          >
            {loadingAnalysis ? "Checking gaps..." : "Run world gap detection"}
          </button>
        </div>
      </div>
    </section>
  )

  const analysisPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>World gap detection</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Grouped inconsistencies and cleanup notes</h2>
        </div>
        <div className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          {analysis?.generated_at ? `Last run ${new Date(analysis.generated_at).toLocaleString()}` : "Run a pass after updating the world corpus or story manuscript."}
        </div>
      </div>
      {loadingAnalysis ? (
        <div className={`mt-5 rounded-[1.3rem] border border-dashed px-5 py-10 text-center ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
          Comparing the world corpus against chapters, characters, and timeline signals...
        </div>
      ) : analysis ? (
        <div className="mt-5 space-y-5">
          {analysis.gap_groups.length === 0 ? (
            <div className={`rounded-[1.3rem] border px-5 py-8 text-sm ${isDark ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
              No major world-to-story inconsistencies were surfaced on this pass.
            </div>
          ) : (
            analysis.gap_groups.map((group) => (
              <div key={group.key} className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <h3 className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{group.label}</h3>
                    {group.description ? <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{group.description}</p> : null}
                  </div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    {group.items.length} item{group.items.length === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="mt-4 grid gap-3">
                  {group.items.map((item) => {
                    const alreadySaved = openGapIds.has(item.id)
                    return (
                      <article key={item.id} className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={severityClass(item.severity, isDark)}>{item.severity}</span>
                              {item.world_document_title ? (
                                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/6 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
                                  {item.world_document_title}
                                </span>
                              ) : null}
                              {item.story_chapter_number ? (
                                <Link
                                  href={`/${bookId}/chapter/${item.story_chapter_number}`}
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-indigo-400/10 text-indigo-200" : "bg-violet-50 text-violet-700"}`}
                                >
                                  Chapter {item.story_chapter_number}
                                </Link>
                              ) : null}
                            </div>
                            <h4 className={`mt-3 text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{item.title}</h4>
                            <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{item.description}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => void saveGapAsNote(item)}
                            disabled={alreadySaved || noteSavingId === item.id}
                            className={`rounded-[1rem] px-4 py-2.5 text-sm font-semibold transition ${
                              alreadySaved
                                ? isDark
                                  ? "bg-emerald-500/10 text-emerald-200 opacity-70"
                                  : "bg-emerald-50 text-emerald-700 opacity-80"
                                : "bg-[linear-gradient(135deg,#7c3aed,#6d28d9)] text-white"
                            }`}
                          >
                            {alreadySaved ? "Saved to notes" : noteSavingId === item.id ? "Saving..." : "Save as note"}
                          </button>
                        </div>
                        <div className="mt-4 grid gap-3 lg:grid-cols-2">
                          <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/30" : "border-stone-200 bg-stone-50"}`}>
                            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>World evidence</p>
                            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{item.world_evidence || "No direct world document excerpt was attached to this item."}</p>
                          </div>
                          <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/30" : "border-stone-200 bg-stone-50"}`}>
                            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Story evidence</p>
                            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{item.story_evidence || "No direct story excerpt was attached to this item."}</p>
                          </div>
                        </div>
                        <div className={`mt-4 rounded-[1rem] border px-4 py-3 ${isDark ? "border-amber-300/15 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.22em]">Suggested fix</p>
                          <p className="mt-2 text-sm leading-6">{item.suggested_fix}</p>
                        </div>
                      </article>
                    )
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className={`mt-5 rounded-[1.3rem] border border-dashed px-5 py-10 text-center ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
          {documents.length === 0
            ? "Upload at least one worldbuilding document to start the comparison."
            : "Run the detector to compare your world corpus against the story manuscript."}
        </div>
      )}
    </section>
  )

  const notesPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>World-gap notes</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Saved cleanup backlog</h2>
        </div>
        <button
          type="button"
          onClick={() => void loadNotes()}
          className={`rounded-full border px-3 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
        >
          Refresh notes
        </button>
      </div>
      {loadingNotes ? (
        <p className={`mt-5 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading saved world-gap notes...</p>
      ) : (
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <div className={`rounded-[1.3rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Open notes</p>
            <div className="mt-3 space-y-3">
              {groupedNotes.open.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No open world-gap notes right now.</p> : null}
              {groupedNotes.open.map((note) => (
                <article key={note.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || "Untitled note"}</h4>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        {note.context_label || "General world gap"} {note.chapter_number ? `· Chapter ${note.chapter_number}` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void setNoteStatus(note.id, "addressed")}
                      disabled={noteStatusId === note.id}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}
                    >
                      {noteStatusId === note.id ? "Updating..." : "Resolve"}
                    </button>
                  </div>
                  <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{note.body}</p>
                  {note.suggested_fix ? (
                    <p className={`mt-3 text-xs leading-6 ${isDark ? "text-amber-100" : "text-amber-900"}`}>
                      Suggested fix: {note.suggested_fix}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          </div>
          <div className={`rounded-[1.3rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Addressed notes</p>
            <div className="mt-3 space-y-3">
              {groupedNotes.addressed.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No resolved notes yet.</p> : null}
              {groupedNotes.addressed.map((note) => (
                <article key={note.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || "Untitled note"}</h4>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        Resolved {note.addressed_at ? new Date(note.addressed_at).toLocaleDateString() : "recently"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void setNoteStatus(note.id, "open")}
                      disabled={noteStatusId === note.id}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                    >
                      {noteStatusId === note.id ? "Updating..." : "Reopen"}
                    </button>
                  </div>
                  <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{note.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  )

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryTile label="Active docs" value={String(documents.length)} note="Separate from story chapters" isDark={isDark} />
        <SummaryTile label="Corpus words" value={totalWorldWords.toLocaleString()} note="Live reference material" isDark={isDark} />
        <SummaryTile label="Open notes" value={String(groupedNotes.open.length)} note="Saved cleanup backlog" isDark={isDark} />
      </div>
      {statusMessage ? (
        <div className={`rounded-[1.2rem] border px-4 py-3 text-sm ${isDark ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
          {statusMessage}
        </div>
      ) : null}
      <div className="grid gap-5 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/82"}`}>
          <div className="flex items-center justify-between gap-3">
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Documents</p>
            <button
              type="button"
              onClick={() => {
                setSelectedDocumentId(null)
                setDraftTitle("")
                setDraftText("")
              }}
              className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
            >
              New
            </button>
          </div>
          <div className="mt-4 space-y-2">
            {loadingDocuments ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading world documents...</p> : null}
            {!loadingDocuments && documents.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No world documents yet.</p> : null}
            {documents.map((document) => {
              const active = document.id === selectedDocumentId
              return (
                <button
                  key={document.id}
                  type="button"
                  onClick={() => void loadDocumentBody(document.id)}
                  className={`w-full rounded-[1rem] border px-3 py-3 text-left text-sm transition ${active ? isDark ? "border-amber-300/30 bg-amber-400/15 text-white" : "border-amber-300 bg-amber-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/8" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                >
                  <p className="font-semibold">{document.title}</p>
                  <p className="mt-1 text-xs opacity-75">
                    {document.word_count?.toLocaleString() ?? 0} words · {new Date(document.updated_at).toLocaleDateString()}
                  </p>
                </button>
              )
            })}
          </div>
        </aside>
        <div className="space-y-5">
          {uploadPanel}
          {loadingDocumentBody ? (
            <div className={`rounded-[1.6rem] border px-5 py-10 text-center ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-stone-200 bg-white/82 text-stone-500"}`}>
              Loading document content...
            </div>
          ) : null}
          {focus === "gap" ? (
            <>
              {analysisPanel}
              {editorPanel}
            </>
          ) : (
            <>
              {editorPanel}
              {analysisPanel}
            </>
          )}
          {notesPanel}
        </div>
      </div>
    </div>
  )
}

function SummaryTile({
  label,
  value,
  note,
  isDark,
}: {
  label: string
  value: string
  note: string
  isDark: boolean
}) {
  return (
    <div className={`rounded-[1.3rem] border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/85"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-3 text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{note}</p>
    </div>
  )
}

function severityClass(severity: string, isDark: boolean) {
  const normalized = severity.toLowerCase()
  if (normalized === "critical") {
    return isDark
      ? "rounded-full bg-rose-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-200"
      : "rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700"
  }
  if (normalized === "high") {
    return isDark
      ? "rounded-full bg-amber-400/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100"
      : "rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-800"
  }
  return isDark
    ? "rounded-full bg-white/8 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-200"
    : "rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-700"
}
