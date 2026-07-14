import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import type { Book } from "@/types/book"
import type {
  Character,
  CharacterIdentityDiagnostics,
  CharacterRepairPreview,
  CharacterReviewResponse,
  RelationshipGraph as RelationshipGraphData,
} from "@/types/character"
import type { ChapterListResponse, ReadingProgress } from "@/types/reader"
import { formatChapterAppearanceText } from "./charactersPage.helpers"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type UseCharacterPageQueriesArgs = {
  book: Book | null
  bookId: string
  isAuthorMode: boolean
  progress: ReadingProgress | null
  relationshipsEnabled: boolean
  reprocessAllowDemote: boolean
  reprocessAllowMerge: boolean
  reviewDataEnabled: boolean
  workspaceMode: WorkspaceMode
}

export function useCharacterPageQueries({
  book,
  bookId,
  isAuthorMode,
  progress,
  relationshipsEnabled,
  reprocessAllowDemote,
  reprocessAllowMerge,
  reviewDataEnabled,
  workspaceMode,
}: UseCharacterPageQueriesArgs) {
  const { data: bookData = null, isLoading: bookLoading } = useBookDetail(bookId)
  const { data: progressData = null } = useQuery<ReadingProgress | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, "progress")),
    queryFn: () => readerApi.getProgress(bookId).catch(() => null),
  })
  const { data: chapterListData = null } = useQuery<ChapterListResponse | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId).catch(() => null),
  })
  const {
    data: charactersData = [],
    refetch: refetchCharacters,
    isLoading: charactersLoading,
  } = useQuery<Character[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters")),
    queryFn: () => booksApi.getCharacters(bookId),
  })

  const emptyReview = useMemo<CharacterReviewResponse>(() => ({
    candidates: [],
    duplicate_suggestions: [],
    relationship_candidates: [],
    shadow_characters: [],
    decision_events: [],
    counts: {
      pending_candidates: 0,
      pending_duplicate_suggestions: 0,
      pending_relationship_candidates: 0,
    },
  }), [])

  const emptyIdentityDiagnostics = useMemo<CharacterIdentityDiagnostics>(() => ({
    suppressed_count: 0,
    auto_merged_count: 0,
    auto_alias_count: 0,
    blocked_duplicate_count: 0,
    hidden_candidate_count: 0,
    suppression_reasons: {},
    recent_identity_actions: [],
  }), [])

  const {
    data: reviewData = emptyReview,
    refetch: refetchCharacterReview,
  } = useQuery<CharacterReviewResponse>({
    queryKey: asQueryKey(bookCacheKey(bookId, "character-review")),
    queryFn: () => booksApi.getCharacterReview(bookId, {
      includeQuarantined: true,
      includePlaces: true,
      includeRejected: false,
    }).catch(() => emptyReview),
    enabled: reviewDataEnabled,
    staleTime: 60_000,
  })

  const chapterTitleByNumber = useMemo(() => {
    const titles = new Map<number, string>()
    for (const chapter of chapterListData?.chapters ?? []) {
      if (chapter.title?.trim()) titles.set(chapter.number, chapter.title.trim())
    }
    return titles
  }, [chapterListData])
  const chapterAppearanceText = (chapter: number | null | undefined) => formatChapterAppearanceText(chapter, chapterTitleByNumber)

  const {
    data: identityDiagnostics = emptyIdentityDiagnostics,
    refetch: refetchIdentityDiagnostics,
  } = useQuery<CharacterIdentityDiagnostics>({
    queryKey: asQueryKey(bookCacheKey(bookId, "character-identity-diagnostics")),
    queryFn: () => booksApi.getCharacterIdentityDiagnostics(bookId).catch(() => emptyIdentityDiagnostics),
    enabled: isAuthorMode && workspaceMode === "repair",
    staleTime: 60_000,
  })

  const emptyRepairPreview = useMemo<CharacterRepairPreview>(() => ({
    book_id: bookId,
    dry_run: true,
    allow_merge_safe_pairs: true,
    allow_demote_obvious_noise: true,
    auto_merged: 0,
    auto_aliases: 0,
    auto_suppressed: 0,
    blocked_suggestions: 0,
    remaining_review_items: 0,
    planned_merges: [],
    planned_aliases: [],
    planned_demotions: [],
    planned_suppressions: [],
    blocked_duplicate_suggestions: [],
    skipped_protected_merge_pairs: [],
    skipped_protected_demotions: [],
    updated_first_chapters: {},
    updated_last_seen_chapters: {},
    character_labels: {},
    pending_duplicate_suggestions: 0,
    pending_relationship_candidates: 0,
    pending_character_candidates_suppressed: 0,
    pending_character_candidates_kept: 0,
    pending_relationship_candidates_suppressed: 0,
    pending_relationship_candidates_kept: 0,
    protected_manual_records_skipped: 0,
    unresolved_relationship_deltas: {},
  }), [bookId])

  const {
    data: repairPreview = emptyRepairPreview,
    refetch: refetchRepairPreview,
    isFetching: repairPreviewFetching,
  } = useQuery<CharacterRepairPreview>({
    queryKey: asQueryKey(bookCacheKey(bookId, `character-review:reprocess:${reprocessAllowMerge}:${reprocessAllowDemote}`)),
    queryFn: () => booksApi.previewCharacterReprocess(bookId, {
      allowMergeSafePairs: reprocessAllowMerge,
      allowDemoteObviousNoise: reprocessAllowDemote,
    }).catch(() => emptyRepairPreview),
    enabled: isAuthorMode && workspaceMode === "repair",
  })

  const relationshipChapter = book?.mode === "author"
    ? Math.max(book?.total_chapters ?? 1, progress?.current_chapter ?? 1)
    : Math.max(progress?.current_chapter ?? 1, 1)
  const relationshipGraphQueryKey = asQueryKey(readerCacheKey(
    bookId,
    `relationships:${relationshipChapter}:${isAuthorMode ? "all" : "active"}`,
  ))
  const {
    data: relationshipGraphData = null,
    refetch: refetchRelationshipGraph,
  } = useQuery<RelationshipGraphData | null>({
    queryKey: relationshipGraphQueryKey,
    queryFn: () => readerApi.getRelationships(bookId, relationshipChapter, {
      includeInactive: isAuthorMode,
      include: "nodes,edges,hidden_nodes",
    }).catch(() => null),
    enabled: Boolean(book && relationshipsEnabled),
    staleTime: 60_000,
  })

  return {
    bookData,
    charactersData,
    charactersLoading,
    chapterAppearanceText,
    identityDiagnostics,
    loading: bookLoading || charactersLoading,
    progressData,
    refetchCharacterReview,
    refetchCharacters,
    refetchIdentityDiagnostics,
    refetchRelationshipGraph,
    refetchRepairPreview,
    relationshipChapter,
    relationshipGraphData,
    repairPreview,
    repairPreviewFetching,
    reviewData,
  }
}
