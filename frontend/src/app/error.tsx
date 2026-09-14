"use client"

export default function GlobalError({
  error: _error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center bg-stone-50 px-6 py-12 text-center text-slate-950">
      <div className="w-full rounded-lg border border-slate-200 bg-white p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-rose-600">Something went wrong</p>
        <h1 className="mt-3 text-3xl font-semibold text-slate-950">This screen hit a problem.</h1>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          Try again, refresh the page, or contact support if it keeps happening. We do not show internal error details here.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Refresh
          </button>
          <a
            href="mailto:support@getlorevia.com"
            className="rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Contact support
          </a>
        </div>
      </div>
    </main>
  )
}
