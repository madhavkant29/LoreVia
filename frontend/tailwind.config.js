module.exports = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--background) / <alpha-value>)",
        foreground: "rgb(var(--foreground) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        card: {
          DEFAULT: "rgb(var(--card) / <alpha-value>)",
          foreground: "rgb(var(--card-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT: "rgb(var(--muted) / <alpha-value>)",
          foreground: "rgb(var(--muted-foreground) / <alpha-value>)",
        },
        brand: { 50: "#f0f4ff", 500: "#6366f1", 600: "#4f46e5", 700: "#4338ca" },
      },
      fontFamily: {
        reading: ["Merriweather", "Georgia", "serif"],
      },
      boxShadow: {
        premium: "0 20px 40px -15px rgba(0, 0, 0, 0.1)",
        "premium-dark": "0 20px 40px -15px rgba(0, 0, 0, 0.5)",
      },
    },
  },
  plugins: [],
}
