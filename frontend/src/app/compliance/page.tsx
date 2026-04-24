export default function CompliancePage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">LoreVia</p>
      <h1 className="mt-3 text-4xl font-semibold text-white">Compliance</h1>
      <div className="mt-8 space-y-6 text-sm leading-7 text-slate-300">
        <p>LoreVia is designed for reader-owned, licensed, or otherwise authorized material. Users must only upload books and documents they are permitted to store and analyze.</p>
        <p>We maintain takedown and legal contact channels for copyright notices, licensing concerns, and formal complaints. Please send those requests to legal@getlorevia.com with enough detail to identify the work and the claimed issue.</p>
        <div>
          <p className="font-semibold text-white">Data we collect</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Account details: name, email address, password hash, plan tier, and auth/session tokens.</li>
            <li>Uploaded content: book files, chapter text, titles, series details, covers, descriptions, and generated notes.</li>
            <li>Reader data: highlights, searches, progress, bookmarks, and reading preferences such as theme or mode.</li>
            <li>AI activity: prompts, retrieved context, summaries, character data, continuity checks, and response logs needed for the feature to work.</li>
            <li>Billing data: subscription status, plan selection, checkout metadata, and payment-provider references. We do not store full card numbers.</li>
            <li>Support and contact data: emails, messages, bug reports, and follow-up correspondence.</li>
            <li>Technical data: IP address, user agent, device/browser information, rate-limit events, cookies, and operational logs for security and reliability.</li>
            <li>Public-content data: titles, descriptions, chapters, and other fields you choose to expose publicly.</li>
          </ul>
        </div>
        <p>Public-facing content is subject to moderation, visibility controls, and removal when required for policy, legal, trust, or safety reasons.</p>
        <p>We minimize operational logging and avoid storing more request detail than needed for reliability, abuse prevention, billing, and debugging. Sensitive credentials should never be pasted into public fields.</p>
        <p>For the full privacy notice and retention details, see the Privacy Policy page. If you need a data handling clarification, compliance statement, or operational contact, use support@getlorevia.com for product questions and legal@getlorevia.com for formal legal matters.</p>
      </div>
      </div>
    </main>
  )
}
