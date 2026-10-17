"use client"

import { usePathname } from "next/navigation"

import { SiteFooter } from "@/components/layout/SiteFooter"

export function PublicSiteFooter() {
  const pathname = usePathname()
  const isChapterReader = /^\/public\/[^/]+\/chapter\/[^/]+\/?$/.test(pathname)

  if (isChapterReader) return null

  return <SiteFooter />
}
