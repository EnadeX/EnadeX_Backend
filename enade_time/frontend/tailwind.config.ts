import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        academia: {
          50: "#f5f7fb",
          100: "#e6ecf5",
          200: "#c4d2e7",
          300: "#9bb3d4",
          400: "#6c8dba",
          500: "#446ea3",
          600: "#345689",
          700: "#2b4470",
          800: "#26395b",
          900: "#1d2c46",
        },
        chart: {
          seq: "#94a3b8",
          paralelo: "#2563eb",
          ideal: "#10b981",
          alert: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
