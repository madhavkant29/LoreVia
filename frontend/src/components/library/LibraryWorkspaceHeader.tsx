import { Button } from "@/components/ui/Button"
import { Tooltip } from "@/components/ui/Tooltip"

export function LibraryWorkspaceHeader({
  createDisabled,
  isDark,
  onCreate,
  onOpenForum,
}: {
  createDisabled: boolean
  isDark: boolean
  onCreate: () => void
  onOpenForum: () => void
}) {
  return (
    <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <h1 className={`font-display text-3xl leading-tight tracking-[-0.025em] sm:text-4xl ${isDark ? "text-[#f5f0e8]" : "text-stone-950"}`}>
          Library
        </h1>
        <p className={`max-w-2xl text-base leading-7 ${isDark ? "text-[#a6a39b]" : "text-stone-600"}`}>
          Return to a draft, review its status, or start a new project.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Tooltip content="Open public beta reader discussions" className="order-2">
          <Button variant="ghost" size="md" onClick={onOpenForum} className="inline-flex min-h-11 items-center justify-center rounded-sm px-4">
            <ForumIcon className={isDark ? "text-[#d2cdc3]" : "text-stone-600"} />
            Book discussions
          </Button>
        </Tooltip>
        <Button variant="primary" size="md" disabled={createDisabled} onClick={onCreate} className="dark:bg-teal-700 dark:text-white inline-flex min-h-11 items-center justify-center rounded-sm px-4">
          <PlusIcon />
          New project
        </Button>
      </div>
    </header>
  )
}

function ForumIcon({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={`mr-2 h-4 w-4 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.5 5h11A2.5 2.5 0 0 1 20 7.5v6a2.5 2.5 0 0 1-2.5 2.5H12l-4.5 3.5V16h-1A2.5 2.5 0 0 1 4 13.5v-6A2.5 2.5 0 0 1 6.5 5Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 9h8M8 12h5" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg aria-hidden="true" className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
    </svg>
  )
}
