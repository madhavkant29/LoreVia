import Link from "next/link"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <section className="rounded-[2rem] border border-stone-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-stone-500">Contact</p>
        <h1 className="mt-3 font-serif text-4xl text-stone-950">Talk to LoreVia</h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-600">
          Use the support inbox for feedback, bugs, account issues, and general product questions. Use the legal inbox for copyright notices, takedown requests, licensing, or other formal legal matters.
        </p>
      </section>

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <section className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">Support</p>
          <h2 className="mt-3 text-2xl font-semibold text-stone-950">Feedback, bugs, and help</h2>
          <p className="mt-3 text-sm leading-6 text-stone-600">
            For product feedback, bug reports, feature requests, billing help, or account support, email{" "}
            <a className="font-medium text-stone-900 underline decoration-stone-300 underline-offset-4" href={`mailto:${SUPPORT_EMAIL}`}>
              {SUPPORT_EMAIL}
            </a>.
          </p>
        </section>

        <section className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">Legal</p>
          <h2 className="mt-3 text-2xl font-semibold text-stone-950">Copyright and legal issues</h2>
          <p className="mt-3 text-sm leading-6 text-stone-600">
            For copyright concerns, takedown requests, licensing questions, or other formal legal issues, email{" "}
            <a className="font-medium text-stone-900 underline decoration-stone-300 underline-offset-4" href={`mailto:${LEGAL_EMAIL}`}>
              {LEGAL_EMAIL}
            </a>.
          </p>
        </section>
      </div>

      <p className="mt-8 text-sm text-stone-500">
        Back to <Link href="/library" className="text-stone-900 underline decoration-stone-300 underline-offset-4">your library</Link>.
      </p>
    </div>
  )
}
