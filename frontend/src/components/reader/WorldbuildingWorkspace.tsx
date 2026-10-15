"use client"

import { memo, useEffect, useMemo, useRef, useState } from "react"

import { useWorldbuildingCanonActions } from "./WorldbuildingWorkspace.canonActions"
import type {
  WorldGapResult,
  WorldNote,
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
type WorldbuildingView = "gaps" | "sources" | "canon"

export const WorldbuildingWorkspace = memo(function WorldbuildingWorkspace({
  bookId,
  isDark,
  focus = "editor",
}: {
  bookId: string
  isDark: boolean
  focus?: WorkspaceFocus
}) {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null | undefined>(undefined)
  const [draftTitle, setDraftTitle] = useState("")
  const [draftText, setDraftText] = useState("")
  const [savingDocument, setSavingDocument] = useState(false)
  const [deletingDocument, setDeletingDocument] = useState(false)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [uploadTitle, setUploadTitle] = useState("")
  const [replaceCorpusOnUpload, setReplaceCorpusOnUpload] = useState(false)
  const [uploadingFiles, setUploadingFiles] = useState(false)
  const [analysis, setAnalysis] = useState<WorldGapResult | null>(null)
  const [noteSavingId, setNoteSavingId] = useState<string | null>(null)
  const [noteStatusId, setNoteStatusId] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const comparisonSourcesChanged = useRef(false)
  const { integration, setIntegration, loadingIntegration, canonName, setCanonName, canonAliases, setCanonAliases, savingCanon, wikiGenerating, logicQuery, setLogicQuery, logicResult, logicLoading, submittedQuery, logicStale, busy: canonBusy, markSourcesChanged, runIntegration, saveCanonOverride, generateWiki, runLogicQuery } = useWorldbuildingCanonActions(bookId, setStatusMessage, () => { comparisonSourcesChanged.current = true; setAnalysis((current) => current ? { ...current, is_stale: true } : null) })
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
  const [activeWorkspaceView, setActiveWorkspaceView] = useState<WorldbuildingView>("gaps")
  const leaveGuard = useRef(false)
  leaveGuard.current = canonBusy || documentDraftDirty || !!uploadFiles.length || !!uploadTitle.trim() || !!canonName.trim() || !!canonAliases.trim() || !!logicQuery.trim() || savingDocument || deletingDocument || uploadingFiles
  const {
    bootstrapLoading, bootstrapReady, bootstrapError, refetchBootstrap, documentError, refreshErrors, availableChapters,
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
  } = useWorldbuildingWorkspaceData(bookId, focus, activeWorkspaceView === "sources" ? selectedDocumentId ?? null : null)

  const selectedDocument = useMemo(
    () => findSelectedWorldDocument(documents, selectedDocumentId ?? null),
    [documents, selectedDocumentId]
  )
  const openGapIds = useMemo(
    () => new Set(notes.filter((note) => note.linked_gap_id).map((note) => note.linked_gap_id!)),
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
  const visibleElements = useMemo(() => getVisibleWorldElements(extractedElements, extractedElements.length), [extractedElements])
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
    comparisonSourcesChanged.current = false
    try {
      const { data: payload, error } = await refetchAnalysis()
      if (error || !payload) return
      setAnalysis({ ...payload, is_stale: payload.is_stale || comparisonSourcesChanged.current })
      await refetchElements()
    } catch {
      setStatusMessage("Could not refresh the comparison. The previous result is retained.")
    }
  }

  useEffect(() => {
    if (activeWorkspaceView !== "sources" || !bootstrapReady || selectedDocumentId !== undefined) return
    setSelectedDocumentId(documents[0]?.id ?? null)
  }, [activeWorkspaceView, bootstrapReady, documents, selectedDocumentId])

  useEffect(() => {
    if (!selectedDocumentData || selectedDocumentData.id !== selectedDocumentId || documentDraftDirty) return
    setDraftTitle(selectedDocumentData.title)
    setDraftText(selectedDocumentData.text)
  }, [documentDraftDirty, selectedDocumentData, selectedDocumentId])

  useEffect(() => {
    if (focus !== "gap") return
    if (initialAnalysis) {
      setAnalysis({ ...initialAnalysis, is_stale: initialAnalysis.is_stale || comparisonSourcesChanged.current })
    }
  }, [focus, initialAnalysis])

  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (leaveGuard.current) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!leaveGuard.current || !link || link.target === "_blank" || link.hasAttribute("download") || event.ctrlKey || event.metaKey) return
      if (new URL(link.href).pathname === location.pathname) return
      if (!window.confirm("Leave World gaps? Unsaved source edits, selected files, and canon tool drafts will be lost.")) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [])

  const {
    deleteDocument,
    saveDocument,
    selectDocument,
    startNewDocument,
    uploadDocumentFiles,
  } = useWorldbuildingDocumentActions({
    bookId,
    documentDraftDirty,
    onSourcesChanged: () => { comparisonSourcesChanged.current = true; markSourcesChanged(); setAnalysis((current) => current ? { ...current, is_stale: true } : null) },
    draftText,
    draftTitle,
    focus,
    replaceCorpusOnUpload,
    selectedDocument,
    selectedDocumentId: selectedDocumentId ?? null,
    uploadFiles,
    uploadTitle,
    refetchDocuments,
    refetchElements,
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
    refreshNotes, notesMessage, appliedChapter,
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

  const { acceptElementSuggestion, accepting } = useWorldbuildingElementActions({
    setAnalysis,
    setIntegration,
    setStatusMessage,
  })

  const uploadLimitNote = buildUploadLimitNote(uploadStats)

  if (!bootstrapReady) return <div className="py-6" role={bootstrapError ? "alert" : "status"}>{bootstrapError ? <><p>Worldbuilding data could not be loaded. Saved sources and cleanup notes have not been replaced.</p><button type="button" className="app-button-secondary mt-3" onClick={() => void refetchBootstrap()}>Retry worldbuilding workspace</button></> : <p>Loading canon sources, comparison, and saved cleanup notes…</p>}</div>

  return (
    <div>
      {bootstrapError ? <div className="mb-4" role="alert"><p>The workspace could not refresh. Last loaded data is shown.</p><button type="button" className="app-button-secondary" disabled={bootstrapLoading} onClick={() => void refetchBootstrap()}>Retry worldbuilding workspace</button></div> : null}
      {refreshErrors.map((error) => <div key={error.label} className="mb-3 border-l-2 border-amber-500 pl-3 text-sm" role="alert"><p>Could not refresh {error.label}. Previously loaded content is retained.</p><button type="button" className="app-button-secondary mt-2" disabled={error.busy} onClick={() => void (error.label === "comparison" ? runAnalysis() : error.retry())}>Retry {error.label}</button></div>)}
      <WorldbuildingMetricsStrip
        isDark={isDark}
        documentCount={documents.length}
        totalWorldWords={totalWorldWords}
        extractedElementCount={extractedElements.length}
        openNoteCount={groupedNotes.open.length}
      />

      <div className="mt-4">
        <WorldbuildingStatusMessage isDark={isDark} message={statusMessage} />
      </div>

      <div className={`mt-4 flex gap-1 overflow-x-auto border-b ${isDark ? "border-white/10" : "border-stone-200"}`} role="tablist" aria-label="Worldbuilding workspace views">
        {([
          ["gaps", "Review gaps"],
          ["sources", "Canon sources"],
          ["canon", "Canon tools"],
        ] as Array<[WorldbuildingView, string]>).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`world-tab-${id}`}
            aria-controls={`world-panel-${id}`}
            tabIndex={activeWorkspaceView === id ? 0 : -1}
            aria-selected={activeWorkspaceView === id}
            onClick={() => setActiveWorkspaceView(id)}
            onKeyDown={(event) => {
              const views: WorldbuildingView[] = ["gaps", "sources", "canon"]
              const index = views.indexOf(id)
              const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : -1
              if (next < 0) return
              event.preventDefault(); setActiveWorkspaceView(views[next]); document.getElementById(`world-tab-${views[next]}`)?.focus()
            }}
            className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${activeWorkspaceView === id
              ? (isDark ? "border-teal-300 text-white" : "border-[#1f615d] text-stone-950")
              : (isDark ? "border-transparent text-slate-400 hover:text-slate-200" : "border-transparent text-stone-500 hover:text-stone-800")}`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeWorkspaceView === "gaps" ? (
        <div id="world-panel-gaps" role="tabpanel" aria-labelledby="world-tab-gaps" className="mt-5 space-y-6">
          {notesMessage ? <p role="status" className="border-l-2 border-[rgb(var(--border))] pl-3 text-sm">{notesMessage}</p> : null}
          <GapAnalysisCard
            availableChapters={availableChapters}
            bookId={bookId}
            isDark={isDark}
            analysis={analysis}
            analysisLoading={analysisLoading}
            runButtonLoading={loadingAnalysis}
            documentsAvailable={documents.length > 0}
            expandedGapGroups={expandedGapGroups}
            openGapIds={openGapIds}
            noteSavingId={noteSavingId ?? noteStatusId}
            initialGapItemsPerGroup={INITIAL_GAP_ITEMS_PER_GROUP}
            onRunAnalysis={() => void runAnalysis()}
            onStartNewDocument={() => {
              setActiveWorkspaceView("sources")
              startNewDocument()
            }}
            onSaveGapAsNote={(item) => void saveGapAsNote(item)}
            onToggleGapGroup={(groupKey) => setExpandedGapGroups((current) => ({ ...current, [groupKey]: !current[groupKey] }))}
          />

          <SavedCleanupBacklogCard
            isDark={isDark}
            notesLoading={notesLoading}
            chapterFilter={chapterFilter}
            loadingChapterNotes={loadingChapterNotes}
            isChapterFiltered={chapterNotes !== null}
            openNotes={groupedDisplayed.open}
            addressedNotes={groupedDisplayed.addressed}
            noteStatusId={noteStatusId ?? noteSavingId}
            appliedChapter={appliedChapter}
            onChapterFilterChange={setChapterFilter}
            onFetchNotesByChapter={() => void handleFetchNotesByChapter()}
            onClearChapterFilter={handleClearChapterFilter}
            onRefreshNotes={() => void refreshNotes()}
            onResolveNote={(noteId) => void setNoteStatus(noteId, "addressed")}
            onReopenNote={(noteId) => void setNoteStatus(noteId, "open")}
            onDeleteNote={(noteId) => void deleteNote(noteId)}
          />
        </div>
      ) : null}

      {activeWorkspaceView === "sources" ? (
        <fieldset id="world-panel-sources" role="tabpanel" aria-labelledby="world-tab-sources" disabled={savingDocument || deletingDocument || uploadingFiles} className="mt-5 grid min-w-0 gap-4 border-0 p-0 xl:grid-cols-[17.5rem_minmax(0,1fr)]">
          <WorldbuildingDocumentSidebar
            documentsLoading={documentsLoading}
            documents={documents}
            visibleDocuments={visibleDocuments}
            selectedDocumentId={selectedDocumentId ?? null}
            showAllDocuments={showAllDocuments}
            isDark={isDark}
            onNewDocument={startNewDocument}
            onSelectDocument={selectDocument}
            onToggleShowAllDocuments={() => setShowAllDocuments((current) => !current)}
          />
          <div className="order-first min-w-0 space-y-4 xl:order-last">
          <details><summary className="cursor-pointer py-3 font-semibold">Import reference files</summary>
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
          </details>

          {loadingDocumentBody ? <DocumentBodyLoadingState isDark={isDark} /> : null}
          {selectedDocumentId && documentError ? <div role="alert"><p>Source content could not be loaded or refreshed. Existing edits are retained.</p><button type="button" className="app-button-secondary mt-2" onClick={() => void refetchSelectedDocument()}>Retry source content</button></div> : null}
          {selectedDocumentId && !selectedDocument ? <p role="status">This source is not in the current source list. Refresh the list before saving changes.</p> : null}
          {!selectedDocumentId || (selectedDocumentData?.id === selectedDocumentId && !!selectedDocument) ? <WorldbuildingDocumentEditorCard
            isDark={isDark}
            selectedDocument={selectedDocument}
            draftTitle={draftTitle}
            draftText={draftText}
            savingDocument={savingDocument}
            deletingDocument={deletingDocument}
            analysisLoading={analysisLoading || loadingAnalysis}
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
          : null}
          <p className="text-sm text-[rgb(var(--muted-foreground))]">{documentDraftDirty ? "Unsaved source edits. " : ""}Source drafts stay on this page while you switch tabs. Save before leaving.</p>
          <button type="button" className="app-button-secondary" onClick={() => void refetchDocuments()}>Refresh source list</button>
          </div>
        </fieldset>
      ) : null}

      {activeWorkspaceView === "canon" ? (
        <fieldset id="world-panel-canon" role="tabpanel" aria-labelledby="world-tab-canon" disabled={canonBusy} className="mt-5 min-w-0 space-y-4 border-0 p-0">
          {notesMessage ? <p role="status" className="border-l-2 border-[rgb(var(--border))] pl-3 text-sm">{notesMessage}</p> : null}
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
              accepting={accepting}
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
            submittedQuery={submittedQuery}
            logicStale={logicStale}
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
        </fieldset>
      ) : null}
    </div>
  )
})
