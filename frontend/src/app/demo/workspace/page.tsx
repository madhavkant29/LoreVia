import type { Metadata } from "next"

import { DemoWorkspace } from "./DemoWorkspace"

export const metadata: Metadata = {
  title: "Interactive manuscript demo",
  description: "Review evidence-backed continuity findings in a local, no-login LoreVia workspace demo.",
}

export default function DemoWorkspacePage() {
  return <DemoWorkspace />
}
