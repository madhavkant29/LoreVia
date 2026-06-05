"use client"

import Link from "next/link"

import { Button } from "@/components/ui/Button"
import { choosePrimaryEmptyStateAction } from "@/lib/utils/uxActions"
import type { SmartEmptyStateAction } from "@/types/ux"

export function ActionableEmptyState({
  title,
  body,
  actions,
  className = "",
}: {
  title: string
  body: string
  actions: SmartEmptyStateAction[]
  className?: string
}) {
  const primary = choosePrimaryEmptyStateAction(actions)
  const secondary = actions.find((action) => action !== primary)

  return (
    <div className={`app-empty-state ${className}`}>
      <p className="text-lg font-semibold text-[rgb(var(--foreground))]">{title}</p>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">{body}</p>
      {primary || secondary ? (
        <div className="mt-5 flex flex-col items-center justify-center gap-3 sm:flex-row">
          {primary ? <EmptyStateButton action={primary} variant="primary" /> : null}
          {secondary ? <EmptyStateButton action={secondary} variant="secondary" /> : null}
        </div>
      ) : null}
    </div>
  )
}

function EmptyStateButton({
  action,
  variant,
}: {
  action: SmartEmptyStateAction
  variant: "primary" | "secondary"
}) {
  if (action.href) {
    return (
      <Link href={action.href} className={variant === "primary" ? "app-button-primary" : "app-button-secondary"}>
        {action.label}
      </Link>
    )
  }

  return (
    <Button type="button" variant={variant} onClick={action.onClick}>
      {action.label}
    </Button>
  )
}
