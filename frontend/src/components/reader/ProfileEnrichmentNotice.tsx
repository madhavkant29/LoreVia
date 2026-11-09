import Link from "next/link"

import type { BookProcessing } from "@/types/book"

type Props = {
  processing?: BookProcessing | null
  bookId: string
  isDark: boolean
  onReview?: () => void
}

export function ProfileEnrichmentNotice({ processing, bookId, isDark, onReview }: Props) {
  const invalidBatches = processing?.parser_diagnostics?.character_extraction?.totals?.invalid_profile_batches ?? 0
  if (invalidBatches <= 0) return null

  return (
    <div role="alert" className={`rounded-sm border px-4 py-3 text-sm ${isDark ? "border-amber-400/50 bg-amber-950/30 text-amber-100" : "border-amber-600/50 bg-amber-50 text-amber-950"}`}>
      <strong>Some character profiles are incomplete.</strong>{" "}
      {invalidBatches} profile evidence {invalidBatches === 1 ? "batch" : "batches"} could not be verified. Names and mentions were still processed, but some traits or motivations may be missing. Review the Character Bible before relying on these profiles.
      {onReview ? (
        <button type="button" className="ml-2 font-semibold underline underline-offset-4" onClick={onReview}>Review characters</button>
      ) : (
        <Link className="ml-2 font-semibold underline underline-offset-4" href={`/${bookId}/characters`}>Review characters</Link>
      )}
    </div>
  )
}
