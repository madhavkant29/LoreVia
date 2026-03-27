import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "LoreVia — AI Reading Companion",
  description: "Your books, deeply understood.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900 antialiased">{children}</body>
    </html>
  )
}
