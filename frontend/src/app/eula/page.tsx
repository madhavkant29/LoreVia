export default function EulaPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">LoreVia</p>
      <h1 className="mt-3 text-4xl font-semibold text-white">End User License Agreement</h1>
      <div className="mt-8 space-y-6 text-sm leading-7 text-slate-300">
        <p>LoreVia grants you a limited, revocable, non-exclusive license to use the application for your own reading, study, and approved publishing workflows.</p>
        <p>You may not reverse engineer, resell, sublicense, mirror, copy at scale, or use the product to build a competing service from LoreVia outputs, interfaces, or internal behavior.</p>
        <p>The software is provided on an as-available basis. We work to keep it stable, but uptime, feature availability, extraction quality, and AI responses are not guaranteed.</p>
        <p>All rights not expressly granted remain with LoreVia and its licensors. Uploaded works remain governed by their original copyright and license status.</p>
        <p>By continuing to use the application, you agree to this license and the associated service terms.</p>
      </div>
      </div>
    </main>
  )
}
