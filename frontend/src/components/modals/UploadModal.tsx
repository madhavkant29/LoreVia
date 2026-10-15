"use client"

import { X } from "lucide-react"
import { memo, useEffect } from "react"

import { AdvancedImportSettings } from "@/components/modals/upload/AdvancedImportSettings"
import { ExistingProjectImportStep } from "@/components/modals/upload/ExistingProjectImportStep"
import { UploadProjectDetailsStep } from "@/components/modals/upload/UploadProjectDetailsStep"
import { UploadResultsPanel } from "@/components/modals/upload/UploadResultsPanel"
import { UploadSourceStep } from "@/components/modals/upload/UploadSourceStep"
import { useUploadModalController } from "@/components/modals/upload/useUploadModalController"
import { UploadWizardSteps } from "@/components/modals/upload/UploadWizardPanels"
import { Dialog } from "@/components/ui/Dialog"
import { ProcessingStatusPanel } from "@/components/ui/ResponsivenessStatus"
import type { BookMode } from "@/lib/stores/bookModeStore"

export const UploadModal = memo(function UploadModal({
  onClose,
  initialMode = "reader",
  initialExistingBookId = "",
  presentation = "modal",
  onDraftChange,
}: {
  onClose: () => void
  initialMode?: BookMode
  initialExistingBookId?: string
  presentation?: "modal" | "inline"
  onDraftChange?: (hasDraft: boolean) => void
}) {
  const {
    wizard, isInline, shellClassName, isManagingExisting, startEmpty, storyUnitLabel, storyUnitLabelTitle, isDark,
    uploadStage, processingBook, processingSummary, processingRetrying, retryProcessing, submit,
    inputRef, coverInputRef, newUploadAccept, files, handleFilesSelected, handleCoverSelected,
    chapterUploadAccept, primaryFile, isScreenplayWorkspace,
    importPreview, setImportPreview, dismissPreview, setDismissPreview, previewLoading, fetchPreview,
    setImportAsSingle, showEditor, setShowEditor, canUploadAuthorMode, needsUsername, settingUsername,
    usernameError, handleSetUsername, existingAuthorBooks, selectedExistingBook, existingBookSelectLabel,
    existingBookMenuRef, suggestedTags, series, uploadLimitCopy, addTag, removeTag, toggleSeries,
    chapterSource, setChapterSource, setError, chapterNumber, setChapterNumber, setChapterNumberDirty,
    replaceExisting, setReplaceExisting, chapterTitle, setChapterTitle, chapterText, setChapterText,
    chapterUploadHelp, splitIntoChapters, setSplitIntoChapters, chunkLongDocuments, setChunkLongDocuments,
    infoButtonClass, chapterReports, advancedSettingsOpen, setAdvancedSettingsOpen, preserveChapterNumbers,
    setPreserveChapterNumbers, preserveSourceChapters, setPreserveSourceChapters, coverFile,
    autoExtractCover, setAutoExtractCover, error, uploading, uploadProgress, postImportReview, reportReady,
    postImportSynopsis, postImportPassages, postImportThreads, postImportSuggestions, user, confirm,
    booksApi, existingBookId, refetchBooks, primaryActionDisabled, primaryActionLabel,
  } = useUploadModalController({ onClose, initialMode, initialExistingBookId, presentation })
  useEffect(() => {
    onDraftChange?.(uploading || files.length > 0 || !!chapterText.trim() || !!chapterTitle.trim())
  }, [chapterText, chapterTitle, files.length, onDraftChange, uploading])
  const TitleElement = isInline ? "h2" : "div"

  const content = (
      <div className={shellClassName} onClick={(e) => e.stopPropagation()}>
        <div className={`relative border-b px-6 py-5 ${isDark ? "border-white/10" : "border-slate-200/80"}`}>
          <div>
            <TitleElement className="text-xl font-semibold tracking-normal">{isManagingExisting ? `Add New ${storyUnitLabelTitle}` : "Upload manuscript"}</TitleElement>
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {isManagingExisting
                ? "Paste or upload one scene, chapter, or script segment, process it incrementally, and review what changed before moving on."
                : wizard.mode === "author"
                  ? "After extraction, LoreVia starts with a supportive full-manuscript read—what is working first, then evidence-backed revision opportunities."
                  : "Bring in one manuscript, choose how it should be processed, and keep setup lightweight."}
            </p>
          </div>
          {!isManagingExisting ? (
            <div className={`hidden rounded-full px-3 py-1 text-xs font-medium md:inline-flex ${isDark ? "bg-white/5 text-slate-300" : "bg-slate-100 text-slate-600"}`}>
              Private workspace
            </div>
          ) : null}
          <button
            onClick={onClose}
            className={`absolute right-6 top-5 rounded-full p-2 text-xl leading-none transition-colors ${
              isDark ? "text-slate-400 hover:bg-white/5 hover:text-white" : "text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            }`}
            aria-label="Close upload modal"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <UploadWizardSteps
          isDark={isDark}
          activeStep={uploadStage === "processing" ? 4 : importPreview && !dismissPreview ? 2 : files.length > 0 || startEmpty || isManagingExisting ? 1 : 0}
          isManagingExisting={isManagingExisting}
        />

        {uploadStage === "processing" && processingBook ? (
          <div className="mb-4 space-y-3 px-6 pt-4">
            <ProcessingStatusPanel
              status={processingSummary}
              retrying={processingRetrying}
              onRetry={processingSummary?.retryAvailable ? () => void retryProcessing() : undefined}
            />
            {!isManagingExisting && wizard.mode === "author" ? (
              <p className={`rounded-lg border px-4 py-3 text-sm leading-6 ${isDark ? "border-teal-300/15 bg-teal-300/5 text-slate-300" : "border-teal-900/10 bg-teal-50 text-stone-700"}`}>
                When extraction finishes, LoreVia will read the whole manuscript for its voice, characters, scenes, and emotional core before leading you into detailed critique.
              </p>
            ) : null}
            <div className="flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${
                  isDark ? "bg-white/10 text-slate-100 hover:bg-white/15" : "bg-white text-stone-800 hover:bg-stone-100"
                }`}
              >
                Close
              </button>
            </div>
          </div>
        ) : null}

        <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
          <div className="reader-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="flex flex-col gap-4">
          <UploadSourceStep
            isDark={isDark}
            isManagingExisting={isManagingExisting}
            startEmpty={startEmpty}
            inputRef={inputRef}
            newUploadAccept={newUploadAccept}
            files={files}
            onFilesSelected={handleFilesSelected}
            primaryFile={primaryFile}
            isScreenplayWorkspace={isScreenplayWorkspace}
            importPreview={importPreview}
            setImportPreview={setImportPreview}
            dismissPreview={dismissPreview}
            setDismissPreview={setDismissPreview}
            previewLoading={previewLoading}
            fetchPreview={fetchPreview}
            setImportAsSingle={setImportAsSingle}
            showEditor={showEditor}
            setShowEditor={setShowEditor}
          />

          <UploadProjectDetailsStep
            wizard={wizard}
            isDark={isDark}
            isManagingExisting={isManagingExisting}
            canUploadAuthorMode={canUploadAuthorMode}
            needsUsername={needsUsername}
            settingUsername={settingUsername}
            usernameError={usernameError}
            onSetUsername={handleSetUsername}
            existingAuthorBooks={existingAuthorBooks}
            selectedExistingBook={selectedExistingBook}
            existingBookSelectLabel={existingBookSelectLabel}
            existingBookMenuRef={existingBookMenuRef}
            suggestedTags={suggestedTags}
            series={series}
            uploadLimitCopy={uploadLimitCopy}
            username={user?.username}
            addTag={addTag}
            removeTag={removeTag}
            toggleSeries={toggleSeries}
          />

          <ExistingProjectImportStep
            isDark={isDark}
            isManagingExisting={isManagingExisting}
            isScreenplayWorkspace={isScreenplayWorkspace}
            selectedExistingBook={selectedExistingBook}
            chapterSource={chapterSource}
            setChapterSource={setChapterSource}
            setError={setError}
            chapterNumber={chapterNumber}
            setChapterNumber={setChapterNumber}
            setChapterNumberDirty={setChapterNumberDirty}
            replaceExisting={replaceExisting}
            setReplaceExisting={setReplaceExisting}
            storyUnitLabel={storyUnitLabel}
            storyUnitLabelTitle={storyUnitLabelTitle}
            chapterTitle={chapterTitle}
            setChapterTitle={setChapterTitle}
            chapterText={chapterText}
            setChapterText={setChapterText}
            inputRef={inputRef}
            files={files}
            onFilesSelected={handleFilesSelected}
            chapterUploadAccept={chapterUploadAccept}
            chapterUploadHelp={chapterUploadHelp}
            splitIntoChapters={splitIntoChapters}
            setSplitIntoChapters={setSplitIntoChapters}
            chunkLongDocuments={chunkLongDocuments}
            setChunkLongDocuments={setChunkLongDocuments}
            infoButtonClass={infoButtonClass}
            chapterReports={chapterReports}
          />

          <AdvancedImportSettings
            isDark={isDark}
            isManagingExisting={isManagingExisting}
            isScreenplayWorkspace={isScreenplayWorkspace}
            advancedSettingsOpen={advancedSettingsOpen}
            setAdvancedSettingsOpen={setAdvancedSettingsOpen}
            preserveChapterNumbers={preserveChapterNumbers}
            setPreserveChapterNumbers={setPreserveChapterNumbers}
            preserveSourceChapters={preserveSourceChapters}
            setPreserveSourceChapters={setPreserveSourceChapters}
            coverInputRef={coverInputRef}
            coverFile={coverFile}
            onCoverSelected={handleCoverSelected}
            autoExtractCover={autoExtractCover}
            setAutoExtractCover={setAutoExtractCover}
          />

          {error && <p className="text-sm text-red-500">{error}</p>}

          {uploading ? (
            <div
              className={`rounded-xl border p-3 ${
                isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"
              }`}
            >
              <div className="mb-2 flex items-center justify-between text-xs font-medium">
                <span className={isDark ? "text-slate-300" : "text-slate-600"}>
                  {uploadStage === "uploading" ? "Uploading file" : "Handing off for processing"}
                </span>
                <span className={isDark ? "text-slate-200" : "text-slate-700"}>
                  {uploadStage === "uploading"
                    ? `${uploadProgress}%`
                    : uploadProgress > 0
                      ? `${uploadProgress}%`
                      : "Queued"}
                </span>
              </div>
              <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-gray-200"}`}>
                <div
                  className="h-full rounded-full bg-indigo-600 transition-all duration-200"
                  style={{ width: `${uploadStage === "uploading" ? uploadProgress : Math.max(uploadProgress, 5)}%` }}
                />
              </div>
              <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                {uploadStage === "uploading"
                  ? "Large PDFs can take a bit depending on your network speed."
                  : isManagingExisting
                    ? "Your chapter is in LoreVia. Incremental extraction and continuity review are being refreshed now."
                    : wizard.mode === "author"
                      ? "Your manuscript upload finished. Extraction continues in the background, followed by its supportive first read."
                      : "Your book upload finished. Parsing and AI extraction continue in the background."}
              </p>
            </div>
          ) : null}

          <UploadResultsPanel
            isDark={isDark}
            chapterReports={chapterReports}
            storyUnitLabel={storyUnitLabel}
            storyUnitLabelTitle={storyUnitLabelTitle}
            postImportReview={postImportReview}
            reportReady={reportReady}
            postImportSynopsis={postImportSynopsis}
            postImportPassages={postImportPassages}
            postImportThreads={postImportThreads}
            postImportSuggestions={postImportSuggestions}
          />
          </div>
          </div>
          <div className={`sticky bottom-0 border-t px-6 py-4 ${isDark ? "border-white/10 bg-[#0B0B0B]" : "border-slate-200 bg-white"}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                {isManagingExisting
                  ? `LoreVia will process this ${storyUnitLabel} after upload.`
                  : importPreview && !dismissPreview
                    ? "Review the detected structure, then confirm to import."
                    : files.length > 0
                      ? "Ready to upload your manuscript."
                      : "Select a file to enable upload."}
              </p>
              <div className="flex items-center gap-3">
                {isManagingExisting ? (
                  <button
                    type="button"
                    onClick={async () => {
                      const confirmed = await confirm({
                        title: "Delete and reimport project?",
                        body: "Delete this project and all its data? This cannot be undone.",
                        confirmLabel: "Delete and reimport",
                        tone: "danger",
                      })
                      if (!confirmed) return
                      try {
                        await booksApi.delete(existingBookId)
                        void refetchBooks()
                        onClose()
                      } catch {
                        setError("Failed to delete project.")
                      }
                    }}
                    className={`rounded-xl px-4 py-2.5 text-sm font-medium transition ${
                      isDark ? "border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20" : "border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
                    }`}
                  >
                    Delete &amp; reimport
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={onClose}
                  className={`rounded-xl px-4 py-2.5 text-sm font-medium transition ${
                    isDark ? "border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={primaryActionDisabled}
                  className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {primaryActionLabel}
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
  )

  return isInline ? content : (
    <Dialog
      open
      onClose={onClose}
      title={isManagingExisting ? `Add New ${storyUnitLabelTitle}` : "Upload manuscript"}
      description={isManagingExisting
        ? "Add and process the next story unit in this project."
        : "Import a manuscript into a private workspace and begin its first read."}
      size="xl"
      className="!max-w-5xl border-0 bg-transparent shadow-none"
      contentClassName="p-0"
      titleClassName="sr-only"
      descriptionClassName="sr-only"
    >
      {content}
    </Dialog>
  )
})
