import type { Metadata } from "next"

import { PublicUploadsAnalyticsPageClient } from "@/components/public/PublicUploadsAnalyticsPageClient"
import { getPublicUploadsAnalyticsServer } from "@/lib/api/public.server"
import { SITE_NAME, SITE_URL } from "@/lib/seo"

export const metadata: Metadata = {
  title: "Public Upload Analytics",
  description: "Public analytics for creator-published LoreVia books, including visible catalog totals and upload breakdowns.",
  alternates: {
    canonical: "/public/analytics",
  },
  openGraph: {
    title: `Public Upload Analytics | ${SITE_NAME}`,
    description: "Public analytics for creator-published LoreVia books, including visible catalog totals and upload breakdowns.",
    url: `${SITE_URL}/public/analytics`,
  },
}

export default async function PublicUploadsAnalyticsPage() {
  const overview = await getPublicUploadsAnalyticsServer()
  return <PublicUploadsAnalyticsPageClient overview={overview} />
}
