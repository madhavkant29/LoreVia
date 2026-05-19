import type { Metadata } from "next"
import { AppRuntime } from "@/components/app/AppRuntime"

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: false,
  },
}

export default function ReaderLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppRuntime>
      <div className="min-h-screen bg-white">{children}</div>
    </AppRuntime>
  )
}
