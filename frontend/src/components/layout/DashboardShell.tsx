import { DashboardSidebar } from "@/components/layout/DashboardSidebar"

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return <DashboardSidebar>{children}</DashboardSidebar>
}
