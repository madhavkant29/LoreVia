import { getAdminSessionServer } from "@/lib/api/admin.server"

export const dynamic = "force-dynamic"

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  await getAdminSessionServer()
  return children
}
