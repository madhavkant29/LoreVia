"use client"

import { useRef } from "react"
import dynamic from "next/dynamic"
import { useEffect, useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { LibraryWorkspaceHeader } from "@/components/library/LibraryWorkspaceHeader"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey, booksPageCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { getBookHref } from "@/lib/utils/bookRoutes"
import { normalizeProcessingStatus } from "@/lib/utils/processingStatus"
import type { Book } from "@/types/book"
import type { BookPage } from "@/lib/api/books"
import {
  EMPTY_BOOKS,
  deriveLibraryCollections,
  getVisibleLibraryBooks,
  type ModeFilter,
  type SortOption,
  type StatusFilter,
  type ViewMode,
} from "./LibraryClient.helpers"
import { LibraryProjectControls } from "./LibraryClient.controls"
import { PermanentDeleteBookDialog, PublishBookDialog } from "./LibraryClient.dialogs"
import { useLibrarySearchShortcut, usePinnedLibraryProjects } from "./LibraryClient.hooks"
import {
  FolderIcon,
  PinIcon,
} from "./LibraryClient.icons"
import { FirstManuscriptHero } from "./LibraryClient.panels"
import { LibraryProjectSection } from "./LibraryClient.sections"
import { LibraryAuthLoadingState, LibraryErrorState } from "./LibraryClient.states"

const UploadModal = dynamic(
  () => import("@/components/modals/UploadModal").then((module) => module.UploadModal),
  {
    ssr: false,
  }
)

export function LibraryClient() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const confirm = useConfirmDialog()
  const { theme } = usePreferencesStore()
  const authUser = useAuthStore((s) => s.user)
  const authReady = useAuthStore((s) => s.hydrated)
  const isDark = theme === "dark"

  const [showUpload, setShowUpload] = useState(false)
  const [publishBook, setPublishBook] = useState<Book | null>(null)
  const [publishSlug, setPublishSlug] = useState("")
  const [publishDescription, setPublishDescription] = useState("")
  const [publishConfirmed, setPublishConfirmed] = useState(false)
  const [deleteBook, setDeleteBook] = useState<Book | null>(null)
  const [deleteConfirmation, setDeleteConfirmation] = useState("")
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [uploadPreset, setUploadPreset] = useState<{ mode?: "reader" | "author"; existingBookId?: string }>({})
  const [busyBookId, setBusyBookId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState<SortOption>("recent")
  const [viewMode, setViewMode] = useState<ViewMode>("grid")
  const [modeFilter, setModeFilter] = useState<ModeFilter>("all")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [showArchived, setShowArchived] = useState(false)
  const [menuBookId, setMenuBookId] = useState<string | null>(null)
  const [pinnedIds, setPinnedIds] = usePinnedLibraryProjects()
  const [additionalBookPages, setAdditionalBookPages] = useState<BookPage[]>([])
  const [loadingMoreBooks, setLoadingMoreBooks] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [publishError, setPublishError] = useState<string | null>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const {
    data: booksData,
    isLoading: loading,
    isError: booksError,
    refetch,
  } = useQuery<BookPage | Book[]>({
    queryKey: asQueryKey(booksPageCacheKey(true)),
    queryFn: () => booksApi.listPage(true),
    staleTime: 20_000,
    enabled: authReady && !!authUser,
    refetchInterval: (query) => {
      const page = query.state.data as BookPage | Book[] | undefined
      const items = Array.isArray(page) ? page : page?.items ?? []
      const hasProcessingBook = items.some(
        (book) =>
          book.status === "processing" ||
          book.status === "pending" ||
          (!book.cover_url && book.format === "pdf"),
      )
      const canPoll = typeof document === "undefined" || document.visibilityState === "visible"
      return canPoll && hasProcessingBook ? 5_000 : false
    },
    refetchIntervalInBackground: false,
  })
  const firstBookPage = useMemo<BookPage>(
    () =>
      Array.isArray(booksData)
        ? { items: booksData, next_cursor: null }
        : booksData ?? { items: EMPTY_BOOKS, next_cursor: null },
    [booksData],
  )
  const books = useMemo(
    () => [firstBookPage, ...additionalBookPages].flatMap((page) => page.items),
    [firstBookPage, additionalBookPages],
  )
  const nextBookCursor = (additionalBookPages.at(-1) ?? firstBookPage).next_cursor

  async function loadMoreBooks() {
    if (!nextBookCursor || loadingMoreBooks) return
    setLoadingMoreBooks(true)
    setLoadMoreError(false)
    try {
      const page = await booksApi.listPage(true, nextBookCursor)
      setAdditionalBookPages((current) => [...current, page])
    } catch {
      setLoadMoreError(true)
    } finally {
      setLoadingMoreBooks(false)
    }
  }

  async function refreshLibrary() {
    const result = await refetch()
    if (!result.isError) setAdditionalBookPages([])
  }

  useLibrarySearchShortcut(searchInputRef)

  const normalizedSearch = search.trim().toLowerCase()
  const visibleBooks = useMemo(
    () => getVisibleLibraryBooks(books),
    [books]
  )

  const { filteredBooks, pinnedBooks, allProjectBooks } = useMemo(
    () => deriveLibraryCollections({
      visibleBooks,
      showArchived,
      modeFilter,
      statusFilter,
      normalizedSearch,
      sortBy,
      pinnedIds,
    }),
    [visibleBooks, showArchived, modeFilter, statusFilter, normalizedSearch, sortBy, pinnedIds],
  )

  const hasAnyProjects = visibleBooks.length > 0
  const hasOnlyArchivedProjects = hasAnyProjects && visibleBooks.every((book) => Boolean(book.archived_at))
  const hasActiveProjectFilters = Boolean(normalizedSearch) || modeFilter !== "all" || statusFilter !== "all" || showArchived
  const canStartAuthorProject = canUseAuthorFeatures(authUser?.tier) || Boolean(authUser?.trial_active)
  const showFirstManuscriptHero = !loading && !hasAnyProjects && !nextBookCursor && canStartAuthorProject

  async function handleArchive(bookId: string, archived: boolean) {
    setActionError(null)
    setBusyBookId(bookId)
    try {
      await booksApi.archive(bookId, archived)
      await refreshLibrary()
      setMenuBookId(null)
    } catch {
      setActionError(`Could not ${archived ? "archive" : "restore"} this project. Please try again from its actions menu.`)
    } finally {
      setBusyBookId(null)
    }
  }

  async function handleRemove(bookId: string) {
    setActionError(null)
    const confirmed = await confirm({
      title: "Remove project from library view?",
      body: "Remove this project from your library view? It will stay counted for usage.",
      confirmLabel: "Remove project",
      tone: "danger",
    })
    if (!confirmed) return

    setBusyBookId(bookId)
    try {
      await booksApi.hide(bookId, true)
      await refreshLibrary()
      setMenuBookId(null)
    } catch {
      setActionError("Could not remove this project. Please try again from its actions menu.")
    } finally {
      setBusyBookId(null)
    }
  }

  async function handlePermanentDelete(book: Book) {
    setDeleteBook(book)
    setDeleteConfirmation("")
    setDeleteError(null)
  }

  async function confirmPermanentDelete() {
    if (!deleteBook) return
    if (deleteConfirmation !== "DELETE BOOK") {
      setDeleteError("Type DELETE BOOK exactly to continue.")
      return
    }

    setBusyBookId(deleteBook.id)
    try {
      await booksApi.deletePermanently(deleteBook.id, deleteConfirmation)
      await refreshLibrary()
      setMenuBookId(null)
      setDeleteBook(null)
      setDeleteConfirmation("")
      setDeleteError(null)
    } catch {
      setDeleteError("Could not delete this project. Your confirmation is saved; please try again.")
    } finally {
      setBusyBookId(null)
    }
  }

  function handleAddChapter(book: Book) {
    router.push(`/library/add-chapter?book=${book.id}&title=${encodeURIComponent(book.title)}` as Route)
  }

  function openBook(book: Book) {
    router.push(getBookHref(book) as Route)
  }

  function prefetchBook(book: Book) {
    const href = getBookHref(book) as Route
    router.prefetch(href)
    void queryClient.prefetchQuery({
      queryKey: asQueryKey(bookCacheKey(book.id, "reader-bootstrap")),
      queryFn: () => booksApi.getReaderBootstrap(book.id, { profile: "critical" }),
      staleTime: 30_000,
    })
  }

  function togglePinned(bookId: string) {
    setPinnedIds((current) => ({ ...current, [bookId]: !current[bookId] }))
    setMenuBookId(null)
  }

  async function handlePublish(book: Book) {
    if (!publishConfirmed || !publishSlug.trim()) return
    setBusyBookId(book.id)
    setPublishError(null)
    try {
      await booksApi.publishPublicly(book.id, {
        publicSlug: publishSlug.trim(),
        rightsConfirmation: true,
        description: publishDescription.trim() || null,
      })
      setPublishBook(null)
      setPublishConfirmed(false)
      setPublishSlug("")
      setPublishDescription("")
      await refreshLibrary()
    } catch {
      setPublishError("Could not publish this project. Check the public URL slug and try again.")
    } finally {
      setBusyBookId(null)
    }
  }

  async function handleUnpublish(bookId: string) {
    setActionError(null)
    setBusyBookId(bookId)
    try {
      await booksApi.unpublishPublicly(bookId)
      await refreshLibrary()
      setMenuBookId(null)
    } catch {
      setActionError("Could not unpublish this project. Please try again from its actions menu.")
    } finally {
      setBusyBookId(null)
    }
  }

  async function handleRetryProcessing(bookId: string) {
    setActionError(null)
    setBusyBookId(bookId)
    try {
      const targetBook = books.find((book) => book.id === bookId)
      const processingStatus = normalizeProcessingStatus(targetBook?.processing, targetBook)
      if (processingStatus?.resumeAvailable) {
        await booksApi.continueProcessing(bookId)
      } else {
        await booksApi.retryProcessing(bookId)
      }
      await refreshLibrary()
    } catch {
      setActionError("Could not restart processing. Please try the processing action again.")
    } finally {
      setBusyBookId(null)
    }
  }

  function startCreateProject() {
    setUploadPreset({ mode: canStartAuthorProject ? "author" : "reader" })
    setShowUpload(true)
  }

  function openPublishDialog(book: Book) {
    setPublishError(null)
    setPublishBook(book)
    setPublishSlug(book.public_slug ?? book.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""))
    setPublishDescription(book.public_description ?? "")
    setPublishConfirmed(false)
  }

  function resetProjectFilters() {
    setSearch("")
    setModeFilter("all")
    setStatusFilter("all")
    setShowArchived(false)
  }

  const projectSectionHandlers = {
    onMenuToggle: (book: Book) => setMenuBookId((current) => (current === book.id ? null : book.id)),
    onOpen: openBook,
    onPrefetch: prefetchBook,
    onRetryProcessing: (book: Book) => void handleRetryProcessing(book.id),
    onTogglePinned: (book: Book) => togglePinned(book.id),
    onArchive: (book: Book) => void handleArchive(book.id, true),
    onRestore: (book: Book) => void handleArchive(book.id, false),
    onRemove: (book: Book) => void handleRemove(book.id),
    onPermanentDelete: (book: Book) => void handlePermanentDelete(book),
    onAddChapter: (book: Book) => handleAddChapter(book),
    onPublish: openPublishDialog,
    onUnpublish: (book: Book) => void handleUnpublish(book.id),
  }

  const pageBackground = isDark ? "bg-[rgb(20,24,27)] text-[#efe9df]" : "bg-[#f4f6f8] text-stone-950"
  const surfaceClass = isDark ? "border-white/[0.08] bg-[#101b24]" : "border-stone-200 bg-white"
  const mutedText = isDark ? "text-[#a6a39b]" : "text-stone-600"
  const headingText = isDark ? "text-[#f5f0e8]" : "text-stone-950"
  const controlClass = isDark ? "border-white/[0.08] bg-[#0c1720] text-[#ebe7df]" : "border-stone-200 bg-white text-stone-800"
  const [interactiveReady, setInteractiveReady] = useState(false)

  useEffect(() => {
    setInteractiveReady(true)
  }, [])

  if (!authReady || !authUser) {
    return <LibraryAuthLoadingState isDark={isDark} pageBackground={pageBackground} />
  }

  if (booksError && !booksData) {
    return (
      <LibraryErrorState
        isDark={isDark}
        pageBackground={pageBackground}
        onRetry={() => refreshLibrary()}
      />
    )
  }

  return (
    <div className={`min-h-screen transition-colors duration-300 ${pageBackground}`}>
      <div className="w-full pb-20">
        <section className="space-y-5" data-testid="library-workspace">
          <LibraryWorkspaceHeader
            createDisabled={!interactiveReady}
            isDark={isDark}
            onOpenForum={() => router.push("/public/forum" as Route)}
            onCreate={startCreateProject}
          />

          {actionError || booksError ? <div role="alert" className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-rose-400 bg-rose-500/10 p-4 text-sm text-rose-800 dark:text-rose-200">
            <p>{actionError ?? "Could not refresh your library. Your last loaded projects are still shown."}</p>
            <button type="button" className="min-h-11 underline underline-offset-4" onClick={() => actionError ? setActionError(null) : void refreshLibrary()}>{actionError ? "Dismiss" : "Retry"}</button>
          </div> : null}

          {showFirstManuscriptHero ? (
            <FirstManuscriptHero isDark={isDark} onUpload={startCreateProject} />
          ) : (
          <>
          <LibraryProjectControls
            isDark={isDark}
            searchInputRef={searchInputRef}
            search={search}
            modeFilter={modeFilter}
            statusFilter={statusFilter}
            showArchived={showArchived}
            sortBy={sortBy}
            viewMode={viewMode}
            controlClass={controlClass}
            mutedText={mutedText}
            onSearchChange={setSearch}
            onModeFilterChange={setModeFilter}
            onStatusFilterChange={setStatusFilter}
            onShowArchivedToggle={() => setShowArchived((current) => !current)}
            onSortChange={setSortBy}
            onViewModeChange={setViewMode}
            onResetFilters={resetProjectFilters}
          />

          {!loading ? <p role="status" className={`text-sm ${mutedText}`}>{filteredBooks.length} {filteredBooks.length === 1 ? "project" : "projects"}{hasActiveProjectFilters ? " match this view" : " in this view"}{nextBookCursor ? " · More projects available below. Search and filters apply to loaded projects." : ""}</p> : null}

          {pinnedBooks.length > 0 ? <LibraryProjectSection
            isDark={isDark}
            loading={loading}
            viewMode={viewMode}
            title="Pinned projects"
            icon={<PinIcon className={isDark ? "text-[#d7d0c6]" : "text-stone-700"} />}
            helperText={pinnedBooks.length > 0 ? "Manage pins from each project menu." : undefined}
            books={pinnedBooks}
            busyBookId={busyBookId}
            pinnedIds={pinnedIds}
            menuBookId={menuBookId}
            skeletonLabel="Loading pinned projects"
            emptyState={{ show: false, title: "", body: "" }}
            handlers={projectSectionHandlers}
          /> : null}

          {allProjectBooks.length > 0 || pinnedBooks.length === 0 ? <LibraryProjectSection
            isDark={isDark}
            loading={loading}
            viewMode={viewMode}
            title={pinnedBooks.length ? "Other projects" : "All projects"}
            icon={<FolderIcon className={isDark ? "text-[#d7d0c6]" : "text-stone-700"} />}
            books={allProjectBooks}
            busyBookId={busyBookId}
            pinnedIds={pinnedIds}
            menuBookId={menuBookId}
            skeletonLabel="Loading all projects"
            emptyState={{
              show: allProjectBooks.length === 0 && filteredBooks.length === 0,
              title: hasOnlyArchivedProjects && !hasActiveProjectFilters ? "Your projects are archived" : hasAnyProjects ? "No projects match this view" : "No projects yet",
              body: hasOnlyArchivedProjects && !hasActiveProjectFilters
                ? "Include archived projects to open or restore them."
                : hasAnyProjects
                ? "Try a different search or filter to bring projects back into view."
                : "Start a new project to keep your ideas organized.",
              actionLabel: hasOnlyArchivedProjects && !hasActiveProjectFilters ? "Show archived projects" : hasAnyProjects ? undefined : "New Project",
              onAction: hasOnlyArchivedProjects && !hasActiveProjectFilters ? () => setShowArchived(true) : hasAnyProjects ? resetProjectFilters : startCreateProject,
            }}
            handlers={projectSectionHandlers}
          /> : null}
          {nextBookCursor ? (
            <div className="flex flex-col items-center gap-3">
              {loadMoreError ? <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">Could not load more projects. Your current projects are still available.</p> : null}
              <button
                type="button"
                className={`rounded-md border px-4 py-2 text-sm font-semibold ${controlClass}`}
                disabled={loadingMoreBooks}
                onClick={() => void loadMoreBooks()}
              >
                {loadingMoreBooks ? "Loading projects..." : loadMoreError ? "Retry loading projects" : "Load more projects"}
              </button>
            </div>
          ) : null}
          </>
          )}
        </section>
      </div>

      {showUpload ? (
        <UploadModal
          initialMode={uploadPreset.mode}
          initialExistingBookId={uploadPreset.existingBookId}
          onClose={() => {
            setShowUpload(false)
            setUploadPreset({})
            void refreshLibrary()
          }}
        />
      ) : null}

      {publishBook ? (
        <PublishBookDialog
          surfaceClass={surfaceClass}
          mutedText={mutedText}
          headingText={headingText}
          controlClass={controlClass}
          publishSlug={publishSlug}
          publishDescription={publishDescription}
          publishConfirmed={publishConfirmed}
          error={publishError}
          busy={busyBookId === publishBook.id}
          onSlugChange={setPublishSlug}
          onDescriptionChange={setPublishDescription}
          onConfirmedChange={setPublishConfirmed}
          onCancel={() => setPublishBook(null)}
          onPublish={() => void handlePublish(publishBook)}
        />
      ) : null}

      {deleteBook ? (
        <PermanentDeleteBookDialog
          book={deleteBook}
          surfaceClass={surfaceClass}
          mutedText={mutedText}
          headingText={headingText}
          controlClass={controlClass}
          deleteConfirmation={deleteConfirmation}
          deleteError={deleteError}
          busy={busyBookId === deleteBook.id}
          onConfirmationChange={(value) => {
            setDeleteConfirmation(value)
            setDeleteError(null)
          }}
          onCancel={() => {
            setDeleteBook(null)
            setDeleteConfirmation("")
            setDeleteError(null)
          }}
          onConfirm={() => void confirmPermanentDelete()}
        />
      ) : null}
    </div>
  )
}
