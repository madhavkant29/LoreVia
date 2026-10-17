import type { Metadata } from "next"

import { LegalTopBar } from "@/components/legal/LegalPageShell"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Status",
  description: "LoreVia operational updates, maintenance notices, and support guidance.",
  alternates: { canonical: "/status" },
}

export default function StatusPage() {
  return (
    <main className="min-h-[100dvh] bg-[#f8f4ee] text-stone-950">
      <LegalTopBar />
      <div className="mx-auto max-w-3xl px-5 py-14 sm:px-8 sm:py-20">
        <p className="text-sm font-semibold text-teal-800">Service Status</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">No active incident is posted.</h1>
        <p className="mt-5 max-w-2xl text-base leading-8 text-stone-600">
          This page lists broad service interruptions and planned maintenance. It does not provide live telemetry or a contractual uptime guarantee.
        </p>

        <section aria-label="Current status" className="mt-10 border-y border-stone-300 py-6">
          <div className="flex items-start gap-3">
            <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-700" aria-hidden="true" />
            <div>
              <h2 className="text-lg font-semibold">No published incident</h2>
              <p className="mt-1 text-sm leading-6 text-stone-600">Reference information last reviewed {TRUST_EFFECTIVE_DATE}.</p>
            </div>
          </div>
        </section>

        <div className="mt-10 divide-y divide-stone-300 border-y border-stone-300">
          <section className="py-6">
            <h2 className="text-xl font-semibold">If LoreVia is not working for you</h2>
            <p className="mt-3 text-sm leading-7 text-stone-600">
              Check your connection and retry once. If the problem continues while no incident is posted, email <a className="font-semibold text-teal-800 hover:underline" href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with the affected page, approximate time, and any visible error message.
            </p>
          </section>
          <section className="py-6">
            <h2 className="text-xl font-semibold">What appears here</h2>
            <p className="mt-3 text-sm leading-7 text-stone-600">
              Broad outages, material service degradation, and maintenance that may interrupt sign-in, uploads, analysis, exports, or billing.
            </p>
          </section>
          <section className="py-6">
            <h2 className="text-xl font-semibold">Security reports</h2>
            <p className="mt-3 text-sm leading-7 text-stone-600">
              Report suspected vulnerabilities privately through support. Active investigations may not be described publicly until containment is complete.
            </p>
          </section>
        </div>

        <a href={`mailto:${SUPPORT_EMAIL}`} className="mt-8 inline-flex rounded-md bg-stone-950 px-5 py-3 text-sm font-semibold text-white hover:bg-stone-800">
          Contact support
        </a>
      </div>
    </main>
  )
}
