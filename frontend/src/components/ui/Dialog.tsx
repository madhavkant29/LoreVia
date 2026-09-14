"use client"

import * as DialogPrimitive from "@radix-ui/react-dialog"
import { useRef, type ReactNode, type RefObject } from "react"

import { cn } from "@/lib/utils/text"

type DialogSize = "sm" | "md" | "lg" | "xl"

const sizeClasses: Record<DialogSize, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  eyebrow,
  children,
  footer,
  size = "md",
  closeOnOutside = true,
  initialFocusRef,
  className,
  contentClassName,
  titleClassName,
  descriptionClassName,
}: {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  eyebrow?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  size?: DialogSize
  closeOnOutside?: boolean
  initialFocusRef?: RefObject<HTMLElement | null>
  className?: string
  contentClassName?: string
  titleClassName?: string
  descriptionClassName?: string
}) {
  const previousFocusRef = useRef<HTMLElement | null>(null)
  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose()
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[90] bg-black/60 data-[state=open]:animate-in data-[state=closed]:animate-out motion-reduce:animate-none" />
        <DialogPrimitive.Content
          onOpenAutoFocus={(event) => {
            previousFocusRef.current = document.activeElement instanceof HTMLElement
              ? document.activeElement
              : null
            if (!initialFocusRef?.current) return
            event.preventDefault()
            initialFocusRef.current.focus()
          }}
          onCloseAutoFocus={(event) => {
            if (!previousFocusRef.current) return
            event.preventDefault()
            previousFocusRef.current.focus()
          }}
          onPointerDownOutside={(event) => {
            if (!closeOnOutside) event.preventDefault()
          }}
          onInteractOutside={(event) => {
            if (!closeOnOutside) event.preventDefault()
          }}
          className={cn(
            "fixed left-1/2 top-1/2 z-[91] max-h-[calc(100dvh-3rem)] w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-sm border border-[rgba(var(--border),0.5)] bg-[rgb(var(--card))] text-[rgb(var(--card-foreground))] shadow-[var(--shadow-modal)] outline-none",
            sizeClasses[size],
            className,
          )}
        >
          <div className={cn("p-6", contentClassName)}>
            {eyebrow ? <p className="app-eyebrow">{eyebrow}</p> : null}
            <DialogPrimitive.Title className={cn("mt-3 text-2xl font-semibold tracking-normal", titleClassName)}>
              {title}
            </DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className={cn("mt-4 text-sm leading-7 text-[rgb(var(--muted-foreground))]", descriptionClassName)}>
                {description}
              </DialogPrimitive.Description>
            ) : null}
            {children}
            {footer ? <div className="mt-6">{footer}</div> : null}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
