"use client"

import Link from "next/link"
import { MoreHorizontal } from "lucide-react"

import { Button } from "@/components/ui/Button"
import { DisclosureMenu, type DisclosureMenuItem } from "@/components/ui/DisclosureMenu"
import type { NextBestAction } from "@/types/ux"

export function MobileActionBar({
  actions,
  moreActions = [],
}: {
  actions: NextBestAction[]
  moreActions?: NextBestAction[]
}) {
  const primaryActions = actions.slice(0, 2)
  const overflowActions = [...actions.slice(2), ...moreActions]
  if (primaryActions.length === 0 && overflowActions.length === 0) return null
  const menuItems: DisclosureMenuItem[] = overflowActions.map((action) => ({
    id: action.id,
    label: action.label,
    description: action.description,
    href: action.href,
    onSelect: action.onSelect,
    tone: action.tone === "danger" ? "danger" : "default",
  }))

  return (
    <nav aria-label="Primary actions" className="fixed inset-x-0 bottom-0 z-40 border-t border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))]/95 px-4 py-3 backdrop-blur md:hidden">
      <div className="mx-auto flex max-w-xl gap-2">
        {primaryActions.map((action) => {
          const variant = action.tone === "danger" ? "danger" : action.tone === "secondary" ? "secondary" : "primary"
          if (action.href) {
            return (
              <Link
                key={action.id}
                href={action.href}
                className={variant === "primary" ? "app-button-primary flex-1 py-3" : "app-button-secondary flex-1 py-3"}
              >
                {action.label}
              </Link>
            )
          }
          return (
            <Button key={action.id} type="button" variant={variant} onClick={action.onSelect} className="flex-1">
              {action.label}
            </Button>
          )
        })}
        {menuItems.length ? (
          <DisclosureMenu
            label="More actions"
            side="top"
            items={menuItems}
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] text-[rgb(var(--foreground))]"
            trigger={<MoreHorizontal className="h-5 w-5" aria-hidden="true" />}
          />
        ) : null}
      </div>
    </nav>
  )
}
