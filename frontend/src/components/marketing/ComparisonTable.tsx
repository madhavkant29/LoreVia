type ComparisonRow = {
  feature: string
  competitor: string
  lorevia: string
}

type ComparisonTableProps = {
  competitorName: string
  rows: ComparisonRow[]
}

export function ComparisonTable({ competitorName, rows }: ComparisonTableProps) {
  return (
    <div data-testid="comparison-table" className="min-w-0 max-w-full overflow-hidden border-y border-white/10">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] border-separate border-spacing-0 text-left text-sm">
          <thead>
            <tr className="text-[#9fb0a8]">
              {["Feature", competitorName, "LoreVia"].map((heading) => (
                <th
                  key={heading}
                  className={`border-b border-white/[0.08] px-5 py-4 font-semibold ${
                    heading === "LoreVia" ? "bg-[#0f2320] text-[#7ad3c1]" : ""
                  }`}
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.feature} className="text-[#d9e0db]">
                <td className="border-b border-white/6 px-5 py-4 font-medium text-white">{row.feature}</td>
                <td className="border-b border-white/6 px-5 py-4 text-[#aeb9b3]">{row.competitor}</td>
                <td className="border-b border-[#14433d] bg-[#0f2320] px-5 py-4 font-semibold text-[#85e1ce]">
                  {row.lorevia}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
