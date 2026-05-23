"use client"

import type { ReactNode } from "react"

import { EditorToolbar, RichTextEditor } from "@/components/editor/SharedRichTextEditor"
import type { Character } from "@/types/character"
import type {
  ManuscriptFrontMatter,
  ManuscriptWorkspaceTree,
  NovelScene,
  SceneVersion,
  SceneVersionDetail,
  WriterWorkspace,
} from "@/types/book"

type ManuscriptOverlayDialogsProps = {
  isDark: boolean
  sceneEditorOpen: boolean
  editingScene: NovelScene | null
  onCloseSceneEditor: () => void
  sceneTitleDraft: string
  onSceneTitleDraftChange: (value: string) => void
  sceneChapterDraft: number | null
  onSceneChapterDraftChange: (value: number | null) => void
  workspaceTree: ManuscriptWorkspaceTree | null
  sceneDescriptionDraft: string
  onSceneDescriptionDraftChange: (value: string) => void
  characters: Character[]
  sceneHtmlDraft: string
  onSceneDraftChange: (nextHtml: string, nextText: string) => void
  sceneVersions: SceneVersion[]
  sceneVersionNameDraft: string
  onSceneVersionNameDraftChange: (value: string) => void
  sceneVersionDetail: SceneVersionDetail | null
  restoringSceneVersionId: string | null
  sceneBodyDraft: string
  onCreateSceneSnapshot: () => void
  onCompareSceneVersion: (versionId: string) => void
  onRestoreSceneSnapshot: (versionId: string) => void
  sceneSaving: boolean
  onSaveScene: () => void
  showCompileDialog: boolean
  writerWorkspace: WriterWorkspace | null
  manuscriptFrontMatter: ManuscriptFrontMatter | null
  onCloseCompileDialog: () => void
  compileFormat: "pdf" | "docx" | "epub" | "obsidian"
  fullBookWordCount: number
  includeSceneMetadataOnExport: boolean
  onIncludeSceneMetadataOnExportChange: (checked: boolean) => void
  onUpdateFrontMatter: (field: keyof ManuscriptFrontMatter, value: string | boolean) => void
  exporting: "pdf" | "docx" | "epub" | "obsidian" | null
  workspaceSaving: boolean
  onCompileManuscript: () => void
}

