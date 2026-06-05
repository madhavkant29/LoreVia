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
      <div className="space-y-3">
        <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-teal-200" : "text-teal-700"}`}>Author workspace</p>
        <h1 className={`font-display text-[2.75rem] leading-none tracking-[-0.04em] sm:text-[3.25rem] ${isDark ? "text-[#f5f0e8]" : "text-stone-950"}`}>
          Library
        </h1>
        <p className={`max-w-2xl text-base leading-7 ${isDark ? "text-[#a6a39b]" : "text-stone-600"}`}>
          Organize serious writing projects, track manuscript readiness, and return to the next editorial decision without losing context.
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Tooltip content="Open public beta reader discussions" className="w-full sm:w-auto">
          <Button variant="secondary" size="md" onClick={onOpenForum} className="min-h-11 w-full rounded-sm px-4 sm:w-auto">
            <ForumIcon className={isDark ? "text-[#d2cdc3]" : "text-stone-600"} />
            Beta forum
          </Button>
        </Tooltip>
        <Button variant="primary" size="md" disabled={createDisabled} onClick={onCreate} className="min-h-11 w-full rounded-sm px-4 sm:w-auto">
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
