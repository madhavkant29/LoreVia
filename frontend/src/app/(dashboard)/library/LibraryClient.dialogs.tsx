import { useRef } from "react"

import { Button } from "@/components/ui/Button"
import { Dialog } from "@/components/ui/Dialog"
import type { Book } from "@/types/book"

type LibraryDialogThemeProps = {
  surfaceClass: string
  mutedText: string
  headingText: string
  controlClass: string
}

export function PublishBookDialog({
  surfaceClass,
  headingText,
  controlClass,
  publishSlug,
  publishDescription,
  publishConfirmed,
  error,
  busy,
  onSlugChange,
  onDescriptionChange,
  onConfirmedChange,
  onCancel,
  onPublish,
}: LibraryDialogThemeProps & {
  publishSlug: string
  publishDescription: string
  publishConfirmed: boolean
  error?: string | null
  busy: boolean
  onSlugChange: (value: string) => void
  onDescriptionChange: (value: string) => void
  onConfirmedChange: (value: boolean) => void
  onCancel: () => void
  onPublish: () => void
}) {
  return (
    <Dialog
      open
      onClose={onCancel}
      title="Publish your own original work"
      description="Private Workspace and Public Book are different states. Publish only content you own or have explicit permission to share."
      eyebrow="Public book"
      size="lg"
      className={surfaceClass}
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="secondary" size="md" onClick={onCancel} className="rounded-sm">Cancel</Button>
          <Button
            variant="primary"
            size="md"
            disabled={!publishConfirmed || !publishSlug.trim()}
            busy={busy}
            busyLabel="Publishing..."
            onClick={onPublish}
            className="rounded-sm"
          >
            Publish publicly
          </Button>
        </div>
      }
    >
        {error ? <p role="alert" className="mt-4 text-sm text-rose-700 dark:text-rose-300">{error}</p> : null}
        <div className="mt-6 grid gap-4">
          <label className="grid gap-2 text-sm">
            <span className={headingText}>Public URL slug</span>
            <input value={publishSlug} onChange={(event) => onSlugChange(event.target.value)} className={`rounded-sm border px-4 py-3 ${controlClass}`} />
          </label>
          <label className="grid gap-2 text-sm">
            <span className={headingText}>Public description</span>
            <textarea value={publishDescription} onChange={(event) => onDescriptionChange(event.target.value)} rows={4} className={`rounded-sm border px-4 py-3 ${controlClass}`} />
          </label>
          <label className={`flex items-start gap-3 rounded-sm border px-4 py-3 text-sm leading-7 ${controlClass}`}>
            <input type="checkbox" checked={publishConfirmed} onChange={(event) => onConfirmedChange(event.target.checked)} className="mt-1" />
            <span>I confirm that I own the rights to this content or have permission to upload and publish it on LoreVia.</span>
          </label>
        </div>
    </Dialog>
  )
}

export function PermanentDeleteBookDialog({
  book,
  surfaceClass,
  headingText,
  controlClass,
  deleteConfirmation,
  deleteError,
  busy,
  onConfirmationChange,
  onCancel,
  onConfirm,
}: LibraryDialogThemeProps & {
  book: Book
  deleteConfirmation: string
  deleteError: string | null
  busy: boolean
  onConfirmationChange: (value: string) => void
  onCancel: () => void
  onConfirm: () => void
}) {
  const confirmationRef = useRef<HTMLInputElement | null>(null)
  return (
    <Dialog
      open
      onClose={onCancel}
      title={`Delete ${book.title} permanently?`}
      description={<>This deletes the manuscript and generated project data. Type <span className={headingText}>DELETE BOOK</span> to confirm.</>}
      eyebrow="Permanent deletion"
      closeOnOutside={false}
      initialFocusRef={confirmationRef}
      className={surfaceClass}
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="secondary" size="md" onClick={onCancel} className="rounded-sm">Cancel</Button>
          <Button variant="danger" size="md" busy={busy} busyLabel="Deleting..." onClick={onConfirm} className="rounded-sm">
            Delete permanently
          </Button>
        </div>
      }
    >
        <label className="mt-5 grid gap-2 text-sm">
          <span className={headingText}>Confirmation phrase</span>
          <input
            ref={confirmationRef}
            value={deleteConfirmation}
            onChange={(event) => onConfirmationChange(event.target.value)}
            aria-invalid={deleteError ? "true" : "false"}
            aria-describedby={deleteError ? "permanent-delete-error" : undefined}
            className={`rounded-sm border px-4 py-3 ${controlClass}`}
          />
        </label>
        {deleteError ? (
          <p id="permanent-delete-error" className="mt-3 text-sm text-rose-300">
            {deleteError}
          </p>
        ) : null}
    </Dialog>
  )
}
