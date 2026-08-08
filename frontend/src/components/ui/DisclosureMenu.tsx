"use client"

import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import Link from "next/link"
import type { Route } from "next"
import { useState, type ReactNode } from "react"

import { cn } from "@/lib/utils/text"

export type DisclosureMenuItem = {
  id: string
  label: string
  description?: string
  icon?: ReactNode
  href?: Route | string
  onSelect?: () => void
  disabled?: boolean
  tone?: "default" | "danger"
}

export function DisclosureMenu({
  label,
  trigger,
  items,
  align = "end",
  side = "bottom",
  className,
  menuClassName,
  onOpenChange,
  disabled = false,
}: {
  label: string
  trigger: ReactNode
  items: DisclosureMenuItem[]
  align?: "start" | "end"
  side?: "top" | "bottom"
  className?: string
  menuClassName?: string
  onOpenChange?: (open: boolean) => void
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const setMenuOpen = (next: boolean) => {
    setOpen(next)
    onOpenChange?.(next)
  }
  const itemClass = (item: DisclosureMenuItem) => cn(
    "block w-full rounded-md px-3 py-2.5 text-left text-sm tracking-normal outline-none transition data-[highlighted]:bg-[rgba(var(--foreground),0.06)] data-[highlighted]:ring-2 data-[highlighted]:ring-[rgb(var(--accent))]",
    item.tone === "danger" ? "text-red-500" : "text-[rgb(var(--foreground))]",
    item.disabled && "cursor-not-allowed opacity-50",
  )

  return (
    <DropdownMenu.Root open={open} onOpenChange={setMenuOpen}>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={label}
          disabled={disabled}
          className={cn(
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--accent))] focus-visible:ring-offset-2",
            className,
          )}
        >
          {trigger}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align={align}
          side={side}
          sideOffset={8}
          collisionPadding={12}
          aria-label={label}
          className={cn(
            "z-[95] min-w-56 rounded-lg border border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] p-1.5 shadow-[var(--shadow-dropdown)]",
            menuClassName,
          )}
        >
          {items.map((item) => {
            const content = (
              <span className="flex items-start gap-2.5">
                {item.icon ? <span className="mt-0.5 shrink-0" aria-hidden="true">{item.icon}</span> : null}
                <span>
                  <span className="block font-medium">{item.label}</span>
                  {item.description ? (
                    <span className="mt-0.5 block text-xs leading-5 text-[rgb(var(--muted-foreground))]">{item.description}</span>
                  ) : null}
                </span>
              </span>
            )
            if (item.href && !item.disabled) {
              return (
                <DropdownMenu.Item key={item.id} asChild className={itemClass(item)}>
                  <Link href={item.href as Route}>{content}</Link>
                </DropdownMenu.Item>
              )
            }
            return (
              <DropdownMenu.Item
                key={item.id}
                disabled={item.disabled}
                className={itemClass(item)}
                onSelect={() => item.onSelect?.()}
              >
                {content}
              </DropdownMenu.Item>
            )
          })}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