export function ManuscriptOverlayDialogs({
  isDark,
  sceneEditorOpen,
  editingScene,
  onCloseSceneEditor,
  sceneTitleDraft,
  onSceneTitleDraftChange,
  sceneChapterDraft,
  onSceneChapterDraftChange,
  workspaceTree,
  sceneDescriptionDraft,
  onSceneDescriptionDraftChange,
  characters,
  sceneHtmlDraft,
  onSceneDraftChange,
  sceneVersions,
  sceneVersionNameDraft,
  onSceneVersionNameDraftChange,
  sceneVersionDetail,
  restoringSceneVersionId,
  sceneBodyDraft,
  onCreateSceneSnapshot,
  onCompareSceneVersion,
  onRestoreSceneSnapshot,
  sceneSaving,
  onSaveScene,
  showCompileDialog,
  writerWorkspace,
  manuscriptFrontMatter,
  onCloseCompileDialog,
  compileFormat,
  fullBookWordCount,
  includeSceneMetadataOnExport,
  onIncludeSceneMetadataOnExportChange,
  onUpdateFrontMatter,
  exporting,
  workspaceSaving,
  onCompileManuscript,
}: ManuscriptOverlayDialogsProps) {
  return (
    <>
      {sceneEditorOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 px-4 py-8">
          <div className={`max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-[1.6rem] border p-5 shadow-2xl ${isDark ? "border-white/10 bg-[#0b0f17] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Scene workspace</p>
                <h3 className="mt-2 text-2xl font-semibold">{editingScene ? "Edit chapter scene" : "New chapter scene"}</h3>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Scenes live in the chapter file tree. Rich text, scene breaks, comments, and character mentions now share the same editor foundation as the manuscript.</p>
              </div>
              <button onClick={onCloseSceneEditor} className={`rounded-full px-3 py-1.5 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Close</button>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="text-sm">
                <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Title</span>
                <input
                  value={sceneTitleDraft}
                  onChange={(event) => onSceneTitleDraftChange(event.target.value)}
                  placeholder="Scene title"
                  className={`w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                />
              </label>
              <label className="text-sm">
                <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Optional chapter tag</span>
                <select
                  value={sceneChapterDraft ?? ""}
                  onChange={(event) => onSceneChapterDraftChange(event.target.value ? Number(event.target.value) : null)}
                  className={`w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                >
                  <option value="">Unassigned / decide later</option>
                  {(workspaceTree?.chapters ?? []).map((chapter) => (
                    <option key={chapter.chapter_number} value={chapter.chapter_number}>Chapter {chapter.chapter_number}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="mt-4 block text-sm">
              <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Description</span>
              <input
                value={sceneDescriptionDraft}
                onChange={(event) => onSceneDescriptionDraftChange(event.target.value)}
                placeholder="Optional context for later"
                className={`w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              />
            </label>
            <label className="mt-4 block text-sm">
              <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Scene body</span>
              <div className={`overflow-hidden rounded-[1rem] border ${isDark ? "border-white/10 bg-black" : "border-stone-200 bg-white"}`}>
                <EditorToolbar editorKey="scene-editor-modal" isDark={isDark} compact characters={characters} />
                <RichTextEditor
                  editorKey="scene-editor-modal"
                  html={sceneHtmlDraft}
                  onChange={onSceneDraftChange}
                  placeholder="Write the scene here..."
                  className={`min-h-[18rem] px-4 py-3 text-sm leading-7 outline-none ${isDark ? "text-slate-100" : "text-stone-900"}`}
                />
              </div>
            </label>
            <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Unsaved scene changes autosave locally and stay separate from manual scene versions.</p>
            {editingScene?.id ? (
              <div className={`mt-5 rounded-[1.1rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Scene versions</p>
                    <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Name milestones, compare them with the current scene, or restore an earlier pass.</p>
                  </div>
                  <button onClick={onCreateSceneSnapshot} className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Save named version</button>
                </div>
                <input
                  type="text"
                  value={sceneVersionNameDraft}
                  onChange={(event) => onSceneVersionNameDraftChange(event.target.value)}
                  placeholder="Example: Before tightening dialogue"
                  className={`mt-3 w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                />
                <div className="mt-3 space-y-2">
                  {sceneVersions.map((version) => (
                    <div key={version.id} className={`rounded-[0.95rem] border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{version.note || version.scene_title}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                            {new Date(version.created_at).toLocaleString()} {version.word_count ? `· ${version.word_count} words` : ""}
                          </p>
                          <p className={`mt-1 text-[11px] uppercase tracking-[0.12em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{(version.snapshot_kind || "manual").replaceAll("_", " ")}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() => onCompareSceneVersion(version.id)}
                            className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                          >
                            Compare
                          </button>
                          <button
                            onClick={() => onRestoreSceneSnapshot(version.id)}
                            disabled={restoringSceneVersionId === version.id}
                            className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${isDark ? "bg-amber-500/10 text-amber-200 disabled:opacity-50" : "bg-amber-50 text-amber-700 disabled:opacity-50"}`}
                          >
                            {restoringSceneVersionId === version.id ? "Restoring..." : "Restore"}
                          </button>
                        </div>
                      </div>
                      {sceneVersionDetail?.id === version.id ? (
                        <div className="mt-3 grid gap-3 xl:grid-cols-2">
                          <div className={`rounded-[0.8rem] border px-3 py-2 ${isDark ? "border-white/10 bg-black/30" : "border-stone-200 bg-stone-50"}`}>
                            <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Saved version</p>
                            <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{sceneVersionDetail.body || "No scene text stored in this version."}</p>
                          </div>
                          <div className={`rounded-[0.8rem] border px-3 py-2 ${isDark ? "border-white/10 bg-black/30" : "border-stone-200 bg-stone-50"}`}>
                            <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Current draft</p>
                            <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{sceneBodyDraft || "No scene draft yet."}</p>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ))}
                  {sceneVersions.length === 0 ? <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>No scene versions saved yet. The next manual version will appear here.</p> : null}
                </div>
              </div>
            ) : null}
            <div className="mt-5 flex flex-wrap justify-end gap-3">
              <button onClick={onCloseSceneEditor} className={`rounded-full px-4 py-2 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Cancel</button>
              <button onClick={onSaveScene} disabled={sceneSaving || !sceneTitleDraft.trim() || !sceneBodyDraft.trim()} className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                {sceneSaving ? "Saving..." : editingScene ? "Save scene" : "Create scene"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showCompileDialog && writerWorkspace && manuscriptFrontMatter ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8">
          <div className={`max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[1.7rem] border p-6 shadow-2xl ${isDark ? "border-white/10 bg-[#0b0f17] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Compile manuscript</p>
                <h3 className="mt-2 text-2xl font-semibold">Front page and submission metadata</h3>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>This template feeds the title page, headers, word count line, and export packaging before the manuscript compiles.</p>
              </div>
              <button onClick={onCloseCompileDialog} className={`rounded-full px-3 py-1.5 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Close</button>
            </div>

            <div className={`mt-5 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <span>Format: <strong>{compileFormat.toUpperCase()}</strong></span>
                <span>Automatic manuscript word count: <strong>{fullBookWordCount.toLocaleString()}</strong></span>
                <span>Preset: <strong>{writerWorkspace.publishing.active_preset}</strong></span>
              </div>
              <div className={`mt-4 rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                <p>
                  <span className="font-semibold">Author name</span> is the full or legal name you want on submission materials.
                  <span className="font-semibold"> Pen name</span> is the public byline for this manuscript and export package.
                </p>
                <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  These manuscript names are separate from your LoreVia account username.
                </p>
              </div>
              <label className={`mt-4 flex items-start gap-3 rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                <input
                  type="checkbox"
                  checked={includeSceneMetadataOnExport}
                  onChange={(event) => onIncludeSceneMetadataOnExportChange(event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-stone-300"
                />
                <span>
                  <span className="block font-semibold">Include scene metadata</span>
                  <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Turn this off for clean submission prose with scene breaks rendered as ***.
                  </span>
                </span>
              </label>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Field label="Author name">
                <input value={manuscriptFrontMatter.author_name} onChange={(event) => onUpdateFrontMatter("author_name", event.target.value)} className={inputClass(isDark)} />
              </Field>
              <Field label="Pen name">
                <input value={manuscriptFrontMatter.pen_name} onChange={(event) => onUpdateFrontMatter("pen_name", event.target.value)} className={inputClass(isDark)} />
              </Field>
              <Field label="Contact email">
                <input value={manuscriptFrontMatter.contact_email} onChange={(event) => onUpdateFrontMatter("contact_email", event.target.value)} className={inputClass(isDark)} />
              </Field>
              <Field label="Contact phone">
                <input value={manuscriptFrontMatter.contact_phone} onChange={(event) => onUpdateFrontMatter("contact_phone", event.target.value)} className={inputClass(isDark)} />
              </Field>
              <Field label="Book title">
                <input value={manuscriptFrontMatter.title} onChange={(event) => onUpdateFrontMatter("title", event.target.value)} className={inputClass(isDark)} />
              </Field>
              <Field label="Subtitle">
                <input value={manuscriptFrontMatter.subtitle} onChange={(event) => onUpdateFrontMatter("subtitle", event.target.value)} className={inputClass(isDark)} />
              </Field>
              <Field label="Header last name">
                <input value={manuscriptFrontMatter.header_last_name} onChange={(event) => onUpdateFrontMatter("header_last_name", event.target.value)} className={inputClass(isDark)} />
              </Field>
              <Field label="Header title">
                <input value={manuscriptFrontMatter.header_title} onChange={(event) => onUpdateFrontMatter("header_title", event.target.value)} className={inputClass(isDark)} />
              </Field>
            </div>

            <Field label="Contact address" className="mt-4">
              <textarea value={manuscriptFrontMatter.contact_address} onChange={(event) => onUpdateFrontMatter("contact_address", event.target.value)} rows={3} className={textareaClass(isDark)} />
            </Field>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <Field label="Dedication">
                <textarea value={manuscriptFrontMatter.dedication} onChange={(event) => onUpdateFrontMatter("dedication", event.target.value)} rows={4} className={textareaClass(isDark)} />
                <Toggle checked={manuscriptFrontMatter.include_dedication} onChange={(checked) => onUpdateFrontMatter("include_dedication", checked)} isDark={isDark} label="Include in compile" />
              </Field>
              <Field label="Acknowledgments">
                <textarea value={manuscriptFrontMatter.acknowledgments} onChange={(event) => onUpdateFrontMatter("acknowledgments", event.target.value)} rows={4} className={textareaClass(isDark)} />
                <Toggle checked={manuscriptFrontMatter.include_acknowledgments} onChange={(checked) => onUpdateFrontMatter("include_acknowledgments", checked)} isDark={isDark} label="Include in compile" />
              </Field>
              <Field label="Epigraph">
                <textarea value={manuscriptFrontMatter.epigraph} onChange={(event) => onUpdateFrontMatter("epigraph", event.target.value)} rows={4} className={textareaClass(isDark)} />
                <Toggle checked={manuscriptFrontMatter.include_epigraph} onChange={(checked) => onUpdateFrontMatter("include_epigraph", checked)} isDark={isDark} label="Include in compile" />
              </Field>
              <Field label="Prologue page">
                <textarea value={manuscriptFrontMatter.prologue} onChange={(event) => onUpdateFrontMatter("prologue", event.target.value)} rows={4} className={textareaClass(isDark)} />
                <Toggle checked={manuscriptFrontMatter.include_prologue} onChange={(checked) => onUpdateFrontMatter("include_prologue", checked)} isDark={isDark} label="Include in compile" />
              </Field>
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button onClick={onCloseCompileDialog} className={`rounded-full px-4 py-2 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Cancel</button>
              <button onClick={onCompileManuscript} disabled={!!exporting || workspaceSaving} className="rounded-full bg-[linear-gradient(135deg,#1d4ed8,#1e40af)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                {exporting ? "Compiling..." : `Compile ${compileFormat.toUpperCase()}`}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}

function Field({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={className}>
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</span>
      {children}
    </label>
  )
}

function Toggle({
  checked,
  onChange,
  isDark,
  label,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  isDark: boolean
  label: string
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`mt-3 rounded-full px-3 py-1.5 text-xs font-semibold ${checked ? isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700" : isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-700"}`}
    >
      {label}: {checked ? "On" : "Off"}
    </button>
  )
}

function inputClass(isDark: boolean) {
  return `w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`
}

function textareaClass(isDark: boolean) {
  return `w-full rounded-[1rem] border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`
}
