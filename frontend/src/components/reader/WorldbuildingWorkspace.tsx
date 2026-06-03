"use client"

import axios from "axios"
import { useQuery } from "@tanstack/react-query"
import { memo, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import Link from "next/link"
import type { Route } from "next"

import { booksApi } from "@/lib/api/books"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { asQueryKey, booksStatsCacheKey } from "@/lib/query/cacheKeys"
import type { UserStats } from "@/types/book"
import type {
  CanonOverride,
  WikiEntry,
  WorldBuildingDocument,
  WorldElement,
  WorldGapItem,
  WorldGapResult,
  WorldIntegrationResult,
  WorldNote,
  WorldQueryResponse,
} from "@/types/world-building"

type WorkspaceFocus = "editor" | "gap"
const INITIAL_DOCUMENT_COUNT = 10
const INITIAL_GAP_ITEMS_PER_GROUP = 4
const INITIAL_OPPORTUNITY_COUNT = 4
const INITIAL_SUGGESTION_COUNT = 6
const INITIAL_ELEMENT_COUNT = 6
const INITIAL_WIKI_COUNT = 6

function getApiErrorDetail(error: unknown) {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : null
}

export const WorldbuildingWorkspace = memo(function WorldbuildingWorkspace({
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
  const [showAllDocuments, setShowAllDocuments] = useState(false)
  const [expandedGapGroups, setExpandedGapGroups] = useState<Record<string, boolean>>({})
  const [showAllOpportunities, setShowAllOpportunities] = useState(false)
  const [showAllSuggestions, setShowAllSuggestions] = useState(false)
  const [showAllElements, setShowAllElements] = useState(false)
  const [showAllWikiEntries, setShowAllWikiEntries] = useState(false)

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

  const { data: notes = [], isLoading: loadingNotes, refetch: refetchNotes } = useQuery<WorldNote[]>({
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
  const suggestionElements = useMemo(
    () => (integration?.world_elements ?? analysis?.world_elements ?? []).filter((element) => element.suggestions.length > 0),
    [analysis?.world_elements, integration?.world_elements]
  )
  const visibleElements = useMemo(() => {
    return [...extractedElements]
      .sort((left, right) => {
        const leftScore = left.source_scope === "worldbuilding" ? 1 : 0
        const rightScore = right.source_scope === "worldbuilding" ? 1 : 0
        return rightScore - leftScore || right.usage_count - left.usage_count || left.name.localeCompare(right.name)
      })
      .slice(0, 18)
  }, [extractedElements])
  const visibleDocuments = useMemo(
    () => showAllDocuments ? documents : documents.slice(0, INITIAL_DOCUMENT_COUNT),
    [documents, showAllDocuments]
  )
  const visibleOpportunities = useMemo(
    () => showAllOpportunities ? (integration?.integration_opportunities ?? []) : (integration?.integration_opportunities ?? []).slice(0, INITIAL_OPPORTUNITY_COUNT),
    [integration?.integration_opportunities, showAllOpportunities]
  )
  const visibleSuggestionElements = useMemo(
    () => showAllSuggestions ? suggestionElements : suggestionElements.slice(0, INITIAL_SUGGESTION_COUNT),
    [showAllSuggestions, suggestionElements]
  )
  const visibleElementCards = useMemo(
    () => showAllElements ? visibleElements : visibleElements.slice(0, INITIAL_ELEMENT_COUNT),
    [showAllElements, visibleElements]
  )
  const visibleWikiEntries = useMemo(
    () => showAllWikiEntries ? wikiEntries : wikiEntries.slice(0, INITIAL_WIKI_COUNT),
    [showAllWikiEntries, wikiEntries]
  )

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
      ? "Worldbuilding manuscripts count as uploads on every tier. Architect remains unlimited, including for series-linked worldbuilding."
      : typeof uploadStats.private.upload_limit === "number"
        ? `${uploadStats.private.total_uploads}/${uploadStats.private.upload_limit} uploads used. ${uploadStats.private.uploads_remaining ?? 0} remaining. Worldbuilding manuscripts count as uploads on every tier, and series-linked worldbuilding counts once per book in the series.`
        : null
    : null

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Active Docs" value={String(documents.length)} note="Separate from story chapters" accent="teal" isDark={isDark} />
        <MetricCard label="Corpus Words" value={totalWorldWords.toLocaleString()} note="Live reference material" accent="blue" isDark={isDark} />
        <MetricCard label="Extracted Lore" value={String(extractedElements.length)} note="Typed world elements" accent="violet" isDark={isDark} />
        <MetricCard label="Open Notes" value={String(groupedNotes.open.length)} note="Saved cleanup backlog" accent="amber" isDark={isDark} />
      </div>

      {statusMessage ? (
        <div className={`rounded-md border px-4 py-3 text-sm ${isDark ? "border-teal-400/20 bg-teal-500/10 text-teal-100" : "border-teal-200 bg-teal-50 text-teal-800"}`}>
          {statusMessage}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[17.5rem_minmax(0,1fr)]">
        <aside className={`overflow-hidden rounded-lg border ${panelClass(isDark)}`}>
          <div className={`border-b px-5 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`} />
          <div className={`flex items-center justify-between border-b px-5 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <div>
              <p className={eyebrowClass(isDark)}>Documents</p>
              <p className={`mt-2 text-sm ${mutedTextClass(isDark)}`}>Reference docs stay separate from the manuscript.</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setSelectedDocumentId(null)
                setDraftTitle("")
                setDraftText("")
                setDocumentDraftDirty(false)
              }}
              className={secondaryButtonClass(isDark)}
            >
              New
            </button>
          </div>
          <div className="p-4">
            {loadingDocuments ? <LoadingState label="Loading world documents..." isDark={isDark} /> : null}
            {!loadingDocuments && documents.length === 0 ? (
              <EmptyState
                title="No world documents yet."
                description="Add or upload reference documents to begin."
                isDark={isDark}
              />
            ) : null}
            <div className="space-y-2">
              <div className="space-y-2 xl:max-h-[1080px] xl:overflow-y-auto xl:pr-1">
              {visibleDocuments.map((document) => {
                const active = document.id === selectedDocumentId
                return (
                  <button
                    key={document.id}
                    type="button"
                    onClick={() => {
                      setSelectedDocumentId(document.id)
                      setDocumentDraftDirty(false)
                    }}
                    className={`w-full rounded-md border px-4 py-3 text-left transition ${active
                      ? isDark
                        ? "border-teal-400/35 bg-teal-500/12 text-white"
                        : "border-teal-300 bg-teal-50 text-stone-950"
                      : isDark
                        ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]"
                        : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                  >
                    <p className="truncate text-sm font-semibold">{document.title}</p>
                    <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>
                      {(document.word_count ?? 0).toLocaleString()} words - {new Date(document.updated_at).toLocaleDateString()}
                    </p>
                  </button>
                )
              })}
              </div>
              {!loadingDocuments && documents.length > INITIAL_DOCUMENT_COUNT ? (
                <button
                  type="button"
                  onClick={() => setShowAllDocuments((current) => !current)}
                  className={`${secondaryButtonClass(isDark)} w-full`}
                >
                  {showAllDocuments ? "Show fewer documents" : `Show all ${documents.length} documents`}
                </button>
              ) : null}
            </div>
          </div>
        </aside>

        <div className="space-y-4">
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
                      onChange={(event) => setUploadTitle(event.target.value)}
                      placeholder="Optional shared title"
                      className={inputClass(isDark)}
                    />
                  </LabeledField>

                  <div className={`rounded-lg border border-dashed p-4 ${isDark ? "border-white/12 bg-[#07111f]" : "border-stone-300 bg-stone-50"}`}>
                    <label className="block cursor-pointer">
                      <span className="sr-only">Upload world corpus files</span>
                      <input
                        type="file"
                        multiple
                        onChange={(event) => setUploadFiles(Array.from(event.target.files ?? []))}
                        className="sr-only"
                      />
                      <div className="space-y-2">
                        <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-stone-900"}`}>
                          Drag and drop files here, or click to browse
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
                      onChange={(event) => setReplaceCorpusOnUpload(event.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      <span className={`block font-medium ${isDark ? "text-slate-100" : "text-stone-900"}`}>Replace active world corpus</span>
                      <span className={`mt-1 block text-xs ${mutedTextClass(isDark)}`}>Use the uploaded files instead of appending to the current corpus.</span>
                    </span>
                  </label>

                  <button
                    type="button"
                    onClick={uploadDocumentFiles}
                    disabled={uploadingFiles || uploadFiles.length === 0}
                    className={primaryButtonClass("teal")}
                  >
                    {uploadingFiles ? "Uploading..." : replaceCorpusOnUpload ? "Replace corpus" : "Add to corpus"}
                  </button>
                </div>
              </div>
            </div>
          </WorkspaceCard>

          {loadingDocumentBody ? (
            <div className={`rounded-lg border px-5 py-10 text-center ${panelClass(isDark)}`}>
              <p className={`text-sm ${mutedTextClass(isDark)}`}>Loading document content...</p>
            </div>
          ) : null}

          <WorkspaceCard
            number="2"
            sectionLabel="Gap Analysis"
            title="Grouped inconsistencies and cleanup notes"
            description={analysis?.generated_at ? `Last run ${new Date(analysis.generated_at).toLocaleString()}` : "Run a pass after updating the world corpus or story manuscript to surface inconsistencies and cleanup notes."}
            isDark={isDark}
            action={(
              <button
                type="button"
                onClick={() => void runAnalysis()}
                disabled={loadingAnalysis || documents.length === 0}
                className={secondaryButtonClass(isDark)}
              >
                {loadingAnalysis ? "Checking gaps..." : "Run gap detection"}
              </button>
            )}
          >
            {loadingAnalysis ? (
              <LoadingState label="Comparing the world corpus against chapters, characters, and timeline signals..." isDark={isDark} />
            ) : analysis ? (
              <div className="space-y-4">
                {analysis.consistency_flags.length > 0 ? (
                  <SectionPanel
                    title="Consistency flags"
                    meta={`${analysis.consistency_flags.length} item${analysis.consistency_flags.length === 1 ? "" : "s"}`}
                    description="These checks caught conflicting definitions inside the extracted canon before broader gap grouping was applied."
                    isDark={isDark}
                  >
                    <div className="grid gap-3">
                      {analysis.consistency_flags.map((flag, index) => (
                        <article key={String(flag.id ?? `consistency-${index}`)} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={severityClass("high", isDark)}>high</span>
                            {flag.type ? <span className={badgeClass(isDark)}>{String(flag.type).replaceAll("_", " ")}</span> : null}
                          </div>
                          <h4 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{String(flag.title ?? "Consistency flag")}</h4>
                          <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{String(flag.description ?? "LoreVia found an extracted canon definition that needs a closer pass.")}</p>
                        </article>
                      ))}
                    </div>
                  </SectionPanel>
                ) : null}

                {analysis.gap_groups.length === 0 && analysis.consistency_flags.length === 0 ? (
                  <EmptyState
                    title="No analysis yet."
                    description="Upload reference docs and run gap detection to see results here."
                    isDark={isDark}
                  />
                ) : (
                  analysis.gap_groups.map((group) => (
                    <SectionPanel
                      key={group.key}
                      title={group.label}
                      meta={`${group.items.length} item${group.items.length === 1 ? "" : "s"}`}
                      description={group.description ?? undefined}
                      isDark={isDark}
                    >
                      <div className="grid gap-3">
                        {(expandedGapGroups[group.key] ? group.items : group.items.slice(0, INITIAL_GAP_ITEMS_PER_GROUP)).map((item) => {
                          const alreadySaved = openGapIds.has(item.id)
                          return (
                            <article key={item.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className={severityClass(item.severity, isDark)}>{item.severity}</span>
                                    {item.world_document_title ? <span className={badgeClass(isDark)}>{item.world_document_title}</span> : null}
                                    {item.story_chapter_number ? (
                                      <Link href={`/${bookId}/chapter/${item.story_chapter_number}`} className={accentBadgeClass("blue", isDark)}>
                                        Chapter {item.story_chapter_number}
                                      </Link>
                                    ) : null}
                                  </div>
                                  <h4 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{item.title}</h4>
                                  {item.canonical_name ? (
                                    <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>
                                      Canon: {item.canonical_name}
                                      {item.entity_type ? ` - ${item.entity_type}` : ""}
                                      {item.confidence ? ` - ${(item.confidence * 100).toFixed(0)}% confidence` : ""}
                                    </p>
                                  ) : null}
                                  <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{item.description}</p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => void saveGapAsNote(item)}
                                  disabled={alreadySaved || noteSavingId === item.id}
                                  className={alreadySaved ? mutedActionClass(isDark, "teal") : primaryButtonClass("violet")}
                                >
                                  {alreadySaved ? "Saved to notes" : noteSavingId === item.id ? "Saving..." : "Save as note"}
                                </button>
                              </div>

                              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                                <EvidencePanel title="World evidence" body={item.world_evidence || "No direct world document excerpt was attached to this item."} isDark={isDark} />
                                <EvidencePanel title="Story evidence" body={item.story_evidence || "No direct story excerpt was attached to this item."} isDark={isDark} />
                              </div>

                              <div className={`mt-4 rounded-md border px-4 py-3 ${isDark ? "border-amber-300/15 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
                                <p className="text-3xs font-semibold uppercase tracking-[0.22em]">Suggested fix</p>
                                <p className="mt-2 text-sm leading-6">{item.suggested_fix}</p>
                              </div>
                            </article>
                          )
                        })}
                      </div>
                      {group.items.length > INITIAL_GAP_ITEMS_PER_GROUP ? (
                        <button
                          type="button"
                          onClick={() => setExpandedGapGroups((current) => ({ ...current, [group.key]: !current[group.key] }))}
                          className={`mt-3 ${secondaryButtonClass(isDark)}`}
                        >
                          {expandedGapGroups[group.key] ? "Show fewer items" : `Show all ${group.items.length} items`}
                        </button>
                      ) : null}
                    </SectionPanel>
                  ))
                )}
              </div>
            ) : (
              <EmptyState
                title="No analysis yet."
                description={documents.length === 0
                  ? "Upload reference docs and run gap detection to see results here."
                  : "No analysis yet. Upload reference docs and run gap detection to see results here."}
                isDark={isDark}
              />
            )}
          </WorkspaceCard>

          <WorkspaceCard
            number="3"
            sectionLabel="Opportunities"
            title="Underused canon and story opportunities"
            description="Find world elements that could strengthen story presence."
            isDark={isDark}
            action={(
              <button
                type="button"
                onClick={() => void runIntegration()}
                disabled={loadingIntegration || documents.length === 0}
                className={secondaryButtonClass(isDark)}
              >
                {loadingIntegration ? "Mapping..." : "Run opportunities scan"}
              </button>
            )}
          >
            {integration ? (
              <div className="space-y-3">
                {integration.integration_opportunities.length === 0 ? (
                  <EmptyState
                    title="No opportunities yet."
                    description="Run the scan to discover underused canon elements."
                    isDark={isDark}
                  />
                ) : (
                  visibleOpportunities.map((item) => (
                    <article key={item.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap gap-2">
                            <span className={accentBadgeClass("teal", isDark)}>{item.element_type}</span>
                            {item.target_chapter ? <span className={badgeClass(isDark)}>Chapter {item.target_chapter}</span> : null}
                          </div>
                          <h3 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{item.element_name}</h3>
                          <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{item.description}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => void saveIntegrationAsNote(item)}
                          disabled={noteSavingId === item.id}
                          className={primaryButtonClass("teal")}
                        >
                          {noteSavingId === item.id ? "Saving..." : "Save as note"}
                        </button>
                      </div>
                      {item.suggestions.length > 0 ? (
                        <div className="mt-4 grid gap-2 md:grid-cols-2">
                          {item.suggestions.map((suggestion) => (
                            <p key={suggestion} className={`rounded-xl border px-3 py-2 text-sm ${softPanelClass(isDark)}`}>
                              {suggestion}
                            </p>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))
                )}
                {integration.integration_opportunities.length > INITIAL_OPPORTUNITY_COUNT ? (
                  <button
                    type="button"
                    onClick={() => setShowAllOpportunities((current) => !current)}
                    className={secondaryButtonClass(isDark)}
                  >
                    {showAllOpportunities ? "Show fewer opportunities" : `Show all ${integration.integration_opportunities.length} opportunities`}
                  </button>
                ) : null}
              </div>
            ) : (
              <EmptyState
                title="No opportunities yet."
                description="No opportunities yet. Run the scan to discover underused canon elements."
                isDark={isDark}
              />
            )}
          </WorkspaceCard>

          <WorkspaceCard
            number="4"
            sectionLabel="Canon Overrides"
            title="Canon Overrides / Aliases"
            description="Map names and aliases to keep your canon consistent."
            isDark={isDark}
            action={(
              <button type="button" onClick={() => void refetchCanonOverrides()} className={secondaryButtonClass(isDark)}>
                Refresh
              </button>
            )}
          >
            <div className="space-y-4">
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                <LabeledField label="Canonical name" isDark={isDark}>
                  <input
                    value={canonName}
                    onChange={(event) => setCanonName(event.target.value)}
                    placeholder="Enter canonical name"
                    className={inputClass(isDark)}
                  />
                </LabeledField>
                <LabeledField label="Aliases" isDark={isDark}>
                  <input
                    value={canonAliases}
                    onChange={(event) => setCanonAliases(event.target.value)}
                    placeholder="e.g., Altdor, Alt-dore"
                    className={inputClass(isDark)}
                  />
                </LabeledField>
                <div className="flex items-end">
                  <button
                    type="button"
                    onClick={() => void saveCanonOverride()}
                    disabled={savingCanon || !canonName.trim()}
                    className={primaryButtonClass("violet")}
                  >
                    {savingCanon ? "Saving..." : "Save override"}
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {canonOverrides.map((item) => (
                  <span key={item.id} className={badgeClass(isDark)}>
                    {item.canonical_name}{item.aliases.length ? `: ${item.aliases.join(", ")}` : ""}
                  </span>
                ))}
                {canonOverrides.length === 0 ? <p className={`text-sm ${mutedTextClass(isDark)}`}>No alias overrides yet.</p> : null}
              </div>
            </div>
          </WorkspaceCard>

          <div className="grid gap-5 xl:grid-cols-2">
            <WorkspaceCard
              number="5"
              sectionLabel="Element Suggestions"
              title="Element Suggestions"
              description={suggestionElements.length > 0 ? `${suggestionElements.length} item${suggestionElements.length === 1 ? "" : "s"} ready for review.` : "Suggested world elements based on your manuscript."}
              isDark={isDark}
            >
              <div className="space-y-3">
                {suggestionElements.length === 0 ? (
                  <EmptyState title="No element suggestions yet." description="No element suggestions yet." isDark={isDark} compact />
                ) : (
                  visibleSuggestionElements.map((element) => (
                    <article key={element.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                      <h3 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{element.name}</h3>
                      <div className="mt-3 grid gap-2">
                        {element.suggestions.map((suggestion, index) => (
                          <div key={`${element.id}-${index}`} className={`rounded-xl border p-3 text-sm ${softPanelClass(isDark)}`}>
                            <p className={bodyTextClass(isDark)}>{summarizeRecord(suggestion)}</p>
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
                  ))
                )}
                {suggestionElements.length > INITIAL_SUGGESTION_COUNT ? (
                  <button
                    type="button"
                    onClick={() => setShowAllSuggestions((current) => !current)}
                    className={secondaryButtonClass(isDark)}
                  >
                    {showAllSuggestions ? "Show fewer suggestions" : `Show all ${suggestionElements.length} suggestion groups`}
                  </button>
                ) : null}
              </div>
            </WorkspaceCard>

            <WorkspaceCard
              number="6"
              sectionLabel="Extracted Elements"
              title="Extracted Elements"
              description="Countries, regions, races, magic, and lore found in your corpus."
              isDark={isDark}
              action={(
                <button
                  type="button"
                  onClick={() => void refetchElements()}
                  disabled={loadingElements}
                  className={secondaryButtonClass(isDark)}
                >
                  {loadingElements ? "Refreshing..." : "Refresh"}
                </button>
              )}
            >
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <span className={badgeClass(isDark)}>{extractedElements.length} total</span>
                  {Object.entries(elementTypeSummary).slice(0, 5).map(([type, count]) => (
                    <span key={type} className={accentBadgeClass("blue", isDark)}>
                      {formatElementType(type)} {count}
                    </span>
                  ))}
                </div>
                {visibleElements.length === 0 ? (
                  <EmptyState title="No extracted elements yet." description="No extracted elements yet." isDark={isDark} compact />
                ) : (
                  <div className="grid gap-3">
                    {visibleElementCards.map((element) => (
                      <article key={element.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={accentBadgeClass("blue", isDark)}>{formatElementType(element.element_type)}</span>
                          <span className={badgeClass(isDark)}>{element.source_scope}</span>
                          {element.confidence ? <span className={badgeClass(isDark)}>{Math.round(element.confidence * 100)}%</span> : null}
                        </div>
                        <h3 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{element.name}</h3>
                        {element.description ? <p className={`mt-2 line-clamp-3 text-sm leading-6 ${bodyTextClass(isDark)}`}>{element.description}</p> : null}
                        <p className={`mt-3 text-xs ${mutedTextClass(isDark)}`}>
                          {element.usage_count.toLocaleString()} mention{element.usage_count === 1 ? "" : "s"}
                          {element.chapter_numbers.length ? ` - ${element.chapter_numbers.length} chapter${element.chapter_numbers.length === 1 ? "" : "s"}` : ""}
                          {element.world_document_title ? ` - ${element.world_document_title}` : ""}
                        </p>
                      </article>
                    ))}
                  </div>
                )}
                {visibleElements.length > INITIAL_ELEMENT_COUNT ? (
                  <button
                    type="button"
                    onClick={() => setShowAllElements((current) => !current)}
                    className={secondaryButtonClass(isDark)}
                  >
                    {showAllElements ? "Show fewer elements" : `Show all ${visibleElements.length} elements`}
                  </button>
                ) : null}
              </div>
            </WorkspaceCard>
          </div>

          <WorkspaceCard
            number="7"
            sectionLabel="Auto Wiki"
            title="Generate wiki entries from manuscript text"
            description="Query the current canon, then generate entries, next moves, and source citations in one place."
            isDark={isDark}
            action={(
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => void refetchWiki()} className={secondaryButtonClass(isDark)}>
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={() => void generateWiki()}
                  disabled={wikiGenerating}
                  className={primaryButtonClass("blue")}
                >
                  {wikiGenerating ? "Generating..." : "Generate wiki"}
                </button>
              </div>
            )}
          >
            <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
              <div className={`rounded-lg border p-4 ${softPanelClass(isDark)}`}>
                <LabeledField label="Query the canon" isDark={isDark}>
                  <textarea
                    value={logicQuery}
                    onChange={(event) => setLogicQuery(event.target.value)}
                    rows={6}
                    placeholder="Ask about a kingdom, faction, culture, or world rule..."
                    className={`${inputClass(isDark)} min-h-[10rem] resize-y leading-6`}
                  />
                </LabeledField>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={() => void runLogicQuery("story_integration")} disabled={logicLoading || !logicQuery.trim()} className={primaryButtonClass("teal")}>
                    {logicLoading ? "Thinking..." : "Run simulation"}
                  </button>
                  <button type="button" onClick={() => void runLogicQuery("gap_detection")} disabled={logicLoading || !logicQuery.trim()} className={secondaryButtonClass(isDark)}>
                    Canon status
                  </button>
                </div>

                {logicResult ? (
                  <div className={`mt-4 rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                    <div className="flex flex-wrap gap-2">
                      <span className={accentBadgeClass("teal", isDark)}>{logicResult.mode === "gap_detection" ? "Canon stress test" : "Story integration"}</span>
                      {logicResult.logic_alerts.length > 0 ? <span className={accentBadgeClass("amber", isDark)}>{logicResult.logic_alerts.length} alerts</span> : null}
                      {logicResult.citations.length > 0 ? <span className={accentBadgeClass("blue", isDark)}>{logicResult.citations.length} citations</span> : null}
                    </div>
                    <p className={`mt-3 text-sm leading-7 ${bodyTextClass(isDark)}`}>{logicResult.answer}</p>
                    {logicResult.simulation_steps.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <p className={eyebrowClass(isDark)}>Simulation steps</p>
                        {logicResult.simulation_steps.map((step) => (
                          <p key={step} className={`text-xs ${mutedTextClass(isDark)}`}>{step}</p>
                        ))}
                      </div>
                    ) : null}
                    {logicResult.logic_alerts.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <p className={eyebrowClass(isDark)}>Logic alerts</p>
                        {logicResult.logic_alerts.map((alert, index) => (
                          <div key={`alert-${index}`} className={`rounded-xl border px-3 py-2 text-sm ${isDark ? "border-rose-400/20 bg-rose-500/10 text-rose-100" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
                            {summarizeRecord(alert)}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {logicResult.suggestions.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <p className={eyebrowClass(isDark)}>Suggested next moves</p>
                        {logicResult.suggestions.map((suggestion, index) => (
                          <div key={`suggestion-${index}`} className={`rounded-xl border px-3 py-2 text-sm ${softPanelClass(isDark)}`}>
                            {summarizeRecord(suggestion)}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {logicResult.citations.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <p className={eyebrowClass(isDark)}>Source citations</p>
                        {logicResult.citations.slice(0, 4).map((citation, index) => (
                          <div key={`citation-${index}`} className={`rounded-xl border px-3 py-2 text-sm ${softPanelClass(isDark)}`}>
                            {summarizeRecord(citation)}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className={`rounded-lg border p-4 ${softPanelClass(isDark)}`}>
                <div className="flex flex-wrap gap-2">
                  <span className={badgeClass(isDark)}>{wikiEntries.length} total</span>
                  {Object.entries(wikiTypeSummary).slice(0, 3).map(([type, count]) => (
                    <span key={type} className={accentBadgeClass("blue", isDark)}>
                      {count} {type}
                    </span>
                  ))}
                </div>
                <div className="mt-4 space-y-3">
                  {wikiLoading ? <LoadingState label="Loading wiki entries..." isDark={isDark} /> : null}
                  {!wikiLoading && wikiEntries.length === 0 ? (
                    <EmptyState
                      title="No wiki entries yet."
                      description="No wiki entries yet. Generate them from the manuscript when you want a fresh lore review."
                      isDark={isDark}
                    />
                  ) : null}
                  {visibleWikiEntries.map((entry) => (
                    <article key={entry.id} className={`rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                      <div className="flex items-center justify-between gap-3">
                        <h4 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{entry.name}</h4>
                        <span className={badgeClass(isDark)}>{entry.entry_type}</span>
                      </div>
                      {entry.first_mention ? <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>First mention: chapter {entry.first_mention}</p> : null}
                      {entry.description ? <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{entry.description}</p> : null}
                    </article>
                  ))}
                  {wikiEntries.length > INITIAL_WIKI_COUNT ? (
                    <button
                      type="button"
                      onClick={() => setShowAllWikiEntries((current) => !current)}
                      className={`${secondaryButtonClass(isDark)} w-full`}
                    >
                      {showAllWikiEntries ? "Show fewer entries" : `Show all ${wikiEntries.length} entries`}
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          </WorkspaceCard>

          <WorkspaceCard
            number="8"
            sectionLabel="Worldbuilding Manuscript"
            title="Start a new world document"
            description={selectedDocument ? `Editing ${selectedDocument.title}. Last updated ${new Date(selectedDocument.updated_at).toLocaleString()}` : "Type directly or upload files to build the corpus."}
            isDark={isDark}
          >
            <div className="space-y-4">
              <LabeledField label="Document title" isDark={isDark}>
                <input
                  value={draftTitle}
                  onChange={(event) => {
                    setDraftTitle(event.target.value)
                    setDocumentDraftDirty(true)
                  }}
                  placeholder="e.g., The World of Elaria"
                  className={inputClass(isDark)}
                />
              </LabeledField>

              <LabeledField label="Worldbuilding manuscript" isDark={isDark}>
                <textarea
                  value={draftText}
                  onChange={(event) => {
                    setDraftText(event.target.value)
                    setDocumentDraftDirty(true)
                  }}
                  placeholder="Worldbuilding notes, lore rules, places, factions, timeline details, and reference context live here..."
                  rows={18}
                  className={`${inputClass(isDark)} min-h-[26rem] resize-y leading-7`}
                />
              </LabeledField>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={saveDocument}
                  disabled={savingDocument || !draftText.trim()}
                  className={primaryButtonClass("teal")}
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
                  className={secondaryButtonClass(isDark)}
                >
                  New blank document
                </button>
                {selectedDocument ? (
                  <button
                    type="button"
                    onClick={deleteDocument}
                    disabled={deletingDocument}
                    className={dangerButtonClass(isDark)}
                  >
                    {deletingDocument ? "Removing..." : "Delete document"}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => void runAnalysis()}
                  disabled={loadingAnalysis || documents.length === 0}
                  className={accentOutlineButtonClass("amber", isDark)}
                >
                  {loadingAnalysis ? "Checking gaps..." : "Run world gap detection"}
                </button>
              </div>
            </div>
          </WorkspaceCard>

          <WorkspaceCard
            number="9"
            sectionLabel="Saved Cleanup Backlog"
            title="Saved cleanup backlog"
            description="Track open cleanup notes and addressed items."
            isDark={isDark}
            action={(
              <button type="button" onClick={() => void refetchNotes()} className={secondaryButtonClass(isDark)}>
                Refresh notes
              </button>
            )}
          >
            {loadingNotes ? (
              <LoadingState label="Loading saved world-gap notes..." isDark={isDark} />
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                <BacklogColumn
                  label="Open Notes"
                  count={groupedNotes.open.length}
                  isDark={isDark}
                  emptyTitle="No open world gap notes right now."
                  items={groupedNotes.open.map((note) => (
                    <NoteCard
                      key={note.id}
                      note={note}
                      isDark={isDark}
                      noteStatusId={noteStatusId}
                      onPrimaryAction={() => void setNoteStatus(note.id, "addressed")}
                      onDelete={() => void deleteNote(note.id)}
                      primaryLabel={noteStatusId === note.id ? "Updating..." : "Resolve"}
                    />
                  ))}
                />
                <BacklogColumn
                  label="Addressed Notes"
                  count={groupedNotes.addressed.length}
                  isDark={isDark}
                  emptyTitle="No resolved notes yet."
                  items={groupedNotes.addressed.map((note) => (
                    <NoteCard
                      key={note.id}
                      note={note}
                      isDark={isDark}
                      noteStatusId={noteStatusId}
                      onPrimaryAction={() => void setNoteStatus(note.id, "open")}
                      onDelete={() => void deleteNote(note.id)}
                      primaryLabel={noteStatusId === note.id ? "Updating..." : "Reopen"}
                      addressed
                    />
                  ))}
                />
              </div>
            )}
          </WorkspaceCard>
        </div>
      </div>
    </div>
  )
})

function WorkspaceCard({
  number,
  sectionLabel,
  title,
  description,
  action,
  children,
  isDark,
}: {
  number: string
  sectionLabel: string
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
  isDark: boolean
}) {
  return (
    <section className={`rounded-lg border p-4 md:p-5 ${panelClass(isDark)}`}>
      <div className={`flex flex-col gap-3 border-b pb-4 md:flex-row md:items-start md:justify-between ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className={`inline-flex h-6 min-w-6 items-center justify-center rounded-full px-2 text-3xs font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
              {number}
            </span>
            <p className={eyebrowClass(isDark)}>{sectionLabel}</p>
          </div>
          <h2 className={`mt-2 text-[1.15rem] font-semibold ${titleTextClass(isDark)}`}>{title}</h2>
          {description ? <p className={`mt-1.5 max-w-3xl text-sm leading-6 ${mutedTextClass(isDark)}`}>{description}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="pt-4">{children}</div>
    </section>
  )
}

function MetricCard({
  label,
  value,
  note,
  accent,
  isDark,
}: {
  label: string
  value: string
  note: string
  accent: "teal" | "blue" | "violet" | "amber"
  isDark: boolean
}) {
  return (
    <div className={`rounded-lg border px-4 py-4 ${panelClass(isDark)}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={eyebrowClass(isDark)}>{label}</p>
          <p className={`mt-2.5 text-[2rem] font-semibold leading-none ${titleTextClass(isDark)}`}>{value}</p>
          <p className={`mt-2 text-sm ${mutedTextClass(isDark)}`}>{note}</p>
        </div>
        <span className={`mt-1 h-3 w-3 rounded-full ${accentDotClass(accent, isDark)}`} aria-hidden="true" />
      </div>
    </div>
  )
}

function LabeledField({
  label,
  children,
  isDark,
}: {
  label: string
  children: ReactNode
  isDark: boolean
}) {
  return (
    <label className="block">
      <span className={`mb-2 block text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{label}</span>
      {children}
    </label>
  )
}

function SectionPanel({
  title,
  meta,
  description,
  children,
  isDark,
}: {
  title: string
  meta?: string
  description?: string
  children: ReactNode
  isDark: boolean
}) {
  return (
    <div className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-[#08101b]" : "border-stone-200 bg-stone-50/80"}`}>
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h3 className={`text-base font-semibold ${titleTextClass(isDark)}`}>{title}</h3>
          {description ? <p className={`mt-1 text-sm ${mutedTextClass(isDark)}`}>{description}</p> : null}
        </div>
        {meta ? <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${mutedTextClass(isDark)}`}>{meta}</p> : null}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  )
}

function EvidencePanel({ title, body, isDark }: { title: string; body: string; isDark: boolean }) {
  return (
    <div className={`rounded-md border p-3 ${softPanelClass(isDark)}`}>
      <p className={eyebrowClass(isDark)}>{title}</p>
      <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{body}</p>
    </div>
  )
}

function EmptyState({
  title,
  description,
  isDark,
  compact = false,
}: {
  title: string
  description: string
  isDark: boolean
  compact?: boolean
}) {
  return (
    <div className={`rounded-lg border border-dashed px-5 text-center ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-300 bg-stone-50"} ${compact ? "py-6" : "py-10"}`}>
      <p className={`text-sm font-medium ${titleTextClass(isDark)}`}>{title}</p>
      <p className={`mt-2 text-sm ${mutedTextClass(isDark)}`}>{description}</p>
    </div>
  )
}

function LoadingState({ label, isDark }: { label: string; isDark: boolean }) {
  return (
    <div className={`rounded-lg border border-dashed px-5 py-10 text-center ${isDark ? "border-white/10 bg-white/[0.02] text-slate-400" : "border-stone-300 bg-stone-50 text-stone-500"}`}>
      {label}
    </div>
  )
}

function BacklogColumn({
  label,
  count,
  emptyTitle,
  items,
  isDark,
}: {
  label: string
  count: number
  emptyTitle: string
  items: ReactNode[]
  isDark: boolean
}) {
  return (
    <div className={`rounded-lg border p-4 ${softPanelClass(isDark)}`}>
      <div className="flex items-center gap-2">
        <p className={eyebrowClass(isDark)}>{label}</p>
        <span className={badgeClass(isDark)}>{count}</span>
      </div>
      <div className="mt-4 space-y-3">
        {items.length === 0 ? <p className={`text-sm ${mutedTextClass(isDark)}`}>{emptyTitle}</p> : items}
      </div>
    </div>
  )
}

function NoteCard({
  note,
  isDark,
  noteStatusId,
  onPrimaryAction,
  onDelete,
  primaryLabel,
  addressed = false,
}: {
  note: WorldNote
  isDark: boolean
  noteStatusId: string | null
  onPrimaryAction: () => void
  onDelete: () => void
  primaryLabel: string
  addressed?: boolean
}) {
  return (
    <article className={`rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{note.title || "Untitled note"}</h4>
          <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>
            {addressed
              ? `Resolved ${note.addressed_at ? new Date(note.addressed_at).toLocaleDateString() : "recently"}`
              : `${note.context_label || "General world gap"}${note.chapter_number ? ` - Chapter ${note.chapter_number}` : ""}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onPrimaryAction}
            disabled={noteStatusId === note.id}
            className={addressed ? secondaryButtonClass(isDark) : accentOutlineButtonClass("teal", isDark)}
          >
            {primaryLabel}
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={noteStatusId === note.id}
            className={dangerButtonClass(isDark)}
          >
            Delete
          </button>
        </div>
      </div>
      <p className={`mt-3 text-sm leading-6 ${bodyTextClass(isDark)}`}>{note.body}</p>
      {note.suggested_fix ? <p className={`mt-3 text-xs leading-6 ${isDark ? "text-amber-100" : "text-amber-900"}`}>Suggested fix: {note.suggested_fix}</p> : null}
    </article>
  )
}

function panelClass(isDark: boolean) {
  return isDark
    ? "border-white/10 bg-[#0a1322]"
    : "border-stone-200 bg-white/90"
}

function softPanelClass(isDark: boolean) {
  return isDark
    ? "border-white/10 bg-[#07111f]"
    : "border-stone-200 bg-stone-50/90"
}

function eyebrowClass(isDark: boolean) {
  return `text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-500"}`
}

function titleTextClass(isDark: boolean) {
  return isDark ? "text-white" : "text-stone-950"
}

function bodyTextClass(isDark: boolean) {
  return isDark ? "text-slate-300" : "text-stone-700"
}

function mutedTextClass(isDark: boolean) {
  return isDark ? "text-slate-400" : "text-stone-500"
}

function inputClass(isDark: boolean) {
  return `w-full rounded-md border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-black/25 text-slate-100 placeholder:text-slate-500 focus:border-sky-400/40" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400 focus:border-sky-300"}`
}

function secondaryButtonClass(isDark: boolean) {
  return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`
}

function primaryButtonClass(accent: "teal" | "blue" | "violet") {
  const tones = {
    teal: "bg-[#0f766e] hover:bg-[#115e59]",
    blue: "bg-[#2563eb] hover:bg-[#1d4ed8]",
    violet: "bg-[#6d28d9] hover:bg-[#5b21b6]",
  }
  return `inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition disabled:opacity-50 ${tones[accent]}`
}

function accentOutlineButtonClass(accent: "teal" | "amber", isDark: boolean) {
  if (accent === "amber") {
    return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-amber-300/20 bg-amber-400/10 text-amber-100 hover:bg-amber-400/15" : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"}`
  }
  return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-teal-300/20 bg-teal-400/10 text-teal-100 hover:bg-teal-400/15" : "border-teal-200 bg-teal-50 text-teal-800 hover:bg-teal-100"}`
}

function dangerButtonClass(isDark: boolean) {
  return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-rose-400/20 bg-rose-500/10 text-rose-200 hover:bg-rose-500/15" : "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"}`
}

function mutedActionClass(isDark: boolean, accent: "teal") {
  if (accent === "teal") {
    return `inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-medium ${isDark ? "bg-teal-500/10 text-teal-200 opacity-80" : "bg-teal-50 text-teal-700 opacity-80"}`
  }
  return ""
}

function badgeClass(isDark: boolean) {
  return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-stone-100 text-stone-600"}`
}

function accentBadgeClass(accent: "teal" | "blue" | "amber", isDark: boolean) {
  if (accent === "teal") return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-teal-500/10 text-teal-200" : "bg-teal-50 text-teal-700"}`
  if (accent === "amber") return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-amber-400/15 text-amber-100" : "bg-amber-50 text-amber-800"}`
  return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-sky-500/10 text-sky-200" : "bg-sky-50 text-sky-700"}`
}

function accentDotClass(accent: "teal" | "blue" | "violet" | "amber", isDark: boolean) {
  if (accent === "teal") return isDark ? "bg-teal-300" : "bg-teal-500"
  if (accent === "blue") return isDark ? "bg-sky-300" : "bg-sky-500"
  if (accent === "violet") return isDark ? "bg-violet-300" : "bg-violet-500"
  return isDark ? "bg-amber-300" : "bg-amber-500"
}

function summarizeRecord(record: Record<string, unknown> | string) {
  if (typeof record === "string") return record

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
    .join(" - ")
}

function formatElementType(type: string) {
  return (type || "element").replaceAll("_", " ")
}

function severityClass(severity: string, isDark: boolean) {
  const normalized = severity.toLowerCase()
  if (normalized === "critical") {
    return isDark
      ? "rounded-full bg-rose-500/15 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-rose-200"
      : "rounded-full bg-rose-50 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-rose-700"
  }
  if (normalized === "high") {
    return isDark
      ? "rounded-full bg-amber-400/15 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-amber-100"
      : "rounded-full bg-amber-50 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-amber-800"
  }
  return isDark
    ? "rounded-full bg-white/8 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-slate-200"
    : "rounded-full bg-stone-100 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-stone-700"
}
