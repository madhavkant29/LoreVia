import { useState } from "react"

import type { SceneOrderSaveState } from "@/components/reader/ManuscriptSceneOrderStatus"
import type { NovelScene, SceneVersion, SceneVersionDetail } from "@/types/book"

type DraggedSceneState = { chapterNumber: number; sceneId: string }
type SceneDropTarget = { chapterNumber: number; index: number }

export function useManuscriptSceneUiState() {
  const [sceneSearch, setSceneSearch] = useState("")
  const [chapterSearch, setChapterSearch] = useState("")
  const [collapsedSceneGroups, setCollapsedSceneGroups] = useState<Record<string, boolean>>({})
  const [draggedScene, setDraggedScene] = useState<DraggedSceneState | null>(null)
  const [sceneDropTarget, setSceneDropTarget] = useState<SceneDropTarget | null>(null)
  const [sceneOrderSaveState, setSceneOrderSaveState] = useState<Record<number, SceneOrderSaveState>>({})
  const [sceneEditorOpen, setSceneEditorOpen] = useState(false)
  const [editingScene, setEditingScene] = useState<NovelScene | null>(null)
  const [sceneTitleDraft, setSceneTitleDraft] = useState("")
  const [sceneDescriptionDraft, setSceneDescriptionDraft] = useState("")
  const [sceneBodyDraft, setSceneBodyDraft] = useState("")
  const [sceneHtmlDraft, setSceneHtmlDraft] = useState("<p></p>")
  const [sceneChapterDraft, setSceneChapterDraft] = useState<number | null>(null)
  const [sceneSaving, setSceneSaving] = useState(false)
  const [sceneVersions, setSceneVersions] = useState<SceneVersion[]>([])
  const [sceneVersionDetail, setSceneVersionDetail] = useState<SceneVersionDetail | null>(null)
  const [sceneVersionNameDraft, setSceneVersionNameDraft] = useState("")
  const [restoringSceneVersionId, setRestoringSceneVersionId] = useState<string | null>(null)

  return {
    chapterSearch,
    collapsedSceneGroups,
    draggedScene,
    editingScene,
    restoringSceneVersionId,
    sceneBodyDraft,
    sceneChapterDraft,
    sceneDescriptionDraft,
    sceneDropTarget,
    sceneEditorOpen,
    sceneHtmlDraft,
    sceneOrderSaveState,
    sceneSaving,
    sceneSearch,
    sceneTitleDraft,
    sceneVersionDetail,
    sceneVersionNameDraft,
    sceneVersions,
    setChapterSearch,
    setCollapsedSceneGroups,
    setDraggedScene,
    setEditingScene,
    setRestoringSceneVersionId,
    setSceneBodyDraft,
    setSceneChapterDraft,
    setSceneDescriptionDraft,
    setSceneDropTarget,
    setSceneEditorOpen,
    setSceneHtmlDraft,
    setSceneOrderSaveState,
    setSceneSaving,
    setSceneSearch,
    setSceneTitleDraft,
    setSceneVersionDetail,
    setSceneVersionNameDraft,
    setSceneVersions,
  }
}
