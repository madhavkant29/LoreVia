import type { MouseEvent } from "react"
import Link from "next/link"
import type { Route } from "next"

import { Button } from "@/components/ui/Button"
import { ProcessingStatusStrip } from "@/components/ui/ResponsivenessStatus"
import { Tooltip } from "@/components/ui/Tooltip"
import { VisibilityBadge } from "@/components/ui/VisibilityBadge"
import { normalizeProcessingStatus } from "@/lib/utils/processingStatus"
import { getBookHref } from "@/lib/utils/bookRoutes"
import type { Book } from "@/types/book"

import {
  DOT_CLASSES,
  STATUS_LABELS,
  clampProgress,
  countWarnings,
  getBookWordCount,
  formatNumber,
  formatRelativeTime,
  getAccentClass,
  getBookUpdatedAt,
  getGenreLabel,
  getProgressLine,
  getProjectGlyph,
  getPublicSampleStatus,
  getStatusTooltip,
  storyUnitLabel,
} from "./LibraryClient.helpers"
import {
  AlertIcon,
  DotsIcon,
  FolderIcon,
  GroupIcon,
  PageIcon,
  PinIcon,
  PlusIcon,
  PlusLargeIcon,
  ProjectGlyph,
} from "./LibraryClient.icons"
import { MetaBadge, ProjectMenu, ProjectStatusBadge } from "./LibraryClient.projectActions"

type ProjectDisplayProps = {
  book: Book
  isDark: boolean
  busy: boolean
  isPinned: boolean
  menuOpen: boolean
  onMenuToggle: () => void
  onOpen: () => void
  onPrefetch: () => void
  onRetryProcessing: () => void
  onTogglePinned: () => void
  onArchive: () => void
  onRestore: () => void
  onRemove: () => void
  onPermanentDelete: () => void
  onAddChapter: () => void
  onPublish: () => void
  onUnpublish: () => void
}

function ProjectPrimaryLink({ book, onOpen, onPrefetch }: Pick<ProjectDisplayProps, "book" | "onOpen" | "onPrefetch">) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    onOpen()
  }

  return (
    <Link
      href={getBookHref(book) as Route}
      onClick={handleClick}
      onFocus={onPrefetch}
      className="absolute inset-0 z-10 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1f615d]/40"
      aria-label={`Open ${book.title}`}
    />
  )
}

