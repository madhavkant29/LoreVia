"use client"

import dynamic from "next/dynamic"
import { useState, type ButtonHTMLAttributes, type ReactNode } from "react"

import { findWorkspaceStructurePath } from "@/lib/utils/sceneWorkspace"
import type { WorkspaceFolderNode } from "@/lib/utils/workspacePaths"
import type { Book, ManuscriptWorkspaceTree, SceneMetadata, WorkspaceScene } from "@/types/book"

import { metadataTextToList, parseSceneDragItem } from "./scenesPage.helpers"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"

type FolderNode = WorkspaceFolderNode
type StructureNode = NonNullable<ManuscriptWorkspaceTree["structure_tree"]>[number]
type SceneDragItem = { kind: "scene"; id: string }
export type BrowserView = "folders" | "scenes"

const EditorToolbar = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.EditorToolbar),
  { ssr: false },
)

const RichTextEditor = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.RichTextEditor),
  {
    ssr: false,
    loading: () => <div className="min-h-[32rem] animate-pulse bg-black/20" />,
  },
)

const WhatsTheWordPanel = dynamic(
  () => import("@/components/intelligence/WhatsTheWordPanel").then((module) => module.WhatsTheWordPanel),
  { ssr: false },
)

export function WorkspaceHeader({
  book,
  isDark,
  onNewScene,
  onNewFolder,
  disabled = false,
}: {
  book: Book | null
  isDark: boolean
  onNewScene: () => void
  onNewFolder: () => void
  disabled?: boolean
}) {
  return (
    <section className={`flex flex-col gap-4 border-b px-1 pb-5 pt-2 sm:flex-row sm:items-end sm:justify-between ${isDark ? "border-white/10" : "border-stone-200"}`}>
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Scenes</h1>
        <p className={`mt-1 break-words text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book?.title || "Manuscript"} · Draft and organize scene files.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <ActionButton type="button" disabled={disabled} isDark={isDark} onClick={onNewScene}><IconSparkPlus />New scene</ActionButton>
        <ActionButton type="button" disabled={disabled} variant="secondary" isDark={isDark} onClick={onNewFolder}><IconFolderPlus />New folder</ActionButton>
        <button type="button" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))} className="min-h-11 px-3 text-sm underline underline-offset-4">Help</button>
      </div>
    </section>
  )
}

export function MobilePanelToggles({
  isDark,
  showBrowser,
  showInspector,
  onToggleBrowser,
  onToggleInspector,
}: {
  isDark: boolean
  showBrowser: boolean
  showInspector: boolean
  onToggleBrowser: () => void
  onToggleInspector: () => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <ActionButton type="button" aria-pressed={showBrowser} variant={showBrowser ? "secondary" : "ghost"} isDark={isDark} onClick={onToggleBrowser}>
        Outline
      </ActionButton>
      <ActionButton type="button" aria-pressed={showInspector} variant={showInspector ? "secondary" : "ghost"} isDark={isDark} onClick={onToggleInspector}>
        Details
      </ActionButton>
    </div>
  )
}

export function SceneBrowserPanel({
  isDark,
  browserView,
  onBrowserViewChange,
  search,
  onSearchChange,
  scenes,
  filteredScenes,
  selectedFolder,
  selectedSceneId,
  folderTree,
  collapsed,
  onToggleFolder,
  onSelectFolder,
  onCreateFolder,
  onDropScene,
  dropTargetFolder,
  onDropTargetChange,
  onSelectScene,
  onCreateScene,
}: {
  isDark: boolean
  browserView: BrowserView
  onBrowserViewChange: (value: BrowserView) => void
  search: string
  onSearchChange: (value: string) => void
  scenes: WorkspaceScene[]
  filteredScenes: WorkspaceScene[]
  selectedFolder: string | null
  selectedSceneId: string | null
  folderTree: FolderNode
  collapsed: Record<string, boolean>
  onToggleFolder: (path: string) => void
  onSelectFolder: (path: string | null) => void
  onCreateFolder: (path?: string | null) => void
  onDropScene: (sceneId: string, folderPath: string | null) => void
  dropTargetFolder: string | null
  onDropTargetChange: (path: string | null) => void
  onSelectScene: (scene: WorkspaceScene) => void
  onCreateScene: () => void
}) {
  const folderPanelClass = browserView === "scenes" ? "hidden" : "block"
  const scenePanelClass = browserView === "folders" ? "hidden" : "block"

  return (
    <aside className={`h-full min-w-0 p-4 sm:p-5 ${isDark ? "bg-[#07101c]" : "bg-stone-50/70"}`}>
      <div className="space-y-4">
        <WorkspaceTabs isDark={isDark} value={browserView} onChange={onBrowserViewChange} />

        <div className="flex items-center gap-2">
          <label className={`flex min-w-0 flex-1 items-center gap-2 rounded-sm border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-[#030b16] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
            <IconSearch />
            <span className="sr-only">Search scenes</span>
            <input
              value={search}
              onChange={(event) => { onSearchChange(event.target.value); if (event.target.value.trim()) onBrowserViewChange("scenes") }}
              className="min-w-0 flex-1 bg-transparent outline-none"
            />
          </label>
        </div>
        {search || selectedFolder ? <div className="text-sm"><p className="break-words">{filteredScenes.length} scenes{selectedFolder ? ` in ${selectedFolder}` : ""}</p><button type="button" onClick={() => { onSearchChange(""); onSelectFolder(null); onBrowserViewChange("scenes") }} className={`mt-1 min-h-10 underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Clear filters</button></div> : null}

        <div className={folderPanelClass} role="tabpanel" id="scene-browser-folders" aria-labelledby="scene-browser-tab-folders">
          <PanelCard
            isDark={isDark}
            label="Folders"
            title="Scene folders"
            action={(
              <button
                type="button"
                onClick={() => onCreateFolder()}
                aria-label="Create new folder"
                className={`inline-flex h-8 w-8 items-center justify-center rounded-sm border transition-colors ${isDark ? "border-white/10 text-slate-400 hover:bg-white/[0.06] hover:text-white" : "border-stone-200 text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}
              >
                <IconPlus />
              </button>
            )}
          >
            <div className="space-y-2.5">
              <button
                type="button"
                onClick={() => { onSelectFolder(null); onBrowserViewChange("scenes") }}
                onDragOver={(event) => {
                  if (!parseSceneDragItem(event)) return
                  event.preventDefault()
                  onDropTargetChange("")
                }}
                onDragLeave={() => {
                  if (dropTargetFolder === "") onDropTargetChange(null)
                }}
                onDrop={(event) => {
                  const dragItem = parseSceneDragItem(event)
                  if (!dragItem) return
                  event.preventDefault()
                  onDropScene(dragItem.id, null)
                }}
                className={`flex w-full items-center justify-between border-b px-2 py-2.5 text-left text-sm transition-colors ${
                  !selectedFolder
                    ? isDark
                      ? "border-teal-400/30 bg-teal-400/10 text-teal-50"
                      : "border-teal-300 bg-teal-50/70 text-teal-800"
                    : isDark
                      ? "border-white/10 text-slate-300 hover:bg-white/[0.04]"
                      : "border-stone-200 text-stone-700 hover:bg-stone-50"
                } ${dropTargetFolder === "" ? (isDark ? "ring-1 ring-teal-300/50" : "ring-1 ring-teal-300") : ""}`}
              >
                <span className="flex items-center gap-2 font-medium"><IconFolder />All scenes</span>
                <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{scenes.length}</span>
              </button>

              <div className="max-h-[18rem] overflow-auto pr-1">
                <SceneFolderTree
                  node={folderTree}
                  activePath={selectedFolder}
                  collapsed={collapsed}
                  onToggleFolder={onToggleFolder}
                  onSelect={(path) => { onSelectFolder(path); onBrowserViewChange("scenes") }}
                  onCreateFolder={onCreateFolder}
                  onDropScene={(sceneId, folderPath) => void onDropScene(sceneId, folderPath)}
                  dropTargetPath={dropTargetFolder}
                  onDropTargetChange={onDropTargetChange}
                  isDark={isDark}
                />
              </div>

              <button type="button" onClick={() => onCreateFolder(selectedFolder)} className={`inline-flex items-center gap-2 text-sm font-medium ${isDark ? "text-teal-200 hover:text-white" : "text-teal-700 hover:text-teal-900"}`}>
                <IconPlus />
                New folder
              </button>
            </div>
          </PanelCard>
        </div>

        <div className={scenePanelClass} role="tabpanel" id="scene-browser-scenes" aria-labelledby="scene-browser-tab-scenes">
          <PanelCard
            isDark={isDark}
            label="Scenes"
            title="Scene list"
            action={<button type="button" aria-label="Create new scene" onClick={onCreateScene} className={`inline-flex h-8 w-8 items-center justify-center rounded-sm border transition-colors ${isDark ? "border-white/10 text-slate-400 hover:bg-white/[0.06] hover:text-white" : "border-stone-200 text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}><IconPlus /></button>}
          >
            {filteredScenes.length === 0 ? (
              <div className="py-6">
                <p className={`text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-800"}`}>No scenes match this view.</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{scenes.length ? "Try another search or clear the filters." : "Create a new scene to get started."}</p>
                <div className="mt-4">
                  <ActionButton type="button" isDark={isDark} onClick={onCreateScene}>New scene</ActionButton>
                </div>
              </div>
            ) : (
              <div className="max-h-[28rem] space-y-2 overflow-auto pr-1">
                {filteredScenes.map((scene) => (
                  <button
                    key={scene.id}
                    type="button"
                    draggable
                    onDragStart={(event) => {
                      const payload: SceneDragItem = { kind: "scene", id: scene.id }
                      event.dataTransfer.effectAllowed = "move"
                      event.dataTransfer.setData("application/lorevia-scene-item", JSON.stringify(payload))
                    }}
                    onClick={() => onSelectScene(scene)}
                    aria-pressed={selectedSceneId === scene.id}
                    className={`block w-full border-b px-2 py-3 text-left transition-colors ${
                      selectedSceneId === scene.id
                        ? isDark
                          ? "border-teal-400/35 bg-teal-400/10 text-white"
                          : "border-teal-300 bg-teal-50/70 text-stone-950"
                        : isDark
                          ? "border-white/10 text-slate-300 hover:bg-white/[0.05]"
                          : "border-stone-200 text-stone-700 hover:bg-stone-50"
                    }`}
                  >
                    <span className="block break-words text-sm font-semibold">{scene.title}</span>
                    <span className={`mt-1 block break-all text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{scene.path}</span>
                    {scene.description ? (
                      <span className={`mt-2 line-clamp-2 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{scene.description}</span>
                    ) : null}
                  </button>
                ))}
              </div>
            )}
          </PanelCard>
        </div>
      </div>
    </aside>
  )
}

export function SceneMetadataForm({
  isDark,
  description,
  sceneFolderDraft,
  sceneMetadata,
  selectedTagList,
  selectedMoodList,
  onDescriptionChange,
  onSceneFolderDraftChange,
  onSceneMetadataChange,
}: {
  isDark: boolean
  description: string
  sceneFolderDraft: string
  sceneMetadata: SceneMetadata
  selectedTagList: string[]
  selectedMoodList: string[]
  onDescriptionChange: (value: string) => void
  onSceneFolderDraftChange: (value: string) => void
  onSceneMetadataChange: (updater: SceneMetadata | ((current: SceneMetadata) => SceneMetadata)) => void
}) {
  const setSceneMetadata = (updater: SceneMetadata | ((current: SceneMetadata) => SceneMetadata)) => {
    onSceneMetadataChange(typeof updater === "function" ? updater(sceneMetadata) : updater)
  }
  const hasAdvancedMetadata = Boolean(
    sceneMetadata.timeline ||
    sceneMetadata.location ||
    selectedMoodList.length ||
    selectedTagList.length ||
    sceneMetadata.status_note
  )
  const [advancedOpen, setAdvancedOpen] = useState(hasAdvancedMetadata)

  return (
    <section>
      <div className={`border-b pb-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <h2 className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Metadata</h2>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>File location, summary, point of view, and planning metadata.</p>
      </div>

      <div className="mt-5 grid gap-5">
        <Field label="Folder path" detail="Example: scenes/act-1/opening" isDark={isDark}>
          <input id="scene-field-folder-path" aria-describedby="scene-field-folder-path-help" value={sceneFolderDraft} onChange={(event) => onSceneFolderDraftChange(event.target.value)} className={inputClass(isDark)} />
        </Field>

        <Field label="Description" detail="Optional scene summary." isDark={isDark}>
          <textarea id="scene-field-description" aria-describedby="scene-field-description-help" value={description} onChange={(event) => onDescriptionChange(event.target.value)} className={`${inputClass(isDark)} min-h-[9rem] resize-y`} />
        </Field>
      </div>

      <div className="mt-5 grid gap-5">
        <Field label="POV character" detail="Whose eyes are we in?" isDark={isDark}>
          <input id="scene-field-pov-character" aria-describedby="scene-field-pov-character-help" value={sceneMetadata.pov ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, pov: event.target.value || null }))} className={inputClass(isDark)} />
        </Field>
      </div>

      <div className={`mt-5 border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <button
          type="button"
          aria-expanded={advancedOpen}
          onClick={() => setAdvancedOpen((current) => !current)}
          className={`flex w-full items-center justify-between gap-3 text-left text-sm font-medium transition-colors ${isDark ? "text-slate-300 hover:text-white" : "text-stone-700 hover:text-stone-950"}`}
        >
          <span>Advanced metadata</span>
          <span aria-hidden="true" className="text-base font-normal">{advancedOpen ? "−" : "+"}</span>
        </button>
        {advancedOpen ? <div className="mt-5 grid gap-5">
          <Field label="Timeline / date" detail="Example: Day 3, Winter court, 8:12 PM." isDark={isDark}>
            <input id="scene-field-timeline-date" aria-describedby="scene-field-timeline-date-help" value={sceneMetadata.timeline ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, timeline: event.target.value || null }))} className={inputClass(isDark)} />
          </Field>
          <Field label="Location" detail="Name the place or set where the scene happens." isDark={isDark}>
            <input id="scene-field-location" aria-describedby="scene-field-location-help" value={sceneMetadata.location ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, location: event.target.value || null }))} className={inputClass(isDark)} />
          </Field>
          <Field label="Mood / tone" detail="Separate moods with commas, such as tense, intimate, foreboding." isDark={isDark}>
            <div className="space-y-2">
              {selectedMoodList.length > 0 ? <TokenList items={selectedMoodList} isDark={isDark} /> : null}
              <input id="scene-field-mood-tone" aria-describedby="scene-field-mood-tone-help" value={(sceneMetadata.mood ?? []).join(", ")} onChange={(event) => setSceneMetadata((current) => ({ ...current, mood: metadataTextToList(event.target.value, true) }))} className={inputClass(isDark)} />
            </div>
          </Field>
          <Field label="Tags" detail="Separate tags with commas, such as betrayal, dagger, reveal." isDark={isDark}>
            <div className="space-y-2">
              {selectedTagList.length > 0 ? <TokenList items={selectedTagList} isDark={isDark} /> : null}
              <input id="scene-field-tags" aria-describedby="scene-field-tags-help" value={(sceneMetadata.tags ?? []).join(", ")} onChange={(event) => setSceneMetadata((current) => ({ ...current, tags: metadataTextToList(event.target.value, true) }))} className={inputClass(isDark)} />
            </div>
          </Field>
          <Field label="Status note" detail="Example: draft, revised, final, waiting on continuity pass." isDark={isDark}>
            <input id="scene-field-status-note" aria-describedby="scene-field-status-note-help" value={sceneMetadata.status_note ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, status_note: event.target.value || null }))} className={inputClass(isDark)} />
          </Field>
        </div> : null}
      </div>
    </section>
  )
}

