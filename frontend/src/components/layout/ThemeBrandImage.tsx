type BrandVariant = "icon" | "lockup"
type BrandMode = "auto" | "light" | "dark"

type ThemeBrandImageProps = {
  variant?: BrandVariant
  alt?: string
  className?: string
  priority?: boolean
  mode?: BrandMode
}

const brandAssetMap: Record<BrandVariant, { dark: string; light: string }> = {
  icon: {
    dark: "/image.png",
    light: "/imagelight.png",
  },
  lockup: {
    dark: "/logoandtext.png",
    light: "/logoandtextlight.png",
  },
}

export function ThemeBrandImage({
  variant = "lockup",
  alt = "LoreVia",
  className = "",
  priority = false,
  mode = "auto",
}: ThemeBrandImageProps) {
  const assets = brandAssetMap[variant]

  if (mode !== "auto") {
    return (
      <img
        src={assets[mode]}
        alt={alt}
        className={className.trim()}
        fetchPriority={priority ? "high" : undefined}
      />
    )
  }

  return (
    <>
      <img
        src={assets.light}
        alt={alt}
        className={`block ${className} dark:hidden`.trim()}
        fetchPriority={priority ? "high" : undefined}
      />
      <img
        src={assets.dark}
        alt={alt}
        className={`hidden ${className} dark:block`.trim()}
        fetchPriority={priority ? "high" : undefined}
      />
    </>
  )
}
