import type { Metadata } from "next"
import Link from "next/link"

import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "Compliance Notice",
  description: "Read the LoreVia compliance notice for usage, content, and account obligations.",
}

export default function CompliancePage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">LoreVia</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">Compliance Notice</h1>
        <p className="mt-4 text-sm text-slate-500">Effective date: April 28, 2026</p>

        <div className="mt-8 space-y-6 text-sm leading-7 text-slate-300">
          <p>
            You are responsible for the books, drafts, and other content you upload. Only submit material that you own,
            have permission to use, or are otherwise authorized to process.
          </p>
          <p>
            LoreVia analyzes uploaded text to generate summaries, character context, continuity checks, and related
            manuscript insights. AI-generated output can be incomplete or incorrect, so important decisions should be
            verified manually.
          </p>
          <p>
            Do not use the service to upload unlawful, infringing, abusive, or highly sensitive material unless you are
            sure your usage is permitted by law and by your own policies.
          </p>
          <p>
            Questions about this notice can be sent to{" "}
            <a className="font-medium text-white underline decoration-white/30 underline-offset-4" href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
            {" "}or{" "}
            <a className="font-medium text-white underline decoration-white/30 underline-offset-4" href={`mailto:${LEGAL_EMAIL}`}>{LEGAL_EMAIL}</a>.
          </p>
          <p className="pt-2 text-slate-400">
            Back to{" "}
            <Link href="/" className="text-white underline decoration-white/30 underline-offset-4">landing page</Link>.
          </p>
        </div>
      </div>
    </main>
  )
}
