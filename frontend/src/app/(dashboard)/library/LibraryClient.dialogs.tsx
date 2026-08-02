import { Button } from "@/components/ui/Button"
import type { Book } from "@/types/book"

type LibraryDialogThemeProps = {
  surfaceClass: string
  mutedText: string
  headingText: string
  controlClass: string
}

export function PublishBookDialog({
  surfaceClass,
  mutedText,
  headingText,
  controlClass,
  publishSlug,
  publishDescription,
  publishConfirmed,
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
  busy: boolean
  onSlugChange: (value: string) => void
  onDescriptionChange: (value: string) => void
  onConfirmedChange: (value: boolean) => void
  onCancel: () => void
  onPublish: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8">
      <div className={`w-full max-w-2xl rounded-sm border p-6 sm:p-7 ${surfaceClass}`}>
        <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.24em] ${mutedText}`}>Public book</p>
        <h2 className={`mt-3 font-display text-[2rem] tracking-[-0.03em] ${headingText}`}>Publish your own original work</h2>
        <p className={`mt-3 text-sm leading-7 ${mutedText}`}>
          Private Workspace and Public Book are different states. Do not publish books, chapters, EPUBs, web novels, paid content, or third-party works unless you own the rights or have explicit permission.
        </p>
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
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="secondary"
            size="md"
            onClick={onCancel}
            className="rounded-sm"
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="md"
            disabled={!publishConfirmed || !publishSlug.trim() || busy}
            onClick={onPublish}
            className="rounded-sm"
          >
            Publish publicly
          </Button>
        </div>
      </div>
    </div>
  )
}

export function PermanentDeleteBookDialog({
  book,
  surfaceClass,
  mutedText,
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
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8" role="presentation">
      <section
        aria-modal="true"
        role="dialog"
        aria-labelledby="permanent-delete-title"
        aria-describedby="permanent-delete-description"
        className={`w-full max-w-lg rounded-sm border p-6 sm:p-7 ${surfaceClass}`}
      >
        <p className="app-eyebrow text-rose-300">Permanent deletion</p>
        <h2 id="permanent-delete-title" className={`mt-3 font-display text-[1.8rem] tracking-[-0.03em] ${headingText}`}>
          Delete {book.title} permanently?
        </h2>
        <p id="permanent-delete-description" className={`mt-3 text-sm leading-7 ${mutedText}`}>
          This deletes the manuscript and generated project data. Type <span className={headingText}>DELETE BOOK</span> to confirm.
        </p>
        <label className="mt-5 grid gap-2 text-sm">
          <span className={headingText}>Confirmation phrase</span>
          <input
            autoFocus
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
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="secondary"
            size="md"
            onClick={onCancel}
            className="rounded-sm"
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            size="md"
            disabled={busy}
            onClick={onConfirm}
            className="rounded-sm"
          >
            Delete permanently
          </Button>
        </div>
      </section>
    </div>
  )
}
