import type { Metadata } from "next"
import { AppRuntime } from "@/components/app/AppRuntime"
import { DashboardShell } from "@/components/layout/DashboardShell"

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: false,
  },
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppRuntime>
      <DashboardShell>{children}</DashboardShell>
    </AppRuntime>
  )
}
