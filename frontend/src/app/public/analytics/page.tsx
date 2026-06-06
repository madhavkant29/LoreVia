import type { Metadata } from "next"

import { PublicUploadsAnalyticsPageClient } from "@/components/public/PublicUploadsAnalyticsPageClient"
import { getPublicUploadsAnalyticsServer } from "@/lib/api/public.server"
import { SITE_NAME, SITE_URL } from "@/lib/seo"
import type { PublicUploadsOverview } from "@/types/public"

const EMPTY_PUBLIC_UPLOADS_OVERVIEW: PublicUploadsOverview = {
  total_public_books: 0,
  total_authors: 0,
  total_visible_chapters: 0,
  total_visible_words: 0,
  uploads_last_30_days: 0,
  genre_breakdown: [],
  work_type_breakdown: [],
  recent_uploads: [],
}

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
  const overview = await getPublicUploadsAnalyticsServer().catch(() => EMPTY_PUBLIC_UPLOADS_OVERVIEW)
  return <PublicUploadsAnalyticsPageClient overview={overview} />
}
