import type { Metadata } from "next"

import { QueryProvider } from "@/components/app/QueryProvider"
import { Navbar } from "@/components/layout/Navbar"
import { SiteFooter } from "@/components/layout/SiteFooter"

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
        <Navbar />
        {children}
      </div>
      <SiteFooter />
    </QueryProvider>
  )
}
