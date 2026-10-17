import type { ReactNode } from "react"

import type { Book } from "@/types/book"

import { EmptyPanel, ProjectCard, ProjectRow, CreateProjectCard, CreateProjectRow } from "./LibraryClient.projects"
import { SectionHeading } from "./LibraryClient.panels"
import { ProjectSkeletons } from "./LibraryClient.skeletons"
import type { ViewMode } from "./LibraryClient.helpers"

type ProjectHandlers = {
  onMenuToggle: (book: Book) => void
  onOpen: (book: Book) => void
  onPrefetch: (book: Book) => void
  onRetryProcessing: (book: Book) => void
  onTogglePinned: (book: Book) => void
  onArchive: (book: Book) => void
  onRestore: (book: Book) => void
  onRemove: (book: Book) => void
  onPermanentDelete: (book: Book) => void
  onAddChapter: (book: Book) => void
  onPublish: (book: Book) => void
  onUnpublish: (book: Book) => void
}

export function LibraryProjectSection({
  isDark,
  loading,
  viewMode,
  title,
  icon,
  helperText,
  books,
  busyBookId,
  pinnedIds,
  menuBookId,
  skeletonLabel,
  emptyState,
  showCreateProject,
  onCreateProject,
  handlers,
}: {
  isDark: boolean
  loading: boolean
  viewMode: ViewMode
  title: string
  icon: ReactNode
  helperText?: string
  books: Book[]
  busyBookId: string | null
  pinnedIds: Record<string, boolean>
  menuBookId: string | null
  skeletonLabel: string
  emptyState?: {
    show: boolean
    title: string
    body: string
    actionLabel?: string
    onAction?: () => void
  }
  showCreateProject?: boolean
  onCreateProject?: () => void
  handlers: ProjectHandlers
}) {
  const projectCards = books.map((book) => (
    <ProjectCard
      key={book.id}
      book={book}
      isDark={isDark}
      busy={busyBookId === book.id}
      isPinned={!!pinnedIds[book.id]}
      menuOpen={menuBookId === book.id}
      onMenuToggle={() => handlers.onMenuToggle(book)}
      onOpen={() => handlers.onOpen(book)}
      onPrefetch={() => handlers.onPrefetch(book)}
      onRetryProcessing={() => handlers.onRetryProcessing(book)}
      onTogglePinned={() => handlers.onTogglePinned(book)}
      onArchive={() => handlers.onArchive(book)}
      onRestore={() => handlers.onRestore(book)}
      onRemove={() => handlers.onRemove(book)}
      onPermanentDelete={() => handlers.onPermanentDelete(book)}
      onAddChapter={() => handlers.onAddChapter(book)}
      onPublish={() => handlers.onPublish(book)}
      onUnpublish={() => handlers.onUnpublish(book)}
    />
  ))
  const projectRows = books.map((book) => (
    <ProjectRow
      key={book.id}
      book={book}
      isDark={isDark}
      busy={busyBookId === book.id}
      isPinned={!!pinnedIds[book.id]}
      menuOpen={menuBookId === book.id}
      onMenuToggle={() => handlers.onMenuToggle(book)}
      onOpen={() => handlers.onOpen(book)}
      onPrefetch={() => handlers.onPrefetch(book)}
      onRetryProcessing={() => handlers.onRetryProcessing(book)}
      onTogglePinned={() => handlers.onTogglePinned(book)}
      onArchive={() => handlers.onArchive(book)}
      onRestore={() => handlers.onRestore(book)}
      onRemove={() => handlers.onRemove(book)}
      onPermanentDelete={() => handlers.onPermanentDelete(book)}
      onAddChapter={() => handlers.onAddChapter(book)}
      onPublish={() => handlers.onPublish(book)}
      onUnpublish={() => handlers.onUnpublish(book)}
    />
  ))

  return (
    <section className="space-y-4">
      <SectionHeading
        icon={icon}
        title={title}
        helperText={helperText}
        isDark={isDark}
      />

      {loading ? (
        <ProjectSkeletons isDark={isDark} viewMode={viewMode} label={skeletonLabel} />
      ) : emptyState?.show ? (
        <EmptyPanel
          isDark={isDark}
          title={emptyState.title}
          body={emptyState.body}
          actionLabel={emptyState.actionLabel}
          actionHandler={emptyState.onAction}
        />
      ) : viewMode === "grid" ? (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {projectCards}
          {showCreateProject && onCreateProject ? (
            <CreateProjectCard isDark={isDark} onCreate={onCreateProject} />
          ) : null}
        </div>
      ) : (
        <div className="border-t border-[rgb(var(--border))]">
          {projectRows}
          {showCreateProject && onCreateProject ? (
            <CreateProjectRow isDark={isDark} onCreate={onCreateProject} />
          ) : null}
        </div>
      )}
    </section>
  )
}
