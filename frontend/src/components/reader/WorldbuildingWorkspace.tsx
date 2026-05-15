"use client"

import axios from "axios"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import type { Route } from "next"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, booksStatsCacheKey } from "@/lib/query/cacheKeys"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import type { UserStats } from "@/types/book"
import type {
  WorldBuildingDocument,
  WorldGapItem,
  WorldGapResult,
  WorldIntegrationResult,
  WorldNote,
  WorldQueryResponse,
  WikiEntry,
  CanonOverride,
  WorldElement,
} from "@/types/world-building"

type WorkspaceFocus = "editor" | "gap"

function getApiErrorDetail(error: unknown) {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : null
}

export function WorldbuildingWorkspace({
  bookId,
  isDark,
  focus = "editor",
}: {
  bookId: string
  isDark: boolean
  focus?: WorkspaceFocus
}) {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState("")
  const [draftText, setDraftText] = useState("")
  const [savingDocument, setSavingDocument] = useState(false)
  const [deletingDocument, setDeletingDocument] = useState(false)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [uploadTitle, setUploadTitle] = useState("")
  const [replaceCorpusOnUpload, setReplaceCorpusOnUpload] = useState(false)
  const [uploadingFiles, setUploadingFiles] = useState(false)
  const [analysis, setAnalysis] = useState<WorldGapResult | null>(null)
  const [integration, setIntegration] = useState<WorldIntegrationResult | null>(null)
  const [loadingIntegration, setLoadingIntegration] = useState(false)
  const [notes, setNotes] = useState<WorldNote[]>([])
  const [canonName, setCanonName] = useState("")
  const [canonAliases, setCanonAliases] = useState("")
  const [savingCanon, setSavingCanon] = useState(false)
  const [wikiGenerating, setWikiGenerating] = useState(false)
  const [logicQuery, setLogicQuery] = useState("")
  const [logicResult, setLogicResult] = useState<WorldQueryResponse | null>(null)
  const [logicLoading, setLogicLoading] = useState(false)
  const [noteSavingId, setNoteSavingId] = useState<string | null>(null)
  const [noteStatusId, setNoteStatusId] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [documentDraftDirty, setDocumentDraftDirty] = useState(false)

  const { data: documents = [], isLoading: loadingDocuments, refetch: refetchDocuments } = useQuery<WorldBuildingDocument[]>({
    queryKey: [`worldbuilding:${bookId}:documents`],
    queryFn: () => worldBuildingApi.listDocuments(bookId),
  })

  const { data: selectedDocumentData = null, isLoading: loadingDocumentBody, refetch: refetchSelectedDocument } = useQuery<(WorldBuildingDocument & { text: string }) | null>({
    queryKey: selectedDocumentId ? [`worldbuilding:${bookId}:document:${selectedDocumentId}`] : [`worldbuilding:${bookId}:document:none`],
    queryFn: async () => {
      if (!selectedDocumentId) return null
      return worldBuildingApi.getDocument(bookId, selectedDocumentId)
    },
    enabled: Boolean(selectedDocumentId),
  })

  const { data: notesData = [], isLoading: loadingNotes, refetch: refetchNotes } = useQuery<WorldNote[]>({
    queryKey: [`worldbuilding:${bookId}:notes`],
    queryFn: () => worldBuildingApi.listNotes(bookId),
  })

  const { data: canonOverrides = [], refetch: refetchCanonOverrides } = useQuery<CanonOverride[]>({
    queryKey: [`worldbuilding:${bookId}:canon-overrides`],
    queryFn: () => worldBuildingApi.listCanonOverrides(bookId),
  })

  const { data: extractedElements = [], isLoading: loadingElements, refetch: refetchElements } = useQuery<WorldElement[]>({
    queryKey: [`worldbuilding:${bookId}:elements`],
    queryFn: () => worldBuildingApi.listElements(bookId),
  })

  const { data: wikiEntries = [], isLoading: wikiLoading, refetch: refetchWiki } = useQuery<WikiEntry[]>({
    queryKey: [`worldbuilding:${bookId}:wiki`],
    queryFn: () => worldBuildingApi.listWiki(bookId),
  })

  const { data: uploadStats = null, refetch: refetchUploadStats } = useQuery<UserStats | null>({
    queryKey: asQueryKey(booksStatsCacheKey()),
    queryFn: () => booksApi.getStats(),
  })

  const { data: initialAnalysis = null, isLoading: loadingAnalysis, refetch: refetchAnalysis } = useQuery<WorldGapResult | null>({
    queryKey: [`worldbuilding:${bookId}:analysis:${focus}`],
    queryFn: () => worldBuildingApi.getGaps(bookId),
    enabled: focus === "gap" && documents.length > 0,
  })

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
  const wikiTypeSummary = useMemo(() => {
    return wikiEntries.reduce<Record<string, number>>((summary, entry) => {
      const key = entry.entry_type || "entry"
      summary[key] = (summary[key] ?? 0) + 1
      return summary
    }, {})
  }, [wikiEntries])
  const elementTypeSummary = useMemo(() => {
    return extractedElements.reduce<Record<string, number>>((summary, element) => {
      const key = element.element_type || "element"
      summary[key] = (summary[key] ?? 0) + 1
      return summary
    }, {})
  }, [extractedElements])

  const visibleElements = useMemo(() => {
    return [...extractedElements].sort((left, right) => {
      const leftScore = left.source_scope === "worldbuilding" ? 1 : 0
      const rightScore = right.source_scope === "worldbuilding" ? 1 : 0
      return rightScore - leftScore || right.usage_count - left.usage_count || left.name.localeCompare(right.name)
    }).slice(0, 18)
  }, [extractedElements])

  const runAnalysis = async () => {
    try {
      const { data: payload } = await refetchAnalysis()
      if (!payload) {
        setAnalysis(null)
        return
      }
      setAnalysis(payload)
      await refetchElements()
    } catch {
      setAnalysis(null)
    }
  }

  const runIntegration = async () => {
    setLoadingIntegration(true)
    try {
      const payload = await worldBuildingApi.getIntegration(bookId)
      setIntegration(payload)
      await refetchElements()
    } finally {
      setLoadingIntegration(false)
    }
  }

  useEffect(() => {
    setNotes(notesData)
  }, [notesData])

  useEffect(() => {
    if (!documents.length) {
      setSelectedDocumentId(null)
      if (!documentDraftDirty) {
        setDraftTitle("")
        setDraftText("")
      }
      return
    }
    if (selectedDocumentId && documents.some((document) => document.id === selectedDocumentId)) return
    setSelectedDocumentId(documents[0]?.id ?? null)
  }, [documentDraftDirty, documents, selectedDocumentId])

  useEffect(() => {
    if (!selectedDocumentData || documentDraftDirty) return
    setDraftTitle(selectedDocumentData.title)
    setDraftText(selectedDocumentData.text)
  }, [documentDraftDirty, selectedDocumentData])

  useEffect(() => {
    if (focus !== "gap") return
    if (!documents.length) {
      setAnalysis(null)
      return
    }
    if (initialAnalysis) {
      setAnalysis(initialAnalysis)
    }
  }, [documents.length, focus, initialAnalysis])

  useEffect(() => {
    if (!statusMessage) return
    const handle = window.setTimeout(() => setStatusMessage(null), 3200)
    return () => window.clearTimeout(handle)
  }, [statusMessage])

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
        setDocumentDraftDirty(false)
        await refetchDocuments()
        setSelectedDocumentId(updated.id)
        await refetchSelectedDocument()
        setStatusMessage(`Saved ${updated.title}.`)
      } else {
        const created = await worldBuildingApi.uploadDocuments(bookId, {
          title: draftTitle.trim() || "Worldbuilding Manuscript",
          text: draftText,
        })
        const nextSelected = created[0]?.id ?? null
        setDocumentDraftDirty(false)
        await refetchDocuments()
        setSelectedDocumentId(nextSelected)
        setStatusMessage(created.length ? `Created ${created[0].title}.` : "Created worldbuilding document.")
      }
      if (focus === "gap") {
        await runAnalysis()
      } else {
        await refetchElements()
      }
      await refetchUploadStats()
    } catch (error) {
      setStatusMessage(getApiErrorDetail(error) ?? "Could not save the worldbuilding document.")
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
      await refetchDocuments()
      setSelectedDocumentId(created[0]?.id ?? null)
      setDocumentDraftDirty(false)
      if (focus === "gap") {
        await runAnalysis()
      } else {
        await refetchElements()
      }
      setStatusMessage(
        replaceCorpusOnUpload
          ? "Replaced the active world corpus and loaded the new documents."
          : `Added ${created.length} worldbuilding document${created.length === 1 ? "" : "s"} to the corpus.`
      )
      await refetchUploadStats()
    } catch (error) {
      setStatusMessage(getApiErrorDetail(error) ?? "Could not import the worldbuilding files.")
    } finally {
      setUploadingFiles(false)
    }
  }

  const deleteDocument = async () => {
    if (!selectedDocumentId) return
    setDeletingDocument(true)
    try {
      await worldBuildingApi.deleteDocument(bookId, selectedDocumentId)
      setSelectedDocumentId(null)
      setDocumentDraftDirty(false)
      await refetchDocuments()
      if (focus === "gap") {
        await runAnalysis()
      } else {
        await refetchElements()
      }
      setStatusMessage("Removed that worldbuilding document from the active corpus.")
      await refetchUploadStats()
    } finally {
      setDeletingDocument(false)
    }
  }

  const saveGapAsNote = async (item: WorldGapItem) => {
    setNoteSavingId(item.id)
    try {
      await worldBuildingApi.createNote(bookId, {
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
      await refetchNotes()
    } finally {
      setNoteSavingId(null)
    }
  }

  const setNoteStatus = async (noteId: string, status: string) => {
    setNoteStatusId(noteId)
    try {
      await worldBuildingApi.updateNoteStatus(bookId, noteId, status)
      await refetchNotes()
    } finally {
      setNoteStatusId(null)
    }
  }

  const saveIntegrationAsNote = async (item: WorldIntegrationResult["integration_opportunities"][number]) => {
    setNoteSavingId(item.id)
    try {
      await worldBuildingApi.createNote(bookId, {
        world_document_id: item.world_document_id,
        note_type: "world_integration",
        chapter_number: item.target_chapter ?? null,
        title: item.element_name,
        body: item.description,
        priority: item.priority >= 8 ? "critical" : item.priority >= 6 ? "high" : "medium",
        status: "open",
        linked_integration_id: item.id,
        context_label: item.world_document_title ?? item.element_type,
        suggested_fix: item.suggestions.join(" "),
      })
      await refetchNotes()
    } finally {
      setNoteSavingId(null)
    }
  }

  const deleteNote = async (noteId: string) => {
    setNoteStatusId(noteId)
    try {
      await worldBuildingApi.deleteNote(bookId, noteId)
      await refetchNotes()
    } finally {
      setNoteStatusId(null)
    }
  }

  const saveCanonOverride = async () => {
    if (!canonName.trim()) return
    setSavingCanon(true)
    try {
      const saved = await worldBuildingApi.saveCanonOverride(bookId, {
        canonical_name: canonName.trim(),
        aliases: canonAliases.split(",").map((item) => item.trim()).filter(Boolean),
      })
      await refetchCanonOverrides()
      setCanonName("")
      setCanonAliases("")
      setStatusMessage(`Saved canon override for ${saved.canonical_name}.`)
    } finally {
      setSavingCanon(false)
    }
  }

  const acceptElementSuggestion = async (element: WorldElement, suggestion: Record<string, unknown> | string) => {
    const suggestionId = typeof suggestion === "string" ? suggestion : String(suggestion.id ?? suggestion.title ?? suggestion.name ?? "")
    if (!suggestionId) return
    await worldBuildingApi.acceptSuggestion(element.id, { suggestion_id: suggestionId, mark_implemented: true })
    const removeSuggestion = (item: WorldElement) => item.id === element.id
      ? {
          ...item,
          suggestions: item.suggestions.filter((candidate) => {
            const candidateId = typeof candidate === "string" ? candidate : String(candidate.id ?? candidate.title ?? candidate.name ?? "")
            return candidateId !== suggestionId
          }),
        }
      : item
    setIntegration((current) => current ? { ...current, world_elements: current.world_elements.map(removeSuggestion) } : current)
    setAnalysis((current) => current ? { ...current, world_elements: current.world_elements.map(removeSuggestion) } : current)
    setStatusMessage("Marked that world suggestion as implemented.")
  }

  const generateWiki = async () => {
    setWikiGenerating(true)
    try {
      const payload = await worldBuildingApi.generateWiki(bookId)
      await refetchWiki()
      setStatusMessage(
        payload.updated_names.length
          ? `Generated or refreshed ${payload.generated_count} wiki entries from the manuscript, including ${payload.updated_names.slice(0, 3).join(", ")}.`
          : `Generated or refreshed ${payload.generated_count} wiki entries from the manuscript.`
      )
    } finally {
      setWikiGenerating(false)
    }
  }

  const runLogicQuery = async (mode?: string) => {
    if (!logicQuery.trim()) return
    setLogicLoading(true)
    try {
      const payload = await worldBuildingApi.query(bookId, { query: logicQuery.trim(), mode: mode ?? "story_integration" })
      setLogicResult(payload)
      setStatusMessage(mode === "gap_detection" ? "Ran a canon stress test against the active world corpus." : "Ran the world logic simulator against the active canon.")
    } finally {
      setLogicLoading(false)
    }
  }

  const uploadLimitNote = uploadStats
    ? uploadStats.private.upload_limit_unlimited
      ? "Worldbuilding manuscripts count as uploads on every tier. Lore Architect remains unlimited, including for series-linked worldbuilding."
      : typeof uploadStats.private.upload_limit === "number"
        ? `${uploadStats.private.total_uploads}/${uploadStats.private.upload_limit} uploads used. ${uploadStats.private.uploads_remaining ?? 0} remaining. Worldbuilding manuscripts count as uploads on every tier, and series-linked worldbuilding counts once per book in the series.`
        : null
    : null

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
        {uploadLimitNote ? (
          <div className={`rounded-[1rem] border px-4 py-3 text-xs leading-5 ${isDark ? "border-white/10 bg-black/30 text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
            {uploadLimitNote}
          </div>
        ) : null}
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
          onChange={(event) => {
            setDraftTitle(event.target.value)
            setDocumentDraftDirty(true)
          }}
          placeholder="Document title"
          className={`rounded-[1rem] border px-4 py-3 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
        <textarea
          value={draftText}
          onChange={(event) => {
            setDraftText(event.target.value)
            setDocumentDraftDirty(true)
          }}
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
              setDocumentDraftDirty(false)
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

  const elementBrowserPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>Extracted elements</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Countries, regions, races, magic, and lore</h2>
        </div>
        <button
          type="button"
          onClick={() => void refetchElements()}
          disabled={loadingElements}
          className={`rounded-full border px-3 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
        >
          {loadingElements ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {Object.entries(elementTypeSummary).slice(0, 10).map(([type, count]) => (
          <span key={type} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
            {formatElementType(type)} {count}
          </span>
        ))}
        {Object.keys(elementTypeSummary).length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No extracted world elements yet.</p> : null}
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {visibleElements.map((element) => (
          <article key={element.id} className={`rounded-[1.1rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-sky-500/10 text-sky-200" : "bg-sky-50 text-sky-700"}`}>{formatElementType(element.element_type)}</span>
              <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-white text-stone-600"}`}>{element.source_scope}</span>
              {element.confidence ? <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-white text-stone-600"}`}>{Math.round(element.confidence * 100)}%</span> : null}
            </div>
            <h3 className={`mt-3 text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{element.name}</h3>
            {element.description ? (
              <p className={`mt-2 line-clamp-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{element.description}</p>
            ) : null}
            <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
              {element.usage_count.toLocaleString()} mention{element.usage_count === 1 ? "" : "s"}
              {element.chapter_numbers.length ? ` - ${element.chapter_numbers.length} chapter${element.chapter_numbers.length === 1 ? "" : "s"}` : ""}
              {element.world_document_title ? ` - ${element.world_document_title}` : ""}
            </p>
          </article>
        ))}
      </div>
    </section>
  )

  const wikiPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>Auto wiki</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Generate wiki entries from manuscript text</h2>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void refetchWiki()}
            className={`rounded-full border px-3 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={() => void generateWiki()}
            disabled={wikiGenerating}
            className="rounded-full bg-[linear-gradient(135deg,#0891b2,#0e7490)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
          >
            {wikiGenerating ? "Generating..." : "Generate wiki"}
          </button>
        </div>
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        <div className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>World logic engine</p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Query the current canon, then inspect alerts, next moves, and source citations in one place.
          </p>
          <textarea
            value={logicQuery}
            onChange={(event) => setLogicQuery(event.target.value)}
            rows={5}
            placeholder="Ask how a kingdom, faction, culture, or world rule would react based on your current canon."
            className={`mt-3 w-full rounded-[1rem] border px-4 py-3 text-sm leading-7 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => void runLogicQuery("story_integration")} disabled={logicLoading || !logicQuery.trim()} className="rounded-full bg-[linear-gradient(135deg,#059669,#047857)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">
              {logicLoading ? "Thinking..." : "Run simulator"}
            </button>
            <button type="button" onClick={() => void runLogicQuery("gap_detection")} disabled={logicLoading || !logicQuery.trim()} className={`rounded-full border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"} disabled:opacity-50`}>
              Canon stress test
            </button>
          </div>
          {logicResult ? (
            <div className={`mt-4 rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
              <div className="flex flex-wrap gap-2">
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>
                  {logicResult.mode === "gap_detection" ? "Canon stress test" : "Story integration"}
                </span>
                {logicResult.logic_alerts.length > 0 ? (
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}>
                    {logicResult.logic_alerts.length} alert{logicResult.logic_alerts.length === 1 ? "" : "s"}
                  </span>
                ) : null}
                {logicResult.citations.length > 0 ? (
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-cyan-500/10 text-cyan-200" : "bg-cyan-50 text-cyan-700"}`}>
                    {logicResult.citations.length} citation{logicResult.citations.length === 1 ? "" : "s"}
                  </span>
                ) : null}
              </div>
              <p className={`text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{logicResult.answer}</p>
              {logicResult.simulation_steps.length > 0 ? (
                <div className="mt-3 space-y-2">
                  {logicResult.simulation_steps.map((step) => (
                    <p key={step} className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{step}</p>
                  ))}
                </div>
              ) : null}
              {logicResult.logic_alerts.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-rose-300" : "text-rose-700"}`}>Logic alerts</p>
                  {logicResult.logic_alerts.map((alert, index) => (
                    <div key={`alert-${index}`} className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-rose-400/20 bg-rose-500/10 text-rose-100" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
                      {summarizeRecord(alert)}
                    </div>
                  ))}
                </div>
              ) : null}
              {logicResult.suggestions.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Suggested next moves</p>
                  {logicResult.suggestions.map((suggestion, index) => (
                    <div key={`suggestion-${index}`} className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                      {summarizeRecord(suggestion)}
                    </div>
                  ))}
                </div>
              ) : null}
              {logicResult.citations.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>Source citations</p>
                  {logicResult.citations.slice(0, 4).map((citation, index) => (
                    <div key={`citation-${index}`} className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                      {summarizeRecord(citation)}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Generated entries</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-white text-stone-600"}`}>
              {wikiEntries.length} total
            </span>
            {Object.entries(wikiTypeSummary).slice(0, 3).map(([type, count]) => (
              <span key={type} className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-cyan-500/10 text-cyan-200" : "bg-cyan-50 text-cyan-700"}`}>
                {count} {type}
              </span>
            ))}
          </div>
          <div className="mt-3 space-y-3">
            {wikiLoading ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading wiki entries...</p> : null}
            {!wikiLoading && wikiEntries.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No wiki entries yet. Generate them from the manuscript whenever you want a fresh lore index.</p> : null}
            {wikiEntries.slice(0, 10).map((entry) => (
              <article key={entry.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                <div className="flex items-center justify-between gap-3">
                  <h4 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{entry.name}</h4>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-stone-100 text-stone-600"}`}>{entry.entry_type}</span>
                </div>
                {entry.first_mention ? <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>First mention: chapter {entry.first_mention}</p> : null}
                {entry.description ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{entry.description}</p> : null}
              </article>
            ))}
          </div>
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
          {analysis.consistency_flags.length > 0 ? (
            <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h3 className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Consistency flags</h3>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>These checks caught conflicting definitions inside the extracted canon, even before broader gap grouping is applied.</p>
                </div>
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                  {analysis.consistency_flags.length} item{analysis.consistency_flags.length === 1 ? "" : "s"}
                </p>
              </div>
              <div className="mt-4 grid gap-3">
                {analysis.consistency_flags.map((flag, index) => (
                  <article key={String(flag.id ?? `consistency-${index}`)} className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={severityClass("high", isDark)}>high</span>
                      {flag.type ? (
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/6 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
                          {String(flag.type).replaceAll("_", " ")}
                        </span>
                      ) : null}
                    </div>
                    <h4 className={`mt-3 text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{String(flag.title ?? "Consistency flag")}</h4>
                    <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{String(flag.description ?? "LoreVia found an extracted canon definition that needs a closer pass.")}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
          {analysis.gap_groups.length === 0 && analysis.consistency_flags.length === 0 ? (
            <div className={`rounded-[1.3rem] border px-5 py-8 text-sm ${isDark ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
              No hard contradiction surfaced in this pass, but this world still benefits from another canon sweep for coverage, setup, and repeat exposure.
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
                             {item.canonical_name ? (
                               <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                                 Canon: {item.canonical_name}
                                 {item.entity_type ? ` · ${item.entity_type}` : ""}
                                 {item.confidence ? ` · ${(item.confidence * 100).toFixed(0)}% confidence` : ""}
                               </p>
                             ) : null}
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

  const integrationPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>World integration</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Underused canon and story opportunities</h2>
        </div>
        <button
          type="button"
          onClick={() => void runIntegration()}
          disabled={loadingIntegration || documents.length === 0}
          className={`rounded-[1rem] border px-4 py-3 text-sm font-semibold ${isDark ? "border-emerald-300/20 bg-emerald-400/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-800"} disabled:opacity-50`}
        >
          {loadingIntegration ? "Mapping..." : "Run integration analysis"}
        </button>
      </div>
      {integration ? (
        <div className="mt-5 grid gap-3">
          {integration.integration_opportunities.length === 0 ? (
            <p className={`rounded-[1rem] border px-4 py-5 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-400" : "border-stone-200 bg-stone-50 text-stone-500"}`}>
              No underused world elements surfaced on this pass.
            </p>
          ) : null}
          {integration.integration_opportunities.map((item) => (
            <article key={item.id} className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>{item.element_type}</span>
                    {item.target_chapter ? <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-white text-stone-600"}`}>Chapter {item.target_chapter}</span> : null}
                  </div>
                  <h3 className={`mt-3 text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{item.element_name}</h3>
                  <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{item.description}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void saveIntegrationAsNote(item)}
                  disabled={noteSavingId === item.id}
                  className="rounded-[1rem] bg-[linear-gradient(135deg,#059669,#047857)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {noteSavingId === item.id ? "Saving..." : "Save as note"}
                </button>
              </div>
              {item.suggestions.length > 0 ? (
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {item.suggestions.map((suggestion) => (
                    <p key={suggestion} className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-white bg-white text-stone-700"}`}>
                      {suggestion}
                    </p>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className={`mt-5 rounded-[1rem] border border-dashed px-4 py-6 text-center text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
          Run integration analysis to find world elements that need stronger story presence.
        </p>
      )}
    </section>
  )

  const canonPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-fuchsia-300" : "text-fuchsia-700"}`}>Canon overrides</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Tell LoreVia which names are the same thing</h2>
        </div>
        <button
          type="button"
          onClick={() => void refetchCanonOverrides()}
          className={`rounded-full border px-3 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
        >
          Refresh
        </button>
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
        <input
          value={canonName}
          onChange={(event) => setCanonName(event.target.value)}
          placeholder="Canonical name"
          className={`rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
        <input
          value={canonAliases}
          onChange={(event) => setCanonAliases(event.target.value)}
          placeholder="Aliases, comma separated"
          className={`rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
        <button
          type="button"
          onClick={() => void saveCanonOverride()}
          disabled={savingCanon || !canonName.trim()}
          className="rounded-[1rem] bg-[linear-gradient(135deg,#c026d3,#9333ea)] px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
        >
          {savingCanon ? "Saving..." : "Save override"}
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {canonOverrides.map((item) => (
          <span key={item.id} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
            {item.canonical_name}{item.aliases.length ? `: ${item.aliases.join(", ")}` : ""}
          </span>
        ))}
        {canonOverrides.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No author canon overrides yet.</p> : null}
      </div>
    </section>
  )

  const elementSuggestionsPanel = (
    <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Element suggestions</p>
      <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Accept implemented world suggestions</h2>
      <div className="mt-5 grid gap-3">
        {((integration?.world_elements ?? analysis?.world_elements ?? []).filter((element) => element.suggestions.length > 0)).slice(0, 10).map((element) => (
          <article key={element.id} className={`rounded-[1.1rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
            <h3 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{element.name}</h3>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {element.suggestions.map((suggestion, index) => (
                <div key={`${element.id}-${index}`} className={`rounded-[0.9rem] border p-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-white bg-white text-stone-700"}`}>
                  <p>{summarizeRecord(suggestion)}</p>
                  <button
                    type="button"
                    onClick={() => void acceptElementSuggestion(element, suggestion)}
                    className={`mt-3 rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-amber-300 text-stone-950" : "bg-stone-900 text-white"}`}
                  >
                    Mark implemented
                  </button>
                </div>
              ))}
            </div>
          </article>
        ))}
        {((integration?.world_elements ?? analysis?.world_elements ?? []).filter((element) => element.suggestions.length > 0)).length === 0 ? (
          <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No pending element suggestions are available right now.</p>
        ) : null}
      </div>
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
          onClick={() => void refetchNotes()}
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
                    <button
                      type="button"
                      onClick={() => void deleteNote(note.id)}
                      disabled={noteStatusId === note.id}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}
                    >
                      Delete
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
                    <button
                      type="button"
                      onClick={() => void deleteNote(note.id)}
                      disabled={noteStatusId === note.id}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}
                    >
                      Delete
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
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryTile label="Active docs" value={String(documents.length)} note="Separate from story chapters" isDark={isDark} />
        <SummaryTile label="Corpus words" value={totalWorldWords.toLocaleString()} note="Live reference material" isDark={isDark} />
        <SummaryTile label="Extracted lore" value={String(extractedElements.length)} note="Typed world elements" isDark={isDark} />
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
                  onClick={() => {
                    setSelectedDocumentId(document.id)
                    setDocumentDraftDirty(false)
                  }}
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
              {integrationPanel}
              {canonPanel}
              {elementSuggestionsPanel}
              {elementBrowserPanel}
              {wikiPanel}
              {editorPanel}
            </>
          ) : (
            <>
              {editorPanel}
              {elementBrowserPanel}
              {wikiPanel}
              {analysisPanel}
              {integrationPanel}
              {canonPanel}
              {elementSuggestionsPanel}
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

function summarizeRecord(record: Record<string, unknown>) {
  const preferredKeys = [
    "title",
    "label",
    "name",
    "description",
    "summary",
    "message",
    "reason",
    "excerpt",
    "chapter_title",
    "source",
  ]

  for (const key of preferredKeys) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }

  return Object.entries(record)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 3)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`)
    .join(" · ")
}

function formatElementType(type: string) {
  return (type || "element").replaceAll("_", " ")
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
