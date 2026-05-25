import type { Metadata } from "next"
import dynamic from "next/dynamic"

import { getPublicUploadsAnalyticsServer, listRankedCreatorPublicUploadsServer } from "@/lib/api/public.server"
import { SITE_NAME, SITE_URL } from "@/lib/seo"

const PublicUploadsPageClient = dynamic(
  () => import("@/components/public/PublicUploadsPageClient").then((module) => module.PublicUploadsPageClient)
)

export const metadata: Metadata = {
  title: "Creator Public Uploads",
  description: "Browse creator-published public books from LoreVia authors in a dedicated public uploads catalog.",
  alternates: {
    canonical: "/public/uploads",
  },
  openGraph: {
    title: `Creator Public Uploads | ${SITE_NAME}`,
    description: "Browse creator-published public books from LoreVia authors in a dedicated public uploads catalog.",
    url: `${SITE_URL}/public/uploads`,
  },
}

export default async function PublicUploadsPage() {
  const [books, overview] = await Promise.all([
    listRankedCreatorPublicUploadsServer({ ranking: "most_popular", timeWindow: "monthly" }).catch(() => ({
      items: [],
      total: 0,
      page: 1,
      limit: 24,
      has_more: false,
      ranking_key: "most_popular",
      time_window: "monthly",
      surface: "creator_uploads",
    })),
    getPublicUploadsAnalyticsServer().catch(() => null),
  ])

  return <PublicUploadsPageClient initialBooks={books.items} initialRankingData={books} initialOverview={overview} />
}
