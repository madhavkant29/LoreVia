type BrandVariant = "icon" | "lockup"

type ThemeBrandImageProps = {
  variant?: BrandVariant
  alt?: string
  className?: string
  priority?: boolean
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
}: ThemeBrandImageProps) {
  const assets = brandAssetMap[variant]

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
