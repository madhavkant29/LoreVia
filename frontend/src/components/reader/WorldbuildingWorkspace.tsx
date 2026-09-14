"use client"

import { memo, useEffect, useMemo, useState } from "react"

import { worldBuildingApi } from "@/lib/api/worldBuilding"
import type {
  WorldGapResult,
  WorldIntegrationResult,
  WorldNote,
  WorldQueryResponse,
} from "@/types/world-building"
import { SavedCleanupBacklogCard } from "./WorldbuildingWorkspace.backlog"
import { CanonOverrideCard } from "./WorldbuildingWorkspace.canon"
import { useWorldbuildingWorkspaceData, type WorkspaceFocus } from "./WorldbuildingWorkspace.data"
import { WorldbuildingDocumentSidebar } from "./WorldbuildingWorkspace.documents"
import { useWorldbuildingDocumentActions } from "./WorldbuildingWorkspace.documentActions"
import { useWorldbuildingElementActions } from "./WorldbuildingWorkspace.elementActions"
import { WorldbuildingDocumentEditorCard } from "./WorldbuildingWorkspace.editor"
import { ElementSuggestionsCard, ExtractedElementsCard } from "./WorldbuildingWorkspace.elements"
import { GapAnalysisCard } from "./WorldbuildingWorkspace.gaps"
import { WorldbuildingOpportunitiesCard } from "./WorldbuildingWorkspace.opportunities"
import { useWorldbuildingNoteActions } from "./WorldbuildingWorkspace.noteActions"
import { DocumentBodyLoadingState, WorldbuildingMetricsStrip, WorldbuildingStatusMessage } from "./WorldbuildingWorkspace.shell"
import { WorldCorpusUploadCard } from "./WorldbuildingWorkspace.upload"
import { AutoWikiCard } from "./WorldbuildingWorkspace.wiki"
import {
  buildUploadLimitNote,
  countWorldDocumentWords,
  findSelectedWorldDocument,
  getOpenGapIds,
  getSuggestionElements,
  getVisibleItems,
  getVisibleWorldElements,
  groupWorldNotesByStatus,
  summarizeWikiEntryTypes,
  summarizeWorldElementTypes,
} from "./WorldbuildingWorkspace.helpers"

