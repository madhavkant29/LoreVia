"use client"

import React, { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { booksApi } from "@/lib/api/books"
import { cn } from "@/lib/utils/text"
import type { Book } from "@/types/book"

interface CoverEditOverlayProps {
  bookId: string
  isDark?: boolean
  hasCover: boolean
  onCoverUpdated: (book: Book) => void
}

export function CoverEditOverlay({
  bookId,
  isDark = false,
  hasCover,
  onCoverUpdated,
}: CoverEditOverlayProps) {
  const [open, setOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({})
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      setOpen(false)
      const updated = await booksApi.updateCover(bookId, file)
      onCoverUpdated(updated)
    } catch {
      // silently ignore, the cover will remain unchanged
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    }
  }

  const handleRemove = async () => {
    try {
      setUploading(true)
      setOpen(false)
      const updated = await booksApi.deleteCover(bookId)
      onCoverUpdated(updated)
    } catch {
      // silently ignore
    } finally {
      setUploading(false)
    }
  }

  useEffect(() => {
    if (!open || !buttonRef.current) return

    const rect = buttonRef.current.getBoundingClientRect()
    setMenuStyle({
      position: "fixed",
      top: rect.bottom + 4,
      right: window.innerWidth - rect.right,
      zIndex: 50,
    })
  }, [open])

  useEffect(() => {
    if (!open) return

    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setOpen(false)
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    document.addEventListener("keydown", handleEscape)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
      document.removeEventListener("keydown", handleEscape)
    }
  }, [open])

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        disabled={uploading}
        aria-label="Edit cover photo"
        className={cn(
          "absolute z-20 flex h-7 w-7 items-center justify-center rounded-full border shadow-sm transition",
          "right-1 top-1",
          isDark
            ? "border-white/20 bg-slate-800/80 text-slate-200 hover:bg-slate-700"
            : "border-slate-300 bg-white/90 text-slate-600 hover:bg-slate-100",
        )}
      >
        <PencilIcon className="h-3.5 w-3.5" />
      </button>

      {open &&
        createPortal(
          <div
            ref={menuRef}
            role="dialog"
            aria-label="Cover photo options"
            style={menuStyle}
            className={cn(
              "w-48 overflow-hidden rounded-lg border py-1 shadow-lg",
              isDark
                ? "border-white/10 bg-slate-800 text-slate-200"
                : "border-slate-200 bg-white text-slate-800",
            )}
          >
            <button
              type="button"
              onClick={handleUploadClick}
              className={cn(
                "flex w-full items-center gap-2.5 px-3 py-2.5 text-sm transition",
                isDark ? "hover:bg-white/[0.06]" : "hover:bg-slate-50",
              )}
            >
              <UploadIcon className="h-4 w-4" />
              Upload new photo
            </button>
            {hasCover ? (
              <button
                type="button"
                onClick={handleRemove}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2.5 text-sm transition",
                  isDark
                    ? "text-red-400 hover:bg-white/[0.06]"
                    : "text-red-600 hover:bg-red-50",
                )}
              >
                <TrashIcon className="h-4 w-4" />
                Remove cover photo
              </button>
            ) : null}
          </div>,
          document.body,
        )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={handleFileChange}
      />
    </>
  )
}

function PencilIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
      />
    </svg>
  )
}

function UploadIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
      />
    </svg>
  )
}

function TrashIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  )
}
