import type { Metadata } from "next"

import { QueryProvider } from "@/components/app/QueryProvider"
import { Navbar } from "@/components/layout/Navbar"

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
        <div className="app-shell__mesh" />
        <Navbar />
        {children}
      </div>
    </QueryProvider>
  )
}
