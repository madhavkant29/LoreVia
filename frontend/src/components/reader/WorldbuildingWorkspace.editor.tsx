import type { WorldBuildingDocument } from "@/types/world-building"

import { LabeledField, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import {
  accentOutlineButtonClass,
  dangerButtonClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "./WorldbuildingWorkspace.helpers"

export function WorldbuildingDocumentEditorCard({
  isDark,
  selectedDocument,
  draftTitle,
  draftText,
  savingDocument,
  deletingDocument,
  analysisLoading,
  hasDocuments,
  onDraftTitleChange,
  onDraftTextChange,
  onSaveDocument,
  onNewDocument,
  onDeleteDocument,
  onRunAnalysis,
}: {
  isDark: boolean
  selectedDocument: WorldBuildingDocument | null
  draftTitle: string
  draftText: string
  savingDocument: boolean
  deletingDocument: boolean
  analysisLoading: boolean
  hasDocuments: boolean
  onDraftTitleChange: (value: string) => void
  onDraftTextChange: (value: string) => void
  onSaveDocument: () => void
  onNewDocument: () => void
  onDeleteDocument: () => void
  onRunAnalysis: () => void
}) {
  return (
    <WorkspaceCard
      number="8"
      sectionLabel="Worldbuilding Manuscript"
      title={selectedDocument ? "Edit canon source" : "Start a new world document"}
      description={selectedDocument ? `Editing ${selectedDocument.title}. Last updated ${new Date(selectedDocument.updated_at).toLocaleString()}` : "Type directly or upload files to build the corpus."}
      isDark={isDark}
    >
      <div className="space-y-4">
        <LabeledField label="Document title" isDark={isDark}>
          <input
            value={draftTitle}
            onChange={(event) => onDraftTitleChange(event.target.value)}
            className={inputClass(isDark)}
          />
        </LabeledField>

        <LabeledField label="Worldbuilding manuscript" isDark={isDark}>
          <textarea
            value={draftText}
            onChange={(event) => onDraftTextChange(event.target.value)}
            rows={18}
            className={`${inputClass(isDark)} min-h-[26rem] resize-y leading-7`}
          />
        </LabeledField>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onSaveDocument}
            disabled={savingDocument || !draftText.trim()}
            className={primaryButtonClass("teal")}
          >
            {savingDocument ? "Saving..." : selectedDocument ? "Save document" : "Create document"}
          </button>
          <button
            type="button"
            onClick={onNewDocument}
            className={secondaryButtonClass(isDark)}
          >
            New blank document
          </button>
          {selectedDocument ? (
            <button
              type="button"
              onClick={onDeleteDocument}
              disabled={deletingDocument}
              className={dangerButtonClass(isDark)}
            >
              {deletingDocument ? "Removing..." : "Delete document"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onRunAnalysis}
            disabled={analysisLoading || !hasDocuments}
            className={accentOutlineButtonClass("amber", isDark)}
          >
            {analysisLoading ? "Refreshing…" : "Refresh comparison"}
          </button>
        </div>
      </div>
    </WorkspaceCard>
  )
}
