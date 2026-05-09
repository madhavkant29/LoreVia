"use client"

type BrandLockupProps = {
  size?: "sm" | "md" | "lg"
  className?: string
  textClassName?: string
  iconClassName?: string
}

const sizeClasses = {
  sm: {
    wrapper: "gap-3",
    icon: "h-8 w-8 rounded-lg",
    text: "text-sm",
  },
  md: {
    wrapper: "gap-3",
    icon: "h-10 w-10 rounded-xl",
    text: "text-sm",
  },
  lg: {
    wrapper: "gap-3.5",
    icon: "h-12 w-12 rounded-2xl",
    text: "text-base",
  },
} as const

export function BrandLockup({
  size = "md",
  className = "",
  textClassName = "",
  iconClassName = "",
}: BrandLockupProps) {
  const classes = sizeClasses[size]

  return (
    <div className={`flex items-center ${classes.wrapper} ${className}`.trim()}>
      <img
        src="/image.png"
        alt="LoreVia"
        className={`${classes.icon} object-cover ${iconClassName}`.trim()}
      />
      <span
        className={`${classes.text} font-semibold uppercase tracking-[0.34em] text-white ${textClassName}`.trim()}
      >
        LOREVIA
      </span>
    </div>
  )
}
