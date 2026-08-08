import axios from "axios"
import { apiClient } from "./client"
import {
  bookCacheKey,
  booksNotesCacheKey,
  booksSeriesCacheKey,
  booksStatsCacheKey,
  readerCacheKey,
} from "@/lib/query/cacheKeys"
import { invalidateQueryKeys } from "@/lib/query/queryClient"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type { Book, BookCollaborator, BookEvents, BookNote, BookOverviewPayload, BookProcessing, BookSeries, BookWorkType, CanonFact, ChapterConsistencyReport, ChapterSceneOrder, ChapterVersion, ChapterVersionDetail, CollaboratorActivity, CollaborationPermissions, CollaborationRole, CollaborationScope, ContinuityFinding, ContinuityScan, EmotionalArcOverview, ImportPreview, ManuscriptAnnotation, ManuscriptBootstrapPayload, ManuscriptWorkspaceTree, NovelEpubMetadata, NovelExportPreset, NovelFrontMatter, NovelImagePlacement, NovelScene, ReaderBootstrapPayload, VaultGraph, VaultNoteRelations, VaultPreview, VaultNote, VaultNoteSaveResult, PaginatedSeries, PreWritingCheck, ReadabilityMetrics, RevisionIntelligence, RevisionTagSet, RevisionTagTarget, SavedQuote, SceneMetadata, SceneVersion, SceneVersionDetail, SeriesBible, StoryHealth, UserStats, WorkspaceSearchFilters, WorkspaceSearchResult, WriterWorkspace } from "@/types/book"
import type {
  Character,
  CharacterAliasRecord,
  CharacterIdentityDiagnostics,
  CharacterRepairApplyResult,
  CharacterRepairPreview,
  CharacterReviewResponse,
  CharacterShareResponse,
  RelationshipGraph,
} from "@/types/character"
import type { BetaReadAssignment, BetaReadAssignmentCreateInput, BetaReadAssignmentListResponse } from "@/types/reader"
import type { BookVisibilitySummary } from "@/types/uiPreferences"

export interface ManuscriptImportResponse {
  book_id: string
  imported_chapters: number[]
  chapter_content_versions: Record<number, number>
  total_chapters: number
  mode: "reader" | "author"
  source_kind: string
  chapter_reports: ChapterConsistencyReport[]
}

type BootstrapProfile = "critical" | "full"

function invalidateBookCache(bookId: string) {
  void invalidateQueryKeys(`book:${normalizeBookRouteId(bookId)}:`)
  void invalidateQueryKeys("books:list:")
  void invalidateQueryKeys(booksStatsCacheKey())
  void invalidateQueryKeys(booksSeriesCacheKey())
}

function invalidateReaderCache(bookId: string) {
  void invalidateQueryKeys(readerCacheKey(bookId, ""))
}

function bookPath(bookId: string, suffix = "") {
  return `/books/${normalizeBookRouteId(bookId)}${suffix}`
}

