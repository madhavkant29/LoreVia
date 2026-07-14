import type { ReactNode } from "react"

import { Button } from "@/components/ui/Button"
import { Tooltip } from "@/components/ui/Tooltip"
import type { Book, BookStatus } from "@/types/book"

import {
  STATUS_LABELS,
  getStatusBadgeClass,
  getStatusTooltip,
  storyUnitLabel,
} from "./LibraryClient.helpers"

export function ProjectMenu({
  isDark,
  busy,
  isPinned,
  isArchived,
  isAuthor,
  isPublic,
  workType,
  onTogglePinned,
  onArchive,
  onRestore,
  onRemove,
  onPermanentDelete,
  onAddChapter,
  onPublish,
  onUnpublish,
}: {
  isDark: boolean
  busy: boolean
  isPinned: boolean
  isArchived: boolean
  isAuthor: boolean
  isPublic: boolean
  workType: Book["work_type"]
  onTogglePinned: () => void
  onArchive: () => void
  onRestore: () => void
  onRemove: () => void
  onPermanentDelete: () => void
  onAddChapter: () => void
  onPublish: () => void
  onUnpublish: () => void
}) {
  return (
    <div
      onClick={(event) => event.stopPropagation()}
      className={`absolute right-0 top-full z-30 mt-2 w-48 rounded-md border py-2 ${isDark ? "border-white/[0.08] bg-[#1b2023]" : "border-stone-200 bg-white"}`}
    >
      <MenuButton isDark={isDark} onClick={onTogglePinned} label={isPinned ? "Unpin project" : "Pin project"} tooltip={isPinned ? "Remove this shortcut" : "Keep this project near the top"} />
      {isAuthor ? <MenuButton isDark={isDark} onClick={onAddChapter} label={`Add ${storyUnitLabel(workType)}`} tooltip="Import or draft the next unit" /> : null}
      {isAuthor ? <MenuButton isDark={isDark} onClick={isPublic ? onUnpublish : onPublish} label={isPublic ? "Unpublish public book" : "Publish publicly"} disabled={busy} tooltip={isPublic ? "Take the public sample offline" : "Review rights before publishing"} /> : null}
      {isArchived ? (
        <MenuButton isDark={isDark} onClick={onRestore} label="Restore" disabled={busy} tooltip="Move this project back into active views" />
      ) : (
        <MenuButton isDark={isDark} onClick={onArchive} label="Archive" disabled={busy} tooltip="Hide from active views without deleting" />
      )}
      <MenuButton isDark={isDark} onClick={onRemove} label="Remove" disabled={busy} danger tooltip="Remove from this library view" />
      <MenuButton isDark={isDark} onClick={onPermanentDelete} label="Delete permanently" disabled={busy} danger tooltip="Delete manuscript and generated project data" />
    </div>
  )
}

function MenuButton({
  isDark,
  onClick,
  label,
  tooltip,
  disabled = false,
  danger = false,
}: {
  isDark: boolean
  onClick: () => void
  label: string
  tooltip?: string
  disabled?: boolean
  danger?: boolean
}) {
  return (
    <Tooltip content={tooltip ?? label} align="end" className="w-full">
      <Button
        variant="ghost"
        size="md"
        onClick={(event) => {
          event.stopPropagation()
          onClick()
        }}
        disabled={disabled}
        className={`w-full justify-start rounded-none ${
          danger
            ? isDark
              ? "text-rose-300 hover:bg-rose-500/10"
              : "text-rose-600 hover:bg-rose-50"
            : isDark
              ? "text-[#efe9df] hover:bg-white/[0.06]"
              : "text-stone-700 hover:bg-stone-50"
        }`}
      >
        {label}
      </Button>
    </Tooltip>
  )
}

export function MetaBadge({ icon, value }: { icon: ReactNode; value: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span>{icon}</span>
      <span>{value}</span>
    </div>
  )
}

export function ProjectStatusBadge({ status, isDark }: { status: BookStatus; isDark: boolean }) {
  return (
    <Tooltip content={`Status: ${STATUS_LABELS[status]} - ${getStatusTooltip(status)}`}>
      <span className={`inline-flex rounded-md px-2.5 py-1 text-xs font-semibold ${getStatusBadgeClass(status, isDark)}`}>
        {STATUS_LABELS[status]}
      </span>
    </Tooltip>
  )
}
