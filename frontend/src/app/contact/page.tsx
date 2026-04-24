import type { Metadata } from "next"
import Link from "next/link"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "Contact",
  description: "Get in touch with the LoreVia team for support, feedback, or partnership inquiries.",
}

export default function ContactPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-4 py-12 text-white">
      <div className="mx-auto max-w-4xl">
        <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-8 shadow-sm shadow-black/20 backdrop-blur">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Contact</p>
          <h1 className="mt-3 font-serif text-4xl text-white">Talk to LoreVia</h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">
          Use the support inbox for feedback, bugs, account issues, and general product questions. Use the legal inbox for copyright notices, takedown requests, licensing, or other formal legal matters.
          </p>
        </section>

        <div className="mt-8 grid gap-6 md:grid-cols-2">
          <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-sm shadow-black/20 backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Support</p>
            <h2 className="mt-3 text-2xl font-semibold text-white">Feedback, bugs, and help</h2>
            <p className="mt-3 text-sm leading-6 text-slate-300">
            For product feedback, bug reports, feature requests, billing help, or account support, email{" "}
            <a className="font-medium text-white underline decoration-white/30 underline-offset-4" href={`mailto:${SUPPORT_EMAIL}`}>
              {SUPPORT_EMAIL}
            </a>.
            </p>
          </section>

          <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-sm shadow-black/20 backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Legal</p>
            <h2 className="mt-3 text-2xl font-semibold text-white">Copyright and legal issues</h2>
            <p className="mt-3 text-sm leading-6 text-slate-300">
            For copyright concerns, takedown requests, licensing questions, or other formal legal issues, email{" "}
            <a className="font-medium text-white underline decoration-white/30 underline-offset-4" href={`mailto:${LEGAL_EMAIL}`}>
              {LEGAL_EMAIL}
            </a>.
            </p>
          </section>
        </div>

        <p className="mt-8 text-sm text-slate-400">
          Back to <Link href="/library" className="text-white underline decoration-white/30 underline-offset-4">your library</Link>.
        </p>
      </div>
    </main>
  )
}