export const booksApi = {
  list: (includeHidden = false) =>
    apiClient.get<Book[]>("/books", { params: { include_hidden: includeHidden } }).then(r => r.data),
  getStats: () => apiClient.get<UserStats>("/books/stats").then(r => r.data),
  listQuotes: () => apiClient.get<SavedQuote[]>("/books/quotes").then(r => r.data),
  listNotes: () => apiClient.get<BookNote[]>("/books/notes").then(r => r.data),
  get: (id: string) => apiClient.get<Book>(bookPath(id)).then(r => r.data),
  getVisibilitySummary: (id: string) =>
    apiClient.get<BookVisibilitySummary>(bookPath(id, "/visibility-summary")).then(r => r.data),
  getOverview: (id: string) => apiClient.get<BookOverviewPayload>(bookPath(id, "/overview")).then(r => r.data),
  retryProcessing: (id: string) => apiClient.post<BookProcessing>(bookPath(id, "/processing/retry")).then(r => {
    invalidateBookCache(id)
    invalidateReaderCache(id)
    return r.data
  }),
  continueProcessing: (id: string) => apiClient.post<BookProcessing>(bookPath(id, "/processing/continue")).then(r => {
    invalidateBookCache(id)
    invalidateReaderCache(id)
    return r.data
  }),
  getReaderBootstrap: (id: string, options?: { profile?: BootstrapProfile }) => {
    const path = bookPath(id, "/reader-bootstrap")
    return options?.profile
      ? apiClient.get<ReaderBootstrapPayload>(path, { params: { profile: options.profile } }).then(r => r.data)
      : apiClient.get<ReaderBootstrapPayload>(path).then(r => r.data)
  },
  getManuscriptBootstrap: (
    id: string,
    params?: { activeChapterNumber?: number | null; annotationChapterNumber?: number | null; profile?: BootstrapProfile }
  ) => apiClient.get<ManuscriptBootstrapPayload>(bookPath(id, "/manuscript-bootstrap"), {
    params: {
      ...(typeof params?.activeChapterNumber === "number" ? { active_chapter_number: params.activeChapterNumber } : {}),
      ...(typeof params?.annotationChapterNumber === "number" ? { annotation_chapter_number: params.annotationChapterNumber } : {}),
      ...(params?.profile ? { profile: params.profile } : {}),
    },
  }).then(r => r.data),
  listCollaborators: (id: string) =>
    apiClient.get<BookCollaborator[]>(bookPath(id, "/collaborators")).then(r => r.data),
  getCollaboratorActivity: (id: string, collaborationId: string) =>
    apiClient.get<CollaboratorActivity>(bookPath(id, `/collaborators/${collaborationId}/activity`)).then(r => r.data),
  createCollaborator: (
    id: string,
    payload: { email: string; displayName?: string | null; role: CollaborationRole; scope: CollaborationScope; permissions?: CollaborationPermissions | null }
  ) => apiClient.post<BookCollaborator>(bookPath(id, "/collaborators"), {
    email: payload.email,
    display_name: payload.displayName,
    role: payload.role,
    scope: payload.scope,
    permissions: payload.permissions,
  }).then(r => {
    invalidateBookCache(id)
    return r.data
  }),
  updateCollaborator: (
    id: string,
    collaborationId: string,
    payload: { displayName?: string | null; role?: CollaborationRole; scope?: CollaborationScope; permissions?: CollaborationPermissions | null; inviteStatus?: "active" | "revoked" }
  ) => apiClient.put<BookCollaborator>(bookPath(id, `/collaborators/${collaborationId}`), {
    display_name: payload.displayName,
    role: payload.role,
    scope: payload.scope,
    permissions: payload.permissions,
    invite_status: payload.inviteStatus,
  }).then(r => {
    invalidateBookCache(id)
    return r.data
  }),
  deleteCollaborator: (id: string, collaborationId: string) =>
    apiClient.delete(bookPath(id, `/collaborators/${collaborationId}`)).then(() => {
      invalidateBookCache(id)
    }),
  listBetaReadAssignments: (id: string) =>
    apiClient.get<BetaReadAssignmentListResponse>(bookPath(id, "/beta-reads")).then(r => r.data.items),
  createBetaReadAssignment: (id: string, payload: BetaReadAssignmentCreateInput) =>
    apiClient.post<BetaReadAssignment>(bookPath(id, "/beta-reads"), {
      reader_email: payload.readerEmail,
      task_label: payload.taskLabel,
      scope_kind: payload.scopeKind ?? "full_book",
      section_label: payload.sectionLabel,
      chapter_start: payload.chapterStart,
      chapter_end: payload.chapterEnd,
      window_days: payload.windowDays,
      required_progress_pct: payload.requiredProgressPct ?? 100,
      required_comment_count: payload.requiredCommentCount ?? 0,
      required_feedback_item_count: payload.requiredFeedbackItemCount ?? 1,
      require_final_feedback: payload.requireFinalFeedback ?? true,
      starts_at: payload.startsAt,
      author_questions: payload.authorQuestions ?? [],
    }).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  revokeBetaReadAssignment: (id: string, assignmentId: string) =>
    apiClient.post<BetaReadAssignment>(bookPath(id, `/beta-reads/${assignmentId}/revoke`)).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  getBookNotes: (id: string) =>
    apiClient.get<BookNote[]>(bookPath(id, "/notes")).then(r => r.data),
  updateRevisionTags: (
    id: string,
    payload: { entityType: RevisionTagTarget; entityId?: string | null; chapterNumber?: number | null; tags: string[] }
  ) => apiClient.put<RevisionTagSet>(bookPath(id, "/revision-tags"), {
    entity_type: payload.entityType,
    entity_id: payload.entityId ?? null,
    chapter_number: payload.chapterNumber ?? null,
    tags: payload.tags,
  }).then(r => {
    invalidateBookCache(id)
    invalidateReaderCache(id)
    return r.data
  }),
  getManuscriptAnnotations: (id: string, chapterNumber?: number) =>
    apiClient.get<ManuscriptAnnotation[]>(bookPath(id, "/annotations"), {
      params: typeof chapterNumber === "number" ? { chapter_number: chapterNumber } : undefined,
    }).then(r => r.data),
  getChapterReports: (id: string, limit = 12) =>
    apiClient.get<ChapterConsistencyReport[]>(bookPath(id, "/chapter-reports"), { params: { limit } }).then(r => r.data),
  getPreWritingCheck: (id: string, upcomingChapter?: number) =>
    apiClient.get<PreWritingCheck>(bookPath(id, "/pre-writing-check"), { params: typeof upcomingChapter === "number" ? { upcoming_chapter: upcomingChapter } : undefined }).then(r => r.data),
  getStoryHealth: (id: string) =>
    apiClient.get<StoryHealth>(bookPath(id, "/story-health")).then(r => r.data),
  getRevisionIntelligence: (id: string) =>
    apiClient.get<RevisionIntelligence>(bookPath(id, "/revision-intelligence")).then(r => r.data),
  createContinuityScan: (
    id: string,
    payload: { scope?: "full_book" | "targeted"; chapterNumbers?: number[] } = {},
  ) => apiClient.post<ContinuityScan>(bookPath(id, "/continuity-scans"), {
    scope: payload.scope ?? "full_book",
    chapter_numbers: payload.chapterNumbers ?? [],
  }).then(r => {
    void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
    return r.data
  }),
  getContinuityScan: (id: string, scanId: string) =>
    apiClient.get<ContinuityScan>(bookPath(id, `/continuity-scans/${scanId}`)).then(r => r.data),
  getContinuityFindings: (
    id: string,
    params?: { status?: string; category?: string; includeStale?: boolean },
  ) => apiClient.get<ContinuityFinding[]>(bookPath(id, "/continuity-findings"), {
    params: {
      status: params?.status,
      category: params?.category,
      include_stale: params?.includeStale ?? true,
    },
  }).then(r => r.data),
  decideContinuityFinding: (
    id: string,
    findingId: string,
    payload: {
      decision: "accepted" | "dismissed" | "intentional" | "resolved"
      action?: "added_to_revision_plan" | "saved_note" | "manuscript_edit" | "exported_report" | null
      reason?: "intentional" | "incorrect" | "not_relevant" | "fixed" | "other" | null
    },
  ) => apiClient.patch<ContinuityFinding>(
    bookPath(id, `/continuity-findings/${findingId}`),
    payload,
  ).then(r => {
    void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
    return r.data
  }),
  recheckContinuityFinding: (id: string, findingId: string) =>
    apiClient.post<ContinuityScan>(
      bookPath(id, `/continuity-findings/${findingId}/recheck`),
    ).then(r => {
      void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
      return r.data
    }),
  getCanonFacts: (id: string) =>
    apiClient.get<CanonFact[]>(bookPath(id, "/canon/facts")).then(r => r.data),
  decideRevisionFinding: (
    id: string,
    findingId: string,
    payload: {
      decision: "accepted" | "dismissed" | "resolved"
      action?: "added_to_revision_plan" | "saved_note" | "manuscript_edit" | "exported_report" | null
      reason?: "intentional" | "incorrect" | "not_relevant" | "other" | null
    },
  ) => apiClient
    .post<RevisionIntelligence>(bookPath(id, `/revision-findings/${findingId}/decision`), payload)
    .then(r => {
      void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
      void invalidateQueryKeys(bookCacheKey(id, "writer-workspace"))
      return r.data
    }),
  getChapterVersions: (id: string, chapterNumber: number, limit = 12) =>
    apiClient.get<ChapterVersion[]>(bookPath(id, "/chapter-versions"), { params: { chapter_number: chapterNumber, limit } }).then(r => r.data),
  createChapterSnapshot: (id: string, chapterNumber: number, note?: string) =>
    apiClient.post<ChapterVersion>(bookPath(id, `/chapters/${chapterNumber}/snapshot`), null, { params: note ? { note } : undefined }).then(r => {
      void invalidateQueryKeys(bookCacheKey(id, `chapter-versions:${chapterNumber}:`))
      return r.data
    }),
  getChapterVersionDetail: (id: string, versionId: string) =>
    apiClient.get<ChapterVersionDetail>(bookPath(id, `/chapter-versions/${versionId}`)).then(r => r.data),
  restoreChapterVersion: (id: string, versionId: string) =>
    apiClient.post<{
      chapter_number: number
      title: string | null
      text: string
      html: string | null
      versions: ChapterVersion[]
      scenes: NovelScene[]
    }>(bookPath(id, `/chapter-versions/${versionId}/restore`)).then(r => {
      invalidateBookCache(id)
      invalidateReaderCache(id)
      return r.data
    }),
  getRestoreStatus: (id: string, versionId: string) =>
    apiClient.get<import("@/types/book").ChapterVersionRestoreStatus>(bookPath(id, `/chapter-versions/${versionId}/restore-status`)).then(r => r.data),
  getSceneVersions: (id: string, sceneId: string, limit = 12) =>
    apiClient.get<SceneVersion[]>(bookPath(id, `/scenes/${sceneId}/versions`), { params: { limit } }).then(r => r.data),
  createSceneSnapshot: (id: string, sceneId: string, note?: string) =>
    apiClient.post<SceneVersion>(bookPath(id, `/scenes/${sceneId}/snapshot`), null, { params: note ? { note } : undefined }).then(r => r.data),
  getSceneVersionDetail: (id: string, versionId: string) =>
    apiClient.get<SceneVersionDetail>(bookPath(id, `/scene-versions/${versionId}`)).then(r => r.data),
  restoreSceneVersion: (id: string, versionId: string) =>
    apiClient.post<{ scene: NovelScene; versions: SceneVersion[] }>(bookPath(id, `/scene-versions/${versionId}/restore`)).then(r => {
      void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
      void invalidateQueryKeys(bookCacheKey(id, "scenes:"))
      void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
      void invalidateQueryKeys(readerCacheKey(id, ""))
      return r.data
    }),
  getWorkspaceTree: (id: string) =>
    apiClient.get<ManuscriptWorkspaceTree>(bookPath(id, "/workspace/tree")).then(r => r.data),
  searchWorkspace: (
    id: string,
    payload: {
      query: string
      scopes?: Array<"manuscript" | "scenes" | "notes">
      caseSensitive?: boolean
      wholeWord?: boolean
      regex?: boolean
      filters?: WorkspaceSearchFilters
    }
  ) => apiClient.post<WorkspaceSearchResult[]>(bookPath(id, "/workspace/search"), {
    query: payload.query,
    scopes: payload.scopes ?? ["manuscript", "scenes", "notes"],
    case_sensitive: payload.caseSensitive ?? false,
    whole_word: payload.wholeWord ?? false,
    regex: payload.regex ?? false,
    filters: payload.filters ?? {},
  }).then(r => r.data),
  listScenes: (id: string, params?: { chapterNumber?: number; status?: string; query?: string }) =>
    apiClient.get<NovelScene[]>(bookPath(id, "/scenes"), {
      params: {
        chapter_number: params?.chapterNumber,
        status: params?.status,
        query: params?.query,
      },
    }).then(r => r.data),
  saveScene: (
    id: string,
    payload: {
      id?: string
      title: string
      description?: string | null
      body: string
      html_body?: string | null
      metadata?: SceneMetadata | null
      path?: string | null
      chapter_number?: number | null
      status?: string | null
      sort_order?: number | null
    }
  ) => {
    const request = payload.id
      ? apiClient.put<NovelScene>(bookPath(id, `/scenes/${payload.id}`), payload)
      : apiClient.post<NovelScene>(bookPath(id, "/scenes"), payload)
    return request.then(r => {
      void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
      void invalidateQueryKeys(bookCacheKey(id, "scenes:"))
      void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
      void invalidateQueryKeys(readerCacheKey(id, ""))
      return r.data
    })
  },
  deleteScene: (id: string, sceneId: string) =>
    apiClient.delete(bookPath(id, `/scenes/${sceneId}`)).then(() => {
      void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
      void invalidateQueryKeys(bookCacheKey(id, "scenes:"))
      void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
      void invalidateQueryKeys(readerCacheKey(id, ""))
    }),
  deleteChapter: (id: string, chapterNumber: number) =>
    apiClient.delete(bookPath(id, `/chapters/${chapterNumber}`)).then(() => {
      invalidateBookCache(id)
      invalidateReaderCache(id)
      void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
      void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
      void invalidateQueryKeys(bookCacheKey(id, `chapter-versions:${chapterNumber}:`))
    }),
  reorderChapterScenes: (
    id: string,
    chapterNumber: number,
    payload: { sceneIds: string[]; expectedStructureVersion: number }
  ) => apiClient.patch<ChapterSceneOrder>(bookPath(id, `/chapters/${chapterNumber}/scenes/order`), {
    scene_ids: payload.sceneIds,
    expected_structure_version: payload.expectedStructureVersion,
  }).then(r => {
    void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
    void invalidateQueryKeys(bookCacheKey(id, "scenes:"))
    void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
    void invalidateQueryKeys(readerCacheKey(id, ""))
    return r.data
  }),
  getSceneInsertion: (id: string, sceneId: string, chapterNumber: number, position: "start" | "end" = "end", includeMetadata = true) =>
    apiClient.post<{
      chapter_number: number
      position: "start" | "end"
      title: string
      body: string
      html_body?: string | null
      scene_id: string
      include_metadata: boolean
    }>(bookPath(id, `/scenes/${sceneId}/insert`), null, { params: { chapter_number: chapterNumber, position, include_metadata: includeMetadata } }).then(r => r.data),
  getWriterWorkspace: (id: string) =>
    apiClient.get<WriterWorkspace>(bookPath(id, "/writer-workspace")).then(r => r.data),
  updateWriterWorkspace: (
    id: string,
    payload: Partial<WriterWorkspace>
  ) => apiClient.put<WriterWorkspace>(bookPath(id, "/writer-workspace"), payload).then(r => {
    void invalidateQueryKeys(bookCacheKey(id, "writer-workspace"))
    void invalidateQueryKeys(bookCacheKey(id, "revision-intelligence"))
    return r.data
  }),
  getEmotionalArc: (id: string) =>
    apiClient.get<EmotionalArcOverview>(bookPath(id, "/emotional-arc")).then(r => r.data),
  getReadability: (id: string, text: string) =>
    apiClient.post<ReadabilityMetrics>(bookPath(id, "/manuscript/readability"), { text }).then(r => r.data),
  getEvents: (id: string) =>
    apiClient.get<BookEvents>(bookPath(id, "/events")).then(r => r.data),
  getReaderEvents: (id: string, chapter?: number) =>
    apiClient.get<BookEvents>(bookPath(id, "/events/reader"), { params: typeof chapter === "number" ? { chapter } : undefined }).then(r => r.data),
  getCharacters: (id: string) =>
    apiClient.get<Character[]>(bookPath(id, "/characters")).then(r => r.data),
  getCharacterReview: (
    id: string,
    options?: { includeQuarantined?: boolean; includePlaces?: boolean; includeRejected?: boolean },
  ) =>
    apiClient.get<CharacterReviewResponse>(bookPath(id, "/character-review"), {
      params: {
        include_quarantined: options?.includeQuarantined,
        include_places: options?.includePlaces,
        include_rejected: options?.includeRejected,
      },
    }).then(r => r.data),
  getCharacterIdentityDiagnostics: (id: string) =>
    apiClient.get<CharacterIdentityDiagnostics>(bookPath(id, "/characters/identity-diagnostics")).then(r => r.data),
  createCharacter: (
    bookId: string,
    payload: {
      name: string
      firstChapter?: number
      aliases?: string[]
      role?: "mc" | "sc" | "background" | null
      description?: string | null
      goal?: string | null
      lieTheyBelieve?: string | null
      backstoryWound?: string | null
      arcType?: string | null
      arcSummary?: string | null
      personalityTags?: string[]
      motivations?: string[]
      fears?: string[]
    }
  ) => apiClient.post<Character>(bookPath(bookId, "/characters"), {
    name: payload.name,
    first_chapter: payload.firstChapter ?? 1,
    aliases: payload.aliases,
    role: payload.role,
    description: payload.description,
    goal: payload.goal,
    lie_they_believe: payload.lieTheyBelieve,
    backstory_wound: payload.backstoryWound,
    arc_type: payload.arcType,
    arc_summary: payload.arcSummary,
    personality_tags: payload.personalityTags,
    motivations: payload.motivations,
    fears: payload.fears,
  }).then(r => {
    invalidateBookCache(bookId)
    return r.data
  }),
  updateCharacter: (
    bookId: string,
    characterId: string,
    payload: {
      name?: string
      aliases?: string[]
      role?: "mc" | "sc" | "background" | null
      description?: string | null
      goal?: string | null
      lieTheyBelieve?: string | null
      backstoryWound?: string | null
      arcType?: string | null
      arcSummary?: string | null
      personalityTags?: string[]
      motivations?: string[]
      fears?: string[]
      graphVisibility?: "include" | "exclude" | null
      protectedFromRepair?: boolean | null
      reviewNote?: string | null
    }
  ) => apiClient.put<Character>(bookPath(bookId, `/characters/${characterId}`), {
    name: payload.name,
    aliases: payload.aliases,
    role: payload.role,
    description: payload.description,
    goal: payload.goal,
    lie_they_believe: payload.lieTheyBelieve,
    backstory_wound: payload.backstoryWound,
    arc_type: payload.arcType,
    arc_summary: payload.arcSummary,
    personality_tags: payload.personalityTags,
    motivations: payload.motivations,
    fears: payload.fears,
    graph_visibility: payload.graphVisibility,
    protected_from_repair: payload.protectedFromRepair,
    review_note: payload.reviewNote,
  }).then(r => {
    invalidateBookCache(bookId)
    invalidateReaderCache(bookId)
    return r.data
  }),
  listCharacterAliases: (bookId: string, characterId: string) =>
    apiClient.get<CharacterAliasRecord[]>(bookPath(bookId, `/characters/${characterId}/aliases`)).then(r => r.data),
  addCharacterAlias: (
    bookId: string,
    characterId: string,
    payload: { aliasText: string; aliasKind?: string; confidence?: number },
  ) => apiClient.post<CharacterAliasRecord>(bookPath(bookId, `/characters/${characterId}/aliases`), {
    alias_text: payload.aliasText,
    alias_kind: payload.aliasKind ?? "user_confirmed",
    confidence: payload.confidence ?? 1,
  }).then(r => {
    invalidateBookCache(bookId)
    invalidateReaderCache(bookId)
    return r.data
  }),
  deleteCharacterAlias: (bookId: string, characterId: string, aliasId: string) =>
    apiClient.delete<{ deleted: string }>(bookPath(bookId, `/characters/${characterId}/aliases/${aliasId}`)).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    }),
  undoCharacterIdentityAction: (bookId: string, actionId: string) =>
    apiClient.post<{ undone: string; restored_character_id?: string | null }>(bookPath(bookId, `/characters/identity-actions/${actionId}/undo`)).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    }),
  mergeCharacters: (bookId: string, payload: { primaryId: string; secondaryId: string }) =>
    apiClient.post<{ merged: string }>(bookPath(bookId, "/characters/merge"), {
      primary_id: payload.primaryId,
      secondary_id: payload.secondaryId,
    }).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  partitionCharacter: (
    bookId: string,
    characterId: string,
    payload: { partitions: Array<{ name: string; aliases?: string[] }> },
  ) => apiClient.post<{ replaced: string; created: string[] }>(bookPath(bookId, `/characters/${characterId}/partition`), {
    partitions: payload.partitions.map((partition) => ({
      name: partition.name,
      aliases: partition.aliases ?? [],
    })),
  }).then(r => {
    invalidateBookCache(bookId)
    return r.data
  }),
  deleteCharacter: (bookId: string, characterId: string) =>
    apiClient.delete<{ deleted: string }>(bookPath(bookId, `/characters/${characterId}`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  demoteCharacter: (bookId: string, characterId: string) =>
    apiClient.post<{ demoted: string; candidate_id: string }>(bookPath(bookId, `/characters/${characterId}/demote`)).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    }),
  approveCharacter: (bookId: string, characterId: string) =>
    apiClient.post<{ approved: string }>(bookPath(bookId, `/characters/${characterId}/approve`)).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    }),
  rejectCharacter: (bookId: string, characterId: string) =>
    apiClient.post<{ rejected: string }>(bookPath(bookId, `/characters/${characterId}/reject`)).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    }),
  repairRelationships: (bookId: string) =>
    apiClient.post<import("@/types/character").RelationshipRepairResult>(bookPath(bookId, "/relationships/repair")).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    }),
  promoteCharacterCandidate: (bookId: string, candidateId: string) =>
    apiClient.post<{ promoted: string; candidate_id: string }>(bookPath(bookId, `/character-review/${candidateId}/promote`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  attachCharacterCandidate: (bookId: string, candidateId: string, characterId: string) =>
    apiClient.post<{ attached: string; candidate_id: string }>(bookPath(bookId, `/character-review/${candidateId}/attach`), {
      character_id: characterId,
    }).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  rejectCharacterCandidate: (bookId: string, candidateId: string) =>
    apiClient.post<{ rejected: string }>(bookPath(bookId, `/character-review/${candidateId}/reject`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  markCharacterCandidatePlace: (bookId: string, candidateId: string) =>
    apiClient.post<{ marked: string; adjudication_status: string }>(bookPath(bookId, `/character-review/${candidateId}/mark-place`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  attachRelationshipCandidateA: (bookId: string, candidateId: string, characterId: string) =>
    apiClient.post<{ attached_a: string; relationship_candidate_id: string }>(bookPath(bookId, `/relationship-review/${candidateId}/attach-a`), {
      character_id: characterId,
    }).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  attachRelationshipCandidateB: (bookId: string, candidateId: string, characterId: string) =>
    apiClient.post<{ attached_b: string; relationship_candidate_id: string }>(bookPath(bookId, `/relationship-review/${candidateId}/attach-b`), {
      character_id: characterId,
    }).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  acceptRelationshipCandidate: (
    bookId: string,
    candidateId: string,
    payload: {
      characterAId: string
      characterBId: string
      relType?: string | null
      sentiment?: number | null
      description?: string | null
      fromChapter?: number | null
      toChapter?: number | null
      sharedLabels?: string[]
      characterAToBLabels?: string[]
      characterBToALabels?: string[]
      labelEvidence?: Record<string, unknown>
    },
  ) => apiClient.post(bookPath(bookId, `/relationship-review/${candidateId}/accept`), {
    character_a_id: payload.characterAId,
    character_b_id: payload.characterBId,
    rel_type: payload.relType,
    sentiment: payload.sentiment,
    description: payload.description,
    from_chapter: payload.fromChapter,
    to_chapter: payload.toChapter,
    ...(payload.sharedLabels !== undefined ? { shared_labels: payload.sharedLabels } : {}),
    ...(payload.characterAToBLabels !== undefined ? { character_a_to_b_labels: payload.characterAToBLabels } : {}),
    ...(payload.characterBToALabels !== undefined ? { character_b_to_a_labels: payload.characterBToALabels } : {}),
    ...(payload.labelEvidence !== undefined ? { label_evidence: payload.labelEvidence } : {}),
  }).then(r => {
    invalidateBookCache(bookId)
    invalidateReaderCache(bookId)
    return r.data
  }),
  resolveRelationshipCandidate: (bookId: string, candidateId: string) =>
    apiClient.post<{ resolved: string }>(bookPath(bookId, `/relationship-review/${candidateId}/resolve`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  rejectRelationshipCandidate: (bookId: string, candidateId: string) =>
    apiClient.post<{ rejected: string }>(bookPath(bookId, `/relationship-review/${candidateId}/reject`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  acceptDuplicateSuggestion: (bookId: string, suggestionId: string) =>
    apiClient.post<{ merged: string; suggestion_id: string }>(bookPath(bookId, `/duplicate-suggestions/${suggestionId}/accept`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  dismissDuplicateSuggestion: (bookId: string, suggestionId: string) =>
    apiClient.post<{ dismissed: string }>(bookPath(bookId, `/duplicate-suggestions/${suggestionId}/dismiss`)).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  previewCharacterReprocess: (
    bookId: string,
    payload?: { allowMergeSafePairs?: boolean; allowDemoteObviousNoise?: boolean },
  ) => apiClient.get<CharacterRepairPreview>(bookPath(bookId, "/character-review/reprocess"), {
    params: {
      allow_merge_safe_pairs: payload?.allowMergeSafePairs ?? true,
      allow_demote_obvious_noise: payload?.allowDemoteObviousNoise ?? true,
    },
  }).then(r => r.data),
  applyCharacterReprocess: (
    bookId: string,
    payload?: { allowMergeSafePairs?: boolean; allowDemoteObviousNoise?: boolean },
  ) => apiClient.post<CharacterRepairApplyResult>(bookPath(bookId, "/character-review/reprocess"), null, {
    params: {
      allow_merge_safe_pairs: payload?.allowMergeSafePairs ?? true,
      allow_demote_obvious_noise: payload?.allowDemoteObviousNoise ?? true,
    },
  }).then(r => {
    invalidateBookCache(bookId)
    invalidateReaderCache(bookId)
    return r.data
  }),
  updateRelationship: (
    bookId: string,
    relationshipId: string,
    payload: {
      relType: string
      sentiment?: number | null
      description?: string | null
      fromChapter?: number | null
      toChapter?: number | null
      sharedLabels?: string[]
      characterAToBLabels?: string[]
      characterBToALabels?: string[]
      labelEvidence?: Record<string, unknown>
    }
  ) => apiClient.put<RelationshipGraph["edges"][number] & { rel_type: string }>(bookPath(bookId, `/relationships/${relationshipId}`), {
    rel_type: payload.relType,
    sentiment: payload.sentiment,
    description: payload.description,
    from_chapter: payload.fromChapter,
    to_chapter: payload.toChapter,
    ...(payload.sharedLabels !== undefined ? { shared_labels: payload.sharedLabels } : {}),
    ...(payload.characterAToBLabels !== undefined ? { character_a_to_b_labels: payload.characterAToBLabels } : {}),
    ...(payload.characterBToALabels !== undefined ? { character_b_to_a_labels: payload.characterBToALabels } : {}),
    ...(payload.labelEvidence !== undefined ? { label_evidence: payload.labelEvidence } : {}),
  }).then(r => {
    invalidateBookCache(bookId)
    invalidateReaderCache(bookId)
    return r.data
  }),
  createRelationship: (
    bookId: string,
    payload: {
      characterAId: string
      characterBId: string
      relType: string
      sentiment?: number | null
      description?: string | null
      fromChapter: number
      toChapter?: number | null
      sharedLabels?: string[]
      characterAToBLabels?: string[]
      characterBToALabels?: string[]
      labelEvidence?: Record<string, unknown>
    }
  ) => apiClient.post(bookPath(bookId, "/relationships"), {
    character_a_id: payload.characterAId,
    character_b_id: payload.characterBId,
    rel_type: payload.relType,
    sentiment: payload.sentiment,
    description: payload.description,
    from_chapter: payload.fromChapter,
    to_chapter: payload.toChapter,
    ...(payload.sharedLabels !== undefined ? { shared_labels: payload.sharedLabels } : {}),
    ...(payload.characterAToBLabels !== undefined ? { character_a_to_b_labels: payload.characterAToBLabels } : {}),
    ...(payload.characterBToALabels !== undefined ? { character_b_to_a_labels: payload.characterBToALabels } : {}),
    ...(payload.labelEvidence !== undefined ? { label_evidence: payload.labelEvidence } : {}),
  }).then(r => {
    invalidateBookCache(bookId)
    invalidateReaderCache(bookId)
    return r.data
  }),
  deleteRelationship: (bookId: string, relationshipId: string) =>
    apiClient.delete(bookPath(bookId, `/relationships/${relationshipId}`)).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    }),
  shareCharacter: (bookId: string, characterId: string) =>
    apiClient.post<CharacterShareResponse>(bookPath(bookId, `/characters/${characterId}/share`)).then(r => r.data),
  exportCharacterCard: (bookId: string, characterId: string, format: "md" | "pdf" | "docx" = "pdf") =>
    apiClient.get<Blob>(bookPath(bookId, `/characters/${characterId}/export`), { params: { format }, responseType: "blob" }).then(r => r.data),
  exportCharacterBible: (id: string, format: "md" | "pdf" | "docx" | "vault_folder" = "md", fontFamily = "serif") =>
    apiClient.get<Blob>(bookPath(id, "/export/character-bible"), { params: { format, font_family: fontFamily }, responseType: "blob" }).then(r => r.data),
  previewCharacterBibleVault: (id: string) =>
    apiClient.get<VaultPreview>(bookPath(id, "/export/character-bible/preview")).then(r => r.data),
  listCharacterBibleVaultNotes: (id: string) =>
    apiClient.get<VaultNote[]>(bookPath(id, "/export/character-bible/notes")).then(r => r.data),
  saveCharacterBibleVaultNote: (id: string, payload: { path: string; content: string }) =>
    apiClient.put<VaultNoteSaveResult>(bookPath(id, "/export/character-bible/notes"), payload).then(r => r.data),
  listVaultNotes: (id: string) =>
    apiClient.get<VaultNote[]>(bookPath(id, "/notes/vault")).then(r => r.data),
  getVaultGraph: (id: string) =>
    apiClient.get<VaultGraph>(bookPath(id, "/notes/vault/graph")).then(r => r.data),
  getVaultNoteRelations: (id: string, path: string) =>
    apiClient.get<VaultNoteRelations>(bookPath(id, "/notes/vault/relations"), { params: { path } }).then(r => r.data),
  saveVaultNote: (id: string, payload: { path: string; content: string }) =>
    apiClient.put<VaultNoteSaveResult>(bookPath(id, "/notes/vault"), payload).then(r => {
      void invalidateQueryKeys(bookCacheKey(id, "vault-notes"))
      void invalidateQueryKeys(bookCacheKey(id, "vault-graph"))
      void invalidateQueryKeys(bookCacheKey(id, "vault-relations:"))
      void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
      return r.data
    }),
  deleteVaultNote: (id: string, path: string) =>
    apiClient.delete(bookPath(id, `/notes/vault/${encodeURIComponent(path)}`)).then(() => {
      void invalidateQueryKeys(bookCacheKey(id, "vault-notes"))
      void invalidateQueryKeys(bookCacheKey(id, "vault-graph"))
      void invalidateQueryKeys(bookCacheKey(id, "vault-relations:"))
      void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
    }),
  importVaultNotes: (id: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return apiClient.post<VaultNoteSaveResult[]>(bookPath(id, "/notes/vault/import"), form).then(r => {
      void invalidateQueryKeys(bookCacheKey(id, "vault-notes"))
      void invalidateQueryKeys(bookCacheKey(id, "vault-graph"))
      void invalidateQueryKeys(bookCacheKey(id, "vault-relations:"))
      void invalidateQueryKeys(bookCacheKey(id, "workspace-tree"))
      return r.data
    })
  },
  exportVaultNotes: (id: string) =>
    apiClient.get<Blob>(bookPath(id, "/notes/vault/export"), { responseType: "blob" }).then(r => r.data),
  saveBookNote: (
    id: string,
    payload: { noteId?: string | null; chapterNumber?: number | null; title?: string | null; body: string }
  ) => apiClient.post<BookNote>(bookPath(id, "/notes"), {
    note_id: payload.noteId,
    chapter_number: payload.chapterNumber,
    title: payload.title,
    body: payload.body,
  }).then(r => {
    invalidateBookCache(id)
    void invalidateQueryKeys(booksNotesCacheKey())
    return r.data
  }),
  saveManuscriptAnnotation: (
    id: string,
    payload: {
      annotationId?: string | null
      chapterNumber?: number | null
      category?: string | null
      status?: "open" | "resolved" | null
      visibility?: "shared" | "private" | null
      quote?: string | null
      comment?: string | null
      anchorContextBefore?: string | null
      anchorContextAfter?: string | null
      startOffset?: number | null
      endOffset?: number | null
    }
  ) => apiClient.post<ManuscriptAnnotation>(bookPath(id, "/annotations"), {
    annotation_id: payload.annotationId,
    chapter_number: payload.chapterNumber,
    category: payload.category,
    status: payload.status,
    visibility: payload.visibility,
    quote: payload.quote,
    comment: payload.comment,
    anchor_context_before: payload.anchorContextBefore,
    anchor_context_after: payload.anchorContextAfter,
    start_offset: payload.startOffset,
    end_offset: payload.endOffset,
  }).then(r => {
    void invalidateQueryKeys(bookCacheKey(id, "annotations:"))
    return r.data
  }),
  deleteBookNote: (id: string, noteId: string) =>
    apiClient.delete(bookPath(id, `/notes/${noteId}`)).then(() => {
      invalidateBookCache(id)
      void invalidateQueryKeys(booksNotesCacheKey())
    }),
  deleteManuscriptAnnotation: (id: string, annotationId: string) =>
    apiClient.delete(bookPath(id, `/annotations/${annotationId}`)).then(() => {
      void invalidateQueryKeys(bookCacheKey(id, "annotations:"))
    }),
  archive: (id: string, archived = true) =>
    apiClient.put<Book>(bookPath(id, "/archive"), null, { params: { archived } }).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  hide: async (id: string, hidden = true) => {
    try {
      const response = await apiClient.put<Book>(bookPath(id, "/hide"), null, { params: { hidden } })
      invalidateBookCache(id)
      return response.data
    } catch (error) {
      // Only fall back to DELETE when the server clearly does not support the
      // hide endpoint. Network failures or auth issues should bubble up
      // directly so we do not fire a second destructive request.
      const status = axios.isAxiosError(error) ? error.response?.status : undefined
      if (!hidden || (status !== 404 && status !== 405)) throw error
      const fallback = await apiClient.delete<Book>(bookPath(id))
      invalidateBookCache(id)
      return fallback.data
    }
  },
  deletePermanently: (id: string, confirmationText: string) =>
    apiClient.delete<{ ok: boolean; book_id: string; deletion_request_id: string; status: string }>(bookPath(id, "/permanent"), {
      data: { confirmation_text: confirmationText },
    }).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  publishPublicly: (id: string, payload: { publicSlug: string; rightsConfirmation: boolean; description?: string | null }) =>
    apiClient.post<{ book_id: string; public_slug?: string | null; message?: string | null }>(bookPath(id, "/publish"), {
      public_slug: payload.publicSlug,
      rights_confirmation: payload.rightsConfirmation,
      content_source_type: "user_original",
      description: payload.description ?? null,
    }).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  unpublishPublicly: (id: string) =>
    apiClient.post<{ book_id: string; message?: string | null }>(bookPath(id, "/unpublish")).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  listSeries: (params?: { limit?: number; offset?: number }) =>
    apiClient.get<PaginatedSeries>("/books/series", { params }).then(r => r.data),
  getSeriesBible: (seriesId: string) =>
    apiClient.get<SeriesBible>(`/books/series/${seriesId}/bible`).then(r => r.data),
  createSeries: (payload: { name: string; description?: string | null }) =>
    apiClient.post<BookSeries>("/books/series", payload).then(r => {
      void invalidateQueryKeys(booksSeriesCacheKey())
      void invalidateQueryKeys("books:series-bible:")
      return r.data
    }),
  setSeries: (id: string, payload: { series_name?: string | null; series_order?: number | null }) =>
    apiClient.put<Book>(bookPath(id, "/series"), payload).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  addBookToSeries: (seriesId: string, bookId: string, payload: { position?: number | null }) =>
    apiClient.post<BookSeries>(`/books/series/${seriesId}/books/${bookId}`, payload).then(r => {
      invalidateBookCache(bookId)
      void invalidateQueryKeys("books:series-bible:")
      return r.data
    }),
  removeBookFromSeries: (seriesId: string, bookId: string) =>
    apiClient.delete<BookSeries>(`/books/series/${seriesId}/books/${bookId}`).then(r => {
      invalidateBookCache(bookId)
      void invalidateQueryKeys("books:series-bible:")
      return r.data
    }),
  setSeriesBookStatus: (seriesId: string, bookId: string, markedComplete = true) =>
    apiClient.put<Book>(`/books/series/${seriesId}/books/${bookId}/status`, { marked_complete: markedComplete }).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  setMode: (id: string, mode: "reader" | "author") =>
    apiClient.put<Book>(bookPath(id, "/mode"), { mode }).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  updateForumMetadata: (
    id: string,
    payload: { title: string; genre: string; description: string }
  ) => apiClient.put<Book>(bookPath(id, "/forum-metadata"), {
    title: payload.title,
    genre: payload.genre,
    description: payload.description,
  }).then(r => {
    invalidateBookCache(id)
    return r.data
  }),
  upload: (
    file: File,
    title: string,
    genre?: string,
    author?: string,
    options?: {
      visibility?: "private"
      description?: string
      seriesIds?: string[]
      autoExtractCover?: boolean
      preserveChapterNumbers?: boolean
      preserveSourceChapters?: boolean
      forceSingleManuscript?: boolean
      workType?: BookWorkType
      coverFile?: File | null
      mode?: "reader" | "author"
      onProgress?: (percent: number) => void
    }
  ) => {
    const form = new FormData()
    form.append("file", file)
    form.append("title", title)
    if (genre) form.append("genre", genre)
    if (author) form.append("author", author)
    if (options?.visibility) form.append("visibility", options.visibility)
    if (options?.description) form.append("description", options.description)
    options?.seriesIds?.forEach((seriesId) => {
      if (seriesId) form.append("series_ids", seriesId)
    })
    if (options?.workType) form.append("work_type", options.workType)
    if (options?.mode) form.append("mode", options.mode)
    form.append("auto_extract_cover", options?.autoExtractCover === false ? "false" : "true")
    form.append("preserve_chapter_numbers", options?.preserveChapterNumbers ? "true" : "false")
    form.append("preserve_source_chapters", options?.preserveSourceChapters ? "true" : "false")
    form.append("force_single_manuscript", options?.forceSingleManuscript ? "true" : "false")
    if (options?.coverFile) form.append("cover_file", options.coverFile)
    return apiClient.post("/books/upload", form, {
      onUploadProgress: (event) => {
        if (!options?.onProgress || !event.total) return
        const percent = Math.min(100, Math.max(0, Math.round((event.loaded / event.total) * 100)))
        options.onProgress(percent)
      },
    }).then(r => {
      void invalidateQueryKeys("books:list:")
      void invalidateQueryKeys(booksStatsCacheKey())
      return r.data
    })
  },
  importManuscript: (
    bookId: string,
    payload: {
      text?: string
      html?: string
      title?: string
      chapterNumber?: number
      expectedContentVersion?: number
      replaceExisting?: boolean
      chunkLongDocuments?: boolean
      splitIntoChapters?: boolean
      workType?: BookWorkType
      files?: File[]
    }
  ) => {
    const form = new FormData()
    if (payload.text) form.append("text", payload.text)
    if (payload.html) form.append("html", payload.html)
    if (payload.title) form.append("title", payload.title)
    if (typeof payload.chapterNumber === "number") form.append("chapter_number", String(payload.chapterNumber))
    if (typeof payload.expectedContentVersion === "number") form.append("expected_content_version", String(payload.expectedContentVersion))
    if (payload.replaceExisting) form.append("replace_existing", "true")
    if (payload.chunkLongDocuments) form.append("chunk_long_documents", "true")
    if (payload.splitIntoChapters === false) form.append("split_into_chapters", "false")
    if (payload.workType) form.append("work_type", payload.workType)
    payload.files?.forEach((file) => form.append("files", file))
    return apiClient.post<ManuscriptImportResponse>(bookPath(bookId, "/manuscript/import"), form).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      return r.data
    })
  },
  exportManuscript: (
    bookId: string,
    format: "pdf" | "docx" | "epub" | "vault" = "docx",
    preset: "standard_manuscript" | "trade_paperback" | "kdp_paperback" = "standard_manuscript",
    includeSceneMetadata = true,
    fontFamily = "serif",
    includeToc = false
  ) =>
    apiClient.get<Blob>(bookPath(bookId, "/manuscript/export"), {
      params: { format, preset, include_scene_metadata: includeSceneMetadata, font_family: fontFamily, include_toc: includeToc },
      responseType: "blob",
    }).then(r => r.data),
  exportNovel: (
    bookId: string,
    format: "pdf" | "docx" | "epub" = "pdf",
    preset: NovelExportPreset = "standard_novel",
    includeImages = false,
    fontFamily = "serif",
    options: {
      imagePlacement?: NovelImagePlacement
      includeImageCaptions?: boolean
      previewChapters?: number | null
    } = {}
  ) =>
    apiClient.get<Blob>(bookPath(bookId, "/novel/export"), {
      params: {
        format,
        preset,
        include_images: includeImages,
        image_placement: options.imagePlacement ?? "end",
        include_image_captions: options.includeImageCaptions ?? false,
        preview_chapters: options.previewChapters ?? undefined,
        font_family: fontFamily,
      },
      responseType: "blob",
    }).then(r => r.data),
  saveNovelPreface: (bookId: string, preface: string) =>
    apiClient.put<{ preface: string }>(bookPath(bookId, "/novel/preface"), { preface }).then(r => {
      void invalidateQueryKeys(bookCacheKey(bookId, "writer-workspace"))
      return r.data
    }),
  saveNovelSettings: (
    bookId: string,
    body: {
      preface: string
      front_matter: NovelFrontMatter
      epub_metadata: NovelEpubMetadata
    }
  ) =>
    apiClient.put<{
      preface: string
      front_matter: NovelFrontMatter
      epub_metadata: NovelEpubMetadata
    }>(bookPath(bookId, "/novel/settings"), body).then(r => {
      void invalidateQueryKeys(bookCacheKey(bookId, "writer-workspace"))
      return r.data
    }),
  delete: (id: string) => apiClient.delete<Book>(bookPath(id)).then(r => {
    invalidateBookCache(id)
    return r.data
  }),
  createEmptyProject: (body: { title: string; author?: string | null; genre?: string | null; work_type?: string | null; series_ids?: string[] | null }) =>
    apiClient.post<{ book_id: string; status: string; mode: string; is_editor_project: boolean }>("/books/empty-project", body).then(r => {
      void invalidateQueryKeys("books:list:")
      void invalidateQueryKeys(booksStatsCacheKey())
      return r.data
    }),
  previewUpload: (file: File, workType?: BookWorkType) => {
    const form = new FormData()
    form.append("file", file)
    if (workType) form.append("work_type", workType)
    return apiClient.post<ImportPreview>("/books/upload/preview", form).then(r => r.data)
  },
  reprocessManuscript: (bookId: string) =>
    apiClient.post<{
      book_id: string
      status: string
      chapters_queued: number
      total_words: number
      upload_charge_consumed: boolean
      charge_kind?: "manual_reprocess" | null
    }>(
      bookPath(bookId, "/manuscript/reprocess"),
      { confirm_upload_charge: true }
    ).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  updateCover: (bookId: string, coverFile: File) => {
    const form = new FormData()
    form.append("cover_file", coverFile)
    return apiClient.put<Book>(bookPath(bookId, "/cover"), form).then(r => {
      invalidateBookCache(bookId)
      return r.data
    })
  },
  deleteCover: (bookId: string) =>
    apiClient.delete<Book>(bookPath(bookId, "/cover")).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  reprocessChapter: (bookId: string, chapterNumber: number) =>
    apiClient.post<{
      book_id: string
      status: string
      chapters_queued: number
      total_words: number
      upload_charge_consumed: boolean
      charge_kind?: "manual_reprocess" | null
    }>(
      bookPath(bookId, `/manuscript/chapters/${chapterNumber}/reprocess`),
      null
    ).then(r => {
      invalidateBookCache(bookId)
      invalidateReaderCache(bookId)
      void invalidateQueryKeys(bookCacheKey(bookId, "writer-workspace"))
      return r.data
    }),
}
