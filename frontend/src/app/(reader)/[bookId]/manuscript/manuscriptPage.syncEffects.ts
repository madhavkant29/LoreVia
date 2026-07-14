import { useEffect, type Dispatch, type SetStateAction } from "react"

import type {
  BookNote,
  ChapterVersion,
  EmotionalArcOverview,
  ManuscriptAnnotation,
  ManuscriptWorkspaceTree,
  PreWritingCheck,
  WriterWorkspace,
} from "@/types/book"
import type { Character } from "@/types/character"
import type { ManuscriptSynopsis } from "@/types/intelligence"

type RightPane = "context" | "advisor" | "notes" | "arcs" | "insights" | "character"

type UseManuscriptPageSyncEffectsArgs = {
  activeRightPane: RightPane
  annotationsData: ManuscriptAnnotation[]
  annotationsQueryLoading: boolean
  charactersData: Character[]
  chapterVersionsData: ChapterVersion[]
  emotionalArcData: EmotionalArcOverview | null
  notesData: BookNote[]
  notesQueryLoading: boolean
  preWritingCheckData: PreWritingCheck | null
  showRightRail: boolean
  synopsisData: ManuscriptSynopsis | null
  workspaceTreeData: ManuscriptWorkspaceTree | null
  writerWorkspaceData: WriterWorkspace | null
  setAnnotations: Dispatch<SetStateAction<ManuscriptAnnotation[]>>
  setAnnotationsLoading: Dispatch<SetStateAction<boolean>>
  setCharacters: Dispatch<SetStateAction<Character[]>>
  setChapterVersions: Dispatch<SetStateAction<ChapterVersion[]>>
  setCollapsedSceneGroups: Dispatch<SetStateAction<Record<string, boolean>>>
  setEmotionalArc: Dispatch<SetStateAction<EmotionalArcOverview | null>>
  setNotes: Dispatch<SetStateAction<BookNote[]>>
  setNotesLoading: Dispatch<SetStateAction<boolean>>
  setPreWritingCheck: Dispatch<SetStateAction<PreWritingCheck | null>>
  setSynopsis: Dispatch<SetStateAction<ManuscriptSynopsis | null>>
  setWorkspaceTree: Dispatch<SetStateAction<ManuscriptWorkspaceTree | null>>
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
}

export function useManuscriptPageSyncEffects({
  activeRightPane,
  annotationsData,
  annotationsQueryLoading,
  charactersData,
  chapterVersionsData,
  emotionalArcData,
  notesData,
  notesQueryLoading,
  preWritingCheckData,
  showRightRail,
  synopsisData,
  workspaceTreeData,
  writerWorkspaceData,
  setAnnotations,
  setAnnotationsLoading,
  setCharacters,
  setChapterVersions,
  setCollapsedSceneGroups,
  setEmotionalArc,
  setNotes,
  setNotesLoading,
  setPreWritingCheck,
  setSynopsis,
  setWorkspaceTree,
  setWriterWorkspace,
}: UseManuscriptPageSyncEffectsArgs) {
  useEffect(() => {
    setCharacters(charactersData)
  }, [charactersData, setCharacters])

  useEffect(() => {
    setWriterWorkspace(writerWorkspaceData)
  }, [setWriterWorkspace, writerWorkspaceData])

  useEffect(() => {
    setEmotionalArc(emotionalArcData)
  }, [emotionalArcData, setEmotionalArc])

  useEffect(() => {
    setSynopsis(synopsisData)
  }, [setSynopsis, synopsisData])

  useEffect(() => {
    setWorkspaceTree(workspaceTreeData)
    if (!workspaceTreeData) return
    setCollapsedSceneGroups((current) => {
      const next = { ...current }
      for (const group of workspaceTreeData.scene_groups) {
        if (!(group.id in next)) next[group.id] = !!group.collapsed_by_default
      }
      return next
    })
  }, [setCollapsedSceneGroups, setWorkspaceTree, workspaceTreeData])

  useEffect(() => {
    setAnnotations(annotationsData)
    setAnnotationsLoading(annotationsQueryLoading)
  }, [annotationsData, annotationsQueryLoading, setAnnotations, setAnnotationsLoading])

  useEffect(() => {
    if (!showRightRail || activeRightPane !== "notes") return
    setNotes(notesData)
    setNotesLoading(notesQueryLoading)
  }, [activeRightPane, notesData, notesQueryLoading, setNotes, setNotesLoading, showRightRail])

  useEffect(() => {
    setPreWritingCheck(preWritingCheckData)
  }, [preWritingCheckData, setPreWritingCheck])

  useEffect(() => {
    setChapterVersions(chapterVersionsData)
  }, [chapterVersionsData, setChapterVersions])
}
