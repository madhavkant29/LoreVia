import type { Metadata } from "next"
import { StatusNavigation } from "@/components/status/StatusNavigation"

export const metadata: Metadata = {
  title: "Status",
  description: "See LoreVia's current service status, uptime information, and incident history.",
}

const statusHistory = [
  {
    date: "Hosted externally",
    title: "Live uptime and incident history",
    description: "This page points to the public status host where current uptime, maintenance notices, and incident history are published.",
  },
]

export default function StatusPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-4 py-12 text-white">
      <div className="mx-auto max-w-4xl">
        <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-8 shadow-sm shadow-black/20 backdrop-blur">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Status</p>
          <h1 className="mt-3 font-serif text-4xl text-white">LoreVia Service Status</h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">
            This page is where we will publish uptime information, maintenance notices, and incident history. For live
            operational updates, visit{" "}
            <a
              className="font-medium text-white underline decoration-white/30 underline-offset-4"
              href="https://status.getlorevia.com"
              target="_blank"
              rel="noreferrer"
            >
              status.getlorevia.com
            </a>
            .
          </p>
        </section>

        <div className="mt-8 grid gap-6 md:grid-cols-[1.2fr_0.8fr]">
          <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-sm shadow-black/20 backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Current uptime</p>
            <p className="mt-4 text-lg font-semibold text-white">Published at status.getlorevia.com</p>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              The public status page is where we show the current service health, planned maintenance windows, and any
              active incident notices.
            </p>
          </section>

          <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-sm shadow-black/20 backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Updates</p>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              Subscribe to the status page for alerts when we post new incidents or maintenance updates.
            </p>
          </section>
        </div>

        <section className="mt-8 rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-sm shadow-black/20 backdrop-blur">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Incident history</p>
          <div className="mt-4 space-y-4">
            {statusHistory.map((incident) => (
              <article key={incident.title} className="rounded-2xl border border-white/10 bg-black/20 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{incident.date}</p>
                <h2 className="mt-2 text-lg font-semibold text-white">{incident.title}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">{incident.description}</p>
              </article>
            ))}
          </div>
        </section>

        <StatusNavigation />
      </div>
    </main>
  )
}
