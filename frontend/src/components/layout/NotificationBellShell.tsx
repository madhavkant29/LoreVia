import Link from "next/link"

function BellIcon() {
  return (
    <svg
      className="h-5 w-5 transition-colors"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.857 17H9.143m5.714 0H18l-1.286-1.286A2 2 0 0116 14.286V11a4 4 0 10-8 0v3.286a2 2 0 01-.714 1.428L6 17h3.143m5.714 0a3 3 0 11-5.714 0"
      />
    </svg>
  )
}

export function NotificationBellShell() {
  return (
    <>
      <Link
        href="/notifications"
        className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card text-foreground transition-colors hover:bg-muted lg:hidden"
        aria-label="Open notifications"
      >
        <BellIcon />
      </Link>
      <button
        type="button"
        className="relative hidden h-10 w-10 items-center justify-center rounded-xl border border-border bg-card text-foreground transition-colors hover:bg-muted lg:flex"
        aria-label="Toggle notifications"
      >
        <BellIcon />
      </button>
    </>
  )
}
