import type { Route } from "next"
import Link from "next/link"

import type { IconName } from "./types"
import { Icon } from "./Icon"

export function IconLink({ href, label, icon, isDark }: { href: Route | string; label: string; icon: IconName; isDark: boolean }) {
  return (
    <Link
      href={href as Route}
      aria-label={label}
      className={`flex h-10 w-10 items-center justify-center rounded-md border transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
    >
      <Icon name={icon} />
    </Link>
  )
}
