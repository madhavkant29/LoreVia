import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Read the LoreVia Terms of Service to understand your rights and responsibilities when using our platform.",
}

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">LoreVia</p>
      <h1 className="mt-3 text-4xl font-semibold text-white">Terms of Service</h1>
      <div className="mt-8 space-y-6 text-sm leading-7 text-slate-300">
        <p>LoreVia is a reading workspace for personal and licensed book use. You are responsible for the files you upload, the rights you hold, and the laws that apply in your region.</p>
        <p>Your account gives you access to reading tools, character tracking, summaries, search, and related intelligence features. Access levels vary by plan and may change as product limits evolve.</p>
        <p>You may not use LoreVia to upload infringing content, abuse the service, probe security, scrape private data, or interfere with other users. We may suspend access for misuse, fraud, or legal risk.</p>
        <p>AI-generated outputs can be incomplete or wrong. LoreVia is a companion tool, not an authoritative source of truth. You should verify important interpretations yourself.</p>
        <p>Paid subscriptions renew according to the billing terms shown at checkout unless canceled. Taxes, pricing, refunds, and processor-specific rules are governed by the checkout provider and applicable law.</p>
        <p>Questions about these terms can be sent to legal@getlorevia.com.</p>
      </div>
      </div>
    </main>
  )
}
