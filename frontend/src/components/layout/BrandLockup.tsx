"use client"

import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"

type BrandLockupProps = {
  size?: "sm" | "md" | "lg" | "xl"
  className?: string
  tone?: "auto" | "light" | "dark"
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
  xl: {
    wrapper: "",
    image: "h-14",
  },
} as const

export function BrandLockup({
  size = "md",
  className = "",
  tone = "auto",
}: BrandLockupProps) {
  const classes = sizeClasses[size]

  return (
    <div className={`flex items-center ${classes.wrapper} ${className}`.trim()}>
      <ThemeBrandImage
        variant="lockup"
        alt="LoreVia"
        mode={tone}
        className={`${classes.image} w-auto object-contain`.trim()}
      />
    </div>
  )
}
