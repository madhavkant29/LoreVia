import type { Metadata } from "next"

import { QueryProvider } from "@/components/app/QueryProvider"
import { PublicContextChrome } from "@/components/public/PublicContextChrome"
import { PublicSiteFooter } from "@/components/public/PublicSiteFooter"

export const metadata: Metadata = {
  robots: {
    index: true,
    follow: true,
  },
}

export default function PublicContentLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <div className="app-shell min-h-screen">
        <PublicContextChrome />
        {children}
      </div>
      <PublicSiteFooter />
    </QueryProvider>
  )
}
