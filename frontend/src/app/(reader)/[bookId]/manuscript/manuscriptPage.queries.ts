import { useQuery } from "@tanstack/react-query"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { bookCacheKey } from "@/lib/query/cacheKeys"
import type {
  BookNote,
  ChapterVersion,
  EmotionalArcOverview,
  ManuscriptAnnotation,
  ManuscriptWorkspaceTree,
  PreWritingCheck,
  VaultNote,
  WriterWorkspace,
} from "@/types/book"
import type { Character } from "@/types/character"
import type { ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread, TimelineResponse } from "@/types/reader"
import {
  EMPTY_ANNOTATIONS,
  EMPTY_CHARACTERS,
  EMPTY_CHAPTER_VERSIONS,
  EMPTY_NOTES,
  type WorkspaceTab,
} from "./manuscriptPage.constants"

type RightPane = "context" | "advisor" | "notes" | "arcs" | "insights" | "character"

type UseManuscriptPageQueriesArgs = {
  activeRightPane: RightPane
  annotationChapterNumber: number | null
  activeChapterNumber: number
  bookId: string
  loading: boolean
  selectedChapter: number | null
  showLeftRail: boolean
  showRightRail: boolean
  workspaceTab: WorkspaceTab
}

export function useManuscriptPageQueries({
  activeRightPane,
  activeChapterNumber,
  annotationChapterNumber,
  bookId,
  loading,
  selectedChapter,
  showLeftRail,
  showRightRail,
  workspaceTab,
}: UseManuscriptPageQueriesArgs) {
  const { data: charactersData = EMPTY_CHARACTERS } = useQuery<Character[]>({
    queryKey: [`manuscript:${bookId}:characters`],
    queryFn: () => booksApi.getCharacters(bookId),
    enabled: false,
    staleTime: 60_000,
  })
  const { data: writerWorkspaceData = null, refetch: refetchWriterWorkspace } = useQuery<WriterWorkspace | null>({
    queryKey: [bookCacheKey(bookId, "writer-workspace")],
    queryFn: () => booksApi.getWriterWorkspace(bookId),
    enabled: false,
    staleTime: 60_000,
  })
  const { data: emotionalArcData = null, refetch: refetchEmotionalArc } = useQuery<EmotionalArcOverview | null>({
    queryKey: [bookCacheKey(bookId, "emotional-arc")],
    queryFn: () => booksApi.getEmotionalArc(bookId),
    enabled: workspaceTab === "plan" || activeRightPane === "arcs" || activeRightPane === "insights",
    staleTime: 60_000,
  })
  const { data: synopsisData = null, refetch: refetchSynopsis } = useQuery<ManuscriptSynopsis | null>({
    queryKey: [`manuscript:${bookId}:synopsis:minimal`],
    queryFn: () => intelligenceApi.synopsis(bookId, "minimal"),
    enabled: activeRightPane === "insights",
    staleTime: 60_000,
  })
  const { data: workspaceTreeData = null, refetch: refetchWorkspaceTree } = useQuery<ManuscriptWorkspaceTree | null>({
    queryKey: [bookCacheKey(bookId, "workspace-tree")],
    queryFn: () => booksApi.getWorkspaceTree(bookId),
    enabled: false,
    staleTime: 60_000,
  })
  const {
    data: annotationsData = EMPTY_ANNOTATIONS,
    isFetching: annotationsQueryLoading,
  } = useQuery<ManuscriptAnnotation[]>({
    queryKey: [`manuscript:${bookId}:annotations:${annotationChapterNumber ?? "none"}`],
    queryFn: () => annotationChapterNumber === null ? Promise.resolve(EMPTY_ANNOTATIONS) : booksApi.getManuscriptAnnotations(bookId, annotationChapterNumber),
    enabled: annotationChapterNumber !== null && (workspaceTab === "write" || activeRightPane === "notes"),
    staleTime: 30_000,
  })
  const {
    data: notesData = EMPTY_NOTES,
    isFetching: notesQueryLoading,
    refetch: refetchNotes,
  } = useQuery<BookNote[]>({
    queryKey: [`manuscript:${bookId}:notes`],
    queryFn: () => booksApi.getBookNotes(bookId),
    enabled: showRightRail && activeRightPane === "notes",
    staleTime: 30_000,
  })
  const { data: vaultNotesData = [], refetch: refetchVaultNotes } = useQuery<VaultNote[]>({
    queryKey: [bookCacheKey(bookId, "vault-notes")],
    queryFn: () => booksApi.listVaultNotes(bookId),
    enabled: showRightRail && activeRightPane === "notes",
    staleTime: 30_000,
  })
  const { data: chapterVersionsData = EMPTY_CHAPTER_VERSIONS } = useQuery<ChapterVersion[]>({
    queryKey: selectedChapter !== null ? [`manuscript:${bookId}:chapter-versions:${selectedChapter}`] : [`manuscript:${bookId}:chapter-versions:none`],
    queryFn: async () => {
      if (selectedChapter === null) return []
      return booksApi.getChapterVersions(bookId, selectedChapter)
    },
    enabled: showLeftRail && selectedChapter !== null,
  })
  const { data: preWritingCheckData = null } = useQuery<PreWritingCheck | null>({
    queryKey: [`manuscript:${bookId}:prewriting:${activeChapterNumber}`],
    queryFn: () => booksApi.getPreWritingCheck(bookId, activeChapterNumber),
    enabled: !loading && activeChapterNumber > 0 && (workspaceTab !== "write" || (showRightRail && activeRightPane === "context")),
    staleTime: 30_000,
  })
  const { data: rightRailPlotThreads = [] } = useQuery<PlotThread[]>({
    queryKey: [`manuscript:${bookId}:right-rail:plot-threads:${activeChapterNumber}`],
    queryFn: () => readerApi.getPlotThreads(bookId, activeChapterNumber),
    enabled: !loading && workspaceTab === "write" && showRightRail && activeRightPane === "context" && activeChapterNumber > 0,
    staleTime: 30_000,
  })
  const { data: rightRailTimelineData = null } = useQuery<TimelineResponse | null>({
    queryKey: [`manuscript:${bookId}:right-rail:timeline`],
    queryFn: () => readerApi.getTimeline(bookId, { limit: 25, include: "events" }),
    enabled: !loading && workspaceTab === "write" && showRightRail && activeRightPane === "context",
    staleTime: 30_000,
  })

  return {
    annotationsData,
    annotationsQueryLoading,
    chapterVersionsData,
    charactersData,
    emotionalArcData,
    notesData,
    notesQueryLoading,
    preWritingCheckData,
    refetchEmotionalArc,
    refetchNotes,
    refetchSynopsis,
    refetchVaultNotes,
    refetchWorkspaceTree,
    refetchWriterWorkspace,
    rightRailPlotThreads,
    rightRailTimelineData,
    synopsisData,
    vaultNotesData,
    workspaceTreeData,
    writerWorkspaceData,
  }
}
