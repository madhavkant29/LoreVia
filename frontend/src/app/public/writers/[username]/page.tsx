import type { Metadata } from "next"
import Script from "next/script"

import { PublicWriterProfilePageClient } from "@/components/public/PublicWriterProfilePageClient"
import { getPublicUserProfileServer } from "@/lib/api/public.server"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  buildProfilePageJsonLd,
} from "@/lib/seo"

export async function generateMetadata({ params }: { params: Promise<{ username: string }> }): Promise<Metadata> {
  const { username } = await params
  const profile = await getPublicUserProfileServer(username).catch(() => null)

  if (!profile) {
    return {}
  }

  const description = `Public LoreVia profile for @${profile.username}, with visible forum activity, trust signals, and any surfaced manuscript sample or discussion.`

  return {
    title: `@${profile.username}`,
    description,
    alternates: {
      canonical: `/public/writers/${profile.username}`,
    },
    openGraph: {
      title: `@${profile.username} | ${SITE_NAME}`,
      description,
      url: `https://getlorevia.com/public/writers/${profile.username}`,
      images: [DEFAULT_OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: `@${profile.username} | ${SITE_NAME}`,
      description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function PublicWriterProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = await params
  const profile = await getPublicUserProfileServer(username)
  const description = `Public LoreVia profile for @${profile.username}, with visible forum activity, trust signals, and any surfaced manuscript sample or discussion.`
  const profileJsonLd = buildProfilePageJsonLd({
    username: profile.username,
    description,
    path: `/public/writers/${profile.username}`,
  })

  return (
    <>
      <Script id={`public-writer-jsonld-${profile.username}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(profileJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <PublicWriterProfilePageClient username={profile.username} initialProfile={profile} />
    </>
  )
}
