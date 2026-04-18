import type { MetadataRoute } from "next"

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "LoreVia",
    short_name: "LoreVia",
    description: "AI-powered reading workspace for long-form books.",
    start_url: "/library",
    scope: "/",
    display: "standalone",
    background_color: "#020617",
    theme_color: "#020617",
    icons: [
      {
        src: "/image.png",
        sizes: "any",
        type: "image/png",
      },
    ],
  }
}
