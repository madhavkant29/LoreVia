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
      <div data-testid="comparison-verdict" className="grid border-y border-white/10 lg:grid-cols-2">
        <article className="py-6 lg:pr-8">
          <p className="text-sm font-semibold text-[#8fa19a]">{competitorName} is best for</p>
          <p className="mt-3 text-xl font-semibold leading-8 text-white">{competitorBestFor}</p>
        </article>
        <article className="border-t border-white/10 py-6 lg:border-l lg:border-t-0 lg:pl-8">
          <p className="text-sm font-semibold text-[#7ad3c1]">LoreVia is best for</p>
          <p className="mt-3 text-xl font-semibold leading-8 text-white">{loreviaBestFor}</p>
        </article>
      </div>
    </section>
  )
}
