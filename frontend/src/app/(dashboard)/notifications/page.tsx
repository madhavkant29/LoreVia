"use client"

import dynamic from "next/dynamic"

const NotificationsPanel = dynamic(
  () => import("@/components/layout/NotificationsPanel").then((module) => module.NotificationsPanel),
  {
    ssr: false,
    loading: () => <div className="min-h-[24rem] border p-6" />,
  }
)

export default function NotificationsPage() {
  return (
    <div className="min-h-0 bg-transparent">
      <NotificationsPanel mode="page" />
    </div>
  )
}