const INITIAL_DOCUMENT_COUNT = 10
const INITIAL_GAP_ITEMS_PER_GROUP = 4
const INITIAL_OPPORTUNITY_COUNT = 4
const INITIAL_SUGGESTION_COUNT = 6
const INITIAL_ELEMENT_COUNT = 6
const INITIAL_WIKI_COUNT = 6

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
  const [chapterFilter, setChapterFilter] = useState("")
  const [chapterNotes, setChapterNotes] = useState<WorldNote[] | null>(null)
  const [loadingChapterNotes, setLoadingChapterNotes] = useState(false)
  const {
    analysisLoading,
    canonOverrides,
    documents,
    documentsLoading,
    elementsLoading,
    extractedElements,
    initialAnalysis,
    loadingAnalysis,
    loadingDocumentBody,
    notes,
    notesLoading,
    refetchAnalysis,
    refetchCanonOverrides,
    refetchDocuments,
    refetchElements,
    refetchNotes,
    refetchSelectedDocument,
    refetchUploadStats,
    refetchWiki,
    selectedDocumentData,
    uploadStats,
    wikiEntries,
    wikiEntriesLoading,
  } = useWorldbuildingWorkspaceData(bookId, focus, selectedDocumentId)

  const selectedDocument = useMemo(
    () => findSelectedWorldDocument(documents, selectedDocumentId),
    [documents, selectedDocumentId]
  )
  const openGapIds = useMemo(
    () => getOpenGapIds(notes),
    [notes]
  )
  const totalWorldWords = useMemo(
    () => countWorldDocumentWords(documents),
    [documents]
  )
  const groupedNotes = useMemo(() => groupWorldNotesByStatus(notes), [notes])

  const displayedNotes = chapterNotes ?? notes
  const groupedDisplayed = useMemo(() => groupWorldNotesByStatus(displayedNotes), [displayedNotes])

  const wikiTypeSummary = useMemo(() => summarizeWikiEntryTypes(wikiEntries), [wikiEntries])
  const elementTypeSummary = useMemo(() => summarizeWorldElementTypes(extractedElements), [extractedElements])
  const suggestionElements = useMemo(
    () => getSuggestionElements(integration, analysis),
    [analysis, integration]
  )
  const visibleElements = useMemo(() => getVisibleWorldElements(extractedElements), [extractedElements])
  const visibleDocuments = useMemo(
    () => getVisibleItems(documents, showAllDocuments, INITIAL_DOCUMENT_COUNT),
    [documents, showAllDocuments]
  )
  const visibleOpportunities = useMemo(
    () => getVisibleItems(integration?.integration_opportunities ?? [], showAllOpportunities, INITIAL_OPPORTUNITY_COUNT),
    [integration?.integration_opportunities, showAllOpportunities]
  )
  const visibleSuggestionElements = useMemo(
    () => getVisibleItems(suggestionElements, showAllSuggestions, INITIAL_SUGGESTION_COUNT),
    [showAllSuggestions, suggestionElements]
  )
  const visibleElementCards = useMemo(
    () => getVisibleItems(visibleElements, showAllElements, INITIAL_ELEMENT_COUNT),
    [showAllElements, visibleElements]
  )
  const visibleWikiEntries = useMemo(
    () => getVisibleItems(wikiEntries, showAllWikiEntries, INITIAL_WIKI_COUNT),
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

  const {
    deleteDocument,
    saveDocument,
    selectDocument,
    startNewDocument,
    uploadDocumentFiles,
  } = useWorldbuildingDocumentActions({
    bookId,
    draftText,
    draftTitle,
    focus,
    replaceCorpusOnUpload,
    selectedDocument,
    selectedDocumentId,
    uploadFiles,
    uploadTitle,
    refetchDocuments,
    refetchElements,
    refetchSelectedDocument,
    refetchUploadStats,
    runAnalysis,
    setDeletingDocument,
    setDocumentDraftDirty,
    setDraftText,
    setDraftTitle,
    setReplaceCorpusOnUpload,
    setSavingDocument,
    setSelectedDocumentId,
    setStatusMessage,
    setUploadingFiles,
    setUploadFiles,
    setUploadTitle,
  })

  const {
    deleteNote,
    handleClearChapterFilter,
    handleFetchNotesByChapter,
    saveGapAsNote,
    saveIntegrationAsNote,
    setNoteStatus,
  } = useWorldbuildingNoteActions({
    bookId,
    chapterFilter,
    refetchNotes,
    setChapterFilter,
    setChapterNotes,
    setLoadingChapterNotes,
    setNoteSavingId,
    setNoteStatusId,
  })

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

  const { acceptElementSuggestion } = useWorldbuildingElementActions({
    setAnalysis,
    setIntegration,
    setStatusMessage,
  })

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

  const uploadLimitNote = buildUploadLimitNote(uploadStats)

  return (
    <div className="space-y-4">
      <WorldbuildingMetricsStrip
        isDark={isDark}
        documentCount={documents.length}
        totalWorldWords={totalWorldWords}
        extractedElementCount={extractedElements.length}
        openNoteCount={groupedNotes.open.length}
      />

      <WorldbuildingStatusMessage isDark={isDark} message={statusMessage} />

      <div className="grid gap-4 xl:grid-cols-[17.5rem_minmax(0,1fr)]">
        <WorldbuildingDocumentSidebar
          documentsLoading={documentsLoading}
          documents={documents}
          visibleDocuments={visibleDocuments}
          selectedDocumentId={selectedDocumentId}
          showAllDocuments={showAllDocuments}
          isDark={isDark}
          onNewDocument={startNewDocument}
          onSelectDocument={selectDocument}
          onToggleShowAllDocuments={() => setShowAllDocuments((current) => !current)}
        />

        <div className="space-y-4">
          <WorldCorpusUploadCard
            bookId={bookId}
            focus={focus}
            isDark={isDark}
            uploadLimitNote={uploadLimitNote}
            uploadTitle={uploadTitle}
            uploadFiles={uploadFiles}
            replaceCorpusOnUpload={replaceCorpusOnUpload}
            uploadingFiles={uploadingFiles}
            onUploadTitleChange={setUploadTitle}
            onUploadFilesChange={setUploadFiles}
            onReplaceCorpusOnUploadChange={setReplaceCorpusOnUpload}
            onUploadDocumentFiles={() => void uploadDocumentFiles()}
          />

          {loadingDocumentBody ? <DocumentBodyLoadingState isDark={isDark} /> : null}

          <GapAnalysisCard
            bookId={bookId}
            isDark={isDark}
            analysis={analysis}
            analysisLoading={analysisLoading}
            runButtonLoading={loadingAnalysis}
            documentsAvailable={documents.length > 0}
            expandedGapGroups={expandedGapGroups}
            openGapIds={openGapIds}
            noteSavingId={noteSavingId}
            initialGapItemsPerGroup={INITIAL_GAP_ITEMS_PER_GROUP}
            onRunAnalysis={() => void runAnalysis()}
            onStartNewDocument={startNewDocument}
            onSaveGapAsNote={(item) => void saveGapAsNote(item)}
            onToggleGapGroup={(groupKey) => setExpandedGapGroups((current) => ({ ...current, [groupKey]: !current[groupKey] }))}
          />

          <WorldbuildingOpportunitiesCard
            isDark={isDark}
            documentsAvailable={documents.length > 0}
            integration={integration}
            visibleOpportunities={visibleOpportunities}
            showAllOpportunities={showAllOpportunities}
            loadingIntegration={loadingIntegration}
            noteSavingId={noteSavingId}
            initialOpportunityCount={INITIAL_OPPORTUNITY_COUNT}
            onRunIntegration={() => void runIntegration()}
            onSaveIntegrationAsNote={(item) => void saveIntegrationAsNote(item)}
            onToggleShowAllOpportunities={() => setShowAllOpportunities((current) => !current)}
          />

          <CanonOverrideCard
            isDark={isDark}
            canonName={canonName}
            canonAliases={canonAliases}
            canonOverrides={canonOverrides}
            savingCanon={savingCanon}
            onCanonNameChange={setCanonName}
            onCanonAliasesChange={setCanonAliases}
            onSaveCanonOverride={() => void saveCanonOverride()}
            onRefreshCanonOverrides={() => void refetchCanonOverrides()}
          />

          <div className="grid gap-5 xl:grid-cols-2">
            <ElementSuggestionsCard
              isDark={isDark}
              suggestionElements={suggestionElements}
              visibleSuggestionElements={visibleSuggestionElements}
              showAllSuggestions={showAllSuggestions}
              initialSuggestionCount={INITIAL_SUGGESTION_COUNT}
              onAcceptElementSuggestion={(element, suggestion) => void acceptElementSuggestion(element, suggestion)}
              onToggleShowAllSuggestions={() => setShowAllSuggestions((current) => !current)}
            />

            <ExtractedElementsCard
              isDark={isDark}
              extractedElements={extractedElements}
              visibleElements={visibleElements}
              visibleElementCards={visibleElementCards}
              elementTypeSummary={elementTypeSummary}
              elementsLoading={elementsLoading}
              showAllElements={showAllElements}
              initialElementCount={INITIAL_ELEMENT_COUNT}
              onRefreshElements={() => void refetchElements()}
              onToggleShowAllElements={() => setShowAllElements((current) => !current)}
            />
          </div>

          <AutoWikiCard
            isDark={isDark}
            logicQuery={logicQuery}
            logicLoading={logicLoading}
            logicResult={logicResult}
            wikiEntries={wikiEntries}
            wikiEntriesLoading={wikiEntriesLoading}
            wikiGenerating={wikiGenerating}
            visibleWikiEntries={visibleWikiEntries}
            wikiTypeSummary={wikiTypeSummary}
            showAllWikiEntries={showAllWikiEntries}
            initialWikiCount={INITIAL_WIKI_COUNT}
            onLogicQueryChange={setLogicQuery}
            onRunLogicQuery={(mode) => void runLogicQuery(mode)}
            onRefreshWiki={() => void refetchWiki()}
            onGenerateWiki={() => void generateWiki()}
            onToggleShowAllWikiEntries={() => setShowAllWikiEntries((current) => !current)}
          />

          <WorldbuildingDocumentEditorCard
            isDark={isDark}
            selectedDocument={selectedDocument}
            draftTitle={draftTitle}
            draftText={draftText}
            savingDocument={savingDocument}
            deletingDocument={deletingDocument}
            analysisLoading={analysisLoading}
            hasDocuments={documents.length > 0}
            onDraftTitleChange={(value) => {
              setDraftTitle(value)
              setDocumentDraftDirty(true)
            }}
            onDraftTextChange={(value) => {
              setDraftText(value)
              setDocumentDraftDirty(true)
            }}
            onSaveDocument={() => void saveDocument()}
            onNewDocument={startNewDocument}
            onDeleteDocument={() => void deleteDocument()}
            onRunAnalysis={() => void runAnalysis()}
          />

          <SavedCleanupBacklogCard
            isDark={isDark}
            notesLoading={notesLoading}
            chapterFilter={chapterFilter}
            loadingChapterNotes={loadingChapterNotes}
            isChapterFiltered={chapterNotes !== null}
            openNotes={groupedDisplayed.open}
            addressedNotes={groupedDisplayed.addressed}
            noteStatusId={noteStatusId}
            onChapterFilterChange={setChapterFilter}
            onFetchNotesByChapter={() => void handleFetchNotesByChapter()}
            onClearChapterFilter={handleClearChapterFilter}
            onRefreshNotes={() => void refetchNotes()}
            onResolveNote={(noteId) => void setNoteStatus(noteId, "addressed")}
            onReopenNote={(noteId) => void setNoteStatus(noteId, "open")}
            onDeleteNote={(noteId) => void deleteNote(noteId)}
          />
        </div>
      </div>
    </div>
  )
})
