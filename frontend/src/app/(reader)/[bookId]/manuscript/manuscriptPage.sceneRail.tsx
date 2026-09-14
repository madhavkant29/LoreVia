import Link from "next/link"
import type { DragEvent } from "react"

import { ManuscriptSceneOrderStatus, type SceneOrderSaveState } from "@/components/reader/ManuscriptSceneOrderStatus"
import type { WorkspaceScene, WorkspaceSceneGroup } from "@/types/book"

import {
  SCENE_DRAG_CHAPTER_MIME,
  SCENE_DRAG_SCENE_ID_MIME,
} from "./manuscriptPage.constants"
import { getSceneDropSlotLabel } from "./manuscriptPage.helpers"

type DraggedSceneState = { chapterNumber: number; sceneId: string }
type SceneDropTarget = { chapterNumber: number; index: number }

type ManuscriptSceneRailSectionProps = {
  bookId: string
  collapsedSceneGroups: Record<string, boolean>
  draggedScene: DraggedSceneState | null
  filteredSceneGroups: WorkspaceSceneGroup[]
  includeSceneMetadataOnImport: boolean
  isDark: boolean
  sceneDropTarget: SceneDropTarget | null
  sceneOrderSaveState: Record<number, SceneOrderSaveState>
  onDragSceneStart: (chapterNumber: number, sceneId: string, index: number) => void
  onInsertSceneIntoDraft: (scene: WorkspaceScene) => void
  onOpenSceneEditor: (scene: WorkspaceScene | null) => void
  onRemoveScene: (scene: WorkspaceScene) => void
  onReorderScenesInChapter: (chapterNumber: number, sceneId: string, targetIndex: number) => void
  onResetSceneDragState: () => void
  onSceneDropTargetChange: (target: SceneDropTarget) => void
  onSceneMetadataImportChange: (checked: boolean) => void
  onToggleSceneGroup: (groupId: string, collapsed: boolean) => void
}

