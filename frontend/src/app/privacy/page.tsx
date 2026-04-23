export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">LoreVia</p>
      <h1 className="mt-3 text-4xl font-semibold text-white">Privacy Policy</h1>
      <div className="mt-8 space-y-6 text-sm leading-7 text-slate-300">
        <p>This page explains what LoreVia collects, how we use it, and what it can be used for. We only collect data needed to run the app, support your account, and keep the service safe.</p>
        <div>
          <p className="font-semibold text-white">What we collect</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Account information: name, email, password hash, auth/session tokens, and plan tier.</li>
            <li>Content you upload: books, chapters, titles, series metadata, descriptions, covers, and manuscript text.</li>
            <li>Generated story data: summaries, character profiles, relationship graphs, timelines, continuity reports, and search indexes.</li>
            <li>Usage data: searches, chapter views, progress, bookmarks, preferences, and feature interactions.</li>
            <li>Support data: emails, messages, bug reports, and any files you send to support.</li>
            <li>Billing and subscription data: checkout status, subscription identifiers, invoice metadata, and plan changes. Payment cards are handled by the payment provider.</li>
            <li>Technical data: IP address, user agent, device and browser info, cookies, logs, rate-limit events, and security signals.</li>
            <li>Public-content data: anything you choose to publish publicly, including book titles, descriptions, and chapters.</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-white">How we use it</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Provide reading, search, advisor, and continuity features.</li>
            <li>Keep books, series, and public/private views separated.</li>
            <li>Prevent abuse, enforce rate limits, and keep the app reliable.</li>
            <li>Handle billing, support, and compliance requests.</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-white">Sharing and retention</p>
          <p className="mt-2">We do not sell user manuscripts or reading history. We may share data with service providers that power hosting, storage, analytics, payments, email, and AI features. We keep data only as long as needed for the service, legal obligations, security, and billing.</p>
        </div>
        <div>
          <p className="font-semibold text-white">Your choices</p>
          <p className="mt-2">You can manage account data, delete content, change visibility, and contact us about access or deletion requests at legal@getlorevia.com or support@getlorevia.com.</p>
        </div>
      </div>
      </div>
    </main>
  )
}
