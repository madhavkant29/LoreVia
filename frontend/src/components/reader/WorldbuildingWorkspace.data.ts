import { useQuery, useQueryClient } from "@tanstack/react-query"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { asQueryKey, booksStatsCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import type { UserStats } from "@/types/book"
import type {
  CanonOverride,
  WikiEntry,
  WorldBuildingBootstrapPayload,
  WorldBuildingDocument,
  WorldBuildingDocumentDetail,
  WorldElement,
  WorldGapResult,
  WorldNote,
} from "@/types/world-building"

export type WorkspaceFocus = "editor" | "gap"

export function useWorldbuildingWorkspaceData(bookId: string, focus: WorkspaceFocus, selectedDocumentId: string | null) {
  const queryClient = useQueryClient()

  const bootstrapQuery = useQuery<WorldBuildingBootstrapPayload>({
    queryKey: [`worldbuilding:${bookId}:bootstrap:${focus}`],
    queryFn: async () => {
      const payload = await worldBuildingApi.getBootstrap(bookId, { focus })
      queryClient.setQueryData([`worldbuilding:${bookId}:documents`], payload.documents)
      queryClient.setQueryData([`worldbuilding:${bookId}:notes`], payload.notes)
      queryClient.setQueryData([`worldbuilding:${bookId}:canon-overrides`], payload.canon_overrides)
      queryClient.setQueryData([`worldbuilding:${bookId}:elements`], payload.elements)
      queryClient.setQueryData([`worldbuilding:${bookId}:wiki`], payload.wiki)
      if (payload.stats) queryClient.setQueryData(asQueryKey(booksStatsCacheKey()), payload.stats)
      if (payload.gap_analysis) queryClient.setQueryData([`worldbuilding:${bookId}:analysis:${focus}`], payload.gap_analysis)
      return payload
    },
    staleTime: 30_000,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const documentsQuery = useQuery<WorldBuildingDocument[]>({
    queryKey: [`worldbuilding:${bookId}:documents`],
    queryFn: () => worldBuildingApi.listDocuments(bookId),
    enabled: false,
    retry: false,
  })

  const selectedDocumentQuery = useQuery<WorldBuildingDocumentDetail | null>({
    queryKey: selectedDocumentId ? [`worldbuilding:${bookId}:document:${selectedDocumentId}`] : [`worldbuilding:${bookId}:document:none`],
    queryFn: async () => {
      if (!selectedDocumentId) return null
      return worldBuildingApi.getDocument(bookId, selectedDocumentId)
    },
    enabled: Boolean(selectedDocumentId),
    retry: false,
    refetchOnWindowFocus: false,
  })

  const notesQuery = useQuery<WorldNote[]>({
    queryKey: [`worldbuilding:${bookId}:notes`],
    queryFn: () => worldBuildingApi.listNotes(bookId),
    enabled: false,
    retry: false,
  })

  const canonOverridesQuery = useQuery<CanonOverride[]>({
    queryKey: [`worldbuilding:${bookId}:canon-overrides`],
    queryFn: () => worldBuildingApi.listCanonOverrides(bookId),
    enabled: false,
    retry: false,
  })

  const elementsQuery = useQuery<WorldElement[]>({
    queryKey: [`worldbuilding:${bookId}:elements`],
    queryFn: () => worldBuildingApi.listElements(bookId),
    enabled: false,
    retry: false,
  })

  const wikiQuery = useQuery<WikiEntry[]>({
    queryKey: [`worldbuilding:${bookId}:wiki`],
    queryFn: () => worldBuildingApi.listWiki(bookId),
    enabled: false,
    retry: false,
  })

  const uploadStatsQuery = useQuery<UserStats | null>({
    queryKey: asQueryKey(booksStatsCacheKey()),
    queryFn: () => booksApi.getStats(),
    enabled: bootstrapQuery.isSuccess && !bootstrapQuery.data?.stats,
  })

  const analysisQuery = useQuery<WorldGapResult | null>({
    queryKey: [`worldbuilding:${bookId}:analysis:${focus}`],
    queryFn: () => worldBuildingApi.getGaps(bookId),
    enabled: false,
    retry: false,
  })

  const loadingBootstrap = bootstrapQuery.isLoading
  const chaptersQuery = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "chapters")), queryFn: () => readerApi.getChapterList(bookId), enabled: bootstrapQuery.isSuccess, retry: false })

  return {
    availableChapters: chaptersQuery.data?.chapters.map((chapter) => chapter.number) ?? [],
    bootstrapLoading: loadingBootstrap,
    bootstrapReady: !!bootstrapQuery.data,
    bootstrapError: bootstrapQuery.isError,
    refetchBootstrap: bootstrapQuery.refetch,
    documentError: selectedDocumentQuery.isError,
    refreshErrors: [
      { label: "canon sources", query: documentsQuery }, { label: "cleanup notes", query: notesQuery }, { label: "canon aliases", query: canonOverridesQuery },
      { label: "lore facts", query: elementsQuery }, { label: "wiki entries", query: wikiQuery }, { label: "upload allowances", query: uploadStatsQuery }, { label: "comparison", query: analysisQuery }, { label: "manuscript chapters", query: chaptersQuery },
    ].flatMap(({ label, query: result }) => {

      return result.isError ? [{ label: String(label), retry: result.refetch, busy: result.isFetching }] : []
    }),
    analysisLoading: loadingBootstrap && focus === "gap" ? true : analysisQuery.isLoading,
    canonOverrides: canonOverridesQuery.data ?? [],
    documents: documentsQuery.data ?? [],
    documentsLoading: loadingBootstrap || documentsQuery.isLoading,
    elementsLoading: loadingBootstrap || elementsQuery.isLoading,
    extractedElements: elementsQuery.data ?? [],
    initialAnalysis: analysisQuery.data ?? null,
    loadingAnalysis: analysisQuery.isFetching,
    loadingDocumentBody: selectedDocumentQuery.isLoading,
    notes: notesQuery.data ?? [],
    notesLoading: loadingBootstrap || notesQuery.isLoading,
    refetchAnalysis: analysisQuery.refetch,
    refetchCanonOverrides: canonOverridesQuery.refetch,
    refetchDocuments: documentsQuery.refetch,
    refetchElements: elementsQuery.refetch,
    refetchNotes: notesQuery.refetch,
    refetchSelectedDocument: selectedDocumentQuery.refetch,
    refetchUploadStats: uploadStatsQuery.refetch,
    refetchWiki: wikiQuery.refetch,
    selectedDocumentData: selectedDocumentQuery.data ?? null,
    uploadStats: uploadStatsQuery.data ?? null,
    wikiEntries: wikiQuery.data ?? [],
    wikiEntriesLoading: loadingBootstrap || wikiQuery.isLoading,
  }
}