export function SceneEditorPanel({
  isDark,
  title,
  chapterNumber,
  chapterOptions,
  htmlBody,
  wordCount,
  readingTime,
  status,
  dirty = false,
  saving,
  canSave,
  hasSelectedScene,
  firstLineIndent,
  onTitleChange,
  onChapterNumberChange,
  onToggleFirstLineIndent,
  onHtmlChange,
  onDelete,
  onSave,
}: {
  isDark: boolean
  title: string
  chapterNumber: number | null
  chapterOptions: number[]
  htmlBody: string
  wordCount: number
  readingTime: string
  status: string | null
  dirty?: boolean
  saving: boolean
  canSave: boolean
  hasSelectedScene: boolean
  firstLineIndent: boolean
  onTitleChange: (value: string) => void
  onChapterNumberChange: (value: number | null) => void
  onToggleFirstLineIndent: () => void
  onHtmlChange: (nextHtml: string, nextText: string) => void
  onDelete: () => void
  onSave: () => void
}) {
  return (
    <section className={`min-w-0 ${isDark ? "bg-[#09111c]" : "bg-white"}`}>
      <fieldset disabled={saving} className={`min-w-0 border-b px-4 py-4 sm:px-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 flex-1">
            <label htmlFor="scene-title" className="sr-only">Scene title</label>
            <input id="scene-title" value={title} onChange={(event) => onTitleChange(event.target.value)} placeholder="Untitled scene" className={`w-full border-0 bg-transparent text-2xl font-semibold tracking-tight outline-none ${isDark ? "text-white placeholder:text-slate-400" : "text-stone-950 placeholder:text-stone-600"}`} />
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{wordCount.toLocaleString()} words · {readingTime}</p>
          </div>
          <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            <span>Chapter</span>
            <select value={chapterNumber ?? ""} onChange={(event) => onChapterNumberChange(event.target.value ? Number(event.target.value) : null)} className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#09111c] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              <option value="">Unassigned</option>
              {chapterOptions.map((chapter) => <option key={chapter} value={chapter}>{chapter}</option>)}
            </select>
          </label>
        </div>
      </fieldset>

      <div className={`flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <p role="status" className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          {saving ? "Working…" : dirty ? "Unsaved changes" : status ?? (hasSelectedScene ? "All changes saved" : "Add a title and scene text to save.")}
        </p>
        <div className="flex flex-wrap gap-2.5">
          {hasSelectedScene ? <ActionButton type="button" variant="ghost" isDark={isDark} disabled={saving} onClick={onDelete}>Delete</ActionButton> : null}
          <ActionButton type="button" isDark={isDark} onClick={onSave} disabled={saving || !canSave || (!dirty && hasSelectedScene)}>{saving ? "Working…" : "Save scene"}</ActionButton>
        </div>
      </div>

      <div inert={saving}>
        <div className={`flex w-full min-w-0 items-center justify-between gap-2 ${isDark ? "bg-[#0d1726]" : "bg-stone-50/70"}`}>
          <div className="min-w-0 flex-1 overflow-x-auto"><div className="min-w-max"><EditorToolbar editorKey="scene-workspace-editor" isDark={isDark} compact portalFormattingMenu /></div></div>
          <div className="flex shrink-0 items-center gap-1 pr-2">
            <button
              type="button"
              aria-pressed={firstLineIndent}
              onClick={onToggleFirstLineIndent}
              className={`whitespace-nowrap rounded-sm px-2.5 py-1.5 text-xs font-medium transition-colors ${isDark ? "text-slate-300 hover:bg-white/[0.07]" : "text-stone-600 hover:bg-stone-100"}`}
            >
              {firstLineIndent ? "Indent on" : "Indent off"}
            </button>
          </div>
        </div>
        <RichTextEditor
          editorKey="scene-workspace-editor"
          ariaLabel="Scene text"
          html={htmlBody}
          onChange={onHtmlChange}
          onShortcutSave={onSave}
          style={{ textIndent: firstLineIndent ? "1.5em" : "0" }}
          className={`min-h-[24rem] px-5 py-4 font-serif text-base leading-8 outline-none sm:min-h-[30rem] ${isDark ? "text-slate-100" : "text-stone-900"}`}
        />
      </div>

    </section>
  )
}

export function MetadataPreviewPanel({
  isDark,
  metadataRows,
  sceneTitle,
  sceneDescription,
  chapterNumber,
  wordCount,
  readingTime,
  currentScenePath,
  selectedSceneId,
  structureTree,
}: {
  isDark: boolean
  metadataRows: Array<[string, unknown]>
  sceneTitle: string
  sceneDescription: string
  chapterNumber: number | null
  wordCount: number
  readingTime: string
  currentScenePath: string | null
  selectedSceneId: string | null
  structureTree: NonNullable<ManuscriptWorkspaceTree["structure_tree"]>
}) {
  const hierarchyPath = findWorkspaceStructurePath(structureTree, selectedSceneId, sceneTitle)
  const displayHierarchyPath: StructureNode[] = hierarchyPath.length
    ? hierarchyPath
    : chapterNumber
      ? [
          { id: `chapter-${chapterNumber}`, label: `Chapter ${chapterNumber}`, kind: "chapter", chapter_number: chapterNumber, children: [] },
          { id: selectedSceneId ?? "draft-scene", label: sceneTitle, kind: "scene", chapter_number: chapterNumber, scene_id: selectedSceneId, children: [] },
        ]
      : []
  const summaryFromMetadata = metadataRows.find(([key]) => key === "summary")?.[1]
  const summary = summaryFromMetadata ? formatMetadataValue(summaryFromMetadata) : sceneDescription
  const detailRows: Array<[string, string]> = [
    ["Chapter", chapterNumber ? `Chapter ${chapterNumber}` : "Unassigned"],
    ["Words", `${wordCount.toLocaleString()} words`],
    ["Read time", readingTime],
    ...metadataRows
      .filter(([key]) => key !== "summary")
      .slice(0, 5)
      .map(([key, value]) => [formatInspectorLabel(key), formatMetadataValue(value)] as [string, string]),
  ]

  return (
    <aside className={`h-full min-w-0 p-4 sm:p-5 ${isDark ? "bg-[#07101c]" : "bg-stone-50/70"}`}>
      <div className={`rounded-md border ${isDark ? "border-white/10 bg-[#0b1421]" : "border-stone-200 bg-white"}`}>
        <div className={`border-b px-4 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <p className={sectionLabel(isDark)}>Inspector</p>
          <h2 className={`mt-1 truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{sceneTitle}</h2>
          <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{chapterNumber ? `Chapter ${chapterNumber}` : "No chapter assigned"}</p>
        </div>

        <div className="space-y-5 px-4 py-4">
          <InspectorSection isDark={isDark} label="Summary">
            {summary ? (
              <p className={`max-h-36 overflow-hidden text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{summary}</p>
            ) : (
              <p className={`rounded-md border border-dashed px-3 py-4 text-sm leading-6 ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
                Add a description or summary to preview the scene here.
              </p>
            )}
          </InspectorSection>

          <InspectorSection isDark={isDark} label="Details">
            <dl className="space-y-2.5">
              {detailRows.map(([label, value]) => (
                <div key={label} className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3">
                  <dt className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</dt>
                  <dd className={`min-w-0 break-words text-right text-xs font-medium leading-5 ${isDark ? "text-slate-200" : "text-stone-800"}`}>{value}</dd>
                </div>
              ))}
            </dl>
          </InspectorSection>

          <InspectorSection isDark={isDark} label="File">
            <p className={`break-words rounded-sm border px-3 py-3 text-xs leading-5 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
              {currentScenePath ?? "Set a title to generate the scene filename."}
            </p>
          </InspectorSection>

          <InspectorSection isDark={isDark} label="Hierarchy">
            {displayHierarchyPath.length ? (
              <div className="space-y-2">
                {displayHierarchyPath.map((node, index) => (
                  <StructureTreePreview
                    key={`${node.id}-${index}`}
                    node={node}
                    isDark={isDark}
                    isCurrent={index === displayHierarchyPath.length - 1}
                  />
                ))}
              </div>
            ) : (
              <p className={`rounded-md border border-dashed px-3 py-4 text-sm leading-6 ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>
                No hierarchy is available for this scene yet.
              </p>
            )}
          </InspectorSection>

          <p className={`border-t pt-4 text-xs leading-5 ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-500"}`}>
            Folder paths stay attached when scenes move into the manuscript.
          </p>
        </div>
      </div>
    </aside>
  )
}

function WorkspaceTabs({
  isDark,
  value,
  onChange,
}: {
  isDark: boolean
  value: BrowserView
  onChange: (value: BrowserView) => void
}) {
  const tabs: Array<{ id: BrowserView; label: string }> = [
    { id: "folders", label: "Folders" },
    { id: "scenes", label: "Scenes" },
  ]

  return (
    <div className={`flex gap-4 border-b ${isDark ? "border-white/10" : "border-stone-200"}`} role="tablist" aria-label="Scene browser sections">
      {tabs.map((tab) => {
        const active = tab.id === value
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`scene-browser-tab-${tab.id}`}
            aria-controls={`scene-browser-${tab.id}`}
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onKeyDown={(event) => {
              if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
              event.preventDefault()
              const next = event.key === "Home" ? "folders" : event.key === "End" ? "scenes" : value === "folders" ? "scenes" : "folders"
              onChange(next)
              document.getElementById(`scene-browser-tab-${next}`)?.focus()
            }}
            onClick={() => onChange(tab.id)}
            className={`border-b-2 px-0 py-2 text-sm font-medium transition-colors ${
              active
                ? isDark
                  ? "border-teal-300 text-teal-100"
                  : "border-teal-700 text-teal-800"
                : isDark
                  ? "border-transparent text-slate-400 hover:text-slate-200"
                  : "border-transparent text-stone-500 hover:text-stone-800"
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

function PanelCard({
  isDark,
  label,
  title,
  action,
  children,
}: {
  isDark: boolean
  label: string
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={`border-b pb-5 last:border-b-0 ${isDark ? "border-white/10" : "border-stone-200"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={sectionLabel(isDark)}>{label}</p>
          <h2 className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</h2>
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function InspectorSection({
  isDark,
  label,
  children,
}: {
  isDark: boolean
  label: string
  children: ReactNode
}) {
  return (
    <section>
      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>{label}</p>
      {children}
    </section>
  )
}

export function WorkspaceStateCard({
  isDark,
  title,
  body,
  action,
}: {
  isDark: boolean
  title: string
  body: string
  action?: ReactNode
}) {
  return (
    <div className="px-5 py-16 sm:px-8">
      <div className={`mx-auto max-w-2xl rounded-md border px-6 py-10 text-center ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
        <p className={sectionLabel(isDark)}>Scene workspace</p>
        <h2 className={`mt-3 text-xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</h2>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{body}</p>
        {action ? <div className="mt-5">{action}</div> : null}
      </div>
    </div>
  )
}

function Field({
  label,
  detail,
  isDark,
  children,
}: {
  label: string
  detail?: string
  isDark: boolean
  children: ReactNode
}) {
  return (
    <div className="block text-sm">
      <label htmlFor={`scene-field-${label.toLowerCase().replace(/[^a-z]+/g, "-")}`} className={labelClass(isDark)}>{label}</label>
      {children}
      {detail ? <span id={`scene-field-${label.toLowerCase().replace(/[^a-z]+/g, "-")}-help`} className={`mt-2 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{detail}</span> : null}
    </div>
  )
}

function TokenList({ items, isDark }: { items: string[]; isDark: boolean }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className={`inline-flex items-center rounded-sm border px-2.5 py-1 text-xs ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}
        >
          {item}
        </span>
      ))}
    </div>
  )
}

function SceneFolderTree({
  node,
  activePath,
  collapsed,
  onToggleFolder,
  onSelect,
  onCreateFolder,
  onDropScene,
  dropTargetPath,
  onDropTargetChange,
  isDark,
  depth = 0,
}: {
  node: FolderNode
  activePath: string | null
  collapsed: Record<string, boolean>
  onToggleFolder: (path: string) => void
  onSelect: (path: string) => void
  onCreateFolder: (path: string) => void
  onDropScene: (sceneId: string, folderPath: string) => void
  dropTargetPath: string | null
  onDropTargetChange: (path: string | null) => void
  isDark: boolean
  depth?: number
}) {
  return (
    <div className="space-y-1.5">
      {[...node.folders.values()].map((child) => {
        const isCollapsed = Boolean(collapsed[child.path])
        const active = child.path === activePath
        return (
          <div key={child.path}>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => onToggleFolder(child.path)}
                aria-label={isCollapsed ? `Expand ${child.name}` : `Collapse ${child.name}`}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-slate-200" : "text-stone-600 hover:bg-stone-100 hover:text-stone-700"}`}
                style={{ marginLeft: `${depth * 12}px` }}
              >
                <IconChevron open={!isCollapsed} />
              </button>
              <button
                type="button"
                onClick={() => onSelect(child.path)}
                onDragOver={(event) => {
                  if (!parseSceneDragItem(event)) return
                  event.preventDefault()
                  onDropTargetChange(child.path)
                }}
                onDragLeave={() => onDropTargetChange(null)}
                onDrop={(event) => {
                  const dragItem = parseSceneDragItem(event)
                  if (!dragItem) return
                  event.preventDefault()
                  onDropScene(dragItem.id, child.path)
                }}
                className={`flex min-w-0 flex-1 items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition ${
                  active
                    ? isDark
                      ? "border-teal-400/30 bg-teal-400/12 text-teal-50"
                      : "border-teal-300 bg-teal-50 text-teal-800"
                    : isDark
                      ? "border-white/10 bg-white/[0.02] text-slate-300 hover:bg-white/[0.04]"
                      : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                } ${dropTargetPath === child.path ? (isDark ? "ring-1 ring-teal-300/50" : "ring-1 ring-teal-300") : ""}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <IconFolder />
                  <span className="truncate font-medium">{child.name}</span>
                </span>
                <span className={`text-xs ${active ? (isDark ? "text-teal-100/80" : "text-teal-700/80") : isDark ? "text-slate-400" : "text-stone-600"}`}>{child.itemCount}</span>
              </button>
              <button
                type="button"
                onClick={() => onCreateFolder(child.path)}
                aria-label={`Create a folder inside ${child.name}`}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-white" : "text-stone-600 hover:bg-stone-100 hover:text-stone-800"}`}
              >
                <IconPlus />
              </button>
            </div>
            {!isCollapsed ? (
              <div className="mt-1">
                <SceneFolderTree
                  node={child}
                  activePath={activePath}
                  collapsed={collapsed}
                  onToggleFolder={onToggleFolder}
                  onSelect={onSelect}
                  onCreateFolder={onCreateFolder}
                  onDropScene={onDropScene}
                  dropTargetPath={dropTargetPath}
                  onDropTargetChange={onDropTargetChange}
                  isDark={isDark}
                  depth={depth + 1}
                />
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

export function ActionButton({
  isDark,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { isDark: boolean; variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const styles = {
    primary: isDark
      ? "border-teal-400/25 bg-[#1f615d] text-white"
      : "border-teal-500 bg-teal-700 text-white",
    secondary: isDark
      ? "border-white/10 bg-white/[0.05] text-slate-100 hover:bg-white/[0.08]"
      : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50",
    ghost: isDark
      ? "border-white/10 bg-transparent text-slate-300 hover:bg-white/[0.05]"
      : "border-stone-200 bg-transparent text-stone-700 hover:bg-white",
    danger: isDark
      ? "border-rose-400/15 bg-rose-500/10 text-rose-100 hover:bg-rose-500/14"
      : "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100",
  }

  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-sm border px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    />
  )
}

function formatMetadataValue(value: unknown) {
  if (Array.isArray(value)) return value.join(", ")
  return String(value ?? "")
}

function formatInspectorLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function sectionLabel(isDark: boolean) {
  return `text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-500"}`
}

function labelClass(isDark: boolean) {
  return `mb-2 block text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-500"}`
}

function inputClass(isDark: boolean) {
  return `w-full rounded-sm border px-3 py-3 text-sm outline-none transition-colors focus-visible:ring-2 ${
    isDark
      ? "border-white/10 bg-[#040b15] text-slate-100 focus-visible:border-teal-300/30 focus-visible:ring-teal-300/20"
      : "border-stone-200 bg-white text-stone-900 focus-visible:border-teal-400 focus-visible:ring-teal-200"
  }`
}

function IconSearch() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
}

function IconChevron({ open }: { open: boolean }) {
  return <svg className={`h-4 w-4 transition ${open ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
}

function IconFolder() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h6l2 2h8v9a2 2 0 01-2 2H6a2 2 0 01-2-2V7z" /></svg>
}

function IconPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
}

export function WritingToolsPanel({
  isDark,
  visible,
  onOpen,
  bookId,
}: {
  isDark: boolean
  visible: boolean
  onOpen: () => void
  bookId: string
}) {
  if (!visible) {
    return (
      <section className={`flex items-center justify-between border-t px-1 pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Need a precise word?</p>
        <button type="button" className={`text-sm font-medium ${isDark ? "text-teal-200" : "text-teal-800"}`} onClick={onOpen}>Open word finder</button>
      </section>
    )
  }

  return (
    <div className={`border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
      <div className="flex items-center justify-between gap-3">
        <p className={sectionLabel(isDark)}>Writing assistant</p>
        <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Loaded on demand</span>
      </div>
      <WhatsTheWordPanel bookId={bookId} isDark={isDark} className="mt-3" />
    </div>
  )
}

function IconSparkPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19 18v4M17 20h4" /></svg>
}

function IconFolderPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M3.5 7.5h6l2 2h9v8.5a2 2 0 01-2 2h-13a2 2 0 01-2-2V7.5z" /><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 13.5v4M14.5 15.5h4" /></svg>
}

function StructureTreePreview({
  node,
  isDark,
  isCurrent,
}: {
  node: StructureNode
  isDark: boolean
  isCurrent: boolean
}) {
  return (
    <div className="flex min-w-0 items-start gap-2">
      <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-sm ${isCurrent ? (isDark ? "bg-teal-300" : "bg-teal-600") : isDark ? "bg-slate-600" : "bg-stone-300"}`} />
      <div className="min-w-0">
        <p className={`truncate text-sm font-medium ${isCurrent ? (isDark ? "text-teal-50" : "text-teal-800") : isDark ? "text-slate-300" : "text-stone-700"}`}>{node.label}</p>
        <p className={`mt-0.5 text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-600" : "text-stone-600"}`}>{node.kind}</p>
      </div>
    </div>
  )
}
