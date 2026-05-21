import type { Metadata } from "next"

import { PublicUploadsPageClient } from "@/components/public/PublicUploadsPageClient"
import { getPublicUploadsAnalyticsServer, listCreatorPublicUploadsServer } from "@/lib/api/public.server"
import { SITE_NAME, SITE_URL } from "@/lib/seo"

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
    listCreatorPublicUploadsServer().catch(() => []),
    getPublicUploadsAnalyticsServer().catch(() => null),
  ])

  return <PublicUploadsPageClient initialBooks={books} initialOverview={overview} />
}
