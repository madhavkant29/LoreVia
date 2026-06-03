import type { ButtonHTMLAttributes, ReactNode } from "react"

import { cn } from "@/lib/utils/text"

export function WorkspacePage({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("app-shell", className)}>
      <div className="app-container">{children}</div>
    </div>
  )
}

export function WorkspacePanel({
  children,
  className,
  tone = "default",
}: {
  children: ReactNode
  className?: string
  tone?: "default" | "strong" | "subtle"
}) {
  return (
    <section
      className={cn(
        tone === "strong"
          ? "app-panel app-panel--strong"
          : tone === "subtle"
            ? "app-panel app-panel--subtle"
            : "app-panel",
        className
      )}
    >
      {children}
    </section>
  )
}

export function WorkspaceHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  className,
}: {
  eyebrow: string
  title: string
  description?: string
  actions?: ReactNode
  meta?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between", className)}>
      <div className="max-w-3xl">
        <p className="app-eyebrow">{eyebrow}</p>
        <h1 className="app-title mt-3">{title}</h1>
        {description ? <p className="app-copy mt-4 max-w-2xl">{description}</p> : null}
      </div>

      {actions || meta ? (
        <div className="flex flex-col gap-3 sm:items-end">
          {actions}
          {meta}
        </div>
      ) : null}
    </div>
  )
}

export function WorkspaceMetric({
  label,
  value,
  note,
  accent = "default",
  className,
}: {
  label: string
  value: string
  note?: string
  accent?: "default" | "accent" | "success" | "warning"
  className?: string
}) {
  return (
    <div className={cn("app-stat", accentClassName(accent), className)}>
      <p className="app-stat__label">{label}</p>
      <p className="app-stat__value">{value}</p>
      {note ? <p className="app-stat__note">{note}</p> : null}
    </div>
  )
}

export function WorkspaceEmptyState({
  title,
  body,
  className,
}: {
  title: string
  body: string
  className?: string
}) {
  return (
    <div className={cn("app-empty-state", className)}>
      <p className="text-lg font-semibold text-[rgb(var(--foreground))]">{title}</p>
      <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">{body}</p>
    </div>
  )
}

export function WorkspaceTabButton({
  active,
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean
}) {
  return (
    <button
      className={cn("app-tab", active && "app-tab--active", className)}
      type="button"
      {...props}
    >
      {children}
    </button>
  )
}

function accentClassName(accent: "default" | "accent" | "success" | "warning") {
  switch (accent) {
    case "accent":
      return "app-stat--accent"
    case "success":
      return "app-stat--success"
    case "warning":
      return "app-stat--warning"
    default:
      return ""
  }
}
