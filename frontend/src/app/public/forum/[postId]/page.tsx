import type { Metadata } from "next"
import dynamic from "next/dynamic"

import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { getPublicForumPostServer, listPublicForumCommentsServer } from "@/lib/api/public.server"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  buildBreadcrumbJsonLd,
  buildForumThreadJsonLd,
} from "@/lib/seo"

const PublicForumPostPageClient = dynamic(
  () => import("@/components/public/PublicForumPostPageClient").then((module) => module.PublicForumPostPageClient)
)

export async function generateMetadata({ params }: { params: Promise<{ postId: string }> }): Promise<Metadata> {
  const { postId } = await params
  const post = await getPublicForumPostServer(postId).catch(() => null)

  if (!post) {
    return {}
  }

  const description = post.body.length > 180 ? `${post.body.slice(0, 177).trimEnd()}...` : post.body

  return {
    title: post.headline,
    description,
    alternates: {
      canonical: `/public/forum/${post.id}`,
    },
    openGraph: {
      title: `${post.headline} | ${SITE_NAME}`,
      description,
      url: `https://getlorevia.com/public/forum/${post.id}`,
      images: [DEFAULT_OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: `${post.headline} | ${SITE_NAME}`,
      description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function PublicForumPostPage({ params }: { params: Promise<{ postId: string }> }) {
  const { postId } = await params
  const [post, comments] = await Promise.all([
    getPublicForumPostServer(postId).catch(() => null),
    listPublicForumCommentsServer(postId).catch(() => []),
  ])
  const threadJsonLd = post ? buildForumThreadJsonLd({
    title: post.headline,
    body: post.body,
    path: `/public/forum/${post.id}`,
    createdAt: post.created_at,
    updatedAt: post.updated_at,
    authorName: post.author_username || post.author || "LoreVia author",
  }) : null
  const breadcrumbJsonLd = post ? buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Public Forum", path: "/public/forum" },
    { name: post.headline, path: `/public/forum/${post.id}` },
  ]) : null

  return (
      <>
      {post && threadJsonLd ? (
        <JsonLdScript id={`public-forum-post-jsonld-${post.id}`} data={threadJsonLd} />
      ) : null}
      {post && breadcrumbJsonLd ? (
        <JsonLdScript id={`public-forum-post-breadcrumbs-jsonld-${post.id}`} data={breadcrumbJsonLd} />
      ) : null}
      <PublicForumPostPageClient postId={postId} initialPost={post} initialComments={comments} />
    </>
  )
}