export function ManuscriptSceneRailSection({
  bookId,
  collapsedSceneGroups,
  draggedScene,
  filteredSceneGroups,
  includeSceneMetadataOnImport,
  isDark,
  sceneDropTarget,
  sceneOrderSaveState,
  onDragSceneStart,
  onInsertSceneIntoDraft,
  onOpenSceneEditor,
  onRemoveScene,
  onReorderScenesInChapter,
  onResetSceneDragState,
  onSceneDropTargetChange,
  onSceneMetadataImportChange,
  onToggleSceneGroup,
}: ManuscriptSceneRailSectionProps) {
  const dropScene = (
    event: DragEvent<HTMLElement>,
    chapterSceneNumber: number,
    chapterReorderDisabled: boolean,
    targetIndex: number,
  ) => {
    if (chapterReorderDisabled) return
    event.preventDefault()
    const sourceSceneId =
      event.dataTransfer.getData(SCENE_DRAG_SCENE_ID_MIME) ||
      event.dataTransfer.getData("text/plain") ||
      draggedScene?.sceneId
    const sourceChapterNumber = Number.parseInt(
      event.dataTransfer.getData(SCENE_DRAG_CHAPTER_MIME) || "",
      10
    )
    if (Number.isFinite(sourceChapterNumber) && sourceChapterNumber !== chapterSceneNumber) {
      onResetSceneDragState()
      return
    }
    if (!sourceSceneId) {
      onResetSceneDragState()
      return
    }
    onResetSceneDragState()
    onReorderScenesInChapter(chapterSceneNumber, sourceSceneId, targetIndex)
  }

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between gap-3">
        <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-stone-600"}`}>Scenes / reorder</p>
        <Link
          href={`/${bookId}/scenes`}
          className={`rounded-sm border px-2.5 py-1 text-3xs font-semibold ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
        >
          Open workspace
        </Link>
        <label className={`flex items-center gap-2 text-3xs ${isDark ? "text-slate-300" : "text-stone-500"}`}>
          <input
            type="checkbox"
            checked={includeSceneMetadataOnImport}
            onChange={(event) => onSceneMetadataImportChange(event.target.checked)}
            className="h-3.5 w-3.5 rounded border-stone-300"
          />
          Insert metadata
        </label>
      </div>
      <div className="mt-2 space-y-2">
        {filteredSceneGroups.map((group) => {
          const collapsed = collapsedSceneGroups[group.id] ?? group.collapsed_by_default
          const chapterSceneNumber = typeof group.chapter_number === "number" ? group.chapter_number : null
          const isChapterSceneGroup = chapterSceneNumber !== null
          const chapterOrderState = chapterSceneNumber !== null ? (sceneOrderSaveState[chapterSceneNumber] ?? "idle") : "idle"
          const isDraggingWithinChapter = chapterSceneNumber !== null && draggedScene?.chapterNumber === chapterSceneNumber
          const chapterSceneCount = group.scenes.length
          const chapterReorderDisabled = !isChapterSceneGroup || chapterOrderState === "saving"
          return (
            <div
              key={group.id}
              style={{ contentVisibility: "auto", containIntrinsicSize: "240px" }}
              className={`rounded-sm border p-2 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}
            >
              <button
                onClick={() => onToggleSceneGroup(group.id, collapsed)}
                className="flex w-full items-center justify-between gap-3 rounded-sm px-2 py-2 text-left"
              >
                <span className={`text-xs font-semibold uppercase tracking-[0.12em] ${isDark ? "text-slate-300" : "text-stone-700"}`}>{group.label}</span>
                <span className={`text-3xs ${isDark ? "text-slate-300" : "text-stone-500"}`}>{collapsed ? "+" : "-"}</span>
              </button>
              {isChapterSceneGroup && (isDraggingWithinChapter || chapterOrderState !== "idle") ? (
                <div className="flex flex-wrap items-center gap-2 px-2 pb-1">
                  <ManuscriptSceneOrderStatus isDark={isDark} isDragging={isDraggingWithinChapter} state={chapterOrderState} />
                </div>
              ) : null}
              {!collapsed ? (
                <div className="mt-1 space-y-2">
                  {group.scenes.map((scene, index) => {
                    const isDraggedScene = draggedScene?.sceneId === scene.id
                    const isBeforeDropTarget = chapterSceneNumber !== null && sceneDropTarget?.chapterNumber === chapterSceneNumber && sceneDropTarget.index === index

                    return (
                      <div key={scene.id} className="space-y-2">
                        {isChapterSceneGroup && chapterSceneNumber !== null ? (
                          <div
                            data-scene-drop-slot={`${chapterSceneNumber}:${index}`}
                            onDragOver={(event) => {
                              if (chapterReorderDisabled || draggedScene?.chapterNumber !== chapterSceneNumber) return
                              event.preventDefault()
                              event.dataTransfer.dropEffect = "move"
                              onSceneDropTargetChange({ chapterNumber: chapterSceneNumber, index })
                            }}
                            onDrop={(event) => dropScene(event, chapterSceneNumber, chapterReorderDisabled, index)}
                            className={`overflow-hidden rounded-sm border text-center text-3xs font-semibold uppercase tracking-[0.16em] transition-all ${isDraggingWithinChapter ? "h-8 px-3" : "h-0 border-transparent px-0 opacity-0"} ${isBeforeDropTarget ? isDark ? "border-teal-400/40 bg-teal-500/15 text-teal-100" : "border-teal-300 bg-teal-50 text-teal-700" : isDark ? "border-dashed border-white/10 bg-white/[0.03] text-slate-300" : "border-dashed border-stone-200 bg-stone-50 text-stone-600"}`}
                          >
                            <span className="inline-flex h-full items-center">{getSceneDropSlotLabel(index, chapterSceneCount)}</span>
                          </div>
                        ) : null}
                        <div
                          data-scene-id={scene.id}
                          className={`rounded-sm border px-3 py-3 transition ${isDraggedScene ? "scale-[0.99] opacity-70" : ""} ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="min-w-0">
                              {isChapterSceneGroup && chapterSceneNumber !== null ? (
                                <div className="flex flex-wrap items-center gap-1">
                                  <button
                                    type="button"
                                    draggable={!chapterReorderDisabled}
                                    onDragStart={(event) => {
                                      if (chapterReorderDisabled) return
                                      event.dataTransfer.effectAllowed = "move"
                                      event.dataTransfer.setData(SCENE_DRAG_SCENE_ID_MIME, scene.id)
                                      event.dataTransfer.setData(SCENE_DRAG_CHAPTER_MIME, String(chapterSceneNumber))
                                      event.dataTransfer.setData("text/plain", scene.id)
                                      onDragSceneStart(chapterSceneNumber, scene.id, index)
                                    }}
                                    onDragEnd={() => {
                                      window.setTimeout(() => {
                                        onResetSceneDragState()
                                      }, 0)
                                    }}
                                    aria-label={`Drag ${scene.title} to reorder this chapter`}
                                    className={`rounded-sm border px-2 py-1 text-3xs font-semibold uppercase tracking-[0.16em] transition ${chapterReorderDisabled ? "cursor-not-allowed opacity-50" : "cursor-grab active:cursor-grabbing"} ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}
                                  >
                                    Drag
                                  </button>
                                  <button
                                    type="button"
                                    disabled={chapterReorderDisabled || index === 0}
                                    data-testid={`move-scene-${scene.id}-up`}
                                    onClick={() => onReorderScenesInChapter(chapterSceneNumber, scene.id, index - 1)}
                                    aria-label={`Move ${scene.title} up`}
                                    className={`rounded-sm border px-2 py-1 text-3xs font-semibold uppercase tracking-[0.16em] transition disabled:cursor-not-allowed disabled:opacity-40 ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}
                                  >
                                    Up
                                  </button>
                                  <button
                                    type="button"
                                    disabled={chapterReorderDisabled || index >= chapterSceneCount - 1}
                                    data-testid={`move-scene-${scene.id}-down`}
                                    onClick={() => onReorderScenesInChapter(chapterSceneNumber, scene.id, index + 2)}
                                    aria-label={`Move ${scene.title} down`}
                                    className={`rounded-sm border px-2 py-1 text-3xs font-semibold uppercase tracking-[0.16em] transition disabled:cursor-not-allowed disabled:opacity-40 ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}
                                  >
                                    Down
                                  </button>
                                </div>
                              ) : null}
                            </div>
                            <button onClick={() => onInsertSceneIntoDraft(scene)} className={`shrink-0 rounded-none px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>Insert</button>
                          </div>
                          <div data-testid={`scene-copy-${scene.id}`} className="mt-3 min-w-0">
                            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                              {isChapterSceneGroup ? <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-stone-600"}`}>Scene {scene.sort_order}</span> : null}
                              <p className={`min-w-0 break-words text-sm font-semibold leading-5 ${isDark ? "text-white" : "text-stone-900"}`}>{scene.title}</p>
                            </div>
                            <p className={`mt-1 break-words text-3xs ${isDark ? "text-slate-300" : "text-stone-500"}`}>{scene.path}</p>
                            {scene.description ? <p className={`mt-2 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-500"}`}>{scene.description}</p> : null}
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button onClick={() => onOpenSceneEditor(scene)} className={`rounded-none px-2.5 py-1 text-3xs ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Edit</button>
                            <button onClick={() => onRemoveScene(scene)} className={`rounded-none px-2.5 py-1 text-3xs ${isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}>Delete</button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  {isChapterSceneGroup && chapterSceneNumber !== null ? (
                    <div
                      data-scene-drop-slot={`${chapterSceneNumber}:${chapterSceneCount}`}
                      onDragOver={(event) => {
                        if (chapterReorderDisabled || draggedScene?.chapterNumber !== chapterSceneNumber) return
                        event.preventDefault()
                        event.dataTransfer.dropEffect = "move"
                        onSceneDropTargetChange({ chapterNumber: chapterSceneNumber, index: chapterSceneCount })
                      }}
                      onDrop={(event) => dropScene(event, chapterSceneNumber, chapterReorderDisabled, chapterSceneCount)}
                      className={`overflow-hidden rounded-sm border text-center text-3xs font-semibold uppercase tracking-[0.16em] transition-all ${isDraggingWithinChapter ? "h-8 px-3" : "h-0 border-transparent px-0 opacity-0"} ${sceneDropTarget?.chapterNumber === chapterSceneNumber && sceneDropTarget.index === chapterSceneCount ? isDark ? "border-teal-400/40 bg-teal-500/15 text-teal-100" : "border-teal-300 bg-teal-50 text-teal-700" : isDark ? "border-dashed border-white/10 bg-white/[0.03] text-slate-300" : "border-dashed border-stone-200 bg-stone-50 text-stone-600"}`}
                    >
                      <span className="inline-flex h-full items-center">{getSceneDropSlotLabel(chapterSceneCount, chapterSceneCount)}</span>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          )
        })}
        {filteredSceneGroups.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-300" : "text-stone-500"}`}>No scenes match this search yet.</p> : null}
      </div>
    </div>
  )
}