export function EmptyPanel({
  isDark,
  title,
  body,
  actionLabel,
  actionHandler,
}: {
  isDark: boolean
  title: string
  body: string
  actionLabel?: string
  actionHandler?: () => void
}) {
  return (
    <div className={`rounded-sm border border-dashed px-6 py-16 text-center ${isDark ? "border-white/[0.08] bg-[#191d20]" : "border-stone-300 bg-[#fbfaf7]"}`}>
      <div className="mx-auto flex max-w-xl flex-col items-center">
        <div className={`flex h-14 w-14 items-center justify-center rounded-full ${isDark ? "bg-[#22272a] text-[#d0c8bc]" : "bg-[#eef3ef] text-[#1f615d]"}`}>
          <FolderIcon className="h-6 w-6" />
        </div>
        <p className={`mt-5 text-[1.75rem] font-semibold tracking-[-0.02em] ${isDark ? "text-[#f5f0e8]" : "text-stone-900"}`}>{title}</p>
        <p className={`mx-auto mt-3 max-w-lg text-sm leading-7 ${isDark ? "text-[#9f9b94]" : "text-stone-500"}`}>{body}</p>
        {actionLabel && actionHandler ? (
          <Button
            variant="secondary"
            size="md"
            onClick={actionHandler}
            className="mt-6 min-h-11 rounded-sm"
          >
            <PlusIcon />
            {actionLabel}
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function ProjectCard({
  book,
  isDark,
  busy,
  isPinned,
  menuOpen,
  onMenuToggle,
  onOpen,
  onPrefetch,
  onRetryProcessing,
  onTogglePinned,
  onArchive,
  onRestore,
  onRemove,
  onPermanentDelete,
  onAddChapter,
  onPublish,
  onUnpublish,
}: ProjectDisplayProps) {
  const accentClass = getAccentClass(book)
  const progress = clampProgress(book.progress_pct)
  const currentWords = getBookWordCount(book)
  const warningCount = countWarnings(book)
  const processingStatus = normalizeProcessingStatus(book.processing, book)
  const isArchived = !!book.archived_at
  const publicSampleStatus = getPublicSampleStatus(book)
  const unitLabel = storyUnitLabel(book.work_type, true)
  const toneClass = isDark ? "text-[#f5f0e8]" : "text-stone-950"
  const subtextClass = isDark ? "text-[#b8b2a8]" : "text-stone-600"
  const metaClass = isDark ? "text-[#9f9b94]" : "text-stone-500"
  return (
    <article
      onMouseEnter={onPrefetch}
      className={`group relative rounded-sm border p-4 transition duration-150 hover:border-[#9fc1be] focus-within:border-[#9fc1be] sm:p-5 ${
        isDark ? "border-white/[0.08] bg-[#101b24] hover:bg-[#13212b]" : "border-stone-200 bg-white hover:bg-[#fcfbf8]"
      }`}
    >
      <ProjectPrimaryLink book={book} onOpen={onOpen} onPrefetch={onPrefetch} />
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-md border ${accentClass}`}>
              <ProjectGlyph glyph={getProjectGlyph(book)} />
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2.5">
                <h3 className={`truncate text-lg font-semibold tracking-[-0.02em] ${toneClass}`}>
                  {book.title}
                </h3>
                <Tooltip content={`Status: ${STATUS_LABELS[book.status]} - ${getStatusTooltip(book.status)}`}>
                  <span className={`h-2 w-2 rounded-full ${DOT_CLASSES[book.status]}`} role="img" aria-label={`Status: ${STATUS_LABELS[book.status]}`} />
                </Tooltip>
                {isPinned ? (
                  <Tooltip content="Pinned project">
                    <span className="text-amber-300">
                      <PinIcon className="h-3.5 w-3.5" />
                    </span>
                  </Tooltip>
                ) : null}
              </div>
              <p className={`mt-1 truncate text-xs ${subtextClass}`}>
                {getGenreLabel(book)} <span className={metaClass}>·</span> {book.work_type === "screenplay" ? "Screenplay" : "Novel"}
              </p>
              <VisibilityBadge
                state={publicSampleStatus ? "public_sample" : book.collaboration_role ? "shared" : "private"}
                className="mt-2"
              />
            </div>
          </div>

          <div className="relative">
            <Tooltip content="Project actions" align="end">
              <Button
                variant="ghost"
                size="sm"
                onClick={(event) => {
                  event.stopPropagation()
                  onMenuToggle()
                }}
                className="relative z-20 rounded-sm p-2"
                aria-label={`Open actions for ${book.title}`}
                aria-expanded={menuOpen}
              >
                <DotsIcon />
              </Button>
            </Tooltip>

            {menuOpen ? (
              <ProjectMenu
                isDark={isDark}
                busy={busy}
                isPinned={isPinned}
                isArchived={isArchived}
                isAuthor={book.mode === "author"}
                isPublic={Boolean(book.is_public && book.public_status === "published")}
                workType={book.work_type}
                onTogglePinned={onTogglePinned}
                onArchive={onArchive}
                onRestore={onRestore}
                onRemove={onRemove}
                onPermanentDelete={onPermanentDelete}
                onAddChapter={onAddChapter}
                onPublish={onPublish}
                onUnpublish={onUnpublish}
              />
            ) : null}
          </div>
        </div>

        <p className={`mt-5 text-sm leading-6 ${subtextClass}`}>{getProgressLine(book)}</p>

        {processingStatus && !processingStatus.ready ? (
          <ProcessingStatusStrip
            status={processingStatus}
            retrying={busy}
            onRetry={processingStatus.retryAvailable ? onRetryProcessing : undefined}
            className="mt-4"
          />
        ) : null}

        <div className="mt-4 space-y-3">
          <ProjectStatusBadge status={book.status} isDark={isDark} />
          <div className={`h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`}>
            <div className="h-full rounded-full bg-[#1f615d]" style={{ width: `${progress}%` }} />
          </div>

          <div className={`flex items-center justify-between gap-4 text-sm ${subtextClass}`}>
            <span>{formatNumber(currentWords)} words</span>
            <span>{progress}% complete</span>
          </div>

          <p className={`text-sm ${metaClass}`}>{formatRelativeTime(getBookUpdatedAt(book))}</p>
        </div>

        <div className={`mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t pt-4 text-sm ${isDark ? "border-white/[0.08] text-[#b7b2aa]" : "border-stone-200 text-stone-600"}`}>
          <MetaBadge icon={<GroupIcon />} value={`${book.total_chapters ?? 0} ${unitLabel}`} />
          <MetaBadge icon={<PageIcon />} value={`${formatNumber(currentWords)} words`} />
          <MetaBadge icon={<AlertIcon />} value={`${warningCount} warnings`} />
        </div>
      </div>
    </article>
  )
}

export function ProjectRow({
  book,
  isDark,
  busy,
  isPinned,
  menuOpen,
  onMenuToggle,
  onOpen,
  onPrefetch,
  onRetryProcessing,
  onTogglePinned,
  onArchive,
  onRestore,
  onRemove,
  onPermanentDelete,
  onAddChapter,
  onPublish,
  onUnpublish,
}: ProjectDisplayProps) {
  const accentClass = getAccentClass(book)
  const progress = clampProgress(book.progress_pct)
  const currentWords = getBookWordCount(book)
  const isArchived = !!book.archived_at
  const processingStatus = normalizeProcessingStatus(book.processing, book)
  const publicSampleStatus = getPublicSampleStatus(book)
  const subtextClass = isDark ? "text-[#b8b2a8]" : "text-stone-600"
  const metaClass = isDark ? "text-[#9f9b94]" : "text-stone-500"
  return (
    <article
      onMouseEnter={onPrefetch}
      className={`relative rounded-sm border px-5 py-5 transition hover:border-[#9fc1be] focus-within:border-[#9fc1be] ${isDark ? "border-white/[0.08] bg-[#101b24] hover:bg-[#13212b]" : "border-stone-200 bg-white hover:bg-[#fcfbf8]"}`}
    >
      <ProjectPrimaryLink book={book} onOpen={onOpen} onPrefetch={onPrefetch} />
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-md border ${accentClass}`}>
            <ProjectGlyph glyph={getProjectGlyph(book)} />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <h3 className={`truncate text-lg font-semibold tracking-[-0.02em] ${isDark ? "text-[#f5f0e8]" : "text-stone-950"}`}>{book.title}</h3>
              <Tooltip content={`Status: ${STATUS_LABELS[book.status]} - ${getStatusTooltip(book.status)}`}>
                <span className={`h-2 w-2 rounded-full ${DOT_CLASSES[book.status]}`} role="img" aria-label={`Status: ${STATUS_LABELS[book.status]}`} />
              </Tooltip>
              {isPinned ? (
                <Tooltip content="Pinned project">
                  <span className="text-amber-300">
                    <PinIcon className="h-3.5 w-3.5" />
                  </span>
                </Tooltip>
              ) : null}
            </div>
            <p className={`mt-1 truncate text-xs ${subtextClass}`}>
              {getGenreLabel(book)} <span className={metaClass}>·</span> {book.work_type === "screenplay" ? "Screenplay" : "Novel"}
            </p>
            <VisibilityBadge
              state={publicSampleStatus ? "public_sample" : book.collaboration_role ? "shared" : "private"}
              className="mt-2"
            />
            <div className="mt-2">
              <ProjectStatusBadge status={book.status} isDark={isDark} />
            </div>
            <p className={`mt-1.5 text-sm ${metaClass}`}>{getProgressLine(book)}</p>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-3 xl:max-w-[32rem]">
          <div className={`h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`}>
            <div className="h-full rounded-full bg-[#1f615d]" style={{ width: `${progress}%` }} />
          </div>
          <div className={`flex flex-wrap items-center gap-x-5 gap-y-2 text-sm ${subtextClass}`}>
            <span>{formatNumber(currentWords)} words</span>
            <span>{progress}% complete</span>
            <span>{formatRelativeTime(getBookUpdatedAt(book))}</span>
          </div>
          {processingStatus && !processingStatus.ready ? (
            <ProcessingStatusStrip
              status={processingStatus}
              retrying={busy}
              onRetry={processingStatus.retryAvailable ? onRetryProcessing : undefined}
            />
          ) : null}
        </div>

        <div className="relative z-20 flex items-center justify-between gap-3 xl:justify-end">
          {book.mode === "author" ? (
            <Tooltip content={`Add a ${storyUnitLabel(book.work_type)} to this project`}>
              <Button
                variant="ghost"
                size="sm"
                onClick={(event) => {
                  event.stopPropagation()
                  onAddChapter()
                }}
                className="relative z-10 rounded-sm"
              >
                Add {storyUnitLabel(book.work_type)}
              </Button>
            </Tooltip>
          ) : null}

          <div className="relative">
            <Tooltip content="Project actions" align="end">
              <Button
                variant="ghost"
                size="sm"
                onClick={(event) => {
                  event.stopPropagation()
                  onMenuToggle()
                }}
                className="relative z-20 rounded-sm p-2"
                aria-label={`Open actions for ${book.title}`}
                aria-expanded={menuOpen}
              >
                <DotsIcon />
              </Button>
            </Tooltip>

            {menuOpen ? (
              <ProjectMenu
                isDark={isDark}
                busy={busy}
                isPinned={isPinned}
                isArchived={isArchived}
                isAuthor={book.mode === "author"}
                isPublic={Boolean(book.is_public && book.public_status === "published")}
                workType={book.work_type}
                onTogglePinned={onTogglePinned}
                onArchive={onArchive}
                onRestore={onRestore}
                onRemove={onRemove}
                onPermanentDelete={onPermanentDelete}
                onAddChapter={onAddChapter}
                onPublish={onPublish}
                onUnpublish={onUnpublish}
              />
            ) : null}
          </div>
        </div>
      </div>
    </article>
  )
}

export function CreateProjectCard({ isDark, onCreate }: { isDark: boolean; onCreate: () => void }) {
  return (
    <button
      type="button"
      onClick={onCreate}
      className={`flex min-h-[18.25rem] w-full flex-col items-center justify-center rounded-sm border border-dashed p-8 text-center transition ${
        isDark
          ? "border-white/[0.08] bg-[#191d20] hover:border-[#3d7a75] hover:bg-[#1f2427]"
          : "border-stone-300 bg-[#fbfaf7] hover:border-[#9fc1be] hover:bg-white"
      }`}
      aria-label="Create new project"
    >
      <div className={`flex h-16 w-16 items-center justify-center rounded-md border ${isDark ? "border-white/[0.08] bg-[#202528] text-[#d0c8bc]" : "border-stone-200 bg-white text-[#1f615d]"}`}>
        <PlusLargeIcon />
      </div>
      <h3 className={`mt-6 text-xl font-semibold tracking-[-0.02em] ${isDark ? "text-[#f7f3ed]" : "text-stone-900"}`}>Create New Project</h3>
      <p className={`mt-2 text-sm leading-7 ${isDark ? "text-[#9f9b94]" : "text-stone-500"}`}>Start a new story</p>
    </button>
  )
}

export function CreateProjectRow({ isDark, onCreate }: { isDark: boolean; onCreate: () => void }) {
  return (
    <button
      type="button"
      onClick={onCreate}
      className={`flex w-full items-center justify-between rounded-sm border border-dashed px-5 py-5 text-left transition ${
        isDark
          ? "border-white/[0.08] bg-[#191d20] hover:border-[#3d7a75] hover:bg-[#1f2427]"
          : "border-stone-300 bg-[#fbfaf7] hover:border-[#9fc1be] hover:bg-white"
      }`}
      aria-label="Create new project"
    >
      <div>
        <h3 className={`text-lg font-semibold tracking-[-0.02em] ${isDark ? "text-[#f7f3ed]" : "text-stone-900"}`}>Create New Project</h3>
        <p className={`mt-1 text-sm ${isDark ? "text-[#9f9b94]" : "text-stone-500"}`}>Start a new story</p>
      </div>
      <div className={`flex h-12 w-12 items-center justify-center rounded-sm border ${isDark ? "border-white/[0.08] bg-[#202528] text-[#d0c8bc]" : "border-stone-200 bg-white text-[#1f615d]"}`}>
        <PlusLargeIcon />
      </div>
    </button>
  )
}
