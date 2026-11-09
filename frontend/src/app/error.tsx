"use client"

import { useEffect } from "react"
import { captureCaughtRenderError } from "@/lib/analytics/browserTelemetry"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    captureCaughtRenderError(error, "route")
  }, [error])

  return (
    <main className="grid min-h-[100dvh] place-items-center bg-[#f8f4ee] px-6 py-12 text-stone-950">
      <section className="w-full max-w-lg border-y border-stone-300 py-8">
        <p className="text-sm font-semibold text-rose-700">Something went wrong</p>
        <h1 className="mt-3 text-3xl font-semibold text-stone-950">This screen hit a problem.</h1>
        <p className="mt-3 text-sm leading-7 text-stone-600">
          Retry the last action. Contact support at <a className="font-semibold text-teal-800 hover:underline" href="mailto:support@getlorevia.com">support@getlorevia.com</a> if the problem continues, and include the page you were using.
        </p>
        <div className="mt-6">
          <button
            type="button"
            onClick={reset}
            className="rounded-md bg-stone-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-stone-800"
          >
            Retry
          </button>
        </div>
      </section>
    </main>
  )
}
