import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        raven: {
          bg: "#070A12",
          panel: "#101522",
          panelSoft: "#151C2B",
          border: "#273142",
          text: "#E5E7EB",
          muted: "#9CA3AF",
          violet: "#7C3AED",
          cyan: "#22D3EE",
          emerald: "#34D399",
          amber: "#F59E0B",
          rose: "#FB7185"
        }
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(124,58,237,0.28), 0 20px 60px rgba(0,0,0,0.35)"
      }
    }
  },
  plugins: []
} satisfies Config;

