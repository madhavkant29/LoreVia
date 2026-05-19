"use client"

type BrandLockupProps = {
  size?: "sm" | "md" | "lg"
  className?: string
  textClassName?: string
  iconClassName?: string
}

const sizeClasses = {
  sm: {
    wrapper: "",
    image: "h-8",
  },
  md: {
    wrapper: "",
    image: "h-10",
  },
  lg: {
    wrapper: "",
    image: "h-12",
  },
} as const

export function BrandLockup({
  size = "md",
  className = "",
}: BrandLockupProps) {
  const classes = sizeClasses[size]

  return (
    <div className={`flex items-center ${classes.wrapper} ${className}`.trim()}>
      <img
        src="/logoandtext.png"
        alt="LoreVia"
        className={`${classes.image} w-auto object-contain`.trim()}
      />
    </div>
  )
}
