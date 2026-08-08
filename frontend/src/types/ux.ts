import type { Route } from "next"
import type { ReactNode } from "react"

export type CommandAction = {
  id: string
  label: string
  description?: string
  href?: Route
  keywords?: string[]
  group?: string
  shortcut?: string
  run?: () => void
}

export type RecentActivityItem = {
  id: string
  label: string
  detail?: string
  href?: Route
  timestamp?: string | null
  tone?: "default" | "success" | "warning" | "danger"
}

export type NextBestAction = {
  id: string
  label: string
  description?: string
  href?: Route
  onSelect?: () => void
  tone?: "primary" | "secondary" | "danger"
  fingerprint?: string
}

export type ConfirmDialogConfig = {
  title: string
  body: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: "default" | "danger"
}

export type PromptDialogConfig = {
  title: string
  body?: ReactNode
  label: string
  initialValue?: string
  placeholder?: string
  confirmLabel?: string
  cancelLabel?: string
  multiline?: boolean
  validate?: (value: string) => string | null
}

export type ToastMessage = {
  id: string
  title?: string
  body: string
  tone?: "default" | "success" | "warning" | "danger"
  actionLabel?: string
  onAction?: () => void
}

export type SmartEmptyStateAction = {
  label: string
  href?: Route
  onClick?: () => void
  tone?: "primary" | "secondary"
}

export type ShortcutDefinition = {
  id: string
  label: string
  keys: string
  description?: string
}
