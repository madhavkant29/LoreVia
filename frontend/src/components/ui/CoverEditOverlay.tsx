"use client"

import { Pencil, Trash2, Upload } from "lucide-react"
import { useRef, useState, type ChangeEvent } from "react"

import { DisclosureMenu } from "@/components/ui/DisclosureMenu"
import { booksApi } from "@/lib/api/books"
import { validateCoverFile } from "@/lib/validation/manuscriptUpload"
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
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const validationError = validateCoverFile(file)
    if (validationError) {
      setError(validationError)
      if (fileInputRef.current) fileInputRef.current.value = ""
      return
    }

    try {
      setError(null)
      setUploading(true)
      onCoverUpdated(await booksApi.updateCover(bookId, file))
    } catch {
      setError("The cover could not be updated. Check your connection and try again.")
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  const handleRemove = async () => {
    try {
      setError(null)
      setUploading(true)
      onCoverUpdated(await booksApi.deleteCover(bookId))
    } catch {
      setError("The cover could not be removed. Check your connection and try again.")
    } finally {
      setUploading(false)
    }
  }

  return (
    <>
      <div className="absolute right-1 top-1 z-20">
        <DisclosureMenu
          label="Edit cover photo"
          disabled={uploading}
          items={[
            {
              id: "upload",
              label: "Upload new photo",
              icon: <Upload className="h-4 w-4" />,
              onSelect: () => fileInputRef.current?.click(),
            },
            ...(hasCover
              ? [{ id: "remove", label: "Remove cover photo", icon: <Trash2 className="h-4 w-4" />, tone: "danger" as const, onSelect: () => void handleRemove() }]
              : []),
          ]}
          trigger={<Pencil className="h-3.5 w-3.5" aria-hidden="true" />}
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-full border shadow-sm transition disabled:cursor-wait disabled:opacity-60",
            isDark
              ? "border-white/20 bg-slate-800/90 text-slate-200 hover:bg-slate-700"
              : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100",
          )}
          menuClassName="w-52"
        />
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(event) => void handleFileChange(event)}
      />

      {error ? (
        <p role="alert" className="absolute left-1 right-1 top-12 z-20 rounded-md bg-red-600/95 px-2 py-1 text-[11px] text-white shadow-sm">
          {error}
        </p>
      ) : null}
    </>
  )
}
