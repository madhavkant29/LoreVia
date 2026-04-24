import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Create Account",
  description: "Create your free LoreVia account and start understanding your manuscript like never before.",
  robots: { index: false, follow: false },
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
