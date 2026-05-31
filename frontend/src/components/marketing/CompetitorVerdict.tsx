type CompetitorVerdictProps = {
  competitorName: string
  competitorBestFor: string
  loreviaBestFor: string
}

export function CompetitorVerdict({
  competitorName,
  competitorBestFor,
  loreviaBestFor,
}: CompetitorVerdictProps) {
  return (
    <section className="mx-auto max-w-7xl px-5 py-12 md:px-8">
      <div className="grid gap-5 lg:grid-cols-2">
        <article className="rounded-lg border border-white/10 bg-[#0d1715] p-6">
          <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-[#6fae9f]">{competitorName} is best for</p>
          <p className="mt-4 text-xl font-semibold leading-8 text-white">{competitorBestFor}</p>
        </article>
        <article className="rounded-lg border border-[#17514a] bg-[#0f2320] p-6">
          <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-[#7ad3c1]">LoreVia is best for</p>
          <p className="mt-4 text-xl font-semibold leading-8 text-white">{loreviaBestFor}</p>
        </article>
      </div>
    </section>
  )
}
